"""Zone storage access. SPEC section 5.

The ONLY code that knows Zone records live in a dict. Signatures are written as
if they were hitting a database, so swapping in PostgreSQL touches this file
and not its callers.
"""

from app.core.errors import NotFound
from app.store import memory
from app.store.entities import Zone


def get(entity_id: str) -> Zone | None:
    """Fetch by id, or None. Callers that require the record use get_or_404."""
    with memory.lock:
        return memory.zones.get(entity_id)


def get_or_404(entity_id: str) -> Zone:
    """Fetch by id, raising NotFound (404) when it does not resolve."""
    found = get(entity_id)
    if found is None:
        raise NotFound(
            f"Zone {entity_id} not found", {"id": entity_id, "kind": "zones"}
        )
    return found


def save(entity: Zone) -> Zone:
    """Insert or update. Returns the stored record."""
    with memory.lock:
        memory.zones[entity.id] = entity
    return entity


def list_all() -> list[Zone]:
    """Every record, insertion-ordered."""
    with memory.lock:
        return list(memory.zones.values())


def count() -> int:
    with memory.lock:
        return len(memory.zones)


def find_by_code(code: str) -> Zone | None:
    """Zone scans arrive with a zone_code, not an id. SPEC section 10."""
    with memory.lock:
        for zone in memory.zones.values():
            if zone.code == code:
                return zone
    return None
