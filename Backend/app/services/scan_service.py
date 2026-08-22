"""Gate entry, zone and exit scans. SPEC section 10.

Phase 4 adds only the audit-trail READ, so GET /visits/{id}/scans has something
behind it. The three scan endpoints and every rule they carry - the five
ordered checks, the mismatch flags, the already-inside rule, writing a
ScanEvent on failure as well as success - arrive at Phase 6.
"""

from app.repositories import scan_repo
from app.store.entities import ScanEvent


def list_for_visit(visit_id: str) -> list[ScanEvent]:
    """Every scan attempt against one visit, oldest first.

    Includes failures. SPEC section 6 is explicit that a ScanEvent is written
    for EVERY attempt, and that the completeness of this history decides
    whether a later scoring phase is possible at all.
    """
    return scan_repo.list_by_visit(visit_id)
