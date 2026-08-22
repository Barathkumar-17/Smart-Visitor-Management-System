"""Visitor storage access.

The ONLY code that knows Visitor records live in a dict. Signatures are written as
if they were hitting a database, so swapping in PostgreSQL touches this file
and not its callers.
"""

from app.core.errors import NotFound
from app.store import memory
from app.store.entities import Visitor


def get(entity_id: str) -> Visitor | None:
    """Fetch by id, or None. Callers that require the record use get_or_404."""
    with memory.lock:
        return memory.visitors.get(entity_id)


def get_or_404(entity_id: str) -> Visitor:
    """Fetch by id, raising NotFound (404) when it does not resolve."""
    found = get(entity_id)
    if found is None:
        raise NotFound(
            f"Visitor {entity_id} not found", {"id": entity_id, "kind": "visitors"}
        )
    return found


def save(entity: Visitor) -> Visitor:
    """Insert or update. Returns the stored record."""
    with memory.lock:
        memory.visitors[entity.id] = entity
    return entity


def list_all() -> list[Visitor]:
    """Every record, insertion-ordered."""
    with memory.lock:
        return list(memory.visitors.values())


def count() -> int:
    with memory.lock:
        return len(memory.visitors)


def find_by_phone(phone: str) -> Visitor | None:
    """Lookup used by the returning-walk-in path at Phase 3."""
    with memory.lock:
        for visitor in memory.visitors.values():
            if visitor.phone == phone:
                return visitor
    return None
