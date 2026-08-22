"""Prototype-only endpoints.

Marked clearly and excluded from the main OpenAPI tags. None of this ships.

They exist so a demonstration can reset the campus, jump the clock, force a
visit into a state, and read back the
notification stub.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core import clock
from app.core.security import require_role, require_user
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
    # service ever saw it, and the 409 that the design wants for a move the
    # table rejects would become untestable.
    to_status: str = Field(
        description="Target status. Anything the the design table does not "
        "allow from the current status returns 409, including a status that "
        "does not exist."
    )


@router.post("/reset")
async def reset(_user=Depends(require_role("admin"))) -> dict[str, Any]:
    """Clear the store and reseed it, and put the clock offset back to zero.

    Step 0 of every test run, so a failed test
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
async def advance_clock(
    body: AdvanceClockRequest, _user=Depends(require_role("admin"))
) -> dict[str, Any]:
    """Shift the module-level offset in core/clock.py.

    Lets a demo trigger escalation and overstay instantly instead of waiting 30
    real minutes. Advancing past 17:00 local reroutes fallback escalation from
    admin to security - intended, not a bug.
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
async def force_transition(
    body: TransitionRequest, _user=Depends(require_role("admin"))
) -> dict[str, Any]:
    """Drive the state machine directly.

    Exists so the state machine is drivable directly, without going through
    the endpoints that normally drive it,
    and to force a visit into a given state during manual testing later.

    The actor is "dev:forced", so the log makes clear a
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
async def list_notifications(_user=Depends(require_user())) -> dict[str, Any]:
    """Everything the notification stub "sent".

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
async def whoami(user: dict[str, Any] = Depends(require_user())) -> dict[str, Any]:
    """Whoever the token belongs to, wrapped for the dev tools.

    GET /auth/me returns the same thing and is the one to use; this predates it
    and stays because scripts point at it."""
    return {"user": user}
