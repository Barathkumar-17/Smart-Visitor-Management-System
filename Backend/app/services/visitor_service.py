"""Registration and verification rules.

Every rule in the design lives here. Two of them are easy to get subtly wrong
and are worth stating up front:

  - EXPIRY IS DERIVED, NOT A JOB. Nothing in this file ever writes a visitor
    back to `temporary`. A vouched visitor is verified while verified_until is
    in the future and temporary after, computed on every read by the `tier`
    property on the entity.

  - DIGILOCKER OVERRIDES A VOUCH AT ANY POINT, and the reverse never happens -
    vouching someone already permanently verified is a no-op.
"""

import logging
from datetime import timedelta

from app.core import clock
from app.core.config import VOUCH_VALIDITY_DAYS
from app.core.errors import InvalidRequest
from app.integrations import digilocker, otp, storage
from app.repositories import visitor_repo
from app.store import ids
from app.store.entities import Visitor

log = logging.getLogger(__name__)


def get_visitor(visitor_id: str) -> Visitor:
    """One visitor, or NotFound (404)."""
    return visitor_repo.get_or_404(visitor_id)


def find_by_phone(phone: str) -> Visitor | None:
    """Returning-visitor lookup. Backs GET /visitors/lookup."""
    return visitor_repo.find_by_phone(phone)


def register(
    name: str,
    phone: str,
    address: str | None = None,
    email: str | None = None,
    photo_b64: str | None = None,
) -> Visitor:
    """Register a visitor. Creates tier `temporary`.

    The photo goes to the storage stub and only its REF is kept on the entity -
    nothing else in the codebase holds base64. An oversized
    or malformed photo raises InvalidRequest from storage.put() before the
    visitor is created, so a rejected registration leaves nothing behind.
    """
    photo_ref = storage.put(photo_b64) if photo_b64 else None

    visitor = visitor_repo.save(
        Visitor(
            id=ids.next_id("visitor"),
            name=name,
            phone=phone,
            address=address,
            email=email,
            photo_ref=photo_ref,
        )
    )
    log.info("registered visitor %s (%s), tier %s", visitor.id, name, visitor.tier)
    return visitor


def send_otp(visitor_id: str) -> str:
    """Send an OTP to the visitor's phone and return the code.

    The code comes back because there is no phone to read it off in a demo -
    see the stub. A real gateway would return a receipt instead.
    """
    visitor = visitor_repo.get_or_404(visitor_id)
    return otp.send_otp(visitor.phone)


def verify_otp(visitor_id: str, code: str) -> Visitor:
    """Set phone_verified when the code checks out.

    Note this verifies the PHONE, not the person - it has no effect on tier.
    Only DigiLocker or a host vouch make a visitor `verified`.
    """
    visitor = visitor_repo.get_or_404(visitor_id)

    if not otp.verify_otp(visitor.phone, code):
        raise InvalidRequest(
            "OTP must be six digits", {"visitor_id": visitor_id, "code": code}
        )

    visitor.phone_verified = True
    visitor_repo.save(visitor)
    log.info("phone verified for visitor %s", visitor.id)
    return visitor


def verify_digilocker(visitor_id: str) -> Visitor:
    """DigiLocker consent.

    Sets verified permanently and OVERRIDES AN EXISTING VOUCH AT ANY POINT.

    The override keeps vouched_by_host_id rather than clearing it: the design requires verified_by and vouched_by_host_id to stay queryable so
    administration can trace who vouched for a visitor who later causes
    problems. Erasing that on upgrade would destroy exactly the record it asks
    for. verified_until is left as it was for the same reason - it is a
    historical fact, and is_permanent makes it irrelevant to the tier.
    """
    visitor = visitor_repo.get_or_404(visitor_id)
    identity = digilocker.fetch_identity(visitor.phone)

    was = visitor.verified_by

    visitor.id_hash = identity["id_hash"]
    visitor.id_last4 = identity["id_last4"]
    visitor.verified_by = "digilocker"
    visitor.is_permanent = True

    visitor_repo.save(visitor)

    if was == "vouch":
        log.info(
            "visitor %s upgraded from vouch (by host %s) to DigiLocker - "
            "vouch history retained for audit",
            visitor.id,
            visitor.vouched_by_host_id,
        )
    else:
        log.info("visitor %s verified by DigiLocker, permanent", visitor.id)
    return visitor


def apply_vouch(visitor: Visitor, host_id: str, origin: str) -> Visitor:
    """A host vouches for a visitor AT APPROVAL.

    NOT AN ENDPOINT OF ITS OWN, deliberately. The design is explicit: vouching
    happens only through a host, only at approval, so that nobody can be
    pre-cleared ahead of a visit. Phase 4's POST /visits/{id}/approve is the
    only production caller.

    Three rules, in order:

      1. Already permanently verified (DigiLocker) -> NO-OP. The design
         forbids ever downgrading is_permanent, and a vouch is the weaker
         claim; letting it write would demote a stronger verification.

      2. Walk-in -> valid for THAT VISIT ONLY, no standing granted. The visitor
         record gains the audit trail of who vouched but no verified_until, so
         the derived tier stays `temporary`. The visit itself carries the
         permission via approved_by.

      3. Pre-registered -> verified_until = now + VOUCH_VALIDITY_DAYS. Any host
         may vouch again at the next approval for a fresh period, so this
         overwrites rather than extends.
    """
    if visitor.is_permanent:
        log.info(
            "vouch by host %s for visitor %s is a no-op - already permanently "
            "verified by %s",
            host_id,
            visitor.id,
            visitor.verified_by,
        )
        return visitor

    visitor.vouched_by_host_id = host_id

    if origin == "walk_in":
        # No standing. Deliberately does NOT set verified_until or verified_by,
        # so tier stays temporary once this visit is over.
        visitor_repo.save(visitor)
        log.info(
            "host %s vouched for walk-in visitor %s - this visit only, no "
            "standing granted",
            host_id,
            visitor.id,
        )
        return visitor

    visitor.verified_by = "vouch"
    visitor.verified_until = clock.now() + timedelta(days=VOUCH_VALIDITY_DAYS)
    visitor_repo.save(visitor)
    log.info(
        "host %s vouched for visitor %s until %s",
        host_id,
        visitor.id,
        visitor.verified_until.isoformat(),
    )
    return visitor
