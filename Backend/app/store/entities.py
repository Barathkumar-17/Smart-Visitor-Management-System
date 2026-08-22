"""Entity dataclasses.

These are the in-memory records, NOT the API surface. Pydantic schemas in
app/schemas/ are that, and they are deliberately separate.

id_hash lives here and must NEVER appear in any API response.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.core import clock


@dataclass
class Visitor:
    """A person who may visit."""

    id: str
    name: str
    phone: str
    address: str | None = None
    email: str | None = None
    photo_ref: str | None = None
    phone_verified: bool = False

    # "digilocker" | "vouch" | None
    verified_by: str | None = None

    # Set only by the DigiLocker stub. id_hash is never returned by any
    # endpoint; id_last4 may be shown.
    id_hash: str | None = None
    id_last4: str | None = None

    vouched_by_host_id: str | None = None
    verified_until: datetime | None = None
    is_permanent: bool = False
    created_at: datetime = field(default_factory=clock.now)

    @property
    def tier(self) -> str:
        """`verified` or `temporary` - DERIVED, never stored.

        A visitor is verified while is_permanent is true, or while
        verified_until is still in the future. Nothing ever writes a visitor
        back to `temporary`: a stored tier and a derived one would drift apart,
        and the stored one would be wrong the moment a vouch lapsed.

        Implemented as a property precisely so no caller can forget to compute
        it - reading `visitor.tier` always recomputes.
        """
        if self.is_permanent:
            return "verified"
        if self.verified_until is not None and self.verified_until > clock.now():
            return "verified"
        return "temporary"


@dataclass
class Companion:
    """Someone accompanying the accountable visitor.

    Up to MAX_LINKED_COMPANIONS of these per visit. Beyond that the group
    collapses to person_count_expected with no Companion records.
    """

    id: str
    visit_id: str
    name: str
    photo_ref: str | None = None


@dataclass
class Host:
    """A member of staff who receives visitors.

    `department` is a bare string - there is no department entity and none is
    to be added.
    """

    id: str
    name: str
    department: str
    email: str | None = None
    phone: str | None = None


@dataclass
class Zone:
    """A checkpoint inside the campus."""

    id: str
    code: str
    name: str


@dataclass
class Visit:
    """One visit by one accountable visitor, covering the whole group. status is assigned ONLY by transition() in
    services/visit_service.py - never anywhere else.
    """

    id: str
    visitor_id: str
    host_id: str
    purpose: str
    scheduled_at: datetime

    status: str = "requested"

    # "pre_registered" | "walk_in"
    origin: str = "pre_registered"

    # The TOTAL including the accountable visitor.
    person_count_expected: int = 1

    vehicle_plate_in: str | None = None
    vehicle_plate_out: str | None = None
    person_count_in: int | None = None
    person_count_out: int | None = None

    meeting_zone_id: str | None = None

    # Zone ids. Read FRESH at every scan, never baked into the QR payload -
    # that is what lets meeting-point change without reissuing.
    allowed_zones: list[str] = field(default_factory=list)

    valid_from: datetime | None = None
    valid_to: datetime | None = None

    # Set ONLY by the fallback-authority decision, which is unbuilt, and cleared by
    # arrival-ack. In this build it arrives only from seed data.
    restricted: bool = False

    # "{role}:{id}" - same format as the transition() actor.
    approved_by: str | None = None
    approval_reason: str | None = None

    entry_at: datetime | None = None
    host_acked_at: datetime | None = None
    exit_at: datetime | None = None
    closed_reason: str | None = None

    # Offline mode is out of scope; the backend only records these.
    entered_offline: bool = False
    authorised_by: str | None = None

    # Two INDEPENDENT escalation chains, tracked separately so a completed
    # approval chain cannot be mistaken for an active acknowledgement one.
    # Each advances null -> department -> fallback -> exhausted, never back.
    #
    # These four fields are the ONE exception to "derive flags at read time"
    #: they record what was SENT, not what is currently true,
    # and cannot be recomputed after the fact.
    #
    # Nothing in this build advances them - the jobs that would are unbuilt.
    # They are created and left null, deliberately.
    approval_escalation_stage: str | None = None
    approval_escalated_at: datetime | None = None
    ack_escalation_stage: str | None = None
    ack_escalated_at: datetime | None = None

    created_at: datetime = field(default_factory=clock.now)


@dataclass
class Pass:
    """A signed QR plus its 6-digit fallback code.

    The payload carries only visit_id and nonce - never visitor data, never
    the time window, never the zone list.
    """

    id: str
    visit_id: str
    code6: str
    signature: str
    nonce: str
    issued_at: datetime = field(default_factory=clock.now)
    revoked_at: datetime | None = None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None


@dataclass
class ScanEvent:
    """The audit trail, and the most important collection here.

    One is written for EVERY scan attempt, successful or not. A later scoring
    phase reads this history and its completeness now decides whether that
    phase is possible at all.

    `result` describes whether the SCAN succeeded. Mismatches sit ALONGSIDE it,
    never inside it: a gate entry whose plate differs is still `ok`, with
    plate_mismatch = True. Collapsing the two would make a mismatch
    indistinguishable from a rejection, and the design forbids ever
    blocking on one.
    """

    id: str
    visit_id: str

    # "entry" | "zone" | "exit"
    kind: str

    # ok | wrong_zone | expired | bad_signature | wrong_status | revoked
    # | already_inside
    result: str

    # null for `entry` and `exit` kinds
    zone_id: str | None = None

    plate_mismatch: bool = False
    count_mismatch: bool = False

    # The count the guard actually entered. null for `zone` kind.
    person_count_recorded: int | None = None

    created_at: datetime = field(default_factory=clock.now)


@dataclass
class Notification:
    """What the notification stub "sent", so a demo can show it."""

    id: str
    recipient: str
    message: str
    created_at: datetime = field(default_factory=clock.now)


@dataclass
class User:
    """A staff account that can log in.

    Four of these exist and no endpoint creates more - there is no sign-up, no
    password reset and no user administration. That is the whole point: the
    accounts are fixtures for a demonstration, not a user management system.

    The password is stored as a PBKDF2 hash with a per-user salt, never as
    plain text. That costs nothing and means a screenshot of the store does not
    hand over the accounts.
    """

    id: str
    username: str
    role: str
    name: str
    salt: str
    password_hash: str
