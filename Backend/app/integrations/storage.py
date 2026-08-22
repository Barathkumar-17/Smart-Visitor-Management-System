"""Photo storage stub, base64 in / ref out. SPEC sections 5 and 16.5.

Signature correct, implementation fake: the base64 stays in a module-level dict
in RAM and a fake ref comes back. Swapping in S3 or a filesystem later replaces
the two functions and nothing else, because ENTITIES HOLD THE REF ONLY and
nothing else in the codebase holds base64.

The 2 MB cap is not optional. The store is a dict in RAM, so an uncapped field
turns a demo into an out-of-memory crash.
"""

import base64
import binascii
import logging

from app.core.config import MAX_PHOTO_BYTES
from app.core.errors import InvalidRequest, NotFound
from app.store import ids

log = logging.getLogger(__name__)

# ref -> base64 string. Deliberately NOT in store/memory.py: SPEC section 5
# lists the store collections and photos are not among them. Cleared by
# /dev/reset through clear().
_photos: dict[str, str] = {}


def put(photo_b64: str) -> str:
    """Store a base64 photo and return its ref, of the form "photo_{n}".

    Raises InvalidRequest (400) when the string is not valid base64 or decodes
    to more than MAX_PHOTO_BYTES. The size is checked on the DECODED bytes,
    which is what actually occupies memory - base64 inflates by about a third,
    so capping the encoded string would cap the wrong number.
    """
    try:
        raw = base64.b64decode(photo_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InvalidRequest(
            "photo_b64 is not valid base64", {"error": str(exc)}
        ) from exc

    if len(raw) > MAX_PHOTO_BYTES:
        raise InvalidRequest(
            f"Photo is {len(raw)} bytes decoded, over the "
            f"{MAX_PHOTO_BYTES} byte limit",
            {"decoded_bytes": len(raw), "limit_bytes": MAX_PHOTO_BYTES},
        )

    ref = ids.next_id("photo")
    _photos[ref] = photo_b64
    log.info("stored photo %s (%d bytes decoded)", ref, len(raw))
    return ref


def get(ref: str) -> str:
    """Return the base64 for a ref, or raise NotFound (404)."""
    photo = _photos.get(ref)
    if photo is None:
        raise NotFound(f"Photo {ref} not found", {"ref": ref})
    return photo


def exists(ref: str) -> bool:
    return ref in _photos


def count() -> int:
    return len(_photos)


def clear() -> None:
    """Drop every stored photo. Called by the seed loader's reset(), so refs do
    not leak across a /dev/reset and dangle."""
    _photos.clear()
