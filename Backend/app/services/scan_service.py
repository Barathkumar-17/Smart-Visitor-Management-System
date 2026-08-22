"""Gate entry, zone and exit scans.

TWO RULES GOVERN EVERYTHING IN THIS FILE.

1. A ScanEvent is written for EVERY attempt, successful or not. The design
   calls this the most important collection in the system, and says a later
   scoring phase's feasibility depends on its completeness now. Failures are
   data, not errors to discard.

2. NO SCAN EVER RAISES for a business outcome. Every entry point returns its
   result, and the router turns that into a 200 carrying an explicit boolean.
   a scan that raised would tempt a caller to abandon the
   request before the event was written.

Phase 6 implements gate entry and Phase 9 the zone scan. Both end at _record()
below, which is the single writer; exit (Phase 10) will too.
"""

import logging

from app.core import clock
from app.core.errors import InvalidRequest
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
    scans produce - the design requires that explicitly.
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


def people_for(visit) -> list[dict]:
    """Every linked person on a visit, visitor first.

    Public because the dashboard renders the same faces the guard sees, and two
    definitions of "who is on this visit" would drift apart.

    This is what the guard compares against the faces in front of them, so it
    leads the response. Refs only, never base64.
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
    """The gate scan.

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
    response and the event, and the visitor is admitted anyway - the design forbids ever blocking on one. The count is evidence, not a gate.
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
    # the SCANNED visit is left completely untouched, still
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
        "people": people_for(visit),
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


def _zone_label(zone) -> str | None:
    return f"{zone.code} - {zone.name}" if zone else None


def _zone_labels(zone_ids: list[str]) -> list[str]:
    """Zone ids rendered for a screen. The dashboard and the guard both want to
    read where someone may go, not a list of z_4-style keys."""
    labels = []
    for zone_id in zone_ids:
        zone = zone_repo.get(zone_id)
        labels.append(_zone_label(zone) or zone_id)
    return labels


def zone_scan(
    zone_code: str,
    payload: dict | None = None,
    signature: str | None = None,
    code6: str | None = None,
) -> dict:
    """A checkpoint scan somewhere inside the campus.

    THIS ENDPOINT NEVER BLOCKS ANYONE. The design says so outright: it
    records and returns what happened. There is no barrier here to hold shut -
    the person is already inside - so refusing would achieve nothing except
    losing the evidence that they were somewhere unexpected.

    allowed_zones IS READ FRESH FROM THE VISIT, never from the QR. That single
    line is the whole point of the pointer-not-payload design in the design: a host moves the meeting point, the visitor's QR does not change by one
    byte, and the very next scan at the new zone comes back ok while the old
    one starts flagging.

    Outcomes, in the order they are decided:

      unknown zone_code   -> InvalidRequest (400). The design decides this
                             one. There is no zone to record an event against.
      signature fails     -> bad_signature, no event - no trustworthy visit id
      visit not `inside`  -> wrong_status, event written, NOBODY notified
                             (decided explicitly)
      zone in the list    -> ok, host notified
      zone not in list    -> wrong_zone, security notified

    TWO CHECKS THE GATE MAKES AND THIS DELIBERATELY DOES NOT. Revocation is not
    checked, because the design says revoking prevents future ENTRY scans
    and does not eject anyone already inside. The pass window is not checked
    either: the design's zone block decides exactly two outcomes and
    the design's list adds one more, and inventing an `expired` result would
    turn every checkpoint into an alarm for a visitor whose overstay the
    dashboard already reports.
    """
    zone = zone_repo.find_by_code(zone_code)
    if zone is None:
        # unknown zone code is InvalidRequest. Unlike every
        # other outcome here this one raises, because with no zone resolved
        # there is nowhere to attach a ScanEvent - the scanner sent something
        # this system has never heard of.
        raise InvalidRequest(
            f"Unknown zone code {zone_code}",
            {"zone_code": zone_code, "field": "zone_code"},
        )

    issued, lookup = pass_service.resolve_scan(payload, signature, code6)

    if lookup in ("bad_signature", "not_found"):
        log.warning("zone scan at %s rejected: pass did not resolve (%s)", zone_code, lookup)
        return {
            "ok": False,
            "result": "bad_signature",
            "message": "No active pass matches this code or payload.",
            "scanned_zone": _zone_label(zone),
        }

    visit = visit_repo.get_or_404(issued.visit_id)
    visitor = visitor_repo.get(visit.visitor_id)
    host = host_repo.get(visit.host_id)

    base = {
        "visit_id": visit.id,
        "visitor_name": visitor.name if visitor else None,
        "host_name": host.name if host else None,
        "purpose": visit.purpose,
        "scanned_zone": _zone_label(zone),
        "meeting_zone": _zone_label(zone_repo.get(visit.meeting_zone_id))
        if visit.meeting_zone_id
        else None,
        "allowed_zones": _zone_labels(visit.allowed_zones),
        "people": people_for(visit),
    }

    # --- not inside ---------------------------------------------------------
    # verbatim: 200, result wrong_status, the event is still
    # written, and nobody is notified. A visit that never entered cannot be
    # confirmed as having arrived anywhere.
    if visit.status != "inside":
        event = _record(visit.id, "zone", "wrong_status", zone_id=zone.id)
        return {
            **base,
            "ok": False,
            "result": "wrong_status",
            "message": f"Visit {visit.id} is {visit.status}, not inside. "
            "Nobody has entered on this pass.",
            "scan_event_id": event.id,
        }

    # --- the fresh read -----------------------------------------------------
    allowed = zone.id in visit.allowed_zones

    if allowed:
        event = _record(visit.id, "zone", "ok", zone_id=zone.id)
        if host is not None and visitor is not None:
            notifications.notify_host(
                host,
                f"{visitor.name} scanned in at {_zone_label(zone)} for visit {visit.id}.",
            )
        return {
            **base,
            "ok": True,
            "result": "ok",
            "message": f"{visitor.name if visitor else 'Visitor'} is expected here.",
            "scan_event_id": event.id,
        }

    event = _record(visit.id, "zone", "wrong_zone", zone_id=zone.id)
    notifications.notify_security(
        f"Wrong-zone scan: visit {visit.id} scanned at {_zone_label(zone)}, "
        f"which is not on the pass. Allowed: {', '.join(base['allowed_zones']) or 'nothing'}."
    )
    return {
        **base,
        "ok": False,
        "result": "wrong_zone",
        "message": f"{visitor.name if visitor else 'This visitor'} is not cleared for "
        f"{_zone_label(zone)}. Security has been notified.",
        "scan_event_id": event.id,
    }


def gate_exit(
    payload: dict | None = None,
    signature: str | None = None,
    code6: str | None = None,
    vehicle_plate_out: str | None = None,
    person_count_out: int | None = None,
) -> dict:
    """The exit scan. One scan, and it never blocks.

    The photos are shown again and the plate is compared against what actually
    entered, because the question at the barrier is whether the people and the
    vehicle leaving are the ones that arrived.

    THE COUNT DECIDES WHETHER THE VISIT CLOSES:

      out == in   -> inside -> closed, exit_at set
      out <  in   -> the visit STAYS `inside`, security is told, and the
                     partial_exit flag derives itself from
                     person_count_out being less than person_count_in. exit_at
                     is deliberately NOT set - people are still on campus, and
                     stamping an exit time would silence the overstay flag too.
                     End-of-day close-out resolves it.
      out >  in   -> record count_mismatch and close normally.
                     Never block. The count is evidence, not a gate.

    Omitting person_count_out is read as a full exit, exactly as omitting
    person_count_in at the gate is read as no mismatch. A guard who did not
    count has not reported a discrepancy.

    TWO CHECKS THIS DOES NOT MAKE. Revocation is not one, because the design says in as many words that a revoked pass on a visit already inside does
    not eject anyone and that exit still works. Neither is the pass window: an
    overstaying visitor is precisely the person who most needs to be able to
    leave, and refusing them would strand them inside the record forever.
    """
    issued, lookup = pass_service.resolve_scan(payload, signature, code6)

    if lookup in ("bad_signature", "not_found"):
        log.warning("gate exit rejected: pass did not resolve (%s)", lookup)
        return {
            "exited": False,
            "result": "bad_signature",
            "message": "No active pass matches this code or payload.",
            "visit_status": None,
        }

    visit = visit_repo.get_or_404(issued.visit_id)
    visitor = visitor_repo.get(visit.visitor_id)
    host = host_repo.get(visit.host_id)

    if visit.status != "inside":
        event = _record(
            visit.id, "exit", "wrong_status", person_count_recorded=person_count_out
        )
        return {
            "exited": False,
            "result": "wrong_status",
            "message": f"Visit {visit.id} is {visit.status}, not inside. "
            "There is nobody to sign out.",
            "people": people_for(visit),
            "visit_id": visit.id,
            "visitor_name": visitor.name if visitor else None,
            "visit_status": visit.status,
            "scan_event_id": event.id,
        }

    # What ACTUALLY entered, not what was declared weeks ago - the gate stores
    # the arriving plate for exactly this comparison. Falls back to the
    # expected group size when the guard took no count on the way in.
    expected_plate = visit.vehicle_plate_in
    baseline = (
        visit.person_count_in
        if visit.person_count_in is not None
        else visit.person_count_expected
    )

    plate_mismatch = bool(
        vehicle_plate_out and expected_plate and vehicle_plate_out != expected_plate
    )
    short = person_count_out is not None and person_count_out < baseline
    count_mismatch = person_count_out is not None and person_count_out != baseline

    visit.vehicle_plate_out = vehicle_plate_out
    visit.person_count_out = person_count_out

    if short:
        # Stays inside. No exit_at: see the docstring - the overstay flag in
        # the design keys off exit_at being null, and some of this group
        # is still on campus.
        visit_repo.save(visit)
        event = _record(
            visit.id,
            "exit",
            "ok",
            plate_mismatch=plate_mismatch,
            count_mismatch=True,
            person_count_recorded=person_count_out,
        )
        notifications.notify_security(
            f"Partial exit on visit {visit.id}: {person_count_out} of {baseline} left. "
            f"{baseline - person_count_out} still inside. Resolve at close-out."
        )
        message = (
            f"{person_count_out} of {baseline} signed out. "
            f"{baseline - person_count_out} still inside - the visit stays open."
        )
    else:
        visit_service.transition(visit, "closed", "guard:u_guard")
        visit.exit_at = clock.now()
        visit_repo.save(visit)
        event = _record(
            visit.id,
            "exit",
            "ok",
            plate_mismatch=plate_mismatch,
            count_mismatch=count_mismatch,
            person_count_recorded=person_count_out,
        )
        if host is not None and visitor is not None:
            notifications.notify_host(
                host, f"{visitor.name} has signed out. Visit {visit.id} is closed."
            )
        message = f"Signed out. Visit {visit.id} is closed."

    if plate_mismatch or (count_mismatch and not short):
        notifications.notify_security(
            f"Visit {visit.id} exited with "
            f"{'plate' if plate_mismatch else ''}"
            f"{' and ' if plate_mismatch and count_mismatch else ''}"
            f"{'headcount' if count_mismatch else ''} mismatch."
        )

    return {
        "exited": not short,
        "result": "ok",
        "message": message,
        "people": people_for(visit),
        "vehicle": {
            "expected": expected_plate,
            "presented": vehicle_plate_out,
            "mismatch": plate_mismatch,
        },
        "headcount": {
            "expected": baseline,
            "recorded": person_count_out,
            "mismatch": count_mismatch,
        },
        "visit_id": visit.id,
        "visitor_name": visitor.name if visitor else None,
        "host_name": host.name if host else None,
        "partial_exit": short,
        "still_inside": (baseline - person_count_out) if short else 0,
        "visit_status": visit.status,
        "exit_at": visit.exit_at,
        "scan_event_id": event.id,
    }
