"""Reference data - GET /zones and GET /hosts.

Both are unguarded reads with no role marker, so any caller may fetch them.
Neither has a business rule, so they read through their repository directly
rather than via a service that would only forward the call. The design
permits this: what it forbids in a router is business LOGIC, and it explicitly
contemplates a router reaching storage through a repository.
"""

from fastapi import APIRouter

from app.repositories import host_repo, zone_repo
from app.schemas.common import HostOut, ZoneOut

router = APIRouter(tags=["reference"])


@router.get("/zones", response_model=list[ZoneOut])
async def list_zones() -> list:
    """Every checkpoint zone. Zone scans arrive by `code`, not id."""
    return zone_repo.list_all()


@router.get("/hosts", response_model=list[HostOut])
async def list_hosts() -> list:
    """Every host, INCLUDING phone, so the guard can call one directly instead
    of waiting on escalation."""
    return host_repo.list_all()
