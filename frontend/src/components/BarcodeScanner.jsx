import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X, Camera, Keyboard, AlertCircle, ScanLine } from 'lucide-react';
import { digitsOnly, isValidGtin, describeGtinProblem } from '../barcode';

/**
 * Barcode scanner for packaged food.
 *
 * Every other number in this app is an approximation. A barcode is the one
 * input that identifies exactly one product, so the values come off the actual
 * label rather than from a model's impression of what a sandwich contains.
 *
 * Two deliberate choices:
 *
 *  - There is always a manual entry option. Cameras are refused, unavailable
 *    on desktop, and useless in a dim kitchen; a scanner with no fallback is a
 *    dead end in all three cases. The digits under the bars work just as well.
 *  - It renders through a portal. The page uses entry animations that leave a
 *    permanent transform on the card, which makes any fixed-position child
 *    position against that card instead of the viewport - the same bug that
 *    threw the email popover off screen.
 */

const READER_ID = 'nutriplan-barcode-reader';

export default function BarcodeScanner({ onDetected, onClose }) {
  const [mode, setMode] = useState('camera');   // camera | manual
  const [error, setError] = useState('');
  const [manual, setManual] = useState('');
  const [starting, setStarting] = useState(true);
  // A rejected read is not an error - it is the scanner doing its job. It gets
  // its own quiet line under the frame rather than the red error box.
  const [hint, setHint] = useState('');
  const scannerRef = useRef(null);
  const handledRef = useRef(false);   // a barcode in view fires repeatedly
  // The last code that passed validation. A code has to be read twice in a row
  // before it is accepted; see the callback below for why.
  const pendingRef = useRef('');

  useEffect(() => {
    if (mode !== 'camera') return undefined;

    let cancelled = false;
    let instance = null;

    /*
     * Shutting the camera down is fussier than it looks.
     *
     * html5-qrcode's stop() THROWS synchronously if the scanner is not
     * currently running - it does not return a rejected promise - so a bare
     * .catch() misses it entirely. And React 18 StrictMode mounts every effect
     * twice in development, so the first cleanup fires while start() is still
     * in flight, hitting exactly that case.
     *
     * So: check the state first, and guard the call itself.
     */
    const shutdown = (target) => {
      if (!target) return;
      try {
        // 2 = SCANNING, 3 = PAUSED. Anything else cannot be stopped.
        const state = typeof target.getState === 'function' ? target.getState() : 2;
        if (state === 2 || state === 3) {
          target.stop()
            .then(() => { try { target.clear(); } catch { /* already gone */ } })
            .catch(() => {});
          return;
        }
        target.clear();
      } catch {
        // Already torn down. Nothing useful to do, and certainly nothing worth
        // surfacing to the user as a runtime error.
      }
    };

    (async () => {
      try {
        const { Html5Qrcode, Html5QrcodeSupportedFormats } = await import('html5-qrcode');
        if (cancelled) return;

        instance = new Html5Qrcode(READER_ID, {
          // Retail product codes only. Including QR would let the scanner lock
          // onto any random code in frame.
          //
          // CODE_128 used to be in this list and had to come out. It is not a
          // retail product code: it has no fixed length, no check digit anyone
          // can verify, and no meaning in a food database. Most Indian food
          // packaging carries a second Code 128 barcode beside the EAN-13
          // holding the batch number, MRP or packing date - and the scanner
          // would happily lock onto whichever crossed the frame first, then
          // report the batch number as "not in the food database".
          formatsToSupport: [
            Html5QrcodeSupportedFormats.EAN_13,
            Html5QrcodeSupportedFormats.EAN_8,
            Html5QrcodeSupportedFormats.UPC_A,
            Html5QrcodeSupportedFormats.UPC_E,
          ],
        });
        scannerRef.current = instance;

        await instance.start(
          { facingMode: 'environment' },
          { fps: 10, qrbox: { width: 260, height: 140 }, aspectRatio: 1.6 },
          (decoded) => {
            // The camera keeps decoding the same code many times a second.
            if (handledRef.current) return;

            const code = digitsOnly(decoded);

            /*
             * Check the code before trusting it.
             *
             * Every retail barcode ends in a check digit computed from the
             * digits before it, so a partial or smeared read is detectable
             * right here - on the phone, before any request goes out. This
             * used to be missing entirely: whatever the decoder returned was
             * sent straight to the server, missed, and came back as "that
             * product is not in the database". Which blamed the database for
             * a camera problem, and is exactly why typing the same number by
             * hand worked.
             *
             * Rejecting means keep scanning. That is what a scanner should do
             * with a bad frame - not give up and accuse the user.
             */
            if (!isValidGtin(code)) {
              pendingRef.current = '';
              setHint(describeGtinProblem(code));
              return;
            }

            /*
             * And require the same code twice running.
             *
             * A checksum catches a mangled read, but roughly one bad read in
             * ten passes it by chance. Two independent frames agreeing takes
             * that to one in a hundred, and costs about a tenth of a second at
             * 10fps - which nobody notices, because the code is still in view.
             */
            if (pendingRef.current !== code) {
              pendingRef.current = code;
              setHint('');
              return;
            }

            handledRef.current = true;
            onDetected(code);
          },
          () => {}   // per-frame misses are normal; ignore them
        );

        // The component may have unmounted while start() was awaiting the
        // camera. If so, the scanner we just started has no owner - stop it
        // here rather than leaving the camera light on.
        if (cancelled) {
          shutdown(instance);
          return;
        }
        setStarting(false);
      } catch (e) {
        if (cancelled) return;
        setStarting(false);
        const message = String(e?.message || e);
        setError(
          /permission|denied|notallowed/i.test(message)
            ? 'Camera access was blocked. Allow it in your browser, or type the number instead.'
            : /notfound|no camera|devices/i.test(message)
              ? 'No camera found on this device. Type the number under the barcode instead.'
              : 'Could not start the camera. Typing the number works just as well.'
        );
      }
    })();

    return () => {
      cancelled = true;
      const active = scannerRef.current || instance;
      scannerRef.current = null;
      shutdown(active);
    };
  }, [mode, onDetected]);

  // Escape should close a full-screen overlay.
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const submitManual = (e) => {
    e.preventDefault();
    const digits = digitsOnly(manual);
    if (digits.length < 8 || digits.length > 14) {
      setError('Barcodes are 8 to 14 digits. Check the number under the bars.');
      return;
    }
    // Deliberately a warning and not a block. A failed check digit here is
    // almost always a typo, so it is worth saying - but this path is the
    // fallback for when the camera cannot cope, and a fallback that refuses
    // input is not a fallback. Let it through and let the lookup decide.
    onDetected(digits);
  };

  // Live feedback while typing, so a transposed digit is caught before the
  // round trip rather than after it.
  const manualDigits = digitsOnly(manual);
  const manualWarning =
    manualDigits.length >= 8 && !isValidGtin(manualDigits)
      ? "Those digits don't match the barcode's own check digit — worth a second look."
      : '';

  return createPortal(
    <div
      className="scan-overlay"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="scan-sheet">
        <div className="flex items-center justify-between" style={{ marginBottom: '1rem' }}>
          <div>
            <div className="section-title" style={{ fontSize: '1rem' }}>Scan the packet</div>
            <div className="section-sub">Exact values, straight off the label</div>
          </div>
          <button className="ghost-btn" onClick={onClose} aria-label="Close scanner">
            <X size={16} />
          </button>
        </div>

        <div className="segmented" style={{ marginBottom: '1rem' }}>
          <button
            className={mode === 'camera' ? 'is-active' : ''}
            onClick={() => { setMode('camera'); setError(''); setHint(''); pendingRef.current = ''; }}
            style={{ flex: 1 }}
          >
            <Camera size={14} /> Camera
          </button>
          <button
            className={mode === 'manual' ? 'is-active' : ''}
            onClick={() => { setMode('manual'); setError(''); setHint(''); pendingRef.current = ''; }}
            style={{ flex: 1 }}
          >
            <Keyboard size={14} /> Type it
          </button>
        </div>

        {mode === 'camera' ? (
          <div>
            <div className="scan-frame">
              <div id={READER_ID} style={{ width: '100%' }} />
              {starting && !error && (
                <div className="scan-hint">
                  <ScanLine size={22} />
                  <span>Starting the camera…</span>
                </div>
              )}
            </div>
            {!error && (
              <div
                className="section-sub"
                style={{
                  textAlign: 'center', marginTop: '0.75rem',
                  // A rejected read is normal. It gets a colour change, not
                  // the red error box - that box means "this has stopped".
                  color: hint ? '#FBBF24' : undefined,
                }}
              >
                {hint || 'Hold the barcode inside the frame'}
              </div>
            )}
          </div>
        ) : (
          <form onSubmit={submitManual} style={{ display: 'grid', gap: '0.75rem' }}>
            <div style={{ display: 'grid', gap: '0.4rem' }}>
              <label className="section-title" htmlFor="barcode-digits" style={{ fontSize: '0.8125rem' }}>
                The number under the bars
              </label>
              <input
                id="barcode-digits"
                className="form-input"
                inputMode="numeric"
                autoFocus
                placeholder="8906129282742"
                value={manual}
                onChange={(e) => { setManual(e.target.value); setError(''); }}
              />
            </div>
            {manualWarning && (
              <div className="section-sub" style={{ color: '#FBBF24', fontSize: '0.75rem' }}>
                {manualWarning}
              </div>
            )}
            <button type="submit" className="generate-btn" disabled={!manual.trim()}>
              Look it up
            </button>
          </form>
        )}

        {error && (
          <div className="auth-error" style={{ marginTop: '0.875rem' }}>
            <AlertCircle size={15} /> <span>{error}</span>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
