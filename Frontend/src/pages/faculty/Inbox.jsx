import { useCallback, useEffect, useState } from 'react';
import { listVisits, approveVisit, rejectVisit } from '../../api/visits';
import { getVisitor } from '../../api/visitors';
import { getZones, getHosts } from '../../api/reference';
import { ZoneSelect, ZoneMultiSelect } from '../../components/ZoneSelect';
import ErrorBanner from '../../components/ErrorBanner';
import { toApiDateTime, formatStamp } from '../../lib/datetime';

// How long an approved pass lasts.
//
// The host is not asked for this. They already chose a time when the visit was
// requested, and making them retype it as two datetime pickers was work with no
// decision in it - every approval used the defaults anyway.
//
// The window opens now (a visitor who turns up early should not be refused) or
// at the scheduled time if that is earlier, and closes VISIT_HOURS after
// whichever of the two is later. That guarantees the window always contains the
// scheduled time and can never end before it starts, which the backend rejects.
const VISIT_HOURS = 4;

function windowFor(visit) {
  const now = new Date();
  const scheduled = visit?.scheduled_at ? new Date(visit.scheduled_at) : now;
  const valid = Number.isNaN(scheduled.getTime()) ? now : scheduled;
  const from = valid < now ? valid : now;
  const anchor = valid > now ? valid : now;
  return { from, to: new Date(anchor.getTime() + VISIT_HOURS * 3600 * 1000) };
}

/**
 * Inbox and approval.
 *
 * The list endpoint returns visitor_id but no visitor name or tier, so each row
 * is enriched with a second fetch. The tier is what decides whether the vouch
 * checkbox appears at all — vouching is the flowchart's "or host vouch" path
 * and only means anything for a visitor who is not already verified.
 */
export default function Inbox() {
  const [rows, setRows] = useState([]);
  const [zones, setZones] = useState([]);
  const [hosts, setHosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [openId, setOpenId] = useState(null);
  const [meetingZone, setMeetingZone] = useState('');
  const [allowedZones, setAllowedZones] = useState([]);
  const [vouch, setVouch] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const visits = await listVisits({ status: 'requested' });
      const enriched = await Promise.all(
        visits.map(async (v) => ({
          ...v,
          visitor: await getVisitor(v.visitor_id).catch(() => null),
        })),
      );
      setRows(enriched);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    getZones().then(setZones).catch(setError);
    getHosts().then(setHosts).catch(() => {});
  }, [load]);

  function openForm(row) {
    setOpenId(row.id);
    setOutcome(null);
    setError(null);
    setMeetingZone('');
    setAllowedZones([]);
    setVouch(false);
    setRejectReason('');
  }

  async function approve(row) {
    setBusy(true);
    setError(null);
    try {
      const { from, to } = windowFor(row);
      // Every datetime carries a UTC offset. A naive value is a 422.
      const visit = await approveVisit(row.id, {
        meeting_zone_id: meetingZone,
        allowed_zones: allowedZones,
        valid_from: toApiDateTime(from),
        valid_to: toApiDateTime(to),
        vouch,
      });
      setOutcome({ kind: 'approved', visit, name: row.visitor?.name });
      setOpenId(null);
      load();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function reject(row) {
    setBusy(true);
    setError(null);
    try {
      const visit = await rejectVisit(row.id, rejectReason.trim());
      setOutcome({ kind: 'rejected', visit, name: row.visitor?.name });
      setOpenId(null);
      load();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const hostName = (id) => hosts.find((h) => h.id === id)?.name ?? id;

  if (outcome) {
    const approved = outcome.kind === 'approved';
    return (
      <>
        <section className="panel">
          <div className={`verdict verdict-${approved ? 'green' : 'red'}`} role="status">
            <strong className="verdict-headline">{approved ? 'Pass issued' : 'Request rejected'}</strong>
            <span className="verdict-reason">
              {approved
                ? `${outcome.name ?? 'The visitor'} can now be admitted. The QR exists immediately.`
                : `${outcome.name ?? 'The visitor'} was turned down: ${outcome.visit.approval_reason}`}
            </span>
          </div>
          {approved && (
            <dl className="detail-grid">
              <dt>Visit</dt>
              <dd>{outcome.visit.id}</dd>
              <dt>Status</dt>
              <dd>{outcome.visit.status}</dd>
              <dt>Valid</dt>
              <dd>
                {formatStamp(outcome.visit.valid_from)} to {formatStamp(outcome.visit.valid_to)}
              </dd>
            </dl>
          )}
        </section>
        <button type="button" className="primary next-button" onClick={() => setOutcome(null)}>
          Back to inbox
        </button>
      </>
    );
  }

  return (
    <>
      <h2 className="step-question">Requests waiting</h2>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />

      {loading && <p className="muted">Loading…</p>}
      {!loading && rows.length === 0 && (
        <section className="panel">
          <p className="muted">Nothing is waiting for approval.</p>
        </section>
      )}

      {rows.map((row) => {
        const open = openId === row.id;
        const alreadyVerified = row.visitor?.tier === 'verified';
        return (
          <section className="panel" key={row.id}>
            <div className="request-head">
              <div>
                <h3 className="request-name">
                  {row.visitor?.name ?? row.visitor_id}{' '}
                  {row.visitor?.tier && (
                    <span className={`tier tier-${row.visitor.tier}`}>{row.visitor.tier}</span>
                  )}
                </h3>
                <p className="muted">{row.purpose}</p>
              </div>
              {!open && (
                <button type="button" onClick={() => openForm(row)}>
                  Review
                </button>
              )}
            </div>

            <dl className="detail-grid">
              <dt>Host</dt>
              <dd>{hostName(row.host_id)}</dd>
              <dt>Scheduled</dt>
              <dd>{formatStamp(row.scheduled_at)}</dd>
              <dt>People</dt>
              <dd>{row.person_count_expected ?? 1}</dd>
              <dt>Vehicle</dt>
              <dd>{row.vehicle_plate_in ?? 'none'}</dd>
            </dl>

            {open && (
              <div className="approval-form">
                <label className="field" htmlFor={`mz-${row.id}`}>
                  <span className="field-label">Meeting zone</span>
                  <ZoneSelect
                    id={`mz-${row.id}`}
                    zones={zones}
                    value={meetingZone}
                    onChange={setMeetingZone}
                  />
                </label>

                <div className="field">
                  <span className="field-label">Allowed zones</span>
                  <ZoneMultiSelect zones={zones} value={allowedZones} onChange={setAllowedZones} />
                </div>

                <div className="field">
                  <span className="field-label">Pass valid</span>
                  <p className="computed-window">
                    {formatStamp(windowFor(row).from)} &rarr; {formatStamp(windowFor(row).to)}
                    <span className="field-hint">
                      {VISIT_HOURS} hours around the requested time. Set automatically.
                    </span>
                  </p>
                </div>

                {alreadyVerified ? (
                  <p className="field-hint">
                    This visitor is already verified, so there is nothing to vouch for.
                  </p>
                ) : (
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={vouch}
                      onChange={(e) => setVouch(e.target.checked)}
                    />
                    <span>
                      I vouch for this visitor
                      <span className="field-hint">
                        Stands in for government ID — the &ldquo;or host vouch&rdquo; path.
                      </span>
                    </span>
                  </label>
                )}

                <div className="decision-row">
                  <button
                    type="button"
                    className="decision decision-approve"
                    disabled={busy || !meetingZone || allowedZones.length === 0}
                    onClick={() => approve(row)}
                  >
                    {busy ? 'Approving…' : 'Approve and issue the pass'}
                  </button>
                </div>

                <div className="reject-row">
                  <label className="field" htmlFor={`rr-${row.id}`}>
                    <span className="field-label">Reason for rejecting</span>
                    <input
                      id={`rr-${row.id}`}
                      value={rejectReason}
                      placeholder="Required"
                      onChange={(e) => setRejectReason(e.target.value)}
                    />
                  </label>
                  <button
                    type="button"
                    className="decision decision-refuse"
                    disabled={busy || rejectReason.trim().length === 0}
                    onClick={() => reject(row)}
                  >
                    Reject
                  </button>
                </div>

                <button type="button" className="link-button" onClick={() => setOpenId(null)}>
                  Cancel
                </button>
              </div>
            )}
          </section>
        );
      })}
    </>
  );
}
