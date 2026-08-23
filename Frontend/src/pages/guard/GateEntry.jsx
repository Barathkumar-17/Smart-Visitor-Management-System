import { useState } from 'react';
import { gateEntry } from '../../api/scans';
import PassSource from '../../components/PassSource';
import PhotoCard from '../../components/PhotoCard';
import ScanResultPanel from '../../components/ScanResultPanel';
import ErrorBanner from '../../components/ErrorBanner';

/**
 * Three steps, one on screen at a time.
 *
 *   1 SCAN     read the pass — nothing is recorded yet
 *   2 VERIFY   the guard compares faces against the people in front of them
 *   3 RESULT   what the system recorded
 *
 * Step 2 is why the backend call is deferred. Reading a pass writes nothing, so
 * refusing at step 2 leaves no entry behind — the refusal is real rather than
 * cosmetic. Approving is what submits the scan.
 */
export default function GateEntry() {
  const [stage, setStage] = useState('scan');
  const [pending, setPending] = useState(null);
  const [plate, setPlate] = useState('');
  const [count, setCount] = useState('');
  const [result, setResult] = useState(null);
  const [refused, setRefused] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  function startOver() {
    setStage('scan');
    setPending(null);
    setResult(null);
    setRefused(false);
    setError(null);
    setPlate('');
    setCount('');
    setRefreshKey((k) => k + 1);
  }

  function onArmed(armed) {
    if (!armed.visit) {
      // Backup code: nobody to show, so it goes straight to the scan.
      submit({ code6: armed.code6 });
      return;
    }
    setPending(armed);
    setPlate(armed.visit.vehicle_plate_in ?? '');
    setCount(
      armed.visit.person_count_expected != null ? String(armed.visit.person_count_expected) : '',
    );
    setStage('verify');
  }

  async function submit(credentials) {
    setBusy(true);
    setError(null);
    try {
      const parsed = Number.parseInt(count, 10);
      // A refusal by the system is a 200 with admitted:false. Only transport
      // and permission problems reach the catch.
      const res = await gateEntry({
        ...credentials,
        vehicle_plate: plate.trim(),
        person_count_in: Number.isNaN(parsed) ? undefined : parsed,
      });
      setResult(res);
      setStage('result');
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  function refuse() {
    // Nothing has been sent to the server, and nothing will be.
    setRefused(true);
    setStage('result');
  }

  if (stage === 'verify' && pending) {
    return (
      <>
        <p className="step-label">Step 2 of 3</p>
        <h2 className="step-question">Do these people match?</h2>

        <section className="panel">
          <div className="photo-strip">
            {pending.people.slice(0, 5).map((person, i) => (
              <PhotoCard key={`${person.photo_ref || person.name}-${i}`} person={person} />
            ))}
          </div>

          <dl className="detail-grid">
            <dt>Visitor</dt>
            <dd>
              {pending.visitor?.name ?? 'Unknown'}{' '}
              {pending.visitor?.tier ? (
                <span className={`tier tier-${pending.visitor.tier}`}>{pending.visitor.tier}</span>
              ) : null}
            </dd>
            <dt>Purpose</dt>
            <dd>{pending.visit.purpose}</dd>
            <dt>Expected vehicle</dt>
            <dd>{pending.visit.vehicle_plate_in ?? 'none'}</dd>
            <dt>Expected people</dt>
            <dd>{pending.visit.person_count_expected ?? 'not stated'}</dd>
          </dl>

          <p className="field-hint not-verified-note">
            The pass itself has not been checked yet. That happens when you approve.
          </p>
        </section>

        <section className="panel">
          <h3>What is actually at the gate</h3>
          <div className="gate-form">
            <label className="field" htmlFor="plate">
              <span className="field-label">Vehicle plate</span>
              <input
                id="plate"
                value={plate}
                placeholder="none"
                onChange={(e) => setPlate(e.target.value.toUpperCase())}
              />
            </label>
            <label className="field" htmlFor="count">
              <span className="field-label">People entering</span>
              <input
                id="count"
                inputMode="numeric"
                value={count}
                onChange={(e) => setCount(e.target.value.replace(/\D/g, ''))}
              />
            </label>
          </div>
        </section>

        <ErrorBanner error={error} onDismiss={() => setError(null)} />

        <div className="decision-row">
          <button
            type="button"
            className="decision decision-approve"
            disabled={busy}
            onClick={() => submit({ qr: pending.qr })}
          >
            {busy ? 'Approving...' : 'Approve - let them in'}
          </button>
          <button
            type="button"
            className="decision decision-refuse"
            disabled={busy}
            onClick={refuse}
          >
            Refuse entry
          </button>
        </div>

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
          {refused ? (
            <div className="verdict verdict-red" role="status">
              <strong className="verdict-headline">Refused at the gate</strong>
              <span className="verdict-reason">
                No entry was recorded. Nothing was sent to the server.
              </span>
            </div>
          ) : (
            <ScanResultPanel result={result} />
          )}
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
      <h2 className="step-question">Scan the pass</h2>
      <PassSource statuses={['issued']} onArmed={onArmed} refreshKey={refreshKey}>
        <label className="field" htmlFor="code-plate">
          <span className="field-label">Vehicle plate</span>
          <input
            id="code-plate"
            value={plate}
            placeholder="none"
            onChange={(e) => setPlate(e.target.value.toUpperCase())}
          />
        </label>
        <label className="field" htmlFor="code-count">
          <span className="field-label">People</span>
          <input
            id="code-count"
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
