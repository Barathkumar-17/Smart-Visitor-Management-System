"""ScanEvent storage access. SPEC section 5.

Append-only. Scan events are the audit trail - nothing updates or deletes one.
Seeded events go through this same repository so their shape matches what real
scans produce. SPEC section 13.
"""

from app.store import memory
from app.store.entities import ScanEvent


def add(event: ScanEvent) -> ScanEvent:
    """Append one scan event. Written for EVERY attempt, successful or not."""
    with memory.lock:
        memory.scan_events.append(event)
    return event


def list_all() -> list[ScanEvent]:
    with memory.lock:
        return list(memory.scan_events)


def list_by_visit(visit_id: str) -> list[ScanEvent]:
    """The audit trail for one visit, oldest first. Backs GET /visits/{id}/scans."""
    with memory.lock:
        return [e for e in memory.scan_events if e.visit_id == visit_id]


def list_by_kind(visit_id: str, kind: str, result: str | None = None) -> list[ScanEvent]:
    """Filtered history. Phase 13 derives no_destination_scan and
    wrong_zone_scan from exactly this."""
    with memory.lock:
        return [
            e
            for e in memory.scan_events
            if e.visit_id == visit_id
            and e.kind == kind
            and (result is None or e.result == result)
        ]


def count() -> int:
    with memory.lock:
        return len(memory.scan_events)
