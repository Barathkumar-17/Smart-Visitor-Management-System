"""Group size, and the fallback code on a pass.

_resolve_person_count has five distinct behaviours in a dozen lines, which is
exactly the shape that breaks quietly when somebody edits it later.
"""

import pytest

from app.core.config import MAX_LINKED_COMPANIONS
from app.core.errors import CompanionLimitExceeded, InvalidRequest
from app.repositories import pass_repo
from app.services import pass_service
from app.services.visit_service import _resolve_person_count


class _Companion:
    """Stands in for one entry of companions[] - only the count matters here."""


def _companions(n: int) -> list:
    return [_Companion() for _ in range(n)]


# --- group size --------------------------------------------------------------


def test_neither_field_means_one_person():
    assert _resolve_person_count(None, None) == 1


def test_companions_add_to_the_accountable_visitor():
    """THE OFF-BY-ONE THAT MATTERS. Three companions is a group of four, and
    four is what the guard counts at the gate."""
    assert _resolve_person_count(_companions(3), None) == 4


def test_a_person_count_is_taken_as_the_total():
    assert _resolve_person_count(None, 8) == 8


def test_the_companion_cap_counts_companions_not_the_group():
    """Four companions is legal and makes a group of five. The limit is on
    named, photographed people, not on how many walk in."""
    assert _resolve_person_count(_companions(MAX_LINKED_COMPANIONS), None) == (
        MAX_LINKED_COMPANIONS + 1
    )
    with pytest.raises(CompanionLimitExceeded):
        _resolve_person_count(_companions(MAX_LINKED_COMPANIONS + 1), None)


def test_supplying_both_is_refused():
    """They would disagree about the group size and nothing says which wins."""
    with pytest.raises(InvalidRequest):
        _resolve_person_count(_companions(2), 5)


def test_a_group_of_nobody_is_refused():
    with pytest.raises(InvalidRequest):
        _resolve_person_count(None, 0)


def test_an_empty_companion_list_is_not_the_same_as_omitting_it():
    """[] is a positive statement that nobody is coming along, and still
    describes one person."""
    assert _resolve_person_count([], None) == 1


# --- the 6-digit fallback code ----------------------------------------------


def test_code6_is_six_digits(store):
    code = pass_service.generate_code6()
    assert len(code) == 6 and code.isdigit()


def test_code6_may_start_with_a_zero(store):
    """Generated as a zero-padded string, never an int - 001234 must survive
    being typed into a keypad."""
    codes = {pass_service.generate_code6() for _ in range(400)}
    assert all(len(c) == 6 for c in codes)


def test_code6_avoids_every_active_pass(store):
    """The whole point: a collision would admit the wrong visitor on a code
    the guard typed in good faith."""
    active = {p.code6 for p in pass_repo.list_active()}
    assert active, "the seed should leave at least one active pass to collide with"
    for _ in range(200):
        assert pass_service.generate_code6() not in active
