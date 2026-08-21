"""Companion storage access. SPEC section 5.

The ONLY code that knows Companion records live in a dict. Signatures are written as
if they were hitting a database, so swapping in PostgreSQL touches this file
and not its callers.
"""

from app.core.errors import NotFound
from app.store import memory
from app.store.entities import Companion


def get(entity_id: str) -> Companion | None:
    """Fetch by id, or None. Callers that require the record use get_or_404."""
    with memory.lock:
        return memory.companions.get(entity_id)


def get_or_404(entity_id: str) -> Companion:
    """Fetch by id, raising NotFound (404) when it does not resolve."""
    found = get(entity_id)
    if found is None:
        raise NotFound(
            f"Companion {entity_id} not found", {"id": entity_id, "kind": "companions"}
        )
    return found


def save(entity: Companion) -> Companion:
    """Insert or update. Returns the stored record."""
    with memory.lock:
        memory.companions[entity.id] = entity
    return entity


def list_all() -> list[Companion]:
    """Every record, insertion-ordered."""
    with memory.lock:
        return list(memory.companions.values())


def count() -> int:
    with memory.lock:
        return len(memory.companions)


def list_by_visit(visit_id: str) -> list[Companion]:
    """Everyone linked to a visit. The gate-entry response leads with these."""
    with memory.lock:
        return [c for c in memory.companions.values() if c.visit_id == visit_id]
