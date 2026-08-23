import PhotoCard from './PhotoCard';
import VerdictBanner from './VerdictBanner';

function Comparison({ label, expected, presented, mismatch }) {
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
          <em>presented</em> {presented ?? '—'}
        </span>
      </span>
      {mismatch && <span className="comparison-flag">mismatch — recorded, not blocked</span>}
    </div>
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
  const hasDetail = result.visitor_name || result.host_name || result.meeting_zone;

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
          {result.visitor_name && (
            <>
              <dt>Visitor</dt>
              <dd>{result.visitor_name}</dd>
            </>
          )}
          {result.host_name && (
            <>
              <dt>Host</dt>
              <dd>{result.host_name}</dd>
            </>
          )}
          {result.meeting_zone && (
            <>
              <dt>Meeting at</dt>
              <dd>{result.meeting_zone}</dd>
            </>
          )}
          {result.purpose && (
            <>
              <dt>Purpose</dt>
              <dd>{result.purpose}</dd>
            </>
          )}
          {result.host_phone && (
            <>
              <dt>Call host</dt>
              <dd>
                <a className="phone-link" href={`tel:${result.host_phone}`}>
                  {result.host_phone}
                </a>
              </dd>
            </>
          )}
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
          />
        </div>
      )}

      {result.restricted && <p className="restricted-flag">Restricted visit</p>}

      {people.length === 0 && !hasDetail && (
        <p className="muted">No visit is attached to this code, so there is nobody to show.</p>
      )}
    </section>
  );
}
