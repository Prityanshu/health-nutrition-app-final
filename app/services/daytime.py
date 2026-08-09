"""
What day is it, for this user?

Every "today" in the app used to be answered three different ways:

    datetime.utcnow()                  - the UTC day
    datetime.now()                     - whatever the server's clock says
    new Date().toISOString().slice(10) - the UTC day again, from the browser

None of those is the user's day. For somebody in IST the effect was that the
dashboard rolled over at 05:30 rather than midnight: a meal logged at 00:30 was
stored as 19:00 the previous day in UTC, counted against yesterday, and the new
day showed 0 kcal until half past five in the morning. Streaks broke the same
way, and challenge progress landed on the wrong date.

The fix is one place that owns the question. Timestamps stay stored in UTC -
that part was right - but any query that asks "which day does this belong to"
converts through the user's timezone first.

Rules for callers:

    * store UTC. `utcnow()` here, never `datetime.now()`.
    * to filter a day, ask for `day_bounds()` and compare against the returned
      UTC pair. Never compare a naive local datetime to a stored column.
    * to display or group by day, use `local_date()`.
"""

from __future__ import annotations

import logging
import math
import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

# Used when a user has no timezone recorded - existing accounts, background
# jobs, anything created before the column existed. This is a fallback, not the
# answer: a user's own timezone always wins.
DEFAULT_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kolkata")

UTC = timezone.utc


def utcnow() -> datetime:
    """
    Naive UTC, matching how every timestamp column in this app is stored.

    Naive rather than aware because the columns are naive; mixing the two
    raises `can't compare offset-naive and offset-aware datetimes` at runtime,
    usually from a query that only runs in one branch.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def _zone(name: Optional[str]) -> ZoneInfo:
    """Resolve an IANA name, falling back rather than raising."""
    for candidate in (name, DEFAULT_TIMEZONE, "UTC"):
        # Not just falsy - ZoneInfo raises TypeError on an int or a bool, and
        # this value comes from a database column that anything could have
        # written. A bad timezone must degrade, never 500.
        if not candidate or not isinstance(candidate, str):
            continue
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            # A bad timezone must never take down a request. The browser sends
            # this string, so it is user-controlled input.
            if candidate == name:
                logger.warning("Unknown timezone %r; falling back.", name)
    return ZoneInfo("UTC")


def normalise_timezone(name: Optional[str]) -> Optional[str]:
    """
    Validate an IANA name, returning it or None.

    The browser supplies this, so it is untrusted input that ends up deciding
    every day boundary for the account. None means "reject" - the caller keeps
    whatever it had rather than storing a value that would silently shift the
    user's whole history.
    """
    if not name or not isinstance(name, str):
        return None
    name = name.strip()
    if not name:
        return None
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return name


def zone_for(user) -> ZoneInfo:
    """The user's timezone, or the app default if they have none."""
    return _zone(getattr(user, "timezone", None))


def to_local(moment: datetime, user=None, tz: Optional[ZoneInfo] = None) -> datetime:
    """A stored (naive UTC) timestamp as the user would read it on a clock."""
    tz = tz or zone_for(user)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(tz)


def local_now(user=None, tz: Optional[ZoneInfo] = None) -> datetime:
    """Right now, on the user's wall clock."""
    return datetime.now(tz or zone_for(user))


def local_date(user=None, moment: Optional[datetime] = None,
               tz: Optional[ZoneInfo] = None) -> date:
    """
    Which calendar day a moment falls on for this user.

    With no moment, the user's today. This is what "today" means everywhere
    else in the app.
    """
    tz = tz or zone_for(user)
    if moment is None:
        return local_now(tz=tz).date()
    return to_local(moment, tz=tz).date()


def day_bounds(day: Optional[date] = None, user=None,
               tz: Optional[ZoneInfo] = None) -> Tuple[datetime, datetime]:
    """
    The UTC half-open window [start, end) covering one local day.

    Half-open on purpose: a meal logged at exactly midnight belongs to the day
    starting, not the one ending, and inclusive bounds on both ends would count
    it twice.

    The conversion goes local-midnight -> UTC rather than UTC-midnight -> local,
    because only the former gives a window that starts when the user's day
    actually starts. On a DST boundary the window is correctly 23 or 25 hours
    long, which is why this subtracts real instants instead of assuming 24h.
    """
    tz = tz or zone_for(user)
    day = day or local_date(tz=tz)

    start_local = datetime.combine(day, time.min, tzinfo=tz)
    # Midnight does not exist on spring-forward days in some zones. Asking for
    # 00:00 there yields a time that never happened; stepping forward an hour
    # gives the first instant the day actually has.
    if start_local.astimezone(tz).date() != day:
        start_local = datetime.combine(day, time(1, 0), tzinfo=tz)

    end_local = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    if end_local.astimezone(tz).date() != day + timedelta(days=1):
        end_local = datetime.combine(day + timedelta(days=1), time(1, 0), tzinfo=tz)

    return (
        start_local.astimezone(UTC).replace(tzinfo=None),
        end_local.astimezone(UTC).replace(tzinfo=None),
    )


def today_bounds(user=None, tz: Optional[ZoneInfo] = None) -> Tuple[datetime, datetime]:
    """The UTC window covering the user's current day."""
    return day_bounds(None, user=user, tz=tz)


def days_ago_start(days: int, user=None, tz: Optional[ZoneInfo] = None) -> datetime:
    """
    UTC start of the local day `days` before today.

    For "the last 7 days" this is what you want rather than `utcnow() - 7d`:
    the latter starts partway through a day, so the oldest day is a fragment
    and a streak can look broken by nothing more than the hour you asked.
    """
    tz = tz or zone_for(user)
    start, _ = day_bounds(local_date(tz=tz) - timedelta(days=days), tz=tz)
    return start


def local_dates_between(rows, attr: str = "logged_at", user=None,
                        tz: Optional[ZoneInfo] = None):
    """
    The set of local calendar days a collection of rows falls on.

    Streak and "days logged" counting used `row.logged_at.date()`, which is the
    UTC day. In IST, UTC midnight falls at 05:30 local, so anything logged
    before 05:30 was attributed to the previous day - a 04:00 snack and an
    08:00 breakfast on one morning counted as two separate days logged.
    """
    tz = tz or zone_for(user)
    return {to_local(getattr(r, attr), tz=tz).date() for r in rows if getattr(r, attr, None)}


def local_hour(moment: Optional[datetime], user=None,
               tz: Optional[ZoneInfo] = None) -> Optional[int]:
    """
    The hour on the user's clock, 0-23.

    `row.logged_at.hour` is the UTC hour. Habit detection used it directly, so
    for an IST user "ate after 22:00" tested against 22:00 UTC - 03:30 local -
    and never fired. Late-night eating was invisible; breakfast detection
    passed only by luck of the offset.
    """
    if moment is None:
        return None
    return to_local(moment, tz=tz or zone_for(user)).hour


def group_by_local_day(rows, attr: str = "logged_at", user=None,
                       tz: Optional[ZoneInfo] = None):
    """Rows bucketed by the user's calendar day rather than the UTC one."""
    tz = tz or zone_for(user)
    buckets = {}
    for row in rows:
        moment = getattr(row, attr, None)
        if moment is None:
            continue
        buckets.setdefault(to_local(moment, tz=tz).date(), []).append(row)
    return buckets


def seconds_until_local_midnight(user=None, tz: Optional[ZoneInfo] = None) -> int:
    """How long until this user's day rolls over. Used for client refresh."""
    tz = tz or zone_for(user)
    now = local_now(tz=tz)
    tomorrow = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=tz)
    # Round UP. Truncating landed a fraction of a second before midnight, so a
    # client scheduling a refresh on this value would have woken while it was
    # still yesterday and re-fetched the day it was trying to leave.
    return max(0, math.ceil((tomorrow - now).total_seconds()))
