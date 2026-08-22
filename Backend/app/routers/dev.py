"""Prototype-only endpoints. SPEC section 10.

Marked clearly and excluded from the main OpenAPI tags. None of this ships.

Phase 0 added /dev/advance-clock and the role probe; Phase 1 adds /dev/reset.
/dev/transition arrives at Phase 2 and /dev/notifications with the
notification stub.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core import clock
from app.core.security import require_role
from app.repositories import (
    host_repo,
    scan_repo,
    visit_repo,
    visitor_repo,
    zone_repo,
)
from app.services import visit_service, visitor_service
from app.store import seed

router = APIRouter(prefix="/dev", tags=["dev"], include_in_schema=False)


class AdvanceClockRequest(BaseModel):
    minutes: int = Field(
        description="Minutes to shift the clock forward. Additive and cumulative."
    )


class VouchRequest(BaseModel):
    visitor_id: str
    host_id: str
    origin: str = Field(
        default="pre_registered",
        description="pre_registered grants VOUCH_VALIDITY_DAYS of standing; "
        "walk_in grants none, per SPEC section 7.",
    )


class TransitionRequest(BaseModel):
    visit_id: str
    # Deliberately a plain str, NOT a Literal of the known statuses. A Literal
    # would make FastAPI reject an unknown status with its own 422 before the
    # service ever saw it, and the 409 that SPEC section 8 wants for a move the
    # table rejects would become untestable.
    to_status: str = Field(
        description="Target status. Anything the SPEC section 8 table does not "
        "allow from the current status returns 409, including a status that "
        "does not exist."
    )


@router.post("/reset")
async def reset() -> dict[str, Any]:
    """Clear the store and reseed it, and put the clock offset back to zero.

    Step 0 of every manual test script from Phase 1 onward, so a failed test
    cannot leave state that breaks the next one.

    Ids are deterministic across a reset because the counters reset first: the
    seed always produces z_1..z_5, h_1..h_3, vr_1, vr_2, v_1, v_2. Test scripts
    depend on that.
    """
    seed.reset()
    return {
        "reset": True,
        "clock_offset_minutes": clock.offset().total_seconds() / 60,
        "now_local": clock.readable(),
        "seeded": {
            "zones": zone_repo.count(),
            "hosts": host_repo.count(),
            "visitors": visitor_repo.count(),
            "visits": visit_repo.count(),
            "scan_events": scan_repo.count(),
        },
    }


@router.post("/advance-clock")
async def advance_clock(body: AdvanceClockRequest) -> dict[str, Any]:
    """Shift the module-level offset in core/clock.py.

    Lets a demo trigger escalation and overstay instantly instead of waiting 30
    real minutes. Advancing past 17:00 local reroutes fallback escalation from
    admin to security - intended, not a bug. SPEC section 16.7.
    """
    before = clock.readable()
    offset = clock.advance(body.minutes)
    return {
        "advanced_by_minutes": body.minutes,
        "was": before,
        "now_local": clock.readable(),
        "clock_offset_minutes": offset.total_seconds() / 60,
        "now": clock.now().isoformat(),
    }


@router.post("/transition")
async def force_transition(body: TransitionRequest) -> dict[str, Any]:
    """Drive the state machine directly. SPEC section 10.

    Exists so the machine is testable at Phase 2, before any real endpoint
    drives it - the first of those is POST /visits/{id}/approve at Phase 4 -
    and to force a visit into a given state during manual testing later.

    The actor is "dev:forced" per SPEC section 16.2, so the log makes clear a
    move was forced rather than reached through the flow.
    """
    visit = visit_repo.get_or_404(body.visit_id)
    from_status = visit.status

    visit_service.transition(visit, body.to_status, actor="dev:forced")

    return {
        "visit_id": visit.id,
        "from": from_status,
        "to": visit.status,
        "is_terminal": visit_service.is_terminal(visit.status),
        "legal_moves_now": visit_service.legal_moves(visit.status),
    }


@router.post("/vouch")
async def force_vouch(body: VouchRequest) -> dict[str, Any]:
    """Apply a host vouch directly, WITHOUT going through approval.

    SPEC section 7 is emphatic that vouching happens only through a host and
    only at approval, so that nobody can be pre-cleared ahead of a visit. That
    rule governs the PRODUCTION surface; POST /visits/{id}/approve at Phase 4
    is the only endpoint that will ever call apply_vouch() for real.

    This route exists for the same reason SPEC section 10 gives for
    /dev/transition - "so the state machine is testable before any real
    endpoint drives it". Without it, Phase 3 cannot test the section 7 rule
    that DigiLocker OVERRIDES an existing vouch, because at Phase 3 nothing can
    create a vouch to override.

    Prototype-only, excluded from the schema, and a candidate for deletion once
    Phase 4 makes it redundant.
    """
    visitor = visitor_service.get_visitor(body.visitor_id)
    before = {"tier": visitor.tier, "verified_by": visitor.verified_by}

    visitor_service.apply_vouch(visitor, body.host_id, body.origin)

    return {
        "visitor_id": visitor.id,
        "before": before,
        "after": {
            "tier": visitor.tier,
            "verified_by": visitor.verified_by,
            "vouched_by_host_id": visitor.vouched_by_host_id,
            "verified_until": (
                visitor.verified_until.isoformat() if visitor.verified_until else None
            ),
            "is_permanent": visitor.is_permanent,
        },
    }


@router.get("/whoami")
async def whoami(user: dict[str, Any] = Depends(require_role("guard"))) -> dict[str, Any]:
    """Role-guarded probe so the 403 path stays verifiable without a real
    guard-only endpoint. Requires the guard role; an absent X-Role resolves to
    admin and is permitted. SPEC section 16.1."""
    return {"user": user}
