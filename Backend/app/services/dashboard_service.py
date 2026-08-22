"""Read-time derived flags.

NOTHING IN THIS FILE IS STORED. Every flag is computed from the visit record
and its scan events at the moment it is asked for, using the definitions table and no other arithmetic. The design says why: a
stored flag and a derived one will drift apart, and the stored one will be the
wrong one - it was true when it was written and nobody went back.

That is also why this is the only file that reads flags. If a second definition
of `overstaying` appears anywhere else in the codebase, one of them is already
wrong.

WHAT THIS BUILD CANNOT PRODUCE. The scheduler is not implemented, so nothing
BECOMES an exception while you watch - the seeded visitors carry those states
from the start. The dashboards are correct either way, because they read the
data rather than the jobs. Nothing here fakes a job to compensate.
"""

import logging
from datetime import date as _date
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core import clock
from app.core.config import ACK_WINDOW, LOCAL_TZ, NO_SCAN_WINDOW
from app.repositories import host_repo, scan_repo, visit_repo, visitor_repo, zone_repo
from app.services import scan_service

log = logging.getLogger(__name__)


# The six flags table, in that order. Named here so the
# dashboards cannot silently disagree about which flags exist.
FLAG_NAMES: tuple[str,...] = (
    "overstaying",
    "no_destination_scan",
    "wrong_zone_scan",
    "partial_exit",
    "restricted",
    "host_not_acked",
)


def _today_local() -> _date:
    """The LOCAL_TZ calendar day containing clock.now().

    /dev/advance-clock moves what "today" means, which the design says is intended.
    """
    return clock.now_local().date()


def _is_today(moment: datetime | None) -> bool:
    if moment is None:
        return False
    return moment.astimezone(ZoneInfo(LOCAL_TZ)).date() == _today_local()


def flags_for(visit, scans: list | None = None) -> dict[str, bool]:
    """The six derived flags, transcribed exactly.

    The `is not None` guards are not extra rules: a visit forced to `inside` through /dev/transition never went
    through the gate and has no entry_at, and comparing a timestamp to None
    would raise rather than return false. A missing timestamp means the
    condition cannot be shown to hold, so the flag is false.
    """
    if scans is None:
        scans = scan_repo.list_by_visit(visit.id)

    now = clock.now()
    is_inside = visit.status == "inside"

    return {
        "overstaying": (
            is_inside and visit.exit_at is None and visit.valid_to is not None
            and now > visit.valid_to
        ),
        "no_destination_scan": (
            is_inside
            and not any(s.kind == "zone" and s.result == "ok" for s in scans)
            and visit.entry_at is not None
            and now > visit.entry_at + NO_SCAN_WINDOW
        ),
        "wrong_zone_scan": any(
            s.kind == "zone" and s.result == "wrong_zone" and _is_today(s.created_at)
            for s in scans
        ),
        "partial_exit": (
            is_inside
            and visit.person_count_out is not None
            and visit.person_count_in is not None
            and visit.person_count_out < visit.person_count_in
        ),
        "restricted": visit.restricted,
        "host_not_acked": (
            is_inside
            and visit.host_acked_at is None
            and visit.entry_at is not None
            and now > visit.entry_at + ACK_WINDOW
        ),
    }


def _zone_label(zone_id: str | None) -> str | None:
    zone = zone_repo.get(zone_id) if zone_id else None
    return f"{zone.code} - {zone.name}" if zone else None


def _minutes_since(moment: datetime | None) -> int | None:
    if moment is None:
        return None
    return int((clock.now() - moment).total_seconds() // 60)


def inside() -> list[dict]:
    """Who is on campus right now.

    SORTED BY entry_at ASCENDING, so the person who has been inside longest is
    at the top. That is the only ordering in the response - the design says
    "flags only, no ranking", so a visitor with four flags does not jump the
    queue over one who has simply been here since morning.
    """
    rows = []

    for visit in visit_repo.list_by_status("inside"):
        visitor = visitor_repo.get(visit.visitor_id)
        host = host_repo.get(visit.host_id)
        flags = flags_for(visit)

        rows.append(
            {
                "visit_id": visit.id,
                "visitor_name": visitor.name if visitor else None,
                "people": scan_service.people_for(visit),
                "host_name": host.name if host else None,
                "host_phone": host.phone if host else None,
                "host_department": host.department if host else None,
                "purpose": visit.purpose,
                "meeting_zone": _zone_label(visit.meeting_zone_id),
                "entry_at": visit.entry_at,
                "minutes_inside": _minutes_since(visit.entry_at),
                "valid_to": visit.valid_to,
                "flags": flags,
                "flag_count": sum(1 for raised in flags.values() if raised),
            }
        )

    # None sorts last: a visit inside with no entry_at is a /dev/transition
    # artefact, not someone who has been here since dawn.
    rows.sort(key=lambda r: (r["entry_at"] is None, r["entry_at"]))
    return rows


def _exception_row(visit, detail: str) -> dict:
    visitor = visitor_repo.get(visit.visitor_id)
    host = host_repo.get(visit.host_id)
    return {
        "visit_id": visit.id,
        "visitor_name": visitor.name if visitor else None,
        "host_name": host.name if host else None,
        "entry_at": visit.entry_at,
        "detail": detail,
    }


def exceptions() -> dict[str, list[dict]]:
    """Five lists, SEPARATE AND UNRANKED.

    A visit appears in every list whose condition it meets, and the lists are
    not merged into one ranked feed. The design is explicit about that,
    and it is a real decision rather than laziness: merging would require
    deciding that overstaying beats a wrong-zone scan, and nothing in the
    system knows that. Security reads five short lists instead.

    TWO KEYS ARE SPELLED DIFFERENTLY FROM THEIR FLAGS. The lists here are
    `wrong_zone` and `awaiting_host_ack`; the flags computed in flags_for()
    call the same two conditions `wrong_zone_scan` and `host_not_acked`. Same
    arithmetic, different labels, and both spellings are deliberate - the list
    names read as categories, the flag names read as statements about a visit.
    """
    lists: dict[str, list[dict]] = {name: [] for name in
                                    ("overstaying", "no_destination_scan", "wrong_zone",
                                     "partial_exit", "awaiting_host_ack")}

    for visit in visit_repo.list_all():
        scans = scan_repo.list_by_visit(visit.id)
        flags = flags_for(visit, scans)

        if flags["overstaying"]:
            over_by = _minutes_since(visit.valid_to)
            lists["overstaying"].append(
                _exception_row(visit, f"Past the pass window by {over_by} minutes.")
            )

        if flags["no_destination_scan"]:
            lists["no_destination_scan"].append(
                _exception_row(
                    visit,
                    f"Entered {_minutes_since(visit.entry_at)} minutes ago and has "
                    "reached no checkpoint. The absence is the signal.",
                )
            )

        if flags["wrong_zone_scan"]:
            zones = [
                _zone_label(s.zone_id)
                for s in scans
                if s.kind == "zone" and s.result == "wrong_zone" and _is_today(s.created_at)
            ]
            lists["wrong_zone"].append(
                _exception_row(visit, f"Scanned today at {', '.join(z for z in zones if z)}.")
            )

        if flags["partial_exit"]:
            still_in = visit.person_count_in - visit.person_count_out
            lists["partial_exit"].append(
                _exception_row(
                    visit,
                    f"{visit.person_count_out} of {visit.person_count_in} signed out. "
                    f"{still_in} still inside.",
                )
            )

        if flags["host_not_acked"]:
            lists["awaiting_host_ack"].append(
                _exception_row(
                    visit,
                    f"Inside {_minutes_since(visit.entry_at)} minutes; the host has not "
                    "confirmed availability.",
                )
            )

    return lists


def _average_minutes_by_department(pairs: list[tuple[str, float]]) -> dict[str, dict]:
    """Group durations by department, carrying the sample size.

    The sample size is returned because an average over one visit is not an
    average, and a panel that says "38 minutes" without saying "of one" invites
    exactly the false confidence this panel exists to avoid.
    """
    buckets: dict[str, list[float]] = {}
    for department, minutes in pairs:
        buckets.setdefault(department, []).append(minutes)

    return {
        department: {
            "average_minutes": round(sum(values) / len(values), 1),
            "sample_size": len(values),
        }
        for department, values in sorted(buckets.items())
    }


def honesty() -> dict:
    """Counts, not charts.

    EVERY FIELD IS ALWAYS RETURNED. A count this build cannot produce comes
    back as zero or an empty breakdown, never omitted - "A
    panel that drops the fields it cannot fill defeats its own purpose."

    `unavailable` names each empty field and says WHY it is empty, which is the
    same argument carried one step further. A zero that means "this never
    happened" and a zero that means "nothing in this build can record it" are
    different facts, and a panel about honesty should not conflate them.
    """
    visits = visit_repo.list_all()

    closed_without_exit = 0
    currently_overstaying = 0
    entries_offline = 0
    # RESTRICTED ADMISSIONS ARE STRUCTURALLY ZERO IN THIS BUILD, and this is a
    # decided position rather than an oversight. The count is of admissions
    # this system PERFORMED on restricted terms, and the only endpoint that
    # performs one is the fallback-authority decision, which is not built.
    # Seeded visitor C carries the restricted state so the dashboard flag has
    # something to render, but no admission ever took place - she is a fixture,
    # not a record of an act. Whoever builds fallback authority fills this in
    # by counting its own decisions; nothing else should.
    restricted_by_approver: dict[str, int] = {}
    walk_ins_denied = 0
    ack_pairs: list[tuple[str, float]] = []

    for visit in visits:
        if visit.status == "closed" and visit.exit_at is None:
            closed_without_exit += 1

        if flags_for(visit)["overstaying"]:
            currently_overstaying += 1

        if visit.entered_offline:
            entries_offline += 1

        if visit.origin == "walk_in" and visit.status == "denied":
            walk_ins_denied += 1

        if visit.host_acked_at is not None and visit.entry_at is not None:
            host = host_repo.get(visit.host_id)
            if host is not None:
                minutes = (visit.host_acked_at - visit.entry_at).total_seconds() / 60
                ack_pairs.append((host.department, minutes))

    wrong_zone_today = sum(
        1
        for event in scan_repo.list_all()
        if event.kind == "zone" and event.result == "wrong_zone" and _is_today(event.created_at)
    )

    return {
        "as_of": clock.readable(),
        "closed_without_exit_scan": closed_without_exit,
        "currently_overstaying": currently_overstaying,
        "wrong_zone_scans_today": wrong_zone_today,
        "entries_made_offline": entries_offline,
        "restricted_admissions_by_approver": restricted_by_approver,
        "walk_ins_denied_after_escalation": walk_ins_denied,
        "average_host_approval_minutes_by_department": {},
        "average_host_ack_minutes_by_department": _average_minutes_by_department(ack_pairs),
        "unavailable": {
            "average_host_approval_minutes_by_department":
                "No Visit field records WHEN a host approved. approved_by says who, "
                "created_at says when the request arrived, and nothing sits between "
                "them. Adding approved_at to the Visit entity is the whole fix.",
            "walk_ins_denied_after_escalation":
                "Walk-in registration and fallback authority are both unbuilt, so no "
                "visit can have origin walk_in or reach denied. "
                "This zero is true, not missing.",
            "restricted_admissions_by_approver":
                "Fallback authority is not built, so no admission on "
                "restricted terms is ever performed by this build. Seeded visitor C "
                "carries the restricted state for the dashboard flag to render, but "
                "she is a fixture rather than a record of an act. This zero is true.",
        },
    }
