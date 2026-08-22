"""Notification stub. SPEC section 5.

Signature correct, implementation fake: logs the recipient and message, and
appends to the notifications list so a demo can SHOW what was sent. Real
deployment swaps the body for email or SMS and changes nothing else.

Recipients are free-text strings, not ids, because SPEC section 16.3 requires
some of them to be addressed to things that are not host records at all -
"department:Computer Science", "admin_block", "security_desk".
"""

import logging

from app.repositories import notification_repo
from app.store import ids
from app.store.entities import Notification

log = logging.getLogger(__name__)


def send(recipient: str, message: str) -> Notification:
    """Record a notification. Never raises - a failed notification must never
    break the flow that triggered it."""
    notification = notification_repo.add(
        Notification(id=ids.next_id("notification"), recipient=recipient, message=message)
    )
    log.info("NOTIFY %s: %s", recipient, message)
    return notification


def notify_host(host, message: str) -> Notification:
    """Notify a host by name and email, so a demo shows who was contacted."""
    return send(f"host:{host.id} <{host.email}>", message)


def notify_visitor(visitor, message: str) -> Notification:
    return send(f"visitor:{visitor.id} <{visitor.phone}>", message)


def notify_security(message: str) -> Notification:
    return send("security_desk", message)
