"""Host storage access.

The ONLY code that knows Host records live in a dict. Signatures are written as
if they were hitting a database, so swapping in PostgreSQL touches this file
and not its callers.
"""

from app.core.errors import NotFound
from app.store import memory
from app.store.entities import Host


def get(entity_id: str) -> Host | None:
    """Fetch by id, or None. Callers that require the record use get_or_404."""
    with memory.lock:
        return memory.hosts.get(entity_id)


def get_or_404(entity_id: str) -> Host:
    """Fetch by id, raising NotFound (404) when it does not resolve."""
    found = get(entity_id)
    if found is None:
        raise NotFound(
            f"Host {entity_id} not found", {"id": entity_id, "kind": "hosts"}
        )
    return found


def save(entity: Host) -> Host:
    """Insert or update. Returns the stored record."""
    with memory.lock:
        memory.hosts[entity.id] = entity
    return entity


def list_all() -> list[Host]:
    """Every record, insertion-ordered."""
    with memory.lock:
        return list(memory.hosts.values())


def count() -> int:
    with memory.lock:
        return len(memory.hosts)


def list_by_department(department: str, exclude_host_id: str | None = None) -> list[Host]:
    """Recipients for a department escalation.

    Excludes the named host. May legitimately return an empty list when a
    department has only one host - the caller must still send one notification
    and advance the stage, so the chain never stalls on a data gap.
    """
    with memory.lock:
        return [
            host
            for host in memory.hosts.values()
            if host.department == department and host.id != exclude_host_id
        ]
