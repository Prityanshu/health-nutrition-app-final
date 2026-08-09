#!/usr/bin/env python3
"""
Why did typing the barcode work when scanning the same packet did not?

Because nothing checked what the camera produced. The decoder was handed a
blurry frame, returned something, and that something went straight to the
server - which missed, and reported "this product is not in the food database".
The database was fine. The read was not.

Two other things were wrong on the same path:

  * Code 128 was in the accepted format list. It is not a retail product code,
    and most food packaging carries one next to the EAN-13 holding the batch
    number. The scanner would lock onto whichever crossed the frame first.
  * A UPC-A packet is 12 digits printed on the box but filed under 13 in Open
    Food Facts, and a UPC-E is a *compressed* number that no database holds at
    all. One lookup attempt meant ordinary products came back as unknown.

The check digit is what makes all of this testable without a camera: every
retail barcode ends in one, computed from the digits before it. It is also
implemented twice - once in Python for the server and once in JS for the phone
- so the most valuable assertion here is that the two agree, digit for digit,
over a corpus. A checksum that disagrees with itself is worse than none.

    python scripts/test_barcode.py
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SRC = ROOT / "frontend" / "src"

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
)
passed = failed = skipped = 0


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  {GREEN}pass{RESET}  {label}")
    else:
        failed += 1
        print(f"  {RED}FAIL{RESET}  {label}")
        for line in str(detail).splitlines()[:8]:
            print(f"        {DIM}{line}{RESET}")


def skip(label, why):
    global skipped
    skipped += 1
    print(f"  {YELLOW}skip{RESET}  {label} {DIM}({why}){RESET}")


# Real, published GTINs. Using invented numbers would test the arithmetic
# against itself.
VALID = {
    "5901234123457": "EAN-13",
    "4006381333931": "EAN-13",
    "036000291452": "UPC-A",
    "012345678905": "UPC-A",
    "96385074": "EAN-8",
    "04252614": "UPC-E",
}

# Each is one digit away from a valid code - the shape a misread actually
# takes, rather than obvious rubbish.
INVALID = [
    "5901234123458",   # wrong check digit
    "5901234123447",   # transposed body digit
    "036000291451",
    "96385075",
    "590123412345",    # 12 digits, but it is an EAN-13 with one dropped
    "1234567",         # too short
    "00000000",        # arithmetically fine, not a product
]


# ---------------------------------------------------------------------------

def test_check_digit():
    from app.services.food_lookup import gtin_check_digit, is_valid_gtin
    print(f"\n{BOLD}1. The check digit every retail barcode carries{RESET}")

    for code, kind in VALID.items():
        check(f"{kind} {code} validates", is_valid_gtin(code))
        if kind != "UPC-E":
            # UPC-E is deliberately excluded here: its check digit belongs to
            # the UPC-A it was compressed from, so the plain routine does NOT
            # reproduce it. Asserting otherwise is what this test caught.
            check(f"...and its check digit is recomputable",
                  gtin_check_digit(code[:-1]) == int(code[-1]),
                  f"computed {gtin_check_digit(code[:-1])}, printed {code[-1]}")

    for code in INVALID:
        check(f"{code} is rejected", not is_valid_gtin(code))

    # Non-digits are stripped, not treated as a failure: a user pastes
    # "8 906129 282742" straight off the packet.
    spaced = "5 901234 123457"
    check("spaces and dashes are ignored", is_valid_gtin(spaced), spaced)
    check("empty input is not a barcode", not is_valid_gtin(""))
    check("None is not a barcode", not is_valid_gtin(None))

    # The weights alternate from the RIGHT, which is what makes one routine
    # cover 8 through 14 digits. Weighting from the left is the obvious
    # mistake, and for an odd number of body digits it gives the identical
    # answer - so it passes on EAN-8 and looks correct. It only diverges on
    # even-length bodies, which is where this check has to look.
    def from_left(body):
        total = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(body))
        return (10 - total % 10) % 10

    diverges = [
        code for code in VALID
        if len(code) in (13,) and from_left(code[:-1]) != gtin_check_digit(code[:-1])
    ]
    check("the weights run from the right, not the left",
          bool(diverges),
          "no published code in the corpus distinguishes the two directions, "
          "so this test proves nothing - add one that does")
    check("...and the published check digits confirm which is correct",
          all(gtin_check_digit(c[:-1]) == int(c[-1]) for c in diverges),
          {c: (gtin_check_digit(c[:-1]), from_left(c[:-1]), c[-1]) for c in diverges})

    # A 14-digit GTIN is a carton code. It is valid and Open Food Facts holds
    # some, so it must not be rejected for being long.
    gtin14 = "0" + "5901234123457"
    check("a 14-digit GTIN is accepted", is_valid_gtin(gtin14), gtin14)


def test_upc_e_expansion():
    from app.services.food_lookup import expand_upc_e, is_valid_gtin
    print(f"\n{BOLD}2. UPC-E is a compressed number, not a number{RESET}")

    # The published example: the zero-suppression rule is chosen by the last
    # digit of the six-digit body.
    check("04252614 expands to 042100005264",
          expand_upc_e("04252614") == "042100005264",
          expand_upc_e("04252614"))

    # Sweep all four branches of the rule table.
    #
    # Building the codes rather than listing them: a UPC-E's check digit is the
    # check digit of its own expansion, so a valid one has to be constructed by
    # expanding first and computing the digit second. Listing hand-typed codes
    # here would only test my typing.
    from app.services.food_lookup import gtin_check_digit
    bad, lengths, covered = [], set(), set()
    for system in ("0", "1"):
        for prefix in ("12345", "90807", "00001", "99999"):
            for selector in "0123456789":
                middle = prefix + selector
                stub = f"{system}{middle}0"                 # placeholder check
                expanded = expand_upc_e(stub)
                if expanded is None:
                    bad.append(f"{stub} did not expand at all")
                    continue
                correct = gtin_check_digit(expanded[:-1])
                upc_e = f"{system}{middle}{correct}"
                upc_a = f"{expanded[:-1]}{correct}"

                lengths.add(len(upc_a))
                covered.add(selector)
                if expand_upc_e(upc_e) != upc_a:
                    bad.append(f"{upc_e} -> {expand_upc_e(upc_e)}, expected {upc_a}")
                elif not is_valid_gtin(upc_a):
                    bad.append(f"expansion {upc_a} is not a valid UPC-A")
                elif not is_valid_gtin(upc_e):
                    bad.append(f"UPC-E {upc_e} rejected, though {upc_a} is valid")

    check("every expansion is a valid 12-digit UPC-A", not bad, "\n".join(bad))
    check("...always exactly 12 digits", lengths == {12}, lengths)
    check("...across all ten zero-suppression selectors",
          covered == set("0123456789"), sorted(covered))

    # The whole reason the branch exists: a UPC-E fails the plain routine, so
    # without expanding it first the scanner calls every small packet a
    # misread and refuses to scan it.
    check("a UPC-E would fail the plain mod-10 check",
          gtin_check_digit("0425261") != 4,
          "if this ever passes, the special case is untested")
    check("...but validates through its expansion", is_valid_gtin("04252614"))

    check("an EAN-8 is left alone - it is already complete",
          expand_upc_e("96385074") is None,
          "number system 9 has no UPC-E form")
    check("a 13-digit code is not a UPC-E", expand_upc_e("5901234123457") is None)


def test_variants():
    from app.services.food_lookup import gtin_variants
    print(f"\n{BOLD}3. The same product, filed under several numbers{RESET}")

    upc_a = gtin_variants("036000291452")
    check("the printed number is tried first", upc_a[0] == "036000291452", upc_a)
    check("...and its EAN-13 form is tried too", "0036000291452" in upc_a, upc_a)

    ean = gtin_variants("0036000291452")
    check("a leading-zero EAN-13 also tries the 12-digit form",
          "036000291452" in ean, ean)

    upc_e = gtin_variants("04252614")
    check("a UPC-E tries its expansion", "042100005264" in upc_e, upc_e)
    check("...and the EAN-13 of that expansion", "0042100005264" in upc_e, upc_e)

    check("no duplicates - each variant costs a network call",
          len(gtin_variants("036000291452")) == len(set(gtin_variants("036000291452"))))
    check("garbage in, nothing out", gtin_variants("") == [])

    # An EAN-13 that does not start with zero has no shorter form, so there is
    # nothing to try beyond itself. Inventing one would be a wasted request on
    # every Indian product, which all start 890.
    check("a plain EAN-13 does not invent alternatives",
          gtin_variants("8906129282742") == ["8906129282742"],
          gtin_variants("8906129282742"))


def test_lookup_tries_every_variant():
    """The functions above are useless if lookup() never calls them."""
    import app.services.food_lookup as fl
    print(f"\n{BOLD}4. lookup() actually uses them{RESET}")

    tried = []

    def fake(query, barcode=None):
        tried.append(barcode)
        # Only the EAN-13 form is in this pretend database, which is the exact
        # situation that made real UPC-A packets look unknown.
        if barcode == "0036000291452":
            return fl.NutritionFacts(
                food_name="", calories=100, protein=1, carbohydrates=1, fat=1,
                matched_name="Found", verified=True, exact=True,
            )
        return None

    original = fl.lookup_open_food_facts
    fl.lookup_open_food_facts = fake
    try:
        found = fl.lookup(query="", barcode="036000291452")
    finally:
        fl.lookup_open_food_facts = original

    check("a UPC-A that is only stored as EAN-13 is now found",
          found is not None and found.matched_name == "Found", tried)
    check("...having tried the printed number first", tried[0] == "036000291452", tried)
    check("...and it stops as soon as it hits", tried[-1] == "0036000291452", tried)


def test_router_separates_misread_from_missing():
    print(f"\n{BOLD}5. A bad read and an unknown product are different things{RESET}")

    source = (ROOT / "app" / "routers" / "nutrient_analyzer.py").read_text()
    barcode_route = source.split("/nutrient/barcode", 1)[-1].split("@router.", 1)[0]

    check("the 404 branch distinguishes the two cases",
          "is_valid_gtin" in barcode_route,
          "one message for both was what told users their packet does not exist")
    check("...and the message says 'misread' when that is what happened",
          "misread" in barcode_route.lower())
    check("...and quotes the digits it actually read",
          "{digits}" in barcode_route,
          "without this there is no way to see that the scan differs from the box")


# ---------------------------------------------------------------------------
# the phone's copy of the same arithmetic
# ---------------------------------------------------------------------------

JS_HARNESS = r"""
const fs = require('fs');
// barcode.js has no imports, only top-level named exports, so dropping the
// keyword turns it into a plain script.
const src = fs.readFileSync(process.argv[2], 'utf8').replace(/^export /gm, '');
eval(src);
const codes = JSON.parse(process.argv[3]);
const out = {};
for (const code of codes) out[code] = isValidGtin(code);
console.log(JSON.stringify(out));
"""


def test_js_agrees_with_python():
    from app.services.food_lookup import is_valid_gtin
    print(f"\n{BOLD}6. The phone and the server compute the same check digit{RESET}")

    node = shutil.which("node")
    if not node:
        skip("JS and Python agree on every code", "node not installed")
        return

    codes = list(VALID) + INVALID + [
        "8906129282742", "5 901234 123457", "042100005264", "0042100005264",
        "1", "999999999999999", "0000000000000",
        # UPC-E, which needs the expansion branch on both sides. This is the
        # case where the two implementations are most likely to drift, because
        # it is the one that does not follow the obvious rule.
        "04252614", "04252615", "01278906", "12345670",
    ]

    with tempfile.TemporaryDirectory() as tmp:
        harness = Path(tmp) / "harness.js"
        harness.write_text(JS_HARNESS)
        result = subprocess.run(
            [node, str(harness), str(SRC / "barcode.js"), json.dumps(codes)],
            capture_output=True, text=True, timeout=30,
        )

    if result.returncode != 0:
        check("the JS module loads", False, result.stderr[-600:])
        return
    check("the JS module loads", True)

    js = json.loads(result.stdout)
    disagreements = [
        f"{code}: js={js[code]} python={is_valid_gtin(code)}"
        for code in codes if js[code] != is_valid_gtin(code)
    ]
    check(f"all {len(codes)} codes get the same verdict on both sides",
          not disagreements, "\n".join(disagreements))


def test_scanner_component():
    print(f"\n{BOLD}7. The scanner rejects a bad read instead of sending it{RESET}")

    scanner = (SRC / "components" / "BarcodeScanner.jsx").read_text()
    formats = scanner.split("formatsToSupport", 1)[-1].split("]", 1)[0]

    check("CODE_128 is no longer an accepted format",
          "CODE_128" not in formats,
          "a batch-number barcode is not a food and will never be in a database")
    check("...but the four retail formats still are",
          all(f in formats for f in ("EAN_13", "EAN_8", "UPC_A", "UPC_E")), formats)

    callback = scanner.split("(decoded) =>", 1)[-1].split("() => {}", 1)[0]
    check("the decoded value is validated before it leaves the phone",
          "isValidGtin" in callback, callback[:400])
    check("a failed read returns without calling onDetected",
          re.search(r"if \(!isValidGtin\(code\)\)[\s\S]{0,200}?return;", callback) is not None,
          callback[:400])
    check("the same code must be read twice before it is accepted",
          "pendingRef" in callback,
          "a checksum still passes about one bad read in ten by chance")
    check("onDetected gets the validated digits, not the raw string",
          "onDetected(code)" in callback, callback[-200:])

    # Manual entry is the fallback for when the camera cannot cope. If it
    # refuses input too, there is no fallback left.
    manual = scanner.split("submitManual", 1)[-1].split("};", 1)[0]
    check("typing a barcode is warned about but never blocked",
          "onDetected(digits)" in manual, manual)


def test_toast_is_wired():
    print(f"\n{BOLD}8. Logging a meal says so{RESET}")

    shell = (SRC / "components" / "AppShell.jsx").read_text()
    check("ToastHost is mounted once, in the shell",
          "<ToastHost />" in shell and "import ToastHost" in shell)

    log_meal = (SRC / "components" / "LogMeal.jsx").read_text()
    save = log_meal.split("const save = async", 1)[-1].split("const pick", 1)[0]
    check("a successful log raises a toast", "toast(" in save, save[:300])
    check("...and a failed one raises an error toast", "toastError(" in save)

    # The reason a toast was needed at all: the inline card renders above the
    # panel the user just tapped, which is off-screen on a phone.
    css = (SRC / "index.css").read_text()
    stack = re.search(r"\.toast-stack\s*\{[^}]*\}", css, re.S)
    check("the toast is fixed, not part of the page flow",
          stack is not None and "position: fixed" in stack.group(0),
          stack.group(0) if stack else "no .toast-stack rule")
    check("...and sits above the whole navigation stack",
          stack is not None and "z-index: 80" in stack.group(0),
          "bottom nav is 45, scrim 55, rail 60")
    check("...and clears the tab bar on a phone",
          "var(--tabbar-h)" in css.split(".toast-stack", 1)[-1][:900],
          "otherwise the confirmation hides behind the tab bar")


def test_native_file_export():
    print(f"\n{BOLD}9. PDF export works in the APK, not just the browser{RESET}")

    native = (SRC / "nativeFiles.js").read_text()
    check("it checks which shell it is running in", "isNativeApp" in native)
    check("native saving goes through Capacitor Filesystem",
          "@capacitor/filesystem" in native)
    check("native sharing goes through Capacitor Share",
          "@capacitor/share" in native)
    check("the browser path is still an anchor click",
          "a.download = filename" in native,
          "the website must not change")

    # The old failure mode: report success for something that did nothing.
    save_fn = native.split("export async function saveFile", 1)[-1].split("export async function shareFile", 1)[0]
    check("a refused Documents write falls back to the share sheet, not the cache",
          "shareFile(" in save_fn and "Cache" not in save_fn,
          "a cache write would report 'saved' about a file the user cannot find")

    ui = (SRC / "components" / "SpecialistUI.jsx").read_text()
    actions = ui.split("export function PlanActions", 1)[-1].split("function EmailDialog", 1)[0]
    check("Download PDF calls saveFile", "await saveFile(" in actions)
    check("Share calls shareFile", "await shareFile(" in actions)
    check("no component builds its own download anchor any more",
          "a.download" not in actions,
          "the Android WebView ignores it and throws nothing")
    check("a dismissed share sheet is not reported as a success",
          "cancelled" in actions, actions[:600])

    # Share needs the file on disk, and FileProvider will only hand out a URI
    # for a directory listed in file_paths.xml.
    paths = (ROOT / "frontend" / "android" / "app" / "src" / "main"
             / "res" / "xml" / "file_paths.xml").read_text()
    for entry in ("cache-path", "external-path", "external-files-path", "files-path"):
        check(f"file_paths.xml grants {entry}", f"<{entry}" in paths)
    check("no double hyphen inside an XML comment",
          not re.search(r"<!--(?:(?!-->)[\s\S])*?--(?:(?!>)[\s\S])", paths),
          "this exact mistake failed a Gradle build once already")

    manifest = (ROOT / "frontend" / "android" / "app" / "src" / "main"
                / "AndroidManifest.xml").read_text()
    check("the storage permission is capped at API 29",
          'android:maxSdkVersion="29"' in manifest,
          "Android 11+ needs no permission; asking would be a prompt for nothing")

    pkg = json.loads((ROOT / "frontend" / "package.json").read_text())
    deps = pkg.get("dependencies", {})
    for plugin in ("@capacitor/filesystem", "@capacitor/share"):
        check(f"{plugin} is a declared dependency", plugin in deps, sorted(deps))


def test_no_orphan_tests():
    """
    Every test above must actually be called.

    A suite that reports 60 passes while two functions were never invoked is
    worse than no suite: it reports confidence it has not earned. This has
    happened here before.
    """
    print(f"\n{BOLD}10. No test is defined and then forgotten{RESET}")
    import inspect
    body = inspect.getsource(main)
    defined = {
        name for name, obj in globals().items()
        if name.startswith("test_") and inspect.isfunction(obj)
    }
    missing = sorted(n for n in defined if f"{n}()" not in body)
    check(f"all {len(defined)} test functions are called", not missing, missing)


def main():
    test_check_digit()
    test_upc_e_expansion()
    test_variants()
    test_lookup_tries_every_variant()
    test_router_separates_misread_from_missing()
    test_js_agrees_with_python()
    test_scanner_component()
    test_toast_is_wired()
    test_native_file_export()
    test_no_orphan_tests()

    print(f"\n{BOLD}{'-' * 62}{RESET}")
    tail = f", {YELLOW}{skipped} skipped{RESET}" if skipped else ""
    print(f"{GREEN}{passed} passed{RESET}, "
          f"{RED if failed else DIM}{failed} failed{RESET}{tail}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
