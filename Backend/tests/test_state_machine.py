"""The legal-move table.

Everything else in the system depends on this being right. A wrong edge here
surfaces as a mysterious 409 somewhere entirely different, which is exactly the
kind of bug an integration test finds late and a unit test finds immediately.
"""

import pytest

from app.core.errors import IllegalTransition
from app.services import visit_service
from app.store.entities import Visit

LEGAL = [
    ("requested", "approved"),
    ("requested", "rejected"),
    ("requested", "denied"),
    ("requested", "expired"),
    ("approved", "issued"),
    ("issued", "inside"),
    ("issued", "expired"),
    ("issued", "cancelled"),
    ("inside", "closed"),
    ("inside", "host_unavailable"),
]

ILLEGAL = [
    ("approved", "rejected"),
    ("inside", "denied"),
    ("inside", "expired"),
    ("closed", "inside"),
    ("host_unavailable", "closed"),
    ("inside", "requested"),
    ("requested", "inside"),
    ("rejected", "approved"),
    ("cancelled", "issued"),
    ("expired", "inside"),
]

TERMINAL = ["rejected", "cancelled", "denied", "host_unavailable", "expired", "closed"]


def _visit(status: str) -> Visit:
    """A bare visit in one status. Not saved - transition() persists it, and
    these tests are about the decision rather than the storage."""
    return Visit(
        id="v_test",
        visitor_id="vr_test",
        host_id="h_test",
        purpose="unit test",
        scheduled_at=None,
        status=status,
        person_count_expected=1,
    )


@pytest.mark.parametrize("frm,to", LEGAL)
def test_legal_moves_are_allowed(frm, to):
    visit = _visit(frm)
    visit_service.transition(visit, to, "test:unit")
    assert visit.status == to


@pytest.mark.parametrize("frm,to", ILLEGAL)
def test_illegal_moves_raise_and_leave_the_status_alone(frm, to):
    visit = _visit(frm)
    with pytest.raises(IllegalTransition):
        visit_service.transition(visit, to, "test:unit")
    assert visit.status == frm, "a refused transition must not half-apply"


def test_an_unknown_status_is_refused_like_any_other_illegal_move():
    """A typo is not a special case. Anything the table does not allow is a
    409, which keeps one rule instead of two."""
    visit = _visit("issued")
    with pytest.raises(IllegalTransition):
        visit_service.transition(visit, "insde", "test:unit")


@pytest.mark.parametrize("status", TERMINAL)
def test_terminal_statuses_have_no_way_out(status):
    assert visit_service.legal_moves(status) == []
    assert visit_service.is_terminal(status) is True


@pytest.mark.parametrize("status", ["requested", "approved", "issued", "inside"])
def test_live_statuses_are_not_terminal(status):
    assert visit_service.is_terminal(status) is False
    assert visit_service.legal_moves(status) != []


def test_nothing_can_re_enter_requested():
    """`requested` is a source and never a target, so a visit cannot be
    reopened by moving it backwards."""
    for source in visit_service.TRANSITIONS:
        assert "requested" not in visit_service.TRANSITIONS[source]


def test_the_derived_terminal_set_matches_the_repository_constant():
    """Two places know which statuses are terminal, and they must agree.

    visit_repo holds its own copy because repositories cannot import services,
    and the pass code6 rule depends on it. This is the check that stops the two
    drifting apart silently.
    """
    from app.repositories import visit_repo

    derived = {s for s in visit_service.TRANSITIONS if visit_service.is_terminal(s)}
    assert derived == set(visit_repo.TERMINAL_STATUSES)
