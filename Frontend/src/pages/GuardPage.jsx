import { useEffect, useState } from 'react';
import { getVisit } from '../api/visits';
import { getPass } from '../api/passes';
import { gateEntry } from '../api/scans';
import ScanResultPanel from '../components/ScanResultPanel';
import ErrorBanner from '../components/ErrorBanner';

// /dev/reset hands back identical ids every time, so the demo picker can name
// them outright. The list endpoint is faculty-only, so each one is fetched
// individually — see UI-SPEC §5.5.
const SEEDED_VISIT_IDS = ['v_1', 'v_2', 'v_3', 'v_4', 'v_5', 'v_6'];

export default function GuardPage() {
  const [visits, setVisits] = useState([]);
  const [loadingVisits, setLoadingVisits] = useState(true);

  const [selected, setSelected] = useState(null); // {visit, qr, code6}
  const [code6, setCode6] = useState('');
  const [plate, setPlate] = useState('');
  const [count, setCount] = useState('');

  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all(
      SEEDED_VISIT_IDS.map((id) => getVisit(id).catch(() => null)),
    ).then((rows) => {
      if (active) {
        setVisits(rows.filter(Boolean));
        setLoadingVisits(false);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  async function armVisit(visit) {
    setError(null);
    setResult(null);
    try {
      const pass = await getPass(visit.id);
      setSelected({ visit, qr: pass.qr, code6: pass.code6 });
      setCode6('');
      // Prefilled with what the pass expects, so the happy path is one click
      // and forcing an amber verdict is a single edit.
      setPlate(visit.vehicle_plate_in ?? '');
      setCount(visit.person_count_expected != null ? String(visit.person_count_expected) : '');
    } catch (err) {
      setSelected(null);
      setError(err);
    }
  }

  function clearSelection() {
    setSelected(null);
    setPlate('');
    setCount('');
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const parsed = Number.parseInt(count, 10);
      const res = await gateEntry({
        qr: selected?.qr,
        code6: selected ? undefined : code6.trim(),
        vehicle_plate: plate.trim(),
        person_count_in: Number.isNaN(parsed) ? undefined : parsed,
      });
      // A refusal is a 200 with admitted:false. Only transport and permission
      // problems reach the catch below.
      setResult(res);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const armed = Boolean(selected) || code6.trim().length > 0;

  return (
    <div className="guard-screen">
      <h2>Gate entry</h2>

      <section className="panel">
        <h3>1 · Pick a pass</h3>

        {loadingVisits && <p className="muted">Loading seeded visits…</p>}

        <div className="visit-picker">
          {visits.map((visit) => {
            const admittable = visit.status === 'issued';
            const isSelected = selected?.visit.id === visit.id;
            return (
              <button
                key={visit.id}
                type="button"
                className={`visit-chip${isSelected ? ' selected' : ''}`}
                disabled={!admittable}
                title={admittable ? undefined : `Status is ${visit.status} — nothing to admit`}
                onClick={() => armVisit(visit)}
              >
                <span className="visit-id">{visit.id}</span>
                <span className={`status-badge status-${visit.status}`}>{visit.status}</span>
                <span className="visit-purpose">{visit.purpose}</span>
              </button>
            );
          })}
        </div>

        <div className="code6-row">
          <label className="field" htmlFor="code6">
            <span className="field-label">…or type the 6-digit backup code</span>
            <input
              id="code6"
              inputMode="numeric"
              maxLength={6}
              placeholder="342941"
              value={code6}
              onChange={(e) => {
                setCode6(e.target.value.replace(/\D/g, ''));
                clearSelection();
              }}
            />
          </label>
          {selected && (
            <p className="muted">
              Armed with <strong>{selected.visit.id}</strong> · backup code{' '}
              <code>{selected.code6}</code>{' '}
              <button type="button" className="link-button" onClick={clearSelection}>
                clear
              </button>
            </p>
          )}
        </div>
      </section>

      <section className="panel">
        <h3>2 · What is actually at the gate</h3>
        <form onSubmit={submit} className="gate-form">
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

          <button type="submit" className="primary scan-button" disabled={busy || !armed}>
            {busy ? 'Scanning…' : 'Scan in'}
          </button>
        </form>
        <p className="field-hint">
          A mismatched plate or headcount still admits — it is recorded, not blocked.
        </p>
      </section>

      <ErrorBanner error={error} onDismiss={() => setError(null)} />

      {result && (
        <section className="panel">
          <ScanResultPanel result={result} />
          <button type="button" onClick={() => setResult(null)}>
            Scan another
          </button>
        </section>
      )}
    </div>
  );
}
