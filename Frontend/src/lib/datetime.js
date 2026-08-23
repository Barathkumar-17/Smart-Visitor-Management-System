/**
 * The backend rejects a naive timestamp with a 422 — it requires a UTC offset,
 * e.g. 2026-08-23T14:30:00+05:30. <input type="datetime-local"> produces
 * exactly the naive form, so every datetime field goes through here.
 */
function pad(n) {
  return String(n).padStart(2, '0');
}

export function toApiDateTime(local) {
  if (!local) return null;
  const date = local instanceof Date ? local : new Date(local);
  if (Number.isNaN(date.getTime())) return null;

  // getTimezoneOffset is minutes *behind* UTC, so the sign is inverted.
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? '+' : '-';
  const abs = Math.abs(offset);

  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}` +
    `${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
  );
}

/** Value for an <input type="datetime-local">, offset from now by minutes. */
export function localInputValue(offsetMinutes = 0) {
  const d = new Date(Date.now() + offsetMinutes * 60000);
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

export function formatStamp(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}
