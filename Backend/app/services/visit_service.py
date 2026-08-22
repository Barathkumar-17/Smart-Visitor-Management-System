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

from app.core.errors import IllegalTransition
from app.repositories import visit_repo
from app.store.entities import Visit

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
