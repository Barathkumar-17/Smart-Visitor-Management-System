"""Visit endpoints. SPEC section 10.

Routers parse, check the role, call a service and return a schema. Every rule
here - the companion cap, the mutual exclusion of companions and person_count,
who may vouch, which statuses accept a reject - lives in visit_service, not
below. SPEC section 15 forbids a status check in a router, and there is not one
in this file: reject and cancel are legal only from certain statuses, and the
state machine enforces that by raising IllegalTransition.
"""

from fastapi import APIRouter, Depends, Query

from app.core.security import require_role
from app.schemas.scan import ScanEventOut
from app.schemas.visit import (
    ApproveRequest,
    ReasonRequest,
    VisitCreate,
    VisitDetail,
    VisitOut,
)
from app.services import scan_service, visit_service

router = APIRouter(prefix="/visits", tags=["visits"])


@router.post("", response_model=VisitOut, status_code=201)
async def create_visit(body: VisitCreate):
    """Pre-registered pass request. Status `requested`. SPEC section 10.

    Returns 409 VisitorAlreadyInside when the visitor is inside on another
    visit, 400 CompanionLimitExceeded beyond four companions, and 400
    InvalidRequest when companions[] and person_count are both supplied.
    """
    return visit_service.create_visit(
        visitor_id=body.visitor_id,
        host_id=body.host_id,
        purpose=body.purpose,
        scheduled_at=body.scheduled_at,
        vehicle_plate=body.vehicle_plate,
        companions=body.companions,
        person_count=body.person_count,
    )


@router.get("", response_model=list[VisitOut])
async def list_visits(
    host_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    date: str | None = Query(
        default=None,
        description="YYYY-MM-DD. Filters scheduled_at as a LOCAL_TZ calendar day.",
    ),
    _user=Depends(require_role("faculty")),
):
    """The faculty inbox. SPEC section 10."""
    return visit_service.list_visits(host_id=host_id, status=status, date=date)


@router.get("/{visit_id}", response_model=VisitDetail)
async def get_visit(visit_id: str):
    """One visit, with everyone linked to it."""
    visit = visit_service.get_visit(visit_id)
    detail = VisitDetail.model_validate(visit)
    detail.companions = visit_service.list_companions(visit_id)
    return detail


@router.get("/{visit_id}/scans", response_model=list[ScanEventOut])
async def get_visit_scans(visit_id: str):
    """The audit trail for one visit. SPEC section 10.

    Empty until Phase 6 writes the first ScanEvent. It is exposed now because
    section 10 lists it under Visits, and an endpoint that returns an honest
    empty list is better than one that 404s until a later phase.
    """
    visit_service.get_visit(visit_id)
    return scan_service.list_for_visit(visit_id)


@router.post("/{visit_id}/approve", response_model=VisitOut)
async def approve_visit(
    visit_id: str, body: ApproveRequest, _user=Depends(require_role("faculty"))
):
    """Approve: requested -> approved -> issued in one call. SPEC section 10.

    If `vouch` is true the SPEC section 7 rules are applied to the visitor -
    this is the ONLY production path that vouches for anyone.

    The acting host is the visit's host_id, not the caller: the header
    establishes the role, the path establishes the identity (SPEC section 16.1).
    """
    return visit_service.approve_visit(
        visit_id=visit_id,
        meeting_zone_id=body.meeting_zone_id,
        allowed_zones=body.allowed_zones,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
        vouch=body.vouch,
    )


@router.post("/{visit_id}/reject", response_model=VisitOut)
async def reject_visit(
    visit_id: str, body: ReasonRequest, _user=Depends(require_role("faculty"))
):
    """Reject a request. Legal only while `requested`; any other status gives
    409 from the state machine. SPEC section 10."""
    return visit_service.reject_visit(visit_id, body.reason)


@router.post("/{visit_id}/cancel", response_model=VisitOut)
async def cancel_visit(
    visit_id: str, body: ReasonRequest, _user=Depends(require_role("faculty"))
):
    """Call off a visit already approved and issued. Legal only while `issued`,
    never once `inside`. Distinct from a security revoke. SPEC section 10."""
    return visit_service.cancel_visit(visit_id, body.reason)
