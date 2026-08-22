"""User storage access.

The ONLY code that knows User records live in a dict, like every other
repository here. Sessions live alongside them because a token is meaningless
without the user it points at, and splitting them would mean two files sharing
one lock for one concept.
"""

from app.core.errors import NotFound
from app.store import memory
from app.store.entities import User


def get(entity_id: str) -> User | None:
    with memory.lock:
        return memory.users.get(entity_id)


def get_or_404(entity_id: str) -> User:
    found = get(entity_id)
    if found is None:
        raise NotFound(f"User {entity_id} not found", {"id": entity_id, "kind": "users"})
    return found


def save(entity: User) -> User:
    with memory.lock:
        memory.users[entity.id] = entity
    return entity


def list_all() -> list[User]:
    with memory.lock:
        return list(memory.users.values())


def find_by_username(username: str) -> User | None:
    """Logins arrive with a username, not an id."""
    with memory.lock:
        for user in memory.users.values():
            if user.username == username:
                return user
    return None


# --- sessions ---------------------------------------------------------------


def save_session(token: str, user_id: str, expires_at) -> None:
    with memory.lock:
        memory.sessions[token] = {"user_id": user_id, "expires_at": expires_at}


def get_session(token: str) -> dict | None:
    with memory.lock:
        return memory.sessions.get(token)


def delete_session(token: str) -> bool:
    with memory.lock:
        return memory.sessions.pop(token, None) is not None


def count_sessions() -> int:
    with memory.lock:
        return len(memory.sessions)
