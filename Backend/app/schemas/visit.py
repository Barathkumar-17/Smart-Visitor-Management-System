"""Visit request and response models. SPEC sections 10, 16.4 and 16.7."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _require_aware(value: datetime | None) -> datetime | None:
    """Reject a naive datetime. SPEC section 16.7.

    All API bodies use ISO 8601 WITH OFFSET. A naive timestamp is ambiguous -
    it would be read as UTC and silently shift a window by five and a half
    hours in this deployment, producing a pass valid at the wrong time with no
    error anywhere.
    """
    if value is not None and value.tzinfo is None:
        raise ValueError(
            "timestamp must include a UTC offset, e.g. 2026-08-22T14:30:00+05:30"
        )
    return value


class CompanionIn(BaseModel):
    """One linked companion on a pass request. SPEC sections 6 and 16.5."""

    name: str = Field(min_length=1)
    photo_b64: str | None = Field(
        default=None, description="Base64 image. Over 2 MB decoded is rejected."
    )


class CompanionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    visit_id: str
    name: str
    photo_ref: str | None = None


class VisitCreate(BaseModel):
    """Pre-registered pass request. SPEC sections 10 and 16.4.

    companions[] and person_count are MUTUALLY EXCLUSIVE - supplying both is
    InvalidRequest, because the two would disagree about the group size and
    nothing says which wins. See SPEC section 16.4 for the full table.
    """

    visitor_id: str
    host_id: str
    purpose: str = Field(min_length=1)
    scheduled_at: datetime
    vehicle_plate: str | None = None

    companions: list[CompanionIn] | None = Field(
        default=None,
        description="Up to MAX_LINKED_COMPANIONS. Mutually exclusive with person_count.",
    )
    person_count: int | None = Field(
        default=None,
        description="TOTAL including the accountable visitor. Mutually exclusive "
        "with companions[].",
    )

    _aware = field_validator("scheduled_at")(_require_aware)


class ApproveRequest(BaseModel):
    """Host approval. SPEC section 10.

    `vouch` applies the SPEC section 7 rules to the visitor. Zones are ZONE IDS
    here, matching meeting_zone_id and the Visit entity; zone CODES are what
    the scan endpoints take, because a guard's scanner reads a code.
    """

    meeting_zone_id: str
    allowed_zones: list[str] = Field(
        default_factory=list, description="Zone ids. The meeting zone is added if absent."
    )
    valid_from: datetime
    valid_to: datetime
    vouch: bool = False

    _aware_from = field_validator("valid_from")(_require_aware)
    _aware_to = field_validator("valid_to")(_require_aware)


class ArrivalAckRequest(BaseModel):
    """Host confirms availability. SPEC sections 4.4 and 10.

    Both fields are REQUIRED when the visit is restricted and IGNORED
    otherwise. A restricted visit is always a fallback admission - nothing else
    in the system sets restricted - so no host ever chose its zones, and there
    is nothing to restore. The host supplies them here, which is the first
    moment a host is in the loop on that visit at all.
    """

    allowed_zones: list[str] | None = Field(
        default=None, description="Zone ids. Required if the visit is restricted."
    )
    valid_to: datetime | None = Field(
        default=None,
        description="Extended window end. Required if the visit is restricted. "
        "Changing it does NOT reissue the QR - the window is not in the signed "
        "payload (SPEC section 9).",
    )

    _aware_to = field_validator("valid_to")(_require_aware)


class ReasonRequest(BaseModel):
    """Body for reject and cancel. Both take a free-text reason."""

    reason: str = Field(min_length=1)


class VisitOut(BaseModel):
    """A visit as returned by the API.

    Carries the whole record, including the four escalation-stage fields. Those
    stay null for the life of this build - the jobs that advance them are Phase
    11, which is deferred - but they are returned rather than hidden so nothing
    downstream has to guess whether a chain ever ran.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    visitor_id: str
    host_id: str
    purpose: str
    scheduled_at: datetime
    status: str
    origin: str

    person_count_expected: int
    person_count_in: int | None = None
    person_count_out: int | None = None

    vehicle_plate_in: str | None = None
    vehicle_plate_out: str | None = None

    meeting_zone_id: str | None = None
    allowed_zones: list[str] = Field(default_factory=list)
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    restricted: bool
    approved_by: str | None = None
    approval_reason: str | None = None

    entry_at: datetime | None = None
    host_acked_at: datetime | None = None
    exit_at: datetime | None = None
    closed_reason: str | None = None

    entered_offline: bool
    authorised_by: str | None = None

    approval_escalation_stage: str | None = None
    approval_escalated_at: datetime | None = None
    ack_escalation_stage: str | None = None
    ack_escalated_at: datetime | None = None

    created_at: datetime


class VisitDetail(VisitOut):
    """A visit plus the people on it, for GET /visits/{id}.

    The companion list is what makes a group visible: SPEC section 10 requires
    the gate-entry response to lead with every linked person, and this is the
    same data a host sees before approving.
    """

    companions: list[CompanionOut] = Field(default_factory=list)
