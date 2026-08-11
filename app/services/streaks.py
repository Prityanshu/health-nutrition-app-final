"""
Consecutive days, counted one way.

WHY THIS IS ITS OWN MODULE
--------------------------
There were two streak implementations. `adherence` counted consecutive days on
target, correctly. `enhanced_challenges_router` had its own inline loop that
counted consecutive ROWS in a progress table - and the two are not the same
thing at all:

    user 1   2026-08-09 21:24   complete
             2026-08-09 21:24   complete     <- same evening
             2026-08-09 22:01   complete     <- same evening
             2026-08-10 13:32   complete

Three challenges finished in one sitting was reported as a three-day streak.
The column is a DateTime rather than a Date, so no two rows ever share a
"date" and every row counted separately.

It was also blind to gaps. Rows that do not exist cannot break a run, so one
user's streak ran from September to November across weeks of nothing - and was
still being reported as *current* nine months later, because the count simply
ended at the last row in the table rather than at today.

Both of those come from counting records instead of days. This module counts
days, and every caller uses it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, List, Sequence, Tuple


@dataclass
class Streak:
    """A run of consecutive days, counted back from the most recent."""

    current: int = 0
    best: int = 0


def over(days: Sequence[Tuple[date, bool]]) -> Streak:
    """
    Count runs over an ordered, CONTIGUOUS sequence of (day, hit).

    Contiguous is the load-bearing word. A caller that passes only the days it
    has records for gets a streak that ignores every gap, which is the bug this
    module exists to stop. Use `from_dates` if you have a sparse set.

    A False entry breaks the run rather than being skipped: a streak claims
    consecutive days, and a day with no evidence is not a day that counted.
    """
    streak = Streak()
    run = 0
    for _, hit in days:
        if hit:
            run += 1
            streak.best = max(streak.best, run)
        else:
            run = 0
    for _, hit in reversed(days):
        if hit:
            streak.current += 1
        else:
            break
    return streak


def from_dates(hit_dates: Iterable[date], *, today: date,
               grace_days: int = 1) -> Streak:
    """
    Build the contiguous range for a sparse set of dates, then count.

    `hit_dates` may contain duplicates and may be in any order - both are
    normal when the source is a table of timestamps rather than one row per
    day.

    `grace_days` decides how stale a run may be and still count as *current*.
    One by default: today is usually still in progress, so a run that ends
    yesterday is live, and one that ended a week ago is history. Without this
    the last run in the table is reported as current forever.
    """
    hits = {d for d in hit_dates if d is not None}
    if not hits:
        return Streak()

    last = max(hits)
    if (today - last).days > grace_days:
        # The run is over. Its length is still worth knowing as a best, so the
        # range is walked anyway - but nothing reaching today means current 0.
        best = _best_only(hits)
        return Streak(current=0, best=best)

    first = min(hits)
    span: List[Tuple[date, bool]] = []
    day = first
    while day <= last:
        span.append((day, day in hits))
        day += timedelta(days=1)
    return over(span)


def _best_only(hits: set) -> int:
    best = run = 0
    day = min(hits)
    last = max(hits)
    while day <= last:
        run = run + 1 if day in hits else 0
        best = max(best, run)
        day += timedelta(days=1)
    return best
