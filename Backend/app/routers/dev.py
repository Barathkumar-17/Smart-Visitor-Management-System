"""Prototype-only endpoints. SPEC section 10.

Marked clearly and excluded from the main OpenAPI tags. None of this ships.

At Phase 0 this router carries /dev/advance-clock and one role-guarded probe
route. /dev/reset arrives at Phase 1, /dev/transition at Phase 2 and
/dev/notifications alongside the notification stub.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core import clock
from app.core.security import require_role

router = APIRouter(prefix="/dev", tags=["dev"], include_in_schema=False)


class AdvanceClockRequest(BaseModel):
    minutes: int = Field(
        description="Minutes to shift the clock forward. Additive and cumulative."
    )


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


@router.get("/whoami")
async def whoami(user: dict[str, Any] = Depends(require_role("guard"))) -> dict[str, Any]:
    """Role-guarded probe so the 403 path is verifiable at Phase 0.

    Requires `guard`. An absent X-Role resolves to admin and is permitted;
    X-Role: visitor is rejected with NotPermitted. SPEC section 16.1.
    """
    return {"user": user}
