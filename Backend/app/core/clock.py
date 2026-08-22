"""The single source of current time.

NO CODE ANYWHERE ELSE MAY CALL datetime.now(). Every time read in the system
goes through now() here, because /dev/advance-clock works by shifting the
module-level offset below. A direct datetime.now() call silently ignores the
offset, and the demo that depends on it stops working with no error.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import LOCAL_TZ

# Additive and cumulative. /dev/advance-clock adds to it; /dev/reset
# sets it back to zero via reset_offset().
_offset: timedelta = timedelta(0)


def now() -> datetime:
    """Current time as a timezone-aware UTC datetime, plus any demo offset.

    THE canonical time read. Everything stored or compared uses this.
    """
    return datetime.now(timezone.utc) + _offset


def now_local() -> datetime:
    """now() converted into LOCAL_TZ. For display and for "today" comparisons.

    Same instant as now(), different presentation. WORKING_HOURS evaluates
    WORKING_HOURS and every "today" rule in LOCAL_TZ, never in UTC.
    """
    return now().astimezone(ZoneInfo(LOCAL_TZ))


def readable(moment: datetime | None = None) -> str:
    """A human-legible LOCAL_TZ rendering, e.g. "Sat 22 Aug 2026, 02:51:00 AM IST".

    For eyeballing responses during manual testing. Never parse this - the
    ISO field alongside it is the machine-readable one.
    """
    moment = now() if moment is None else moment
    return moment.astimezone(ZoneInfo(LOCAL_TZ)).strftime("%a %d %b %Y, %I:%M:%S %p %Z")


def advance(minutes: int) -> timedelta:
    """Shift the clock forward. Returns the new cumulative offset.

    Advancing past 17:00 local reroutes fallback escalation from admin to
    security. That is intended and demoable, not a bug.
    """
    global _offset
    _offset += timedelta(minutes=minutes)
    return _offset


def offset() -> timedelta:
    """The current cumulative demo offset."""
    return _offset


def reset_offset() -> None:
    """Set the offset back to zero. Called by /dev/reset."""
    global _offset
    _offset = timedelta(0)
