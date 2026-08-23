import { useEffect, useRef, useState } from 'react';
import { Html5Qrcode } from 'html5-qrcode';

const REGION_ID = 'qr-camera-region';

/**
 * Camera input for the three scan screens.
 *
 * The QR holds the whole `qr` object, so a successful decode is parsed back
 * into {payload, signature} and handed up exactly as the picker would.
 *
 * Browsers only grant getUserMedia on a secure origin. localhost counts, but a
 * plain-HTTP LAN address does not — so on a phone this needs HTTPS or a tunnel.
 * That failure is reported rather than left as a silent dead camera.
 */
export default function QrScanner({ onDecoded, onError }) {
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState(null);
  const scannerRef = useRef(null);
  const handledRef = useRef(false);

  useEffect(() => {
    return () => {
      const scanner = scannerRef.current;
      if (scanner) {
        scanner.stop().catch(() => {});
        scannerRef.current = null;
      }
    };
  }, []);

  async function start() {
    setMessage(null);
    handledRef.current = false;

    if (!window.isSecureContext) {
      setMessage(
        'The camera needs a secure origin. localhost works; a plain http:// address on another device does not.',
      );
      return;
    }

    try {
      const scanner = new Html5Qrcode(REGION_ID);
      scannerRef.current = scanner;
      setRunning(true);
      await scanner.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 240, height: 240 } },
        (text) => {
          if (handledRef.current) return; // one decode, not one per frame
          handledRef.current = true;
          try {
            const parsed = JSON.parse(text);
            if (!parsed?.payload || !parsed?.signature) {
              throw new Error('shape');
            }
            stop();
            onDecoded(parsed);
          } catch {
            handledRef.current = false;
            setMessage('That code is not a pass from this system.');
          }
        },
        () => {
          // Per-frame "no code found" noise. Not worth surfacing.
        },
      );
    } catch (err) {
      setRunning(false);
      setMessage(
        err?.message?.includes('Permission')
          ? 'Camera permission was refused. Use the picker or the backup code instead.'
          : 'The camera could not be started. Use the picker or the backup code instead.',
      );
      onError?.(err);
    }
  }

  function stop() {
    const scanner = scannerRef.current;
    if (scanner) {
      scanner.stop().catch(() => {});
      scannerRef.current = null;
    }
    setRunning(false);
  }

  return (
    <div className="qr-scanner">
      <div id={REGION_ID} className={running ? 'camera-region active' : 'camera-region'} />
      {running ? (
        <button type="button" onClick={stop}>
          Stop camera
        </button>
      ) : (
        <button type="button" onClick={start}>
          Scan with camera
        </button>
      )}
      {message && <p className="field-hint camera-message">{message}</p>}
    </div>
  );
}
