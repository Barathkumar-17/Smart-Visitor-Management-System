import { fileToBase64 } from '../lib/fileToBase64';

/**
 * One control with two modes, not two fields.
 *
 * Sending both `companions[]` and `person_count` is a 400, so the mode switch
 * is what guarantees only one of them is ever built. `person_count` is the
 * total INCLUDING the visitor — one visitor plus four companions is 5.
 */
const MAX_COMPANIONS = 4;

export default function PeopleInput({ mode, onModeChange, companions, onCompanions, count, onCount, onError }) {
  async function setPhoto(index, file) {
    try {
      const photo_b64 = await fileToBase64(file);
      onCompanions(companions.map((c, i) => (i === index ? { ...c, photo_b64 } : c)));
    } catch (err) {
      onError?.(err);
    }
  }

  return (
    <div className="people-input">
      <div className="mode-row">
        <button
          type="button"
          className={mode === 'named' ? 'selected' : ''}
          onClick={() => onModeChange('named')}
        >
          Named companions
        </button>
        <button
          type="button"
          className={mode === 'count' ? 'selected' : ''}
          onClick={() => onModeChange('count')}
        >
          Just a number
        </button>
      </div>

      {mode === 'named' ? (
        <>
          {companions.map((companion, index) => (
            <div className="companion-row" key={index}>
              <label className="field">
                <span className="field-label">Companion {index + 1}</span>
                <input
                  value={companion.name}
                  placeholder="Full name"
                  onChange={(e) =>
                    onCompanions(
                      companions.map((c, i) => (i === index ? { ...c, name: e.target.value } : c)),
                    )
                  }
                />
              </label>
              <label className="field">
                <span className="field-label">Photo</span>
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => setPhoto(index, e.target.files?.[0])}
                />
              </label>
              <button
                type="button"
                className="link-button"
                onClick={() => onCompanions(companions.filter((_, i) => i !== index))}
              >
                remove
              </button>
            </div>
          ))}
          {companions.length < MAX_COMPANIONS && (
            <button type="button" onClick={() => onCompanions([...companions, { name: '' }])}>
              Add a companion
            </button>
          )}
          <p className="field-hint">
            Up to {MAX_COMPANIONS} named companions. Beyond that, switch to a number.
          </p>
        </>
      ) : (
        <>
          <label className="field" htmlFor="person-count">
            <span className="field-label">Total people</span>
            <input
              id="person-count"
              inputMode="numeric"
              value={count}
              onChange={(e) => onCount(e.target.value.replace(/\D/g, ''))}
            />
          </label>
          <p className="field-hint">
            Including the visitor. One visitor plus four companions is 5.
          </p>
        </>
      )}
    </div>
  );
}
