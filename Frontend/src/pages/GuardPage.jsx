import { useEffect, useState } from 'react';
import { getVisit } from '../api/visits';
import { getVisitor } from '../api/visitors';
import { getPass } from '../api/passes';
import { gateEntry } from '../api/scans';
import ScanResultPanel from '../components/ScanResultPanel';
import PhotoCard from '../components/PhotoCard';
import ErrorBanner from '../components/ErrorBanner';

// /dev/reset hands back identical ids every time. The list endpoint is
// faculty-only, so each one is fetched individually — see UI-SPEC §5.5.
const SEEDED_VISIT_IDS = ['v_1', 'v_2', 'v_3', 'v_4', 'v_5', 'v_6'];

/**
 * Three steps, one on screen at a time.
 *
 *   1 SCAN     read the pass — nothing is recorded yet
 *   2 VERIFY   the guard compares faces against the people in front of them
 *   3 RESULT   what the system recorded
 *
 * Step 2 is why the backend call is deferred. Reading a pass and its visit
 * record writes nothing, so refusing at step 2 leaves no entry behind — the
 * refusal is real rather than cosmetic. Approving is what submits the scan.
 */
export default function GuardPage() {
  const [visits, setVisits] = useState([]);
  const [loadingVisits, setLoadingVisits] = useState(true);

  const [stage, setStage] = useState('scan');
  const [pending, setPending] = useState(null);
  const [code6, setCode6] = useState('');
  const [plate, setPlate] = useState('');
  const [count, setCount] = useState('');

  const [result, setResult] = useState(null);
  const [refused, setRefused] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all(SEEDED_VISIT_IDS.map((id) => getVisit(id).catch(() => null))).then((rows) => {
      if (active) {
        setVisits(rows.filter(Boolean));
        setLoadingVisits(false);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  function startOver() {
    setStage('scan');
    setPending(null);
    setResult(null);
    setRefused(false);
    setError(null);
    setCode6('');
    setPlate('');
    setCount('');
  }

  // Step 1 to 2. Reads the pass and the visit record. Writes nothing.
  async function readPass(visit) {
    setBusy(true);
    setError(null);
    try {
      const [pass, visitor] = await Promise.all([
        getPass(visit.id),
        getVisitor(visit.visitor_id).catch(() => null),
      ]);
      const people = [
        { role: 'visitor', name: visitor?.name ?? 'Visitor', photo_ref: visitor?.photo_ref },
        ...(visit.companions ?? []).map((c) => ({
          role: 'companion',
          name: c.name,
          photo_ref: c.photo_ref,
        })),
      ];
      setPending({ visit, visitor, qr: pass.qr, code6: pass.code6, people });
      setPlate(visit.vehicle_plate_in ?? '');
      setCount(visit.person_count_expected != null ? String(visit.person_count_expected) : '');
      setStage('verify');
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function submitScan(credentials) {
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

  /* ---------------------------------------------------------------- */

  if (stage === 'verify' && pending) {
    return (
      <div className="guard-screen">
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
            onClick={() => submitScan({ qr: pending.qr })}
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
      </div>
    );
  }

  if (stage === 'result') {
    return (
      <div className="guard-screen">
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
      </div>
    );
  }

  /* Step 1 - scan */
  return (
    <div className="guard-screen">
      <p className="step-label">Step 1 of 3</p>
      <h2 className="step-question">Scan the pass</h2>

      <section className="panel">
        {loadingVisits ? <p className="muted">Loading...</p> : null}
        <div className="visit-picker">
          {visits.map((visit) => {
            const admittable = visit.status === 'issued';
            return (
              <button
                key={visit.id}
                type="button"
                className="visit-chip"
                disabled={!admittable || busy}
                title={admittable ? undefined : `Status is ${visit.status} - nothing to admit`}
                onClick={() => readPass(visit)}
              >
                <span className="visit-id">{visit.id}</span>
                <span className={`status-badge status-${visit.status}`}>{visit.status}</span>
                <span className="visit-purpose">{visit.purpose}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="panel">
        <h3>Backup code</h3>
        <div className="gate-form">
          <label className="field" htmlFor="code6">
            <span className="field-label">6-digit code</span>
            <input
              id="code6"
              inputMode="numeric"
              maxLength={6}
              placeholder="000000"
              value={code6}
              onChange={(e) => setCode6(e.target.value.replace(/\D/g, ''))}
            />
          </label>
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
          <button
            type="button"
            disabled={busy || code6.trim().length === 0}
            onClick={() => submitScan({ code6: code6.trim() })}
          >
            {busy ? 'Scanning...' : 'Scan code'}
          </button>
        </div>
        <p className="field-hint">
          Nothing resolves a backup code to a visit, so this path goes straight to the result.
          There is nobody to show you first.
        </p>
      </section>

      <ErrorBanner error={error} onDismiss={() => setError(null)} />
    </div>
  );
}
