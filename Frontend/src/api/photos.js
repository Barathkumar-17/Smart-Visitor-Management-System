import { get } from './client';

/**
 * GET /photos/{ref} returns {ref, photo_b64} as JSON and needs the bearer
 * token, so a plain <img src="/api/photos/…"> fails twice over. Fetch it and
 * hand back a data URL instead.
 *
 * Refs are stable across /dev/reset, so the in-flight promise is cached and the
 * same face is never fetched twice — entry and exit show the same people.
 */
const cache = new Map();

export function getPhotoDataUrl(ref) {
  if (!ref) return Promise.resolve(null);
  if (cache.has(ref)) return cache.get(ref);

  const pending = get(`/photos/${ref}`)
    .then((res) => (res?.photo_b64 ? `data:image/png;base64,${res.photo_b64}` : null))
    .catch(() => {
      cache.delete(ref); // a failure is worth retrying; a missing photo is not
      return null;
    });

  cache.set(ref, pending);
  return pending;
}
