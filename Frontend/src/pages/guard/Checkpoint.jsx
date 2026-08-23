import { useEffect, useState } from 'react';
import { zoneScan } from '../../api/scans';
import { getZones } from '../../api/reference';
import PassSource from '../../components/PassSource';
import ScanResultPanel from '../../components/ScanResultPanel';
import ErrorBanner from '../../components/ErrorBanner';

/**
 * A checkpoint never refuses anyone.
 *
 * Both outcomes are 200: `ok` means expected here, `wrong_zone` means recorded
 * and security notified. Neither is a refusal, so this screen shows no red and
 * never uses the word denied — inside campus the system observes rather than
 * blocks, and a refusal-looking screen would contradict that.
 */
export default function Checkpoint() {
  const [zones, setZones] = useState([]);
  // The CHECKPOINT sends the zone CODE (LIB). Approval sends zone ids (z_2).
  // Mixing them is a silent wrong-zone result rather than an error.
  const [zoneCode, setZoneCode] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    getZones()
      .then((rows) => {
        setZones(rows);
        if (rows.length) setZoneCode(rows[0].code);
      })
      .catch(setError);
  }, []);

  async function onArmed(armed) {
    setBusy(true);
    setError(null);
    try {
      const res = await zoneScan({
        qr: armed.qr,
        code6: armed.qr ? undefined : armed.code6,
        zone_code: zoneCode,
      });
      setResult(res);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  function startOver() {
    setResult(null);
    setError(null);
    setRefreshKey((k) => k + 1);
  }

  if (result) {
    return (
      <>
        <section className="panel">
          <ScanResultPanel result={result} />
        </section>
        <button type="button" className="primary next-button" onClick={startOver}>
          Next scan
        </button>
      </>
    );
  }

  return (
    <>
      <h2 className="step-question">Checkpoint scan</h2>

      <section className="panel">
        <h3>Which checkpoint is this?</h3>
        <div className="zone-picker">
          {zones.map((zone) => (
            <button
              key={zone.id}
              type="button"
              className={`zone-chip${zone.code === zoneCode ? ' selected' : ''}`}
              onClick={() => setZoneCode(zone.code)}
            >
              <span className="zone-code">{zone.code}</span>
              <span className="zone-name">{zone.name}</span>
            </button>
          ))}
        </div>
      </section>

      {busy && <p className="muted">Scanning...</p>}

      <PassSource
        statuses={['inside']}
        onArmed={onArmed}
        refreshKey={refreshKey}
        hint="A checkpoint scan works on anyone who is inside. Nobody is ever turned away here."
      />

      <ErrorBanner error={error} onDismiss={() => setError(null)} />
    </>
  );
}
