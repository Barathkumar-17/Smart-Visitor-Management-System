"""sign_pass / verify_pass. SPEC section 9.

THE PAYLOAD CARRIES ONLY visit_id AND nonce. Never visitor data, never the zone
list, and never the time window. Both of the latter are read fresh from the
visit record at every scan, and that is not an optimisation - it is what makes
two later endpoints possible at all:

  - PATCH /visits/{id}/meeting-point changes the zones
  - POST  /visits/{id}/arrival-ack   changes valid_to

A payload carrying either would be invalidated by those calls and force a
reissue, so a visitor whose host moved the meeting would need a new QR. The QR
is a POINTER to a record, not a copy of one.

Offline verification is unaffected: a gate tablet caches the pass record
alongside the key, verifies the signature locally, and reads the window and
zones from its cached copy.
"""

import hashlib
import hmac
import json
import logging
import secrets

from app.core.config import HMAC_SECRET

log = logging.getLogger(__name__)

NONCE_BYTES = 16


def _canonical(payload: dict) -> bytes:
    """Serialise a payload to the exact bytes that get signed.

    BOTH sign_pass AND verify_pass build their string through this ONE helper,
    which is the whole reason it exists. If the two sides serialised
    independently - different key order, a different separator, a stray space -
    every signature would fail to verify and the failure would look like a
    tampered pass rather than a bug. SPEC section 9 calls this out explicitly.

    sort_keys makes key order irrelevant to the caller; the separators argument
    removes the whitespace json.dumps would otherwise insert.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def new_nonce() -> str:
    """A fresh random nonce, so two passes for the same visit never sign identically."""
    return secrets.token_hex(NONCE_BYTES)


def sign_payload(payload: dict) -> str:
    """HMAC-SHA256 of the canonical payload, as hex."""
    return hmac.new(
        HMAC_SECRET.encode("utf-8"), _canonical(payload), hashlib.sha256
    ).hexdigest()


def sign_pass(visit_id: str, nonce: str) -> tuple[dict, str]:
    """Build the QR payload for a visit and sign it.

    Returns (payload, signature). The payload is what goes in the QR alongside
    the signature; together they are the whole of what a scanner transmits.
    """
    payload = {"visit_id": visit_id, "nonce": nonce}
    return payload, sign_payload(payload)


def verify_pass(payload: dict, signature: str) -> bool:
    """True when the signature matches the payload under this system's key.

    Uses hmac.compare_digest, NEVER ==. A plain equality check on a hex string
    returns as soon as two characters differ, so the time it takes leaks how
    much of a guessed signature was correct - enough to forge one byte at a
    time. compare_digest takes the same time whatever the input.
    """
    if not isinstance(payload, dict) or not isinstance(signature, str):
        return False

    expected = sign_payload(payload)
    ok = hmac.compare_digest(expected, signature)
    if not ok:
        log.warning(
            "signature mismatch for payload %s", payload.get("visit_id", "<no visit_id>")
        )
    return ok
