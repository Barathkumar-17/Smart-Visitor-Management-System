"""/dashboard.

THESE THREE ENDPOINTS ARE READ-ONLY AND DERIVE EVERYTHING. No flag is stored,
nothing is written, and no arithmetic lives here - the router calls
dashboard_service and returns what it gets, so there is exactly one definition
of `overstaying` in the codebase.
"""

from fastapi import APIRouter, Depends

from app.core.security import require_role
from app.schemas.dashboard import ExceptionsResponse, HonestyResponse, InsideRow
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/inside", response_model=list[InsideRow])
async def inside(_user=Depends(require_role("security"))):
    """Who is on campus right now, longest inside first.

    Every row carries all six flags, false ones included,
    computed at read time. Sorted by entry_at ascending and by nothing else -
    flags are shown, never ranked.
    """
    return dashboard_service.inside()


@router.get("/exceptions", response_model=ExceptionsResponse)
async def exceptions(_user=Depends(require_role("security"))):
    """Five separate lists, unmerged and unranked.

    A visit appears in every list whose condition it meets. Each row says in
    words why it is there.
    """
    return dashboard_service.exceptions()


@router.get("/honesty", response_model=HonestyResponse)
async def honesty(_user=Depends(require_role("admin"))):
    """The honesty panel.

    Every field always returned, zero where this build has no source, with
    `unavailable` explaining each empty one. Never omit a field to make the
    panel look better - that is the one thing it exists to prevent.
    """
    return dashboard_service.honesty()
