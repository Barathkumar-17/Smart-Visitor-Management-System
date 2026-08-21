"""Pass storage access. SPEC section 5.

The ONLY code that knows Pass records live in a dict. Signatures are written as
if they were hitting a database, so swapping in PostgreSQL touches this file
and not its callers.
"""

from app.core.errors import NotFound
from app.store import memory
from app.store.entities import Pass


def get(entity_id: str) -> Pass | None:
    """Fetch by id, or None. Callers that require the record use get_or_404."""
    with memory.lock:
        return memory.passes.get(entity_id)


def get_or_404(entity_id: str) -> Pass:
    """Fetch by id, raising NotFound (404) when it does not resolve."""
    found = get(entity_id)
    if found is None:
        raise NotFound(
            f"Pass {entity_id} not found", {"id": entity_id, "kind": "passes"}
        )
    return found


def save(entity: Pass) -> Pass:
    """Insert or update. Returns the stored record."""
    with memory.lock:
        memory.passes[entity.id] = entity
    return entity


def list_all() -> list[Pass]:
    """Every record, insertion-ordered."""
    with memory.lock:
        return list(memory.passes.values())


def count() -> int:
    with memory.lock:
        return len(memory.passes)


def find_by_visit(visit_id: str) -> Pass | None:
    with memory.lock:
        for issued in memory.passes.values():
            if issued.visit_id == visit_id:
                return issued
    return None


def list_active() -> list[Pass]:
    """Passes that are not revoked and whose visit is not terminal.

    This is the set code6 must be unique across. SPEC section 9. Imported
    locally to keep the repository layer free of import cycles.
    """
    from app.repositories import visit_repo

    with memory.lock:
        active = []
        for issued in memory.passes.values():
            if issued.revoked_at is not None:
                continue
            visit = visit_repo.get(issued.visit_id)
            if visit is None or visit.status in visit_repo.TERMINAL_STATUSES:
                continue
            active.append(issued)
        return active


def find_active_by_code6(code6: str) -> Pass | None:
    """Resolve a 6-digit fallback code to exactly one active pass.

    A code matching MORE THAN ONE active pass is a bug, not a case to handle -
    uniqueness is enforced at generation, so it cannot happen. If it somehow
    does, raise rather than picking one: silently admitting the wrong visitor
    is the worst failure this system has. SPEC section 9.
    """
    matches = [p for p in list_active() if p.code6 == code6]
    if len(matches) > 1:
        raise RuntimeError(
            f"code6 {code6} matches {len(matches)} active passes: "
            f"{[p.id for p in matches]}. Uniqueness was violated at generation."
        )
    return matches[0] if matches else None
