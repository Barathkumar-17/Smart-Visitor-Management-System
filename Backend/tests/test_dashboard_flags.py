"""The six derived warning flags.

These decide what security sees. Getting one wrong shows an empty exceptions
list on a campus with a problem on it, or the reverse - and neither failure
announces itself, which is why they are worth testing directly rather than
only through the dashboards.

Every flag is computed from a visit and its scan events, so these tests build
both by hand and never touch the store.
"""

from datetime import timedelta

from app.core import clock
from app.core.config import ACK_WINDOW, NO_SCAN_WINDOW
from app.services import dashboard_service
from app.store.entities import ScanEvent, Visit


def _visit(**overrides) -> Visit:
    """A visit that raises no flags, so each test changes exactly one thing."""
    now = clock.now()
    base = dict(
        id="v_test",
        visitor_id="vr_test",
        host_id="h_test",
        purpose="unit test",
        scheduled_at=now,
        status="inside",
        person_count_expected=1,
        person_count_in=1,
        entry_at=now,
        host_acked_at=now,
        valid_from=now - timedelta(hours=1),
        valid_to=now + timedelta(hours=4),
    )
    base.update(overrides)
    return Visit(**base)


def _scan(kind: str, result: str, created_at=None) -> ScanEvent:
    event = ScanEvent(id="s_test", visit_id="v_test", kind=kind, result=result)
    if created_at is not None:
        event.created_at = created_at
    return event


def test_a_healthy_visit_raises_nothing():
    flags = dashboard_service.flags_for(_visit(), [_scan("zone", "ok")])
    assert not any(flags.values())


def test_every_flag_is_always_present_even_when_false():
    """A dashboard that omits the flags it did not raise makes absence and
    negation look identical."""
    flags = dashboard_service.flags_for(_visit(), [])
    assert set(flags) == set(dashboard_service.FLAG_NAMES)


# --- overstaying -------------------------------------------------------------


def test_overstaying_when_past_valid_to_with_no_exit():
    visit = _visit(valid_to=clock.now() - timedelta(minutes=1))
    assert dashboard_service.flags_for(visit, [])["overstaying"] is True


def test_not_overstaying_once_they_have_left():
    visit = _visit(
        valid_to=clock.now() - timedelta(minutes=1),
        exit_at=clock.now(),
        status="closed",
    )
    assert dashboard_service.flags_for(visit, [])["overstaying"] is False


def test_overstaying_needs_a_window_to_be_past():
    """A visit forced to `inside` without going through approve has no window,
    and cannot be shown to have overrun one."""
    assert dashboard_service.flags_for(_visit(valid_to=None), [])["overstaying"] is False


# --- no_destination_scan -----------------------------------------------------


def test_no_destination_scan_once_the_window_passes_with_no_checkpoint():
    visit = _visit(entry_at=clock.now() - NO_SCAN_WINDOW - timedelta(minutes=1))
    assert dashboard_service.flags_for(visit, [])["no_destination_scan"] is True


def test_a_successful_checkpoint_scan_clears_it():
    visit = _visit(entry_at=clock.now() - NO_SCAN_WINDOW - timedelta(minutes=1))
    flags = dashboard_service.flags_for(visit, [_scan("zone", "ok")])
    assert flags["no_destination_scan"] is False


def test_a_wrong_zone_scan_does_not_count_as_arriving():
    """They scanned somewhere, but not anywhere they were expected. The host
    still has no confirmation they arrived."""
    visit = _visit(entry_at=clock.now() - NO_SCAN_WINDOW - timedelta(minutes=1))
    flags = dashboard_service.flags_for(visit, [_scan("zone", "wrong_zone")])
    assert flags["no_destination_scan"] is True


def test_not_flagged_inside_the_window():
    visit = _visit(entry_at=clock.now() - NO_SCAN_WINDOW + timedelta(minutes=5))
    assert dashboard_service.flags_for(visit, [])["no_destination_scan"] is False


# --- host_not_acked ----------------------------------------------------------


def test_host_not_acked_once_the_window_passes():
    visit = _visit(host_acked_at=None, entry_at=clock.now() - ACK_WINDOW - timedelta(minutes=1))
    assert dashboard_service.flags_for(visit, [])["host_not_acked"] is True


def test_acknowledging_clears_it():
    visit = _visit(entry_at=clock.now() - ACK_WINDOW - timedelta(minutes=1))
    assert dashboard_service.flags_for(visit, [])["host_not_acked"] is False


def test_not_flagged_before_the_window_elapses():
    visit = _visit(host_acked_at=None, entry_at=clock.now())
    assert dashboard_service.flags_for(visit, [])["host_not_acked"] is False


# --- wrong_zone_scan ---------------------------------------------------------


def test_wrong_zone_scan_today():
    flags = dashboard_service.flags_for(_visit(), [_scan("zone", "wrong_zone")])
    assert flags["wrong_zone_scan"] is True


def test_a_wrong_zone_scan_from_yesterday_does_not_count():
    old = _scan("zone", "wrong_zone", created_at=clock.now() - timedelta(days=1))
    assert dashboard_service.flags_for(_visit(), [old])["wrong_zone_scan"] is False


def test_a_wrong_zone_result_on_a_gate_scan_is_not_a_zone_scan():
    flags = dashboard_service.flags_for(_visit(), [_scan("entry", "wrong_zone")])
    assert flags["wrong_zone_scan"] is False


# --- partial_exit ------------------------------------------------------------


def test_partial_exit_when_fewer_left_than_entered():
    visit = _visit(person_count_in=3, person_count_out=2)
    assert dashboard_service.flags_for(visit, [])["partial_exit"] is True


def test_a_full_exit_is_not_partial():
    visit = _visit(person_count_in=3, person_count_out=3)
    assert dashboard_service.flags_for(visit, [])["partial_exit"] is False


def test_more_out_than_in_is_not_a_partial_exit():
    """It is a discrepancy, and a different one. Nobody is still inside."""
    visit = _visit(person_count_in=3, person_count_out=4)
    assert dashboard_service.flags_for(visit, [])["partial_exit"] is False


def test_no_count_taken_is_not_a_partial_exit():
    visit = _visit(person_count_in=3, person_count_out=None)
    assert dashboard_service.flags_for(visit, [])["partial_exit"] is False


# --- flags that only apply while inside --------------------------------------


def test_a_closed_visit_raises_no_live_flags():
    """Every flag except wrong_zone_scan and restricted describes someone
    currently on campus. A closed visit is nobody's problem."""
    visit = _visit(
        status="closed",
        host_acked_at=None,
        entry_at=clock.now() - timedelta(days=1),
        valid_to=clock.now() - timedelta(hours=2),
        person_count_in=3,
        person_count_out=1,
    )
    flags = dashboard_service.flags_for(visit, [])
    assert flags["overstaying"] is False
    assert flags["no_destination_scan"] is False
    assert flags["host_not_acked"] is False
    assert flags["partial_exit"] is False


def test_restricted_is_read_straight_off_the_visit():
    assert dashboard_service.flags_for(_visit(restricted=True), [])["restricted"] is True
    assert dashboard_service.flags_for(_visit(), [])["restricted"] is False
