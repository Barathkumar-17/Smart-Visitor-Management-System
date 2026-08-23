"""Visitor endpoints.

ROUTE ORDER MATTERS HERE. GET /visitors/lookup is declared ABOVE
GET /visitors/{visitor_id} on purpose. Reverse them and FastAPI matches the
literal string "lookup" as a visitor id, and the endpoint becomes permanently
unreachable while still appearing in the schema - a bug that looks like a
missing feature.

GET /photos/{ref} lives here too, on its own prefix-free router. It belongs
alongside registration, and the router
file list, so it gets a second APIRouter rather than a new module.
"""

from fastapi import APIRouter, Depends, Query

from app.core.security import assert_owns_visitor, require_role, require_user
from app.integrations import storage
from app.schemas.visitor import (
    OtpSendResponse,
    OtpVerifyRequest,
    PhotoOut,
    VisitorCreate,
    VisitorOut,
)
from app.services import visitor_service

router = APIRouter(prefix="/visitors", tags=["visitors"])

# Separate router: the path is /photos, not /visitors/photos.
photos_router = APIRouter(tags=["photos"])


@router.post("", response_model=VisitorOut, status_code=201)
async def register_visitor(body: VisitorCreate, _user=Depends(require_user())):
    """Register a visitor. Creates tier `temporary`.

    Verification is a separate step: DigiLocker below, or a host vouch at
    approval. Registering alone confers no standing.
    """
    return visitor_service.register(
        name=body.name,
        phone=body.phone,
        address=body.address,
        email=body.email,
        photo_b64=body.photo_b64,
    )


# --- MUST stay above /{visitor_id} ------------------------------------------
@router.get("/lookup", response_model=VisitorOut | None)
async def lookup_visitor(
    phone: str = Query(description="Exact phone match."),
    _user=Depends(require_role("guard")),
):
    """Find a visitor by phone, so a returning visitor skips the form.

    Returns null rather than 404 when nobody matches: at the gate "no such
    visitor" is an ordinary answer that means "show the form", not an error.
    """
    return visitor_service.find_by_phone(phone)


@router.post("/{visitor_id}/otp/send", response_model=OtpSendResponse)
async def send_otp(visitor_id: str, user=Depends(require_user())):
    """Send an OTP to the visitor's phone."""
    assert_owns_visitor(user, visitor_id)
    visitor = visitor_service.get_visitor(visitor_id)
    code = visitor_service.send_otp(visitor_id)
    return OtpSendResponse(visitor_id=visitor.id, phone=visitor.phone, code=code)


@router.post("/{visitor_id}/otp/verify", response_model=VisitorOut)
async def verify_otp(
    visitor_id: str, body: OtpVerifyRequest, user=Depends(require_user())
):
    """Set phone_verified. Verifies the PHONE, not the person - it does not
    change tier."""
    assert_owns_visitor(user, visitor_id)
    return visitor_service.verify_otp(visitor_id, body.code)


@router.post("/{visitor_id}/digilocker", response_model=VisitorOut)
async def verify_digilocker(visitor_id: str, user=Depends(require_user())):
    """DigiLocker consent stub. Sets verified and permanent, and OVERRIDES ANY
    EXISTING VOUCH.

    Sets id_hash on the entity, which no response ever returns; id_last4 comes
    back and is the part a guard may see.
    """
    assert_owns_visitor(user, visitor_id)
    return visitor_service.verify_digilocker(visitor_id)


@router.get("/{visitor_id}", response_model=VisitorOut)
async def get_visitor(visitor_id: str, user=Depends(require_user())):
    """One visitor. NEVER returns id_hash - see VisitorOut.

    A visitor account may read only itself; staff may read anyone, because a
    guard has to be able to look up whoever is standing at the gate.
    """
    assert_owns_visitor(user, visitor_id)
    return visitor_service.get_visitor(visitor_id)


@photos_router.get("/photos/{ref}", response_model=PhotoOut)
async def get_photo(ref: str, _user=Depends(require_user())):
    """The pixels for a photo ref.

    No role marker, so any caller may fetch one - the guard's screen has to get
    the image from somewhere, and the design requires the gate-entry response
    to lead with faces. NotFound (404) when the ref does not resolve.
    """
    return PhotoOut(ref=ref, photo_b64=storage.get(ref))
