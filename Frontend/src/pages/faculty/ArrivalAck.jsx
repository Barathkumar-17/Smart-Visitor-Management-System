import { useCallback, useEffect, useState } from 'react';
import { getVisit, arrivalAck } from '../../api/visits';
import { getVisitor } from '../../api/visitors';
import { getZones } from '../../api/reference';
import { ZoneMultiSelect } from '../../components/ZoneSelect';
import ErrorBanner from '../../components/ErrorBanner';
import { toApiDateTime, localInputValue, formatStamp } from '../../lib/datetime';

const SEEDED_VISIT_IDS = ['v_1', 'v_2', 'v_3', 'v_4', 'v_5', 'v_6'];

/**
 * The host confirming they are free, on a visit that is already inside.
 *
 * The body is conditional. A restricted visit needs allowed_zones and valid_to
 * — it was admitted to the meeting point only, so there are no host-set zones
 * to restore — and submit stays disabled until both are set. An ordinary inside
 * visit takes an empty body.
 *
 * A visit that is not inside is a 400, which is a state to explain rather than
 * an error to crash on.
 */
export default function ArrivalAck() {
  const [visits, setVisits] = useState([]);
  const [zones, setZones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [allowedZones, setAllowedZones] = useState([]);
  const [validTo, setValidTo] = useState(localInputValue(240));
  const [done, setDone] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const rows = await Promise.all(SEEDED_VISIT_IDS.map((id) => getVisit(id).catch(() => null)));
    const enriched = await Promise.all(
      rows.filter(Boolean).map(async (v) => ({
        ...v,
        visitor: await getVisitor(v.visitor_id).catch(() => null),
      })),
    );
    setVisits(enriched);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    getZones().then(setZones).catch(setError);
  }, [load]);

  function select(visit) {
    setSelected(visit);
    setDone(null);
    setError(null);
    setAllowedZones(visit.allowed_zones ?? []);
    setValidTo(localInputValue(240));
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const body = selected.restricted
        ? { allowed_zones: allowedZones, valid_to: toApiDateTime(validTo) }
        : {};
      const visit = await arrivalAck(selected.id, body);
      setDone(visit);
      setSelected(null);
      load();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  // Submit stays disabled until a restricted visit has both fields.
  const blocked =
    selected?.restricted && (allowedZones.length === 0 || !validTo);

  if (done) {
    return (
      <>
        <section className="panel">
          <div className="verdict verdict-green" role="status">
            <strong className="verdict-headline">Arrival acknowledged</strong>
            <span className="verdict-reason">
              {done.id} — the host confirmed at {formatStamp(done.host_acked_at)}.
            </span>
          </div>
        </section>
        <button type="button" className="primary next-button" onClick={() => setDone(null)}>
          Back
        </button>
      </>
    );
  }

  return (
    <>
      <h2 className="step-question">Confirm you are free</h2>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />

      {loading && <p className="muted">Loading…</p>}

      <section className="panel">
        <h3>Visitors currently inside</h3>
        <div className="visit-picker">
          {visits.map((visit) => {
            const actionable = visit.status === 'inside';
            return (
              <button
                key={visit.id}
                type="button"
                className={`visit-chip${selected?.id === visit.id ? ' selected' : ''}`}
                disabled={!actionable}
                title={actionable ? undefined : `Status is ${visit.status}`}
                onClick={() => select(visit)}
              >
                <span className="visit-id">{visit.id}</span>
                <span className={`status-badge status-${visit.status}`}>{visit.status}</span>
                {visit.restricted && <span className="status-badge status-restricted">restricted</span>}
                {visit.host_acked_at && <span className="status-badge">acked</span>}
                <span className="visit-purpose">
                  {visit.visitor?.name ?? visit.visitor_id} — {visit.purpose}
                </span>
              </button>
            );
          })}
        </div>
        {!loading && !visits.some((v) => v.status === 'inside') && (
          <p className="muted">Nobody is inside right now.</p>
        )}
      </section>

      {selected && (
        <section className="panel">
          <h3>
            {selected.visitor?.name ?? selected.visitor_id} — {selected.id}
          </h3>

          {selected.restricted ? (
            <>
              <p className="restricted-flag">
                This is a restricted visit. It was admitted to the meeting point only, so you must
                set the zones and the window before acknowledging.
              </p>

              <div className="field">
                <span className="field-label">Allowed zones</span>
                <ZoneMultiSelect zones={zones} value={allowedZones} onChange={setAllowedZones} />
              </div>

              <label className="field" htmlFor="ack-valid-to">
                <span className="field-label">Valid until</span>
                <input
                  id="ack-valid-to"
                  type="datetime-local"
                  value={validTo}
                  onChange={(e) => setValidTo(e.target.value)}
                />
              </label>
            </>
          ) : (
            <p className="muted">
              This visit is not restricted, so acknowledging it sends an empty body — there is
              nothing to fill in.
            </p>
          )}

          <div className="decision-row">
            <button
              type="button"
              className="decision decision-approve"
              disabled={busy || blocked}
              onClick={submit}
            >
              {busy ? 'Acknowledging…' : 'Acknowledge arrival'}
            </button>
          </div>
          {blocked && (
            <p className="field-hint">Set at least one zone and a valid-until time to continue.</p>
          )}
        </section>
      )}
    </>
  );
}
