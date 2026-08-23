/**
 * The green / amber / red rule lives here and nowhere else.
 *
 * Amber is the important one. Neither a vehicle nor a headcount mismatch blocks
 * entry, and a wrong-zone scan inside campus is recorded rather than refused —
 * a red screen would contradict what the system actually did.
 */

const RESULT_WORDS = {
  ok: 'Scan accepted',
  bad_signature: 'Signature did not verify — forged, altered, or superseded',
  wrong_status: 'This visit is not in a state where the scan makes sense',
  revoked: 'This pass has been revoked',
  expired: 'Outside the pass window',
  already_inside: 'This visitor is already inside on another visit',
  wrong_zone: 'Not cleared for this checkpoint',
};

export function verdictFor(result) {
  if (!result) return null;

  const decided = result.admitted ?? result.ok ?? result.exited ?? false;
  const mismatch = Boolean(result.vehicle?.mismatch || result.headcount?.mismatch);

  // Inside campus the system observes and never blocks.
  if (result.result === 'wrong_zone') {
    return { tone: 'amber', headline: 'Recorded — security notified' };
  }
  if (result.partial_exit) {
    return { tone: 'amber', headline: 'Partial exit — some people still inside' };
  }
  if (!decided) {
    return { tone: 'red', headline: 'Not admitted' };
  }
  if (mismatch) {
    return { tone: 'amber', headline: 'Admitted — mismatch recorded' };
  }
  return { tone: 'green', headline: 'Admitted' };
}

export default function VerdictBanner({ result }) {
  const verdict = verdictFor(result);
  if (!verdict) return null;

  const reason = result.message || RESULT_WORDS[result.result] || null;

  return (
    <div className={`verdict verdict-${verdict.tone}`} role="status">
      <strong className="verdict-headline">{verdict.headline}</strong>
      {reason && <span className="verdict-reason">{reason}</span>}
    </div>
  );
}
