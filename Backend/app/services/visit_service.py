"""Visit rules and transition(), the state machine. SPEC section 8.

EVERY status change in this system passes through transition(). Routers, the
scan service, the scheduler jobs and close-out all call it, and NO CODE OUTSIDE
THIS FUNCTION ASSIGNS visit.status - that is a hard rule in SPEC section 15.

The legal moves live in TRANSITIONS below as data rather than as branching, so
the table can be read against SPEC section 8 line by line. Building it that way
also means three of the six "specifically illegal" moves that section calls out
need no rule of their own - they are impossible by construction. See the note
under TRANSITIONS.
"""

import logging
from datetime import date as _date
from zoneinfo import ZoneInfo

from app.core.config import LOCAL_TZ, MAX_LINKED_COMPANIONS
from app.core.errors import (
    CompanionLimitExceeded,
    IllegalTransition,
    InvalidRequest,
    VisitorAlreadyInside,
)
from app.integrations import notifications, storage
from app.repositories import (
    companion_repo,
    host_repo,
    visit_repo,
    visitor_repo,
    zone_repo,
)
from app.services import visitor_service
from app.store import ids
from app.store.entities import Companion, Visit

log = logging.getLogger(__name__)


# --- The legal-move table, SPEC section 8 -----------------------------------
#
# Read this against the table in SPEC section 8. Every status is a key,
# including the six terminal ones, which map to an empty set.
#
# Three of the "specifically illegal, because they are plausible guesses" moves
# in section 8 fall out of this shape rather than needing to be listed:
#
#   closed -> anything          the terminal rows below are empty
#   host_unavailable -> closed  likewise - it IS the closure, not a step to one
#   anything -> requested       `requested` appears as a SOURCE and never as a
#                               target, so nothing can re-enter it
#
# The other three (approved -> rejected, inside -> denied, inside -> expired)
# are simply absent from their source rows. Adding one here would silently make
# it legal everywhere, which is exactly why the table is in one place.

TRANSITIONS: dict[str, frozenset[str]] = {
    # Host approves, host rejects, fallback authority denies after escalation,
    # or scheduled_at passes with nobody acting on it.
    "requested": frozenset({"approved", "rejected", "denied", "expired"}),
    # Automatic, in the same call as approve - the pass is generated.
    "approved": frozenset({"issued"}),
    # Gate entry succeeds, the window lapses unscanned, or the host calls it off.
    "issued": frozenset({"inside", "expired", "cancelled"}),
    # Exit scan with a full count or end-of-day close-out; or the
    # acknowledgement chain runs out and nobody was ever reachable.
    "inside": frozenset({"closed", "host_unavailable"}),
    # --- terminal, SPEC section 8: six of them, nothing leaves ---
    "rejected": frozenset(),
    "cancelled": frozenset(),
    "denied": frozenset(),
    "host_unavailable": frozenset(),
    "expired": frozenset(),
    "closed": frozenset(),
}


def legal_moves(status: str) -> list[str]:
    """Where a visit in this status may go next. Empty for a terminal state."""
    return sorted(TRANSITIONS.get(status, frozenset()))


def is_terminal(status: str) -> bool:
    """True when no transition out of this status is legal.

    DERIVED from the table rather than listed separately, so a status cannot be
    terminal in one place and not in another.
    """
    return status in TRANSITIONS and not TRANSITIONS[status]


# The storage layer needs the same set: pass_repo.list_active() uses it to
# decide which passes a code6 must be unique among (SPEC section 9). It cannot
# import this service - repositories do not depend on services - so it holds
# its own literal set. Checking the two agree at import makes them impossible
# to drift apart without someone noticing immediately.
_derived_terminal = frozenset(s for s in TRANSITIONS if is_terminal(s))
if _derived_terminal != visit_repo.TERMINAL_STATUSES:
    raise RuntimeError(
        "Terminal statuses disagree between the state machine and the "
        f"repository layer. Table derives {sorted(_derived_terminal)}; "
        f"visit_repo.TERMINAL_STATUSES holds {sorted(visit_repo.TERMINAL_STATUSES)}. "
        "SPEC section 8 names six terminal states - fix whichever is wrong."
    )


def transition(visit: Visit, to_status: str, actor: str) -> Visit:
    """Move a visit to a new status, or raise. SPEC section 8.

    `actor` is a free-text audit string, never parsed, formatted "{role}:{id}"
    per SPEC section 16.2 - "faculty:h_2", "guard:u_guard",
    "system:job_expiry", "dev:forced". No entity in SPEC section 6 has a field
    to store it, so it goes to the log and nowhere else.

    THIS FUNCTION SETS `status` AND NOTHING ELSE. Not entry_at, not exit_at,
    not closed_reason. Those belong to whichever caller knows WHY the move is
    happening: the scan service stamps entry_at, close-out writes
    closed_reason. Section 6 makes the same point from the other direction for
    escalation stages - "Do not close a visit as a side effect of advancing a
    stage." Keeping this function to one field is what makes it safe to call
    from six different places.

    Raises IllegalTransition (409) for any move not in TRANSITIONS, including
    one whose target is not a real status at all.
    """
    from_status = visit.status
    allowed = TRANSITIONS.get(from_status, frozenset())

    if to_status not in allowed:
        # Covers three cases with one rule: a plausible-but-illegal move, a
        # move out of a terminal state, and a target that is not a status.
        log.warning(
            "REJECTED transition for visit %s: %s -> %s (by %s). Legal: %s",
            visit.id,
            from_status,
            to_status,
            actor,
            sorted(allowed) or "none - terminal",
        )
        raise IllegalTransition(
            f"Cannot move visit {visit.id} from {from_status} to {to_status}",
            {
                "visit_id": visit.id,
                "from": from_status,
                "to": to_status,
                "legal_moves": sorted(allowed),
            },
        )

    visit.status = to_status
    visit_repo.save(visit)

    log.info(
        "visit %s: %s -> %s by %s", visit.id, from_status, to_status, actor
    )
    return visit


# =============================================================================
# Phase 4 - pass request and approval. SPEC sections 10, 16.4, and 7 at approve.
# =============================================================================


def get_visit(visit_id: str) -> Visit:
    """One visit, or NotFound (404)."""
    return visit_repo.get_or_404(visit_id)


def list_companions(visit_id: str) -> list:
    """Everyone linked to a visit."""
    return companion_repo.list_by_visit(visit_id)


def _resolve_person_count(companions: list | None, person_count: int | None) -> int:
    """Work out person_count_expected. SPEC section 16.4, exactly.

    | body                    | expected            | companion records |
    | companions[] supplied   | len(companions) + 1 | one per companion |
    | person_count supplied   | that number, as-is  | none              |
    | neither                 | 1                   | none              |
    | both                    | InvalidRequest      | -                 |

    The number is always the TOTAL INCLUDING the accountable visitor (section
    14), which is what the guard's actual headcount is compared against.
    """
    if companions is not None and person_count is not None:
        raise InvalidRequest(
            "companions[] and person_count are mutually exclusive - supply one",
            {"companions": len(companions), "person_count": person_count},
        )

    if companions is not None:
        if len(companions) > MAX_LINKED_COMPANIONS:
            # Counts COMPANIONS ONLY, excluding the accountable visitor, so a
            # group of five is legal as 1 + 4. SPEC section 6.
            raise CompanionLimitExceeded(
                f"{len(companions)} companions supplied, limit is "
                f"{MAX_LINKED_COMPANIONS} (excluding the accountable visitor)",
                {"supplied": len(companions), "limit": MAX_LINKED_COMPANIONS},
            )
        return len(companions) + 1

    if person_count is not None:
        if person_count < 1:
            raise InvalidRequest(
                "person_count must be at least 1 - it includes the accountable visitor",
                {"person_count": person_count},
            )
        return person_count

    return 1


def create_visit(
    visitor_id: str,
    host_id: str,
    purpose: str,
    scheduled_at,
    vehicle_plate: str | None = None,
    companions: list | None = None,
    person_count: int | None = None,
) -> Visit:
    """Open a pre-registered pass request. Status `requested`. SPEC section 10.

    Raises VisitorAlreadyInside (409) when the visitor is inside on another
    visit. Note the deliberate split in SPEC section 8: that is a 409 here,
    where a visit is being CREATED, while SCANNING an already-inside visitor
    returns 200 with result `already_inside`. Same fact, two paths.
    """
    visitor = visitor_repo.get_or_404(visitor_id)
    host = host_repo.get_or_404(host_id)

    inside = visit_repo.find_inside_for_visitor(visitor_id)
    if inside is not None:
        raise VisitorAlreadyInside(
            f"Visitor {visitor_id} is already inside on visit {inside.id}",
            {"visitor_id": visitor_id, "inside_on_visit": inside.id},
        )

    expected = _resolve_person_count(companions, person_count)

    visit = visit_repo.save(
        Visit(
            id=ids.next_id("visit"),
            visitor_id=visitor.id,
            host_id=host_id,
            purpose=purpose,
            scheduled_at=scheduled_at,
            vehicle_plate_in=vehicle_plate,
            person_count_expected=expected,
            status="requested",
            origin="pre_registered",
        )
    )

    # Companion photos go through the storage stub like any other, so nothing
    # but the ref is held on the record. SPEC section 16.5.
    for entry in companions or []:
        companion_repo.save(
            Companion(
                id=ids.next_id("companion"),
                visit_id=visit.id,
                name=entry.name,
                photo_ref=storage.put(entry.photo_b64) if entry.photo_b64 else None,
            )
        )

    notifications.notify_host(
        host,
        f"New pass request {visit.id} from {visitor.name}, "
        f"{expected} person(s) expected. Purpose: {purpose}",
    )

    log.info(
        "visit %s requested by visitor %s for host %s, %d person(s) expected",
        visit.id,
        visitor.id,
        host_id,
        expected,
    )
    return visit


def list_visits(
    host_id: str | None = None,
    status: str | None = None,
    date: str | None = None,
) -> list[Visit]:
    """The faculty inbox. SPEC section 10.

    `date` filters on scheduled_at as a LOCAL_TZ calendar date (SPEC section
    11), not a UTC one - a visit at 02:00 IST belongs to that IST day, and
    comparing in UTC would file it under the previous one.
    """
    if host_id:
        visits = visit_repo.list_by_host(host_id, status)
    elif status:
        visits = visit_repo.list_by_status(status)
    else:
        visits = visit_repo.list_all()

    if date:
        try:
            wanted = _date.fromisoformat(date)
        except ValueError as exc:
            raise InvalidRequest("date must be YYYY-MM-DD", {"date": date}) from exc
        local = ZoneInfo(LOCAL_TZ)
        visits = [v for v in visits if v.scheduled_at.astimezone(local).date() == wanted]

    return sorted(visits, key=lambda v: v.scheduled_at)


def approve_visit(
    visit_id: str,
    meeting_zone_id: str,
    allowed_zones: list[str],
    valid_from,
    valid_to,
    vouch: bool = False,
) -> Visit:
    """Host approves. requested -> approved -> issued. SPEC section 10.

    TWO transitions in one call, deliberately: SPEC section 8 marks
    approved -> issued as "automatic, same call as approve", so `approved` is a
    state the visit passes through rather than rests in.

    The acting host is the visit's own host_id, not the caller - SPEC section
    16.1: the header establishes the ROLE, the path establishes the IDENTITY.

    NO PASS RECORD IS CREATED HERE. Signing is Phase 5, and a Pass needs a
    signature and a code6 that only that phase can produce. The visit reaches
    `issued` and Phase 5 fills in the pass behind it.
    """
    visit = visit_repo.get_or_404(visit_id)

    zone_repo.get_or_404(meeting_zone_id)
    for zone_id in allowed_zones:
        if zone_repo.get(zone_id) is None:
            raise InvalidRequest(
                f"Unknown zone {zone_id}",
                {"zone_id": zone_id, "field": "allowed_zones"},
            )

    if valid_to <= valid_from:
        raise InvalidRequest(
            "valid_to must be after valid_from",
            {"valid_from": valid_from.isoformat(), "valid_to": valid_to.isoformat()},
        )

    # The meeting point is always reachable - approving someone to a zone they
    # may not enter would flag a wrong-zone scan for doing what they were told.
    zones = list(dict.fromkeys([meeting_zone_id, *allowed_zones]))

    actor = f"faculty:{visit.host_id}"

    transition(visit, "approved", actor)

    visit.meeting_zone_id = meeting_zone_id
    visit.allowed_zones = zones
    visit.valid_from = valid_from
    visit.valid_to = valid_to
    visit.approved_by = actor
    visit_repo.save(visit)

    if vouch:
        # SPEC section 7: vouching happens ONLY here, at approval, through a
        # host. The origin decides whether standing is granted at all.
        visitor = visitor_repo.get_or_404(visit.visitor_id)
        visitor_service.apply_vouch(visitor, visit.host_id, visit.origin)

    transition(visit, "issued", actor)

    visitor = visitor_repo.get_or_404(visit.visitor_id)
    notifications.notify_visitor(
        visitor,
        f"Visit {visit.id} approved. Valid {valid_from.isoformat()} "
        f"to {valid_to.isoformat()}.",
    )

    return visit


def reject_visit(visit_id: str, reason: str) -> Visit:
    """Host rejects. Only legal while `requested` - the state machine enforces
    that, returning 409 from any other status. SPEC sections 8 and 10."""
    visit = visit_repo.get_or_404(visit_id)
    actor = f"faculty:{visit.host_id}"

    transition(visit, "rejected", actor)

    visit.approval_reason = reason
    visit_repo.save(visit)

    visitor = visitor_repo.get_or_404(visit.visitor_id)
    notifications.notify_visitor(visitor, f"Visit {visit.id} was rejected: {reason}")
    return visit


def cancel_visit(visit_id: str, reason: str) -> Visit:
    """Host calls off a visit already approved and issued. SPEC section 10.

    Legal only while `issued`, never once `inside` - again enforced by the
    state machine rather than by a status check here.

    DISTINCT FROM A SECURITY REVOKE, which sets revoked_at on the pass and
    leaves the visit status alone (SPEC section 8).
    """
    visit = visit_repo.get_or_404(visit_id)
    actor = f"faculty:{visit.host_id}"

    transition(visit, "cancelled", actor)

    visit.approval_reason = reason
    visit_repo.save(visit)

    visitor = visitor_repo.get_or_404(visit.visitor_id)
    notifications.notify_visitor(visitor, f"Visit {visit.id} was cancelled: {reason}")
    return visit
