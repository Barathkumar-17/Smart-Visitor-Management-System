"""Visitor request and response models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VisitorOut(BaseModel):
    """A visitor as returned by the API.

    id_hash IS DELIBERATELY ABSENT and must never be added. SPEC section 15
    forbids any endpoint returning it; id_last4 is the field that may be shown.
    Listing fields explicitly rather than dumping the dataclass is what keeps
    that true - a future field on the entity cannot leak through by accident.

    `tier` is a derived property on the entity, recomputed on every read, so a
    lapsed vouch shows as `temporary` here without anything having written to
    the record. SPEC section 6.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    phone: str
    address: str | None = None
    email: str | None = None
    photo_ref: str | None = None
    phone_verified: bool
    tier: str
    verified_by: str | None = None
    id_last4: str | None = None
    vouched_by_host_id: str | None = None
    verified_until: datetime | None = None
    is_permanent: bool
    created_at: datetime


class VisitorCreate(BaseModel):
    """Registration body. SPEC sections 10 and 16.5.

    The photo arrives as base64 in `photo_b64` and leaves as a ref - never as
    base64 (SPEC section 16.5). Over 2 MB decoded is InvalidRequest.

    Only name and phone are required. SPEC section 3 describes a full
    registration as name, address, mobile, email and a live photo, but the
    remaining fields are accepted as optional here so a caller with a partial
    record is not blocked; the fields exist and are stored when supplied.
    """

    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    address: str | None = None
    email: str | None = None
    photo_b64: str | None = Field(
        default=None, description="Base64 image. Over 2 MB decoded is rejected."
    )


class OtpVerifyRequest(BaseModel):
    """OTP check. The stub accepts any six digits, per SPEC section 5."""

    code: str = Field(description="Six digits.")


class OtpSendResponse(BaseModel):
    """The code comes back because a demo has no phone to read it off.

    A real gateway returns a delivery receipt and this field disappears.
    """

    visitor_id: str
    phone: str
    code: str
    note: str = "Stub: the code is returned because there is no real SMS."


class PhotoOut(BaseModel):
    """GET /photos/{ref}. The ONLY place base64 leaves this system.

    SPEC section 16.5: every other response carries photo_ref, because a
    gate-entry response leading with five inline photos would be megabytes of
    JSON on a tablet at a gate. The guard screen fetches pixels from here.
    """

    ref: str
    photo_b64: str
