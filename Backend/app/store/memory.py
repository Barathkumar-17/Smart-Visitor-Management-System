"""The store. Dicts keyed by id, plus two append-only lists. SPEC section 5.

SERVICES AND ROUTERS MUST NEVER TOUCH THESE. Every read and write goes through
a repository function. Repositories are the only code that knows storage is a
dict - swapping in PostgreSQL later touches that folder alone.

`lock` lives here because it guards these structures. Only repositories acquire
it. It is an RLock so a repository function may call another one without
deadlocking against itself.
"""

import threading
from typing import Any

lock = threading.RLock()

visitors: dict[str, Any] = {}
companions: dict[str, Any] = {}
hosts: dict[str, Any] = {}
zones: dict[str, Any] = {}
visits: dict[str, Any] = {}
passes: dict[str, Any] = {}

scan_events: list[Any] = []
notifications: list[Any] = []


def clear_all() -> None:
    """Empty every collection. Called by the seed loader's reset(), never by a
    service or router - see the warning above."""
    with lock:
        visitors.clear()
        companions.clear()
        hosts.clear()
        zones.clear()
        visits.clear()
        passes.clear()
        scan_events.clear()
        notifications.clear()
