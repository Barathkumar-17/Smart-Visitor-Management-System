"""The store. Dicts keyed by id, plus two append-only lists. SPEC section 5.

SERVICES AND ROUTERS MUST NEVER TOUCH THESE. Every read and write goes through
a repository function. Repositories are the only code that knows storage is a
dict - swapping in PostgreSQL later touches that folder alone.

Empty at Phase 0. Phase 1 adds the entities and repositories that fill them,
and the seed loader that populates them at startup.
"""

from typing import Any

visitors: dict[str, Any] = {}
companions: dict[str, Any] = {}
hosts: dict[str, Any] = {}
zones: dict[str, Any] = {}
visits: dict[str, Any] = {}
passes: dict[str, Any] = {}

scan_events: list[Any] = []
notifications: list[Any] = []
