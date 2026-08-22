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
    notification_repo,
    scan_repo,
    visit_repo,
    visitor_repo,
    zone_repo,
)
from app.services import visit_service
from app.store import seed

router = APIRouter(prefix="/dev", tags=["dev"], include_in_schema=False)


class AdvanceClockRequest(BaseModel):
    minutes: int = Field(
        description="Minutes to shift the clock forward. Additive and cumulative."
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


@router.get("/notifications")
async def list_notifications() -> dict[str, Any]:
    """Everything the notification stub "sent". SPEC section 10.

    The stub logs and appends rather than delivering, so this is how a demo
    shows who WOULD have been contacted - the host on a new request, the
    visitor on approval, security on an exception.
    """
    sent = notification_repo.list_all()
    return {
        "count": len(sent),
        "notifications": [
            {
                "id": n.id,
                "recipient": n.recipient,
                "message": n.message,
                "created_at": n.created_at.isoformat(),
            }
            for n in sent
        ],
    }


@router.get("/whoami")
async def whoami(user: dict[str, Any] = Depends(require_role("guard"))) -> dict[str, Any]:
    """Role-guarded probe so the 403 path stays verifiable without a real
    guard-only endpoint. Requires the guard role; an absent X-Role resolves to
    admin and is permitted. SPEC section 16.1."""
    return {"user": user}
