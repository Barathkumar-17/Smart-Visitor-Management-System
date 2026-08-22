"""DigiLocker consent stub.

Signature correct, implementation fake: returns a plausible ID hash and last-4
without contacting anything. Real deployment replaces the body with the consent
flow and keeps the return shape.

The hash is derived from the phone so a given visitor gets a stable value
across a demo - a random one would change on every call and make the audit
trail look wrong.
"""

import hashlib
import logging

log = logging.getLogger(__name__)


def fetch_identity(phone: str) -> dict[str, str]:
    """Return the identity fields DigiLocker would supply.

    id_hash NEVER leaves the backend in an API response - the design
    forbids it, and the visitor schema simply has no field for it. id_last4 is
    the part a guard may see.
    """
    digest = hashlib.sha256(f"digilocker:{phone}".encode()).hexdigest()
    # A real last-4 comes off the document; deriving it from the digest keeps
    # it stable per person without inventing a document number.
    last4 = f"{int(digest[:8], 16) % 10000:04d}"
    log.info("DigiLocker consent granted for %s (stub), last4 %s", phone, last4)
    return {"id_hash": f"sha256:{digest}", "id_last4": last4}
