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

// zone_code is the CODE (LIB), never the id (z_2). Mixing them is a silent
// wrong-zone result rather than an error.
export function zoneScan({ qr, code6, zone_code }) {
  return post('/scans/zone', omitEmpty({ ...credentials({ qr, code6 }), zone_code }));
}

export function gateExit({ qr, code6, vehicle_plate_out, person_count_out }) {
  return post(
    '/scans/gate/exit',
    omitEmpty({ ...credentials({ qr, code6 }), vehicle_plate_out, person_count_out }),
  );
}
