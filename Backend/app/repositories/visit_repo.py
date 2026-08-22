"""Visit storage access.

The ONLY code that knows Visit records live in a dict. Signatures are written as
if they were hitting a database, so swapping in PostgreSQL touches this file
and not its callers.
"""

from app.core.errors import NotFound
from app.store import memory
from app.store.entities import Visit


def get(entity_id: str) -> Visit | None:
    """Fetch by id, or None. Callers that require the record use get_or_404."""
    with memory.lock:
        return memory.visits.get(entity_id)


def get_or_404(entity_id: str) -> Visit:
    """Fetch by id, raising NotFound (404) when it does not resolve."""
    found = get(entity_id)
    if found is None:
        raise NotFound(
            f"Visit {entity_id} not found", {"id": entity_id, "kind": "visits"}
        )
    return found


def save(entity: Visit) -> Visit:
    """Insert or update. Returns the stored record."""
    with memory.lock:
        memory.visits[entity.id] = entity
    return entity


def list_all() -> list[Visit]:
    """Every record, insertion-ordered."""
    with memory.lock:
        return list(memory.visits.values())


def count() -> int:
    with memory.lock:
        return len(memory.visits)


# Statuses from which no further transition is legal.
TERMINAL_STATUSES = frozenset(
    {"rejected", "cancelled", "denied", "host_unavailable", "expired", "closed"}
)


def list_by_status(*statuses: str) -> list[Visit]:
    with memory.lock:
        return [v for v in memory.visits.values() if v.status in statuses]


def list_by_visitor(visitor_id: str) -> list[Visit]:
    with memory.lock:
        return [v for v in memory.visits.values() if v.visitor_id == visitor_id]


def list_by_host(host_id: str, status: str | None = None) -> list[Visit]:
    """The faculty inbox."""
    with memory.lock:
        return [
            v
            for v in memory.visits.values()
            if v.host_id == host_id and (status is None or v.status == status)
        ]


def find_inside_for_visitor(visitor_id: str, exclude_visit_id: str | None = None) -> Visit | None:
    """The visit a visitor is currently inside on, if any.

    Backs both already-inside rules: VisitorAlreadyInside (409) when creating a
    visit, and the `already_inside` scan result (200) when scanning one in.
    """
    with memory.lock:
        for visit in memory.visits.values():
            if (
                visit.visitor_id == visitor_id
                and visit.status == "inside"
                and visit.id != exclude_visit_id
            ):
                return visit
    return None
