"""Gate entry, zone and exit scans. SPEC sections 10 and 14.

TWO RULES GOVERN EVERYTHING IN THIS FILE.

1. A ScanEvent is written for EVERY attempt, successful or not. SPEC section 6
   calls this the most important collection in the system, and says a later
   scoring phase's feasibility depends on its completeness now. Failures are
   data, not errors to discard.

2. NO SCAN EVER RAISES for a business outcome. Every entry point returns its
   result, and the router turns that into a 200 carrying an explicit boolean.
   SPEC section 8: a scan that raised would tempt a caller to abandon the
   request before the event was written.

Phase 6 implements gate entry. Zone scans (Phase 9) and exit (Phase 10) reuse
_record() below, which is the single writer.
"""

import logging

from app.core import clock
from app.integrations import notifications
from app.repositories import (
    companion_repo,
    host_repo,
    scan_repo,
    visit_repo,
    visitor_repo,
    zone_repo,
)
from app.services import pass_service, visit_service
from app.store import ids
from app.store.entities import ScanEvent

log = logging.getLogger(__name__)


def list_for_visit(visit_id: str) -> list[ScanEvent]:
    """Every scan attempt against one visit, oldest first. Includes failures."""
    return scan_repo.list_by_visit(visit_id)


def _record(
    visit_id: str,
    kind: str,
    result: str,
    zone_id: str | None = None,
    plate_mismatch: bool = False,
    count_mismatch: bool = False,
    person_count_recorded: int | None = None,
) -> ScanEvent:
    """The single ScanEvent writer. Every scan path in the system ends here.

    Also used by the seed loader, so seeded history has exactly the shape live
    scans produce - SPEC section 13 requires that explicitly.
    """
    event = scan_repo.add(
        ScanEvent(
            id=ids.next_id("scan_event"),
            visit_id=visit_id,
            kind=kind,
            result=result,
            zone_id=zone_id,
            plate_mismatch=plate_mismatch,
            count_mismatch=count_mismatch,
            person_count_recorded=person_count_recorded,
        )
    )
    log.info(
        "scan %s: visit=%s kind=%s result=%s%s%s",
        event.id,
        visit_id,
        kind,
        result,
        " PLATE_MISMATCH" if plate_mismatch else "",
        " COUNT_MISMATCH" if count_mismatch else "",
    )
    return event


def _people_for(visit) -> list[dict]:
    """Every linked person on a visit, visitor first.

    This is what the guard compares against the faces in front of them, so it
    leads the response. Refs only, never base64 (SPEC section 16.5).
    """
    visitor = visitor_repo.get(visit.visitor_id)
    people = []

    if visitor is not None:
        people.append(
            {
                "role": "visitor",
                "name": visitor.name,
                "photo_ref": visitor.photo_ref,
                "id_last4": visitor.id_last4,
            }
        )

    for companion in companion_repo.list_by_visit(visit.id):
        people.append(
            {
                "role": "companion",
                "name": companion.name,
                "photo_ref": companion.photo_ref,
                "id_last4": None,
            }
        )

    return people


def _refusal(result: str, message: str, visit_id: str | None, event_id: str | None) -> dict:
    """A refused entry. Still 200 at the router, still carries its outcome."""
    return {
        "admitted": False,
        "result": result,
        "message": message,
        "visit_id": visit_id,
        "scan_event_id": event_id,
    }


def gate_entry(
    payload: dict | None = None,
    signature: str | None = None,
    code6: str | None = None,
    vehicle_plate: str | None = None,
    person_count_in: int | None = None,
    entered_offline: bool = False,
    authorised_by: str | None = None,
) -> dict:
    """The gate scan. SPEC section 10.

    FIVE CHECKS, IN THIS ORDER, and the order matters - each one presumes the
    previous passed:

      1. signature verifies (or code6 resolves)  -> bad_signature
      2. pass not revoked                        -> revoked
      3. visit status is `issued`                -> wrong_status
      4. now is inside the window                -> expired
      5. visitor not already inside elsewhere    -> already_inside

    Any failure writes a ScanEvent and returns admitted false. None of them
    raises.

    A plate or headcount mismatch is NOT a failure. It is recorded on both the
    response and the event, and the visitor is admitted anyway - SPEC section
    10 forbids ever blocking on one. The count is evidence, not a gate.
    """
    # --- 1. signature or code6 ---------------------------------------------
    issued, lookup = pass_service.resolve_scan(payload, signature, code6)

    if lookup == "bad_signature":
        # No pass resolved, so there is no visit to write the event against.
        # A visit_id from an unverified payload cannot be trusted enough to
        # attach an event to it.
        log.warning("gate entry rejected: signature did not verify")
        return _refusal(
            "bad_signature",
            "Signature did not verify. This pass was not issued by this system, "
            "or has been altered.",
            None,
            None,
        )

    if lookup == "not_found":
        log.warning("gate entry rejected: no active pass matched")
        return _refusal(
            "bad_signature", "No active pass matches this code or payload.", None, None
        )

    visit = visit_repo.get_or_404(issued.visit_id)

    # --- 2. not revoked -----------------------------------------------------
    if issued.revoked_at is not None:
        event = _record(visit.id, "entry", "revoked", person_count_recorded=person_count_in)
        notifications.notify_security(
            f"Revoked pass presented at the gate for visit {visit.id}."
        )
        return _refusal(
            "revoked",
            f"This pass was revoked at {clock.readable(issued.revoked_at)}.",
            visit.id,
            event.id,
        )

    # --- 3. status is `issued` ---------------------------------------------
    if visit.status != "issued":
        event = _record(
            visit.id, "entry", "wrong_status", person_count_recorded=person_count_in
        )
        return _refusal(
            "wrong_status",
            f"Visit {visit.id} is {visit.status}, not issued. Nothing to admit.",
            visit.id,
            event.id,
        )

    # --- 4. within the window ----------------------------------------------
    # Skipped when no window is set: a visit forced to `issued` through
    # /dev/transition never went through approve and has nothing to violate.
    now = clock.now()
    if visit.valid_from and visit.valid_to and not (visit.valid_from <= now <= visit.valid_to):
        event = _record(visit.id, "entry", "expired", person_count_recorded=person_count_in)
        return _refusal(
            "expired",
            f"Outside the pass window. Valid {clock.readable(visit.valid_from)} "
            f"to {clock.readable(visit.valid_to)}.",
            visit.id,
            event.id,
        )

    # --- 5. not already inside on another visit -----------------------------
    # SPEC section 14: the SCANNED visit is left completely untouched, still
    # `issued`, and the event is written against IT rather than against the
    # visit the person is currently inside on.
    elsewhere = visit_repo.find_inside_for_visitor(visit.visitor_id, exclude_visit_id=visit.id)
    if elsewhere is not None:
        event = _record(
            visit.id, "entry", "already_inside", person_count_recorded=person_count_in
        )
        notifications.notify_security(
            f"Visitor already inside on {elsewhere.id} presented pass for {visit.id}."
        )
        return _refusal(
            "already_inside",
            f"This visitor is already inside on visit {elsewhere.id}.",
            visit.id,
            event.id,
        )

    # --- admitted -----------------------------------------------------------
    # Captured BEFORE the record is updated below. The guard's screen has to
    # show what was DECLARED against what turned up, and overwriting first
    # would make the two read identical while still flagging a mismatch.
    expected_plate = visit.vehicle_plate_in

    plate_mismatch = bool(vehicle_plate and expected_plate and vehicle_plate != expected_plate)
    count_mismatch = bool(
        person_count_in is not None and person_count_in != visit.person_count_expected
    )

    visit_service.transition(visit, "inside", "guard:u_guard")

    visit.entry_at = now
    # Store the plate that ACTUALLY arrived, so the exit comparison at Phase 10
    # is against what entered rather than against what was declared weeks ago.
    # The declared value survives on the ScanEvent as plate_mismatch.
    if vehicle_plate:
        visit.vehicle_plate_in = vehicle_plate
    visit.person_count_in = person_count_in
    visit.entered_offline = entered_offline
    visit.authorised_by = authorised_by
    visit_repo.save(visit)

    event = _record(
        visit.id,
        "entry",
        "ok",
        plate_mismatch=plate_mismatch,
        count_mismatch=count_mismatch,
        person_count_recorded=person_count_in,
    )

    host = host_repo.get(visit.host_id)
    visitor = visitor_repo.get(visit.visitor_id)
    if host is not None and visitor is not None:
        notifications.notify_host(
            host, f"{visitor.name} has arrived at the gate for visit {visit.id}."
        )
    if plate_mismatch or count_mismatch:
        notifications.notify_security(
            f"Visit {visit.id} admitted with "
            f"{'plate' if plate_mismatch else ''}"
            f"{' and ' if plate_mismatch and count_mismatch else ''}"
            f"{'headcount' if count_mismatch else ''} mismatch."
        )

    zone = zone_repo.get(visit.meeting_zone_id) if visit.meeting_zone_id else None

    return {
        "admitted": True,
        "result": "ok",
        "message": f"Admitted. {visitor.name if visitor else 'Visitor'} may proceed.",
        "people": _people_for(visit),
        "vehicle": {
            "expected": expected_plate,
            "presented": vehicle_plate,
            "mismatch": plate_mismatch,
        },
        "headcount": {
            "expected": visit.person_count_expected,
            "recorded": person_count_in,
            "mismatch": count_mismatch,
        },
        "visit_id": visit.id,
        "visitor_name": visitor.name if visitor else None,
        "host_name": host.name if host else None,
        "host_phone": host.phone if host else None,
        "purpose": visit.purpose,
        "meeting_zone": f"{zone.code} - {zone.name}" if zone else None,
        "valid_until": visit.valid_to,
        "entry_at": visit.entry_at,
        "restricted": visit.restricted,
        "scan_event_id": event.id,
    }
