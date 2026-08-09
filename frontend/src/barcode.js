/**
 * Is this actually a product barcode?
 *
 * THE BUG THIS FIXES
 * ------------------
 * Typing the digits under the bars worked. Pointing the camera at the same
 * packet said "not in the food database". Same packet, two answers - so the
 * digits the camera produced were not the digits printed on the box.
 *
 * Two causes, both silent:
 *
 *  1. A partial read. The decoder is handed a blurry or half-covered frame and
 *     returns *something*. There was no check on the result, so a misread went
 *     straight to the server, missed, and was reported as "this product does
 *     not exist" - blaming the database for a camera problem.
 *
 *  2. Code 128. It was in the accepted format list, and it has no fixed length
 *     and no retail meaning. Most Indian food packaging carries a second
 *     Code 128 barcode next to the EAN-13 holding the batch number, MRP or
 *     packing date. The scanner would lock onto whichever entered the frame
 *     first, and a batch number is never in a food database.
 *
 * Every retail barcode - EAN-8, EAN-13, UPC-A, UPC-E - ends in a check digit
 * computed from the ones before it. That makes a misread detectable *on the
 * phone*, before a request is ever sent. A code that fails its own arithmetic
 * is thrown away and the camera keeps looking, which is what a scanner is
 * supposed to do.
 */

export const digitsOnly = (value) => String(value ?? '').replace(/\D/g, '');

// The four lengths that exist in retail. 14 is GTIN-14, used on cartons rather
// than consumer packs, but it is valid and Open Food Facts holds some.
export const GTIN_LENGTHS = [8, 12, 13, 14];

/**
 * The GS1 mod-10 check digit.
 *
 * Weights alternate 3 and 1 from the RIGHT, so they do not depend on the
 * length - which is why the same routine covers EAN-8 through GTIN-14. Getting
 * the direction wrong still validates about one code in ten, so it would look
 * like it worked.
 */
export function gtinCheckDigit(digits) {
  const body = digitsOnly(digits);
  let sum = 0;
  // i counts from the right of the body, ignoring the check digit position.
  for (let i = 0; i < body.length; i += 1) {
    const digit = Number(body[body.length - 1 - i]);
    sum += digit * (i % 2 === 0 ? 3 : 1);
  }
  return (10 - (sum % 10)) % 10;
}

/**
 * UPC-E (8 digits) back to the UPC-A (12) it was compressed from.
 *
 * The last of the six middle digits says where the run of zeroes was removed.
 * This is a fixed GS1 table, not a heuristic. It has to be mirrored here
 * because a UPC-E cannot be validated without it - see isValidGtin.
 */
export function expandUpcE(value) {
  const code = digitsOnly(value);
  if (code.length !== 8) return null;
  const system = code[0];
  // Only number systems 0 and 1 have a UPC-E form. Anything else that is eight
  // digits long is an EAN-8, which is already a complete number.
  if (system !== '0' && system !== '1') return null;

  const [a, b, c, d, e, f] = code.slice(1, 7);
  const check = code[7];

  let body;
  if (f === '0' || f === '1' || f === '2') body = `${system}${a}${b}${f}0000${c}${d}${e}`;
  else if (f === '3') body = `${system}${a}${b}${c}00000${d}${e}`;
  else if (f === '4') body = `${system}${a}${b}${c}${d}00000${e}`;
  else body = `${system}${a}${b}${c}${d}${e}0000${f}`;

  return `${body}${check}`;
}

/**
 * Does this code's final digit agree with the rest of it?
 *
 * UPC-E is the exception, and it is not a small one. Its check digit belongs
 * to the UPC-A it was compressed from, NOT to the eight digits as printed - so
 * running the plain routine over a UPC-E rejects it about nine times in ten.
 * Without this branch the scanner would have called every small packet in the
 * shop a misread and refused to scan it at all.
 *
 * An 8-digit code beginning 0 or 1 is genuinely ambiguous - it can be a UPC-E
 * or a real EAN-8, and nothing in the digits says which - so both readings are
 * tried rather than guessed at.
 */
export function isValidGtin(value) {
  const code = digitsOnly(value);
  if (!GTIN_LENGTHS.includes(code.length)) return false;
  // All zeroes passes the arithmetic and is not a product.
  if (/^0+$/.test(code)) return false;

  if (code.length === 8 && (code[0] === '0' || code[0] === '1')) {
    const expanded = expandUpcE(code);
    if (expanded
        && gtinCheckDigit(expanded.slice(0, -1)) === Number(expanded[expanded.length - 1])) {
      return true;
    }
  }

  return gtinCheckDigit(code.slice(0, -1)) === Number(code[code.length - 1]);
}

/**
 * What went wrong, in words a person can act on.
 *
 * Returns '' when the code is fine. The distinction matters: "hold it steadier"
 * and "that product is not in the database" are completely different problems
 * and used to produce the same message.
 */
export function describeGtinProblem(value) {
  const code = digitsOnly(value);
  if (!code) return 'No digits in that scan.';
  if (code.length < 8) return `Only read ${code.length} digits — barcodes have at least 8.`;
  if (!GTIN_LENGTHS.includes(code.length)) {
    return `Read ${code.length} digits, which is not a product barcode length.`;
  }
  if (!isValidGtin(code)) return 'That scan did not check out — hold the packet steadier.';
  return '';
}
