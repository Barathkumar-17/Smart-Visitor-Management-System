"""Visit endpoints.

Routers parse, check the role, call a service and return a schema. Every rule
here - the companion cap, the mutual exclusion of companions and person_count,
who may vouch, which statuses accept a reject - lives in visit_service, not
below. The design forbids a status check in a router, and there is not one
in this file: reject and cancel are legal only from certain statuses, and the
state machine enforces that by raising IllegalTransition.
"""

from fastapi import APIRouter, Depends, Query

from app.core.security import assert_owns_visitor, require_role, require_user
from app.schemas.scan import ScanEventOut
from app.schemas.visit import (
    ApproveRequest,
    ArrivalAckRequest,
    CloseRequest,
    MeetingPointRequest,
    ReasonRequest,
    VisitCreate,
    VisitDetail,
    VisitOut,
)
from app.services import scan_service, visit_service

router = APIRouter(prefix="/visits", tags=["visits"])


@router.post("", response_model=VisitOut, status_code=201)
async def create_visit(body: VisitCreate, user=Depends(require_user())):
    """Pre-registered pass request. Status `requested`.

    A visitor account may only request a pass for itself, so the visitor_id in
    the body is ignored for that role and replaced with the account's own -
    otherwise anyone could book a visit in somebody else's name.

    Returns 409 VisitorAlreadyInside when the visitor is inside on another
    visit, 400 CompanionLimitExceeded beyond four companions, and 400
    InvalidRequest when companions[] and person_count are both supplied.
    """
    visitor_id = (
        user["visitor_id"] if user.get("role") == "visitor" else body.visitor_id
    )
    return visit_service.create_visit(
        visitor_id=visitor_id,
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
    """The faculty inbox."""
    return visit_service.list_visits(host_id=host_id, status=status, date=date)


@router.get("/{visit_id}", response_model=VisitDetail)
async def get_visit(visit_id: str, user=Depends(require_user())):
    """One visit, with everyone linked to it.

    A visitor account sees only its own visits. Staff see any, because the
    guard picker and the faculty inbox both need to read a visit they are not
    the subject of.
    """
    visit = visit_service.get_visit(visit_id)
    assert_owns_visitor(user, visit.visitor_id)
    detail = VisitDetail.model_validate(visit)
    detail.companions = visit_service.list_companions(visit_id)
    return detail


@router.get("/{visit_id}/scans", response_model=list[ScanEventOut])
async def get_visit_scans(visit_id: str, user=Depends(require_user())):
    """The audit trail for one visit.

    Empty until the first scan writes a ScanEvent. It is exposed because
    the design lists it under Visits, and an endpoint that returns an honest
    empty list is better than one that 404s until a later phase.
    """
    visit = visit_service.get_visit(visit_id)
    assert_owns_visitor(user, visit.visitor_id)
    return scan_service.list_for_visit(visit_id)


@router.post("/{visit_id}/approve", response_model=VisitOut)
async def approve_visit(
    visit_id: str, body: ApproveRequest, _user=Depends(require_role("faculty"))
):
    """Approve: requested -> approved -> issued in one call.

    If `vouch` is true the the design rules are applied to the visitor -
    this is the ONLY production path that vouches for anyone.

    The acting host is the visit's host_id, not the caller: the header
    establishes the role, the path establishes the identity.
    """
    return visit_service.approve_visit(
        visit_id=visit_id,
        meeting_zone_id=body.meeting_zone_id,
        allowed_zones=body.allowed_zones,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
        vouch=body.vouch,
    )


@router.post("/{visit_id}/arrival-ack", response_model=VisitOut)
async def arrival_ack(
    visit_id: str, body: ArrivalAckRequest, _user=Depends(require_role("faculty"))
):
    """The host confirms availability, and lifts a restriction if there is one. The visitor is never held at the gate waiting for
    this - they entered already, and this only decides how far they may go and
    for how long.

    allowed_zones and valid_to are REQUIRED when the visit is restricted and
    IGNORED otherwise. Changing valid_to does NOT reissue the QR.
    """
    return visit_service.arrival_ack(
        visit_id=visit_id,
        allowed_zones=body.allowed_zones,
        valid_to=body.valid_to,
    )


@router.post("/{visit_id}/reject", response_model=VisitOut)
async def reject_visit(
    visit_id: str, body: ReasonRequest, _user=Depends(require_role("faculty"))
):
    """Reject a request. Legal only while `requested`; any other status gives
    409 from the state machine."""
    return visit_service.reject_visit(visit_id, body.reason)


@router.post("/{visit_id}/cancel", response_model=VisitOut)
async def cancel_visit(
    visit_id: str, body: ReasonRequest, _user=Depends(require_role("faculty"))
):
    """Call off a visit already approved and issued. Legal only while `issued`,
    never once `inside`. Distinct from a security revoke."""
    return visit_service.cancel_visit(visit_id, body.reason)


@router.patch("/{visit_id}/meeting-point", response_model=VisitOut)
async def change_meeting_point(
    visit_id: str, body: MeetingPointRequest, _user=Depends(require_role("faculty"))
):
    """Move the meeting on a pass the visitor is already carrying.

    this endpoint exists to prove the pointer-not-payload
    design, and it MUST NOT reissue the QR. It does not touch the pass at all -
    zones are not in the signed payload, so the next scan
    reads this record fresh and the QR is byte-identical either side.
    """
    return visit_service.change_meeting_point(
        visit_id=visit_id,
        meeting_zone_id=body.meeting_zone_id,
        allowed_zones=body.allowed_zones,
    )


@router.post("/{visit_id}/close", response_model=VisitOut)
async def close_visit(
    visit_id: str, body: CloseRequest, _user=Depends(require_role("guard"))
):
    """End-of-day close-out.

    The guard's sweep for whatever the exit scan could not resolve. Legal only
    from `inside` - the state machine returns 409 from anywhere else - and it
    leaves exit_at null on purpose, because nobody scanned out.
    """
    return visit_service.close_visit(visit_id, body.reason)
