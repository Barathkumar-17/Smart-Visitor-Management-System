"""Per-collection id counters, so no two repositories invent their own scheme. Ids are of the form `{prefix}_{n}` - v_1, h_2, z_3.
"""

import threading

_lock = threading.Lock()

_counters: dict[str, int] = {}

# Prefix per collection. Repositories pass the collection name, never the
# prefix, so the mapping lives in exactly one place.
PREFIXES: dict[str, str] = {
    "visitor": "vr",
    "companion": "c",
    "host": "h",
    "zone": "z",
    "visit": "v",
    "pass": "p",
    "scan_event": "s",
    "notification": "n",
    # Photo refs are "photo_{n}", not an entity id, but
    # the counter belongs here so /dev/reset makes refs deterministic too.
    "photo": "photo",
}


def next_id(collection: str) -> str:
    """Return the next id for a collection, e.g. next_id("visit") -> "v_3"."""
    if collection not in PREFIXES:
        raise KeyError(f"Unknown collection '{collection}'")
    with _lock:
        n = _counters.get(collection, 0) + 1
        _counters[collection] = n
    return f"{PREFIXES[collection]}_{n}"


def reset() -> None:
    """Clear every counter. Called by /dev/reset at Phase 1."""
    with _lock:
        _counters.clear()
