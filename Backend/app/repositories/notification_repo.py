"""Notification storage access. SPEC section 5.

Append-only, and read back by GET /dev/notifications so a demo can show what
the system "sent".
"""

from app.store import memory
from app.store.entities import Notification


def add(notification: Notification) -> Notification:
    with memory.lock:
        memory.notifications.append(notification)
    return notification


def list_all() -> list[Notification]:
    with memory.lock:
        return list(memory.notifications)


def list_for(recipient: str) -> list[Notification]:
    with memory.lock:
        return [n for n in memory.notifications if n.recipient == recipient]


def count() -> int:
    with memory.lock:
        return len(memory.notifications)
