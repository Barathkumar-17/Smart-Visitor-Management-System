"""Dashboard response models. SPEC sections 10 and 11.

These are the three screens the system is judged on, so the shapes here are
chosen for reading rather than for parsing. Flags come back as a named object
rather than six loose booleans, zone and host references come back resolved
rather than as ids, and the honesty panel carries a note beside every field it
cannot fill.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.scan import PersonOut


class VisitFlags(BaseModel):
    """SPEC section 11's six derived flags. Every one is computed at read time.

    All six are ALWAYS present, including the false ones. A dashboard that
    omits the flags it did not raise makes absence and negation look the same.
    """

    overstaying: bool = False
    no_destination_scan: bool = False
    wrong_zone_scan: bool = False
    partial_exit: bool = False
    restricted: bool = False
    host_not_acked: bool = False


class InsideRow(BaseModel):
    """One person on campus. SPEC section 10.

    Rows arrive sorted by entry_at ascending - longest inside first - and that
    is the ONLY ordering. `flag_count` is there to be read, never to sort by:
    section 10 says flags only, no ranking.
    """

    visit_id: str
    visitor_name: str | None = None
    people: list[PersonOut] = Field(default_factory=list)

    host_name: str | None = None
    host_phone: str | None = Field(
        default=None, description="So security can call the host without escalating."
    )
    host_department: str | None = None

    purpose: str | None = None
    meeting_zone: str | None = None

    entry_at: datetime | None = None
    minutes_inside: int | None = None
    valid_to: datetime | None = None

    flags: VisitFlags
    flag_count: int = 0


class ExceptionRow(BaseModel):
    """One line on one exception list.

    `detail` says WHY this visit is on this list, in words. A list of visit ids
    tells security nothing they can act on at two in the morning.
    """

    visit_id: str
    visitor_name: str | None = None
    host_name: str | None = None
    entry_at: datetime | None = None
    detail: str


class ExceptionsResponse(BaseModel):
    """Five separate, unmerged, unranked lists. SPEC section 10.

    A visit may appear in several. They are not merged into one feed because
    merging would mean deciding that overstaying outranks a wrong-zone scan,
    and nothing in this system knows that.

    Two keys use section 10's names rather than section 11's flag names -
    `wrong_zone` and `awaiting_host_ack` are the same conditions section 11
    calls `wrong_zone_scan` and `host_not_acked`.
    """

    overstaying: list[ExceptionRow] = Field(default_factory=list)
    no_destination_scan: list[ExceptionRow] = Field(default_factory=list)
    wrong_zone: list[ExceptionRow] = Field(default_factory=list)
    partial_exit: list[ExceptionRow] = Field(default_factory=list)
    awaiting_host_ack: list[ExceptionRow] = Field(default_factory=list)


class DepartmentAverage(BaseModel):
    """An average with its sample size attached, because an average over one
    visit is not an average."""

    average_minutes: float
    sample_size: int


class HonestyResponse(BaseModel):
    """Counts, not charts. SPEC section 10.

    EVERY FIELD IS ALWAYS RETURNED, zero or empty where this build has no
    possible source. `unavailable` names each empty field and says why - a zero
    meaning "this never happened" and a zero meaning "nothing here can record
    it" are different facts, and this panel exists to keep them apart.
    """

    as_of: str

    closed_without_exit_scan: int = 0
    currently_overstaying: int = 0
    wrong_zone_scans_today: int = 0
    entries_made_offline: int = 0

    restricted_admissions_by_approver: dict[str, int] = Field(default_factory=dict)
    walk_ins_denied_after_escalation: int = 0

    average_host_approval_minutes_by_department: dict[str, DepartmentAverage] = Field(
        default_factory=dict
    )
    average_host_ack_minutes_by_department: dict[str, DepartmentAverage] = Field(
        default_factory=dict
    )

    unavailable: dict[str, str] = Field(
        default_factory=dict,
        description="Field name -> why it is empty. Read this before quoting a zero.",
    )
