"""Pass issue, code6 and revoke.

A Pass is the signed QR payload plus the 6-digit fallback code. It is created
by approval (and, in the full system, by a fallback admission) and is the thing
every scan endpoint resolves before doing anything else.
"""

import logging
import secrets

from app.core import clock, signing
from app.core.errors import InvalidRequest, NotFound
from app.repositories import pass_repo, visit_repo
from app.store import ids
from app.store.entities import Pass

log = logging.getLogger(__name__)

CODE6_DIGITS = 6
CODE6_MAX_ATTEMPTS = 50


def generate_code6() -> str:
    """A 6-digit code unique among ACTIVE passes.

    A pass is active while revoked_at is null AND its visit is not in a
    terminal state. Codes are freely reused once the owning visit is terminal -
    a million-wide space with a retry loop needs nothing more.

    Uniqueness is enforced HERE, at generation, which is what makes the lookup
    in pass_repo.find_active_by_code6 safe to treat a multi-match as a bug
    rather than a case to handle. Silently admitting the wrong visitor is the
    worst failure this system has.
    """
    taken = {p.code6 for p in pass_repo.list_active()}

    for _ in range(CODE6_MAX_ATTEMPTS):
        code = f"{secrets.randbelow(10 ** CODE6_DIGITS):0{CODE6_DIGITS}d}"
        if code not in taken:
            return code

    # Only reachable if a huge share of the million-code space is active at
    # once, which would mean something else has gone badly wrong. Raising beats
    # returning a duplicate.
    raise RuntimeError(
        f"Could not find a free code6 in {CODE6_MAX_ATTEMPTS} attempts; "
        f"{len(taken)} codes are currently active."
    )


def issue_pass(visit_id: str) -> Pass:
    """Create and sign the pass for a visit. Called by approve.

    One pass per visit: if one already exists it is returned unchanged rather
    than reissued, so nothing can silently invalidate a QR a visitor is already
    carrying.
    """
    visit = visit_repo.get_or_404(visit_id)

    existing = pass_repo.find_by_visit(visit_id)
    if existing is not None:
        log.info("visit %s already has pass %s, not reissuing", visit_id, existing.id)
        return existing

    nonce = signing.new_nonce()
    _, signature = signing.sign_pass(visit.id, nonce)

    issued = pass_repo.save(
        Pass(
            id=ids.next_id("pass"),
            visit_id=visit.id,
            code6=generate_code6(),
            signature=signature,
            nonce=nonce,
        )
    )
    log.info("issued pass %s for visit %s, code6 %s", issued.id, visit.id, issued.code6)
    return issued


def get_pass_for_visit(visit_id: str) -> Pass:
    """The pass for a visit, or NotFound (404)."""
    visit_repo.get_or_404(visit_id)
    found = pass_repo.find_by_visit(visit_id)
    if found is None:
        raise NotFound(
            f"No pass issued for visit {visit_id}",
            {"visit_id": visit_id, "hint": "a pass is created when the visit is approved"},
        )
    return found


def build_qr_payload(issued: Pass) -> dict:
    """What a QR encodes: the payload and its signature, nothing else.

    Deliberately excludes the window and the zone list. Both are read fresh
    from the visit at scan time, which is what lets a host move the meeting
    point or extend the window without the visitor's QR changing at all.
    """
    return {
        "payload": {"visit_id": issued.visit_id, "nonce": issued.nonce},
        "signature": issued.signature,
    }


def revoke_pass(visit_id: str, actor: str = "security:u_security") -> Pass:
    """Revoke a pass.

    Sets revoked_at and NOTHING ELSE. It does not change the visit's status,
    does not eject anyone already inside, and does not stop them leaving:
    the design is explicit that revocation prevents FUTURE entry scans,
    and that exit still works. Ejecting someone is a decision for a person at
    the gate, not a side effect of a database write.

    Distinct from a host's cancel, which does move the visit to `cancelled`.
    """
    issued = get_pass_for_visit(visit_id)

    if issued.revoked_at is not None:
        raise InvalidRequest(
            f"Pass {issued.id} is already revoked",
            {"pass_id": issued.id, "revoked_at": issued.revoked_at.isoformat()},
        )

    issued.revoked_at = clock.now()
    pass_repo.save(issued)

    log.warning(
        "pass %s for visit %s REVOKED by %s - visit status left at %s",
        issued.id,
        visit_id,
        actor,
        visit_repo.get(visit_id).status,
    )
    return issued


def resolve_scan(
    payload: dict | None = None,
    signature: str | None = None,
    code6: str | None = None,
) -> tuple[Pass, str]:
    """Resolve a scan to its pass, by signed payload OR by 6-digit code.

    Returns (pass, result) where result is "ok", "bad_signature" or a marker
    that no pass matched. It does NOT raise for a bad signature: the design
    requires every scan endpoint to return 200 carrying its outcome so the
    ScanEvent can never be lost to an early exit.

    Every scan endpoint comes through here, so the two
    lookups are defined once rather than three times.
    """
    if code6:
        found = pass_repo.find_active_by_code6(code6)
        if found is None:
            return None, "not_found"
        return found, "ok"

    if payload and signature:
        if not signing.verify_pass(payload, signature):
            return None, "bad_signature"

        visit_id = payload.get("visit_id")
        found = pass_repo.find_by_visit(visit_id) if visit_id else None
        if found is None:
            return None, "not_found"

        # A valid signature over a payload whose nonce does not match the
        # stored pass means an OLD payload for a reissued pass. Treat it as a
        # bad signature rather than admitting on a superseded QR.
        if found.nonce != payload.get("nonce"):
            return None, "bad_signature"

        return found, "ok"

    raise InvalidRequest(
        "Supply either a signed payload with its signature, or code6",
        {"got": {"payload": bool(payload), "signature": bool(signature), "code6": bool(code6)}},
    )
