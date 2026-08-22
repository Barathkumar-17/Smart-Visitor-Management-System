"""Scan request and response models. SPEC sections 6, 10 and 14.

The gate-entry response is the most-looked-at payload in this system. SPEC
section 10: "Response leads with EVERY linked person's photo and details, the
vehicle, and the expected headcount - the guard's job is comparing faces to a
screen." So `people` comes first and carries a photo ref per person, and the
comparisons the guard actually makes are grouped rather than scattered as loose
booleans.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pass_ import QrPayload


class ScanEventOut(BaseModel):
    """One entry in the audit trail. SPEC section 6.

    `result` says whether the SCAN succeeded. The mismatch flags sit ALONGSIDE
    it, never inside it: a gate entry whose plate differs is still result `ok`
    with plate_mismatch true, because SPEC section 10 forbids ever blocking on
    a mismatch and collapsing the two would hide that distinction.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    visit_id: str
    kind: str
    result: str
    zone_id: str | None = None
    plate_mismatch: bool
    count_mismatch: bool
    person_count_recorded: int | None = None
    created_at: datetime


class PersonOut(BaseModel):
    """One face on the guard's screen.

    photo_ref, never base64 - the pixels come from GET /photos/{ref}. A
    response leading with five inline photos would be megabytes of JSON on a
    tablet at a gate (SPEC section 16.5).
    """

    role: str = Field(description="visitor or companion")
    name: str
    photo_ref: str | None = None
    id_last4: str | None = Field(
        default=None, description="Visitor only, and only when DigiLocker-verified."
    )


class PlateCheck(BaseModel):
    expected: str | None = None
    presented: str | None = None
    mismatch: bool = False


class HeadcountCheck(BaseModel):
    expected: int
    recorded: int | None = None
    mismatch: bool = False


class GateEntryRequest(BaseModel):
    """SPEC section 10. Either a signed payload or the 6-digit code."""

    payload: QrPayload | None = None
    signature: str | None = None
    code6: str | None = Field(
        default=None, description="Fallback for handsets that cannot show a QR."
    )

    vehicle_plate: str | None = None
    person_count_in: int | None = Field(
        default=None, description="The count the guard actually sees."
    )

    # Offline mode is out of scope; the backend only records these.
    entered_offline: bool = False
    authorised_by: str | None = None


class GateEntryResponse(BaseModel):
    """What the guard's screen renders.

    `admitted` is an explicit boolean and the response is ALWAYS 200, even when
    the answer is no. SPEC section 8: a scan that raised would tempt a caller
    to abandon the request before the ScanEvent was written, and section 15
    requires that event either way.
    """

    admitted: bool
    result: str = Field(description="ok | bad_signature | revoked | wrong_status | expired | already_inside")
    message: str

    people: list[PersonOut] = Field(default_factory=list)
    vehicle: PlateCheck | None = None
    headcount: HeadcountCheck | None = None

    visit_id: str | None = None
    visitor_name: str | None = None
    host_name: str | None = None
    host_phone: str | None = Field(
        default=None, description="So the guard can call the host directly."
    )
    purpose: str | None = None
    meeting_zone: str | None = None
    valid_until: datetime | None = None
    entry_at: datetime | None = None

    restricted: bool = False
    scan_event_id: str | None = None


class ZoneScanRequest(BaseModel):
    """A checkpoint scan. SPEC section 10.

    zone_code is a CODE, not an id, because that is what a scanner at a door
    reads off its own configuration. Zone IDS are what the approve and
    meeting-point bodies take, where a host is picking from a list.
    """

    zone_code: str = Field(min_length=1, description="The zone's short code, e.g. LAB.")

    payload: QrPayload | None = None
    signature: str | None = None
    code6: str | None = Field(
        default=None, description="Fallback for handsets that cannot show a QR."
    )


class ZoneScanResponse(BaseModel):
    """What the checkpoint screen renders. ALWAYS 200, refusals included.

    `allowed_zones` is returned in full and in readable form on purpose. It is
    read fresh from the visit at every scan, so showing it is what makes the
    pointer-not-payload design visible: move the meeting point and this list
    changes while the visitor's QR does not.
    """

    ok: bool
    result: str = Field(description="ok | wrong_zone | wrong_status | bad_signature")
    message: str

    people: list[PersonOut] = Field(default_factory=list)

    visit_id: str | None = None
    visitor_name: str | None = None
    host_name: str | None = None
    purpose: str | None = None

    scanned_zone: str | None = Field(default=None, description="Where the scan happened.")
    meeting_zone: str | None = Field(default=None, description="Where they are expected.")
    allowed_zones: list[str] = Field(
        default_factory=list, description="Read fresh from the visit at scan time."
    )

    scan_event_id: str | None = None
