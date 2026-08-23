/**
 * Both of these deal in zone IDS (z_2), which is what approval and arrival-ack
 * send. The checkpoint screen picks zone CODES (LIB) instead. Mixing the two is
 * a silent wrong-zone result rather than an error, so they stay separate
 * components with separate names.
 */

export function ZoneSelect({ zones, value, onChange, id }) {
  return (
    <select id={id} value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
      <option value="">Choose a zone…</option>
      {zones.map((zone) => (
        <option key={zone.id} value={zone.id}>
          {zone.code} — {zone.name}
        </option>
      ))}
    </select>
  );
}

export function ZoneMultiSelect({ zones, value = [], onChange }) {
  function toggle(id) {
    onChange(value.includes(id) ? value.filter((z) => z !== id) : [...value, id]);
  }

  return (
    <div className="zone-multi">
      {zones.map((zone) => {
        const checked = value.includes(zone.id);
        return (
          <label key={zone.id} className={`zone-check${checked ? ' checked' : ''}`}>
            <input type="checkbox" checked={checked} onChange={() => toggle(zone.id)} />
            <span className="zone-code">{zone.code}</span>
            <span className="zone-name">{zone.name}</span>
          </label>
        );
      })}
    </div>
  );
}
