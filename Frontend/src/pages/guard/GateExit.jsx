import { useState } from 'react';
import { gateExit } from '../../api/scans';
import PassSource from '../../components/PassSource';
import PhotoCard from '../../components/PhotoCard';
import ScanResultPanel from '../../components/ScanResultPanel';
import ErrorBanner from '../../components/ErrorBanner';

/**
 * Faces are shown again before the count is submitted, so the guard can check
 * the same people are leaving as arrived.
 *
 * Counting everyone out closes the visit. Counting fewer out is a partial exit:
 * the visit stays open and the remainder is reported as still inside. Neither
 * is an error.
 */
export default function GateExit() {
  const [stage, setStage] = useState('scan');
  const [pending, setPending] = useState(null);
  const [plate, setPlate] = useState('');
  const [count, setCount] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  function startOver() {
    setStage('scan');
    setPending(null);
    setResult(null);
    setError(null);
    setPlate('');
    setCount('');
    setRefreshKey((k) => k + 1);
  }

  function onArmed(armed) {
    if (!armed.visit) {
      submit({ code6: armed.code6 });
      return;
    }
    setPending(armed);
    setPlate(armed.visit.vehicle_plate_in ?? '');
    const expected = armed.visit.person_count_in ?? armed.visit.person_count_expected;
    setCount(expected != null ? String(expected) : '');
    setStage('verify');
  }

  async function submit(credentials) {
    setBusy(true);
    setError(null);
    try {
      const parsed = Number.parseInt(count, 10);
      const res = await gateExit({
        ...credentials,
        vehicle_plate_out: plate.trim(),
        person_count_out: Number.isNaN(parsed) ? undefined : parsed,
      });
      setResult(res);
      setStage('result');
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (stage === 'verify' && pending) {
    const wentIn = pending.visit.person_count_in ?? pending.visit.person_count_expected;
    return (
      <>
        <p className="step-label">Step 2 of 3</p>
        <h2 className="step-question">Are these the same people leaving?</h2>

        <section className="panel">
          <div className="photo-strip">
            {pending.people.slice(0, 5).map((person, i) => (
              <PhotoCard key={`${person.photo_ref || person.name}-${i}`} person={person} />
            ))}
          </div>
          <dl className="detail-grid">
            <dt>Visitor</dt>
            <dd>{pending.visitor?.name ?? 'Unknown'}</dd>
            <dt>Went in</dt>
            <dd>{wentIn ?? 'not recorded'}</dd>
            <dt>Vehicle in</dt>
            <dd>{pending.visit.vehicle_plate_in ?? 'none'}</dd>
          </dl>
        </section>

        <section className="panel">
          <h3>Who is actually leaving</h3>
          <div className="gate-form">
            <label className="field" htmlFor="exit-plate">
              <span className="field-label">Vehicle plate out</span>
              <input
                id="exit-plate"
                value={plate}
                placeholder="none"
                onChange={(e) => setPlate(e.target.value.toUpperCase())}
              />
            </label>
            <label className="field" htmlFor="exit-count">
              <span className="field-label">People leaving</span>
              <input
                id="exit-count"
                inputMode="numeric"
                value={count}
                onChange={(e) => setCount(e.target.value.replace(/\D/g, ''))}
              />
            </label>
            <button
              type="button"
              className="primary scan-button"
              disabled={busy}
              onClick={() => submit({ qr: pending.qr })}
            >
              {busy ? 'Signing out...' : 'Sign them out'}
            </button>
          </div>
          <p className="field-hint">
            Counting fewer people out than went in is a partial exit. The visit stays open and the
            remainder is reported as still inside.
          </p>
        </section>

        <ErrorBanner error={error} onDismiss={() => setError(null)} />
        <button type="button" className="link-button back-link" onClick={startOver}>
          Back
        </button>
      </>
    );
  }

  if (stage === 'result') {
    return (
      <>
        <p className="step-label">Step 3 of 3</p>
        <section className="panel">
          <ScanResultPanel result={result} />
        </section>
        <button type="button" className="primary next-button" onClick={startOver}>
          Next visitor
        </button>
      </>
    );
  }

  return (
    <>
      <p className="step-label">Step 1 of 3</p>
      <h2 className="step-question">Scan the pass on the way out</h2>
      <PassSource
        statuses={['inside']}
        onArmed={onArmed}
        refreshKey={refreshKey}
        hint="Only someone recorded as inside can sign out."
      >
        <label className="field" htmlFor="exit-code-plate">
          <span className="field-label">Vehicle plate out</span>
          <input
            id="exit-code-plate"
            value={plate}
            placeholder="none"
            onChange={(e) => setPlate(e.target.value.toUpperCase())}
          />
        </label>
        <label className="field" htmlFor="exit-code-count">
          <span className="field-label">People leaving</span>
          <input
            id="exit-code-count"
            inputMode="numeric"
            value={count}
            onChange={(e) => setCount(e.target.value.replace(/\D/g, ''))}
          />
        </label>
      </PassSource>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
    </>
  );
}
