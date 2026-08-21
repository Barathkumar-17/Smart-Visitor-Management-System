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
from app.store import seed

router = APIRouter(prefix="/dev", tags=["dev"], include_in_schema=False)


class AdvanceClockRequest(BaseModel):
    minutes: int = Field(
        description="Minutes to shift the clock forward. Additive and cumulative."
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


@router.get("/whoami")
async def whoami(user: dict[str, Any] = Depends(require_role("guard"))) -> dict[str, Any]:
    """Role-guarded probe so the 403 path stays verifiable without a real
    guard-only endpoint. Requires the guard role; an absent X-Role resolves to
    admin and is permitted. SPEC section 16.1."""
    return {"user": user}
