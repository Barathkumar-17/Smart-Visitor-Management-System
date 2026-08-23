/**
 * The green / amber / red rule lives here and nowhere else.
 *
 * Amber is the important one. Neither a vehicle nor a headcount mismatch blocks
 * entry, and a wrong-zone scan inside campus is recorded rather than refused —
 * a red screen would contradict what the system actually did.
 *
 * The three scan responses are told apart by which decision key they carry:
 * `admitted` for the gate, `ok` for a checkpoint, `exited` for the way out.
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

function kindOf(result) {
  if ('admitted' in result) return 'entry';
  if ('exited' in result) return 'exit';
  if ('ok' in result) return 'zone';
  return 'entry';
}

export function verdictFor(result) {
  if (!result) return null;

  const kind = kindOf(result);
  const decided = result.admitted ?? result.exited ?? result.ok ?? false;
  const mismatch = Boolean(result.vehicle?.mismatch || result.headcount?.mismatch);

  // A checkpoint never refuses anyone. Inside campus the system observes.
  if (kind === 'zone') {
    return result.result === 'wrong_zone'
      ? { tone: 'amber', headline: 'Recorded — security notified' }
      : { tone: 'green', headline: 'Expected here' };
  }

  if (kind === 'exit') {
    if (result.partial_exit) {
      const left = result.still_inside;
      return {
        tone: 'amber',
        headline: left ? `Partial exit — ${left} still inside` : 'Partial exit',
      };
    }
    if (!decided) return { tone: 'red', headline: 'Not signed out' };
    if (mismatch) return { tone: 'amber', headline: 'Signed out — mismatch recorded' };
    return { tone: 'green', headline: 'Signed out' };
  }

  if (!decided) return { tone: 'red', headline: 'Not admitted' };
  if (mismatch) return { tone: 'amber', headline: 'Admitted — mismatch recorded' };
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
