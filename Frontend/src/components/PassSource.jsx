import { useCallback, useEffect, useState } from 'react';
import { getVisit } from '../api/visits';
import { getVisitor } from '../api/visitors';
import { getPass } from '../api/passes';
import ErrorBanner from './ErrorBanner';

// /dev/reset hands back identical ids every time. GET /visits (the list) is
// faculty-only and 403s a guard, so each one is fetched individually.
const SEEDED_VISIT_IDS = ['v_1', 'v_2', 'v_3', 'v_4', 'v_5', 'v_6'];

/**
 * Step 1 of every scan screen: choose which pass is being presented.
 *
 * Reading a pass writes nothing on the server, so a screen can show the guard
 * who they are about to deal with before anything is recorded.
 *
 * `onArmed` receives {visit, visitor, qr, code6, people} from the picker, or
 * {code6} alone from the manual box — nothing resolves a six-digit code to a
 * visit, so that path cannot be previewed.
 */
export default function PassSource({
  statuses,
  onArmed,
  refreshKey = 0,
  hint = null,
  children = null,
}) {
  const [visits, setVisits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [code6, setCode6] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    const rows = await Promise.all(SEEDED_VISIT_IDS.map((id) => getVisit(id).catch(() => null)));
    setVisits(rows.filter(Boolean));
    setLoading(false);
  }, []);

  // Statuses change underneath this screen — an entry flips a visit from
  // issued to inside — so the list is re-read whenever the parent says so.
  useEffect(() => {
    load();
  }, [load, refreshKey]);

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
      onArmed({ visit, visitor, qr: pass.qr, code6: pass.code6, people });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="panel">
        {loading ? <p className="muted">Loading...</p> : null}
        <div className="visit-picker">
          {visits.map((visit) => {
            const actionable = statuses.includes(visit.status);
            return (
              <button
                key={visit.id}
                type="button"
                className="visit-chip"
                disabled={!actionable || busy}
                title={actionable ? undefined : `Status is ${visit.status}`}
                onClick={() => readPass(visit)}
              >
                <span className="visit-id">{visit.id}</span>
                <span className={`status-badge status-${visit.status}`}>{visit.status}</span>
                <span className="visit-purpose">{visit.purpose}</span>
              </button>
            );
          })}
        </div>
        {visits.length > 0 && !visits.some((v) => statuses.includes(v.status)) && (
          <p className="muted">
            No visit is in a state this screen can act on. It needs one of: {statuses.join(', ')}.
          </p>
        )}
      </section>

      <section className="panel">
        <h3>Backup code</h3>
        <div className="gate-form">
          <label className="field" htmlFor="ps-code6">
            <span className="field-label">6-digit code</span>
            <input
              id="ps-code6"
              inputMode="numeric"
              maxLength={6}
              placeholder="000000"
              value={code6}
              onChange={(e) => setCode6(e.target.value.replace(/\D/g, ''))}
            />
          </label>
          {children}
          <button
            type="button"
            disabled={busy || code6.trim().length === 0}
            onClick={() => onArmed({ code6: code6.trim() })}
          >
            Use code
          </button>
        </div>
        <p className="field-hint">
          {hint ??
            'Nothing resolves a backup code to a visit, so this path cannot show you anyone first.'}
        </p>
      </section>

      <ErrorBanner error={error} onDismiss={() => setError(null)} />
    </>
  );
}
