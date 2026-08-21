"""Seed loader. SPEC section 13.

The prototype must be demoable the moment it starts, so this runs at startup
and again on every /dev/reset.

THIS FILE IS DELIBERATELY UNFINISHED. Some seeded records need capability that
arrives later - a signed pass needs Phase 5's signing, a scan event needs Phase
6's scan service. So it is written at Phase 1 and extended at Phases 5 and 6.
Records this build cannot yet produce are NOT faked here.

Seeded at Phase 1:  zones, hosts, visitor A (+ requested visit),
                    visitor C (+ fallback-admitted visit, already inside)
Added at Phase 5:   visitor B and her issued pass - needs signing
Added at Phase 6:   visitors D, E, F, and the scan events for C, D, E and F
                    - needs the scan service

Everything is created through a REPOSITORY, never by writing to a store dict,
so seeded records have exactly the shape live ones do.
"""

from datetime import timedelta

from app.core import clock
from app.core.config import RESTRICTED_VISIT_DURATION
from app.repositories import host_repo, visit_repo, visitor_repo, zone_repo
from app.store import ids, memory
from app.store.entities import Host, Visit, Visitor, Zone

# --- Zones ------------------------------------------------------------------
# The five from SPEC section 13.

ZONES: list[tuple[str, str]] = [
    ("MAIN", "Main Block"),
    ("LIB", "Library"),
    ("ADMIN", "Admin Block"),
    ("HOSTEL", "Hostel Gate"),
    ("DEPT", "Department Office"),
]

# --- Hosts ------------------------------------------------------------------
# Three across two departments, per SPEC section 13. The split is deliberate:
# Computer Science has TWO hosts so a department escalation has a real
# recipient to notify, and Mechanical Engineering has ONE so the "department
# with no other host" path in SPEC section 16.3 - where a notification is still
# written and the stage still advances - is reachable. Escalation is Phase 11
# and deferred, but the fixture it will need exists now.

HOSTS: list[tuple[str, str, str, str]] = [
    (
        "Dr. Anitha Rao",
        "Computer Science",
        "anitha.rao@mit.example.in",
        "+91-90000-10001",
    ),
    (
        "Prof. Vikram Menon",
        "Computer Science",
        "vikram.menon@mit.example.in",
        "+91-90000-10002",
    ),
    (
        "Dr. Sunita Pillai",
        "Mechanical Engineering",
        "sunita.pillai@mit.example.in",
        "+91-90000-10003",
    ),
]


def _seed_zones() -> dict[str, Zone]:
    by_code: dict[str, Zone] = {}
    for code, name in ZONES:
        zone = zone_repo.save(Zone(id=ids.next_id("zone"), code=code, name=name))
        by_code[code] = zone
    return by_code


def _seed_hosts() -> list[Host]:
    return [
        host_repo.save(
            Host(
                id=ids.next_id("host"),
                name=name,
                department=department,
                email=email,
                phone=phone,
            )
        )
        for name, department, email, phone in HOSTS
    ]


def _seed_visitor_a(hosts: list[Host]) -> None:
    """Visitor A - DigiLocker-verified, with a visit still `requested`.

    id_hash and id_last4 are normally set by the DigiLocker stub, which arrives
    at Phase 3. They are set directly here because CLAUDE.md requires A at
    Phase 1 and SPEC section 13 defines her as DigiLocker-verified; the values
    are inert data of exactly the shape that stub will produce.

    photo_ref is deliberately left null - see the note at the end of this file.
    """
    visitor = visitor_repo.save(
        Visitor(
            id=ids.next_id("visitor"),
            name="Ramesh Kumar",
            phone="+91-98400-11111",
            address="14 Anna Salai, Chennai 600002",
            email="ramesh.kumar@example.in",
            phone_verified=True,
            verified_by="digilocker",
            id_hash=(
                "sha256:7f3a1c9e2b8d4a6f5e0c3b7a9d1f4e8c"
                "2a6b0d5f9e3c7a1b4d8f2e6c0a9b3d7f"
            ),
            id_last4="4321",
            is_permanent=True,
        )
    )

    visit_repo.save(
        Visit(
            id=ids.next_id("visit"),
            visitor_id=visitor.id,
            host_id=hosts[0].id,
            purpose="Project discussion - final year review",
            scheduled_at=clock.now() + timedelta(hours=2),
            status="requested",
            origin="pre_registered",
            person_count_expected=1,
        )
    )


def _seed_visitor_c(hosts: list[Host], zones_by_code: dict[str, Zone]) -> None:
    """Visitor C - fallback-admitted, already inside, RESTRICTED.

    C is the most load-bearing fixture in the seed. Nothing in the built scope
    sets restricted = True: the only path is fallback-decision, which is Phase
    12 and deferred. Without C seeded this way THREE things are dead - the
    `restricted` flag on /dashboard/inside, the restricted-admissions count on
    the honesty panel, and Phase 8's restriction-lifting test, which has
    nothing else to run against.

    Her shape follows what fallback-decision would have produced:
      - approved_by is the fallback authority, not a host (SPEC 16.2 format)
      - approval_reason is required by that endpoint, so it is set
      - allowed_zones is the meeting zone ONLY; a fallback admission grants
        nothing wider
      - the window is RESTRICTED_VISIT_DURATION from entry
      - host_acked_at is null: no host has ever been in the loop on this visit

    entry_at is 25 minutes back. That is past ACK_WINDOW (12 min), so
    host_not_acked derives true and Phase 8 can prove that acknowledging clears
    it, but short of NO_SCAN_WINDOW (30 min), so she does not also trip
    no_destination_scan and blur which fixture demonstrates what.

    Her pass and her entry ScanEvent are NOT created here - those need Phase
    5's signing and Phase 6's scan service. Phase 6 extends her.
    """
    entry_at = clock.now() - timedelta(minutes=25)
    meeting_zone = zones_by_code["MAIN"]

    visitor = visitor_repo.save(
        Visitor(
            id=ids.next_id("visitor"),
            name="Deepa Nair",
            phone="+91-98400-22222",
            address="27 Gandhi Street, Guindy, Chennai 600032",
            email="deepa.nair@example.in",
            phone_verified=True,
            verified_by=None,
            is_permanent=False,
        )
    )

    visit_repo.save(
        Visit(
            id=ids.next_id("visit"),
            visitor_id=visitor.id,
            host_id=hosts[1].id,
            purpose="Vendor demonstration - unscheduled",
            scheduled_at=entry_at,
            status="inside",
            origin="pre_registered",
            person_count_expected=1,
            person_count_in=1,
            vehicle_plate_in="TN-09-BC-4455",
            meeting_zone_id=meeting_zone.id,
            allowed_zones=[meeting_zone.id],
            valid_from=entry_at,
            valid_to=entry_at + RESTRICTED_VISIT_DURATION,
            restricted=True,
            approved_by="security:u_security",
            approval_reason=(
                "Host unreachable after escalation; admitted to the meeting "
                "point only, on a short window, pending host acknowledgement."
            ),
            entry_at=entry_at,
            host_acked_at=None,
        )
    )


def load() -> None:
    """Populate an empty store. Called at startup and by /dev/reset."""
    zones_by_code = _seed_zones()
    hosts = _seed_hosts()
    _seed_visitor_a(hosts)
    _seed_visitor_c(hosts, zones_by_code)


def reset() -> None:
    """Clear everything and reseed - the whole of POST /dev/reset.

    The clock offset goes back to zero too, per SPEC section 16.7, so a test
    that advanced time does not leave the next one running in the future.
    """
    memory.clear_all()
    ids.reset()
    clock.reset_offset()
    load()


# --- Known gap at Phase 1, deliberately not filled --------------------------
#
# photo_ref is null on both seeded visitors. Setting one needs
# integrations/storage.py, which is Phase 3. A literal ref written here would
# be a DANGLING POINTER: GET /photos/{ref} would 404 on it at Phase 3, and
# Phase 6's gate-entry response - which SPEC section 10 requires to lead with
# faces - would carry refs resolving to nothing. Extending the seed with real
# photos belongs at Phase 3, alongside the stub that can produce them.
