import { QRCodeCanvas } from 'qrcode.react';

/**
 * The QR carries the whole `qr` object — payload and signature together —
 * because that is what a scanner has to hand back to the scan endpoints. They
 * are split into two top-level fields at the point of sending, not here.
 *
 * `code6` sits underneath as the basic-phone fallback, and the signature is
 * shown small and monospace below that so it is visibly a machine artefact.
 */
export default function QrDisplay({ qr, code6, size = 260 }) {
  if (!qr) return null;
  const encoded = JSON.stringify(qr);

  return (
    <div className="qr-display">
      <div className="qr-frame">
        <QRCodeCanvas value={encoded} size={size} level="M" includeMargin />
      </div>

      {code6 && (
        <div className="qr-code6">
          <span className="field-label">Backup code</span>
          <strong>{code6}</strong>
        </div>
      )}

      <details className="qr-signature">
        <summary>Signature</summary>
        <code>{qr.signature}</code>
      </details>
    </div>
  );
}
