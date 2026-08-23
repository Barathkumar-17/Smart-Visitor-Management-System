import { post } from './client';

/**
 * Scan bodies take `payload` and `signature` as two separate top-level fields.
 * Posting the whole `qr` object that /passes/{id} returns is a 400, and it is
 * the single most common mistake against this API — so the destructuring lives
 * here and no screen ever handles it.
 */
function credentials({ qr, code6 }) {
  if (qr) return { payload: qr.payload, signature: qr.signature };
  return { code6 };
}

// Empty strings are dropped rather than sent as "", which would read as a
// presented-but-blank vehicle plate.
function omitEmpty(body) {
  return Object.fromEntries(
    Object.entries(body).filter(([, v]) => v !== '' && v !== undefined && v !== null),
  );
}

export function gateEntry({ qr, code6, vehicle_plate, person_count_in }) {
  return post(
    '/scans/gate/entry',
    omitEmpty({ ...credentials({ qr, code6 }), vehicle_plate, person_count_in }),
  );
}
