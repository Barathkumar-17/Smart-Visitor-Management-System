import PhotoCard from './PhotoCard';
import VerdictBanner from './VerdictBanner';

function Comparison({ label, expected, presented, mismatch, presentedLabel = 'presented' }) {
  if (expected == null && presented == null) return null;
  return (
    <div className={`comparison${mismatch ? ' comparison-mismatch' : ''}`}>
      <span className="comparison-label">{label}</span>
      <span className="comparison-values">
        <span>
          <em>expected</em> {expected ?? '—'}
        </span>
        <span aria-hidden="true" className="comparison-arrow">
          →
        </span>
        <span>
          <em>{presentedLabel}</em> {presented ?? '—'}
        </span>
      </span>
      {mismatch && <span className="comparison-flag">does not match — recorded, not blocked</span>}
    </div>
  );
}

function Row({ term, children }) {
  if (!children) return null;
  return (
    <>
      <dt>{term}</dt>
      <dd>{children}</dd>
    </>
  );
}

/**
 * Takes any of the three scan responses. One component, three screens.
 *
 * A refusal still returns 200 but blanks nearly everything — people is [] and
 * the vehicle, headcount and identity fields are all null — so every section
 * below is guarded rather than assumed.
 */
export default function ScanResultPanel({ result }) {
  if (!result) return null;

  const people = result.people ?? [];
  const hasDetail =
    result.visitor_name || result.host_name || result.meeting_zone || result.scanned_zone;

  return (
    <section className="scan-result">
      <VerdictBanner result={result} />

      {people.length > 0 && (
        <div className="photo-strip">
          {people.slice(0, 5).map((person, index) => (
            <PhotoCard key={`${person.photo_ref || person.name}-${index}`} person={person} />
          ))}
        </div>
      )}

      {hasDetail && (
        <dl className="detail-grid">
          <Row term="Visitor">{result.visitor_name}</Row>
          <Row term="Host">{result.host_name}</Row>
          <Row term="Scanned at">{result.scanned_zone}</Row>
          <Row term="Meeting at">{result.meeting_zone}</Row>
          <Row term="Purpose">{result.purpose}</Row>
          <Row term="Cleared for">
            {result.allowed_zones?.length ? result.allowed_zones.join(', ') : null}
          </Row>
          <Row term="Call host">
            {result.host_phone ? (
              <a className="phone-link" href={`tel:${result.host_phone}`}>
                {result.host_phone}
              </a>
            ) : null}
          </Row>
        </dl>
      )}

      {(result.vehicle || result.headcount) && (
        <div className="comparisons">
          <Comparison
            label="Vehicle"
            expected={result.vehicle?.expected}
            presented={result.vehicle?.presented}
            mismatch={result.vehicle?.mismatch}
          />
          <Comparison
            label="People"
            expected={result.headcount?.expected}
            presented={result.headcount?.recorded}
            mismatch={result.headcount?.mismatch}
            presentedLabel={'exited' in result ? 'signed out' : 'presented'}
          />
        </div>
      )}

      {result.partial_exit && (
        <p className="still-inside">
          {result.still_inside} still inside — the visit stays open.
        </p>
      )}

      {result.restricted && <p className="restricted-flag">Restricted visit</p>}

      {people.length === 0 && !hasDetail && (
        <p className="muted">No visit is attached to this code, so there is nobody to show.</p>
      )}
    </section>
  );
}
