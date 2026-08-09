#!/usr/bin/env python3
"""
The day must roll over at the user's midnight. Not at UTC's, not at the
server's.

These tests exist because all three were true at once before: meals were
stored in UTC, the browser asked for the UTC date via toISOString(), and half
the backend compared against server-local datetime.now(). For an IST user the
visible symptom was a dashboard that kept showing yesterday until 05:30.

    python scripts/test_daytime.py
"""

import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GREEN, RED, DIM, BOLD, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[1m", "\033[0m"
passed = failed = 0

ZONES = ["Asia/Kolkata", "UTC", "America/New_York", "America/Los_Angeles",
         "Pacific/Kiritimati", "Pacific/Midway", "Australia/Lord_Howe",
         "Asia/Kathmandu", "Europe/London"]


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  {GREEN}pass{RESET}  {label}")
    else:
        failed += 1
        print(f"  {RED}FAIL{RESET}  {label}")
        for line in str(detail).splitlines()[:6]:
            print(f"        {DIM}{line}{RESET}")


class FakeUser:
    """Just enough of a User for daytime to read .timezone off it."""
    def __init__(self, tz=None):
        self.timezone = tz


class Row:
    """Stands in for a MealLog: a naive UTC timestamp on .logged_at."""
    def __init__(self, utc):
        self.logged_at = utc


def as_utc(local: datetime) -> datetime:
    """A local aware time, stored the way the app stores it: naive UTC."""
    return local.astimezone(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------

def test_the_original_bug():
    """The 00:30 IST meal. This is the report, reproduced."""
    from app.services import daytime
    print(f"\n{BOLD}1. The reported bug: a meal at 00:30 IST{RESET}")

    ist = ZoneInfo("Asia/Kolkata")
    user = FakeUser("Asia/Kolkata")

    logged_local = datetime(2026, 8, 9, 0, 30, tzinfo=ist)
    stored = as_utc(logged_local)

    check("stored as the previous UTC day, as it always was",
          stored.date() == date(2026, 8, 8), stored)
    check("but belongs to 9 Aug for the user",
          daytime.local_date(user, stored) == date(2026, 8, 9),
          daytime.local_date(user, stored))

    start, end = daytime.day_bounds(date(2026, 8, 9), user)
    check("and falls inside the 9 Aug window", start <= stored < end,
          f"{start} <= {stored} < {end}")

    # The old behaviour, kept as a contrast so the test says what changed.
    utc_start = datetime.combine(date(2026, 8, 9), time.min)
    check("the old UTC window would have excluded it (this was the bug)",
          not (utc_start <= stored < utc_start + timedelta(days=1)))


def test_rollover_is_at_local_midnight():
    """The day must change at 00:00 local, in every zone."""
    from app.services import daytime
    print(f"\n{BOLD}2. Rollover happens at local midnight, everywhere{RESET}")

    for name in ZONES:
        tz = ZoneInfo(name)
        user = FakeUser(name)
        day = date(2026, 8, 9)

        just_before = as_utc(datetime(2026, 8, 8, 23, 59, 59, tzinfo=tz))
        at_midnight = as_utc(datetime(2026, 8, 9, 0, 0, 0, tzinfo=tz))
        just_after = as_utc(datetime(2026, 8, 9, 0, 0, 1, tzinfo=tz))

        check(f"{name}: 23:59:59 is still the 8th",
              daytime.local_date(user, just_before) == date(2026, 8, 8))
        check(f"{name}: 00:00:00 is the 9th",
              daytime.local_date(user, at_midnight) == day)
        check(f"{name}: 00:00:01 is the 9th",
              daytime.local_date(user, just_after) == day)

        # Half-open bounds: midnight belongs to the day starting, exactly once.
        prev_start, prev_end = daytime.day_bounds(date(2026, 8, 8), user)
        start, end = daytime.day_bounds(day, user)
        check(f"{name}: windows meet exactly, no gap or overlap",
              prev_end == start, f"{prev_end} vs {start}")
        check(f"{name}: midnight counts once, in the new day",
              (start <= at_midnight < end) and not (prev_start <= at_midnight < prev_end))


def test_no_day_lost_or_double_counted():
    """
    Walk a whole year of local midnights. Every instant must land in exactly
    one day, and consecutive days must abut.
    """
    from app.services import daytime
    print(f"\n{BOLD}3. A year of days, with no gaps and no overlaps{RESET}")

    for name in ZONES:
        user = FakeUser(name)
        day = date(2026, 1, 1)
        gaps = []
        previous_end = None

        while day < date(2027, 1, 1):
            start, end = daytime.day_bounds(day, user)
            if end <= start:
                gaps.append(f"{day}: empty or inverted window {start}..{end}")
            if previous_end is not None and previous_end != start:
                gaps.append(f"{day}: {previous_end} -> {start}")
            previous_end = end
            day += timedelta(days=1)

        check(f"{name}: 365 contiguous days", not gaps, "\n".join(gaps[:4]))


def test_dst():
    """DST days are 23 or 25 hours. Assuming 24 loses or repeats an hour."""
    from app.services import daytime
    print(f"\n{BOLD}4. DST transitions{RESET}")

    ny = FakeUser("America/New_York")
    london = FakeUser("Europe/London")

    for user, day, expected, what in [
        (ny, date(2026, 3, 8), 23, "spring forward"),
        (ny, date(2026, 11, 1), 25, "fall back"),
        (ny, date(2026, 6, 1), 24, "an ordinary day"),
        (london, date(2026, 3, 29), 23, "BST starts"),
        (london, date(2026, 10, 25), 25, "BST ends"),
    ]:
        start, end = daytime.day_bounds(day, user)
        hours = (end - start).total_seconds() / 3600
        check(f"{user.timezone} {day} ({what}) is {expected}h",
              hours == expected, f"got {hours}h")

    # The hour that does not exist must still produce a usable window.
    lord_howe = FakeUser("Australia/Lord_Howe")   # 30-minute DST shift
    start, end = daytime.day_bounds(date(2026, 10, 4), lord_howe)
    check("Lord Howe's 30-minute shift produces a sane window",
          timedelta(hours=23) <= (end - start) <= timedelta(hours=25),
          f"{end - start}")


def test_local_hour_and_grouping():
    """Habit detection reads the hour. It has to be the user's hour."""
    from app.services import daytime
    print(f"\n{BOLD}5. Local hour, not UTC hour{RESET}")

    ist = ZoneInfo("Asia/Kolkata")
    user = FakeUser("Asia/Kolkata")

    late = as_utc(datetime(2026, 8, 9, 23, 15, tzinfo=ist))
    check("a 23:15 IST meal reads as hour 23",
          daytime.local_hour(late, user) == 23,
          f"got {daytime.local_hour(late, user)} (UTC hour is {late.hour})")
    check("the UTC hour would have missed the 22:00 late-meal rule",
          late.hour < 22, f"UTC hour {late.hour}")

    breakfast = as_utc(datetime(2026, 8, 9, 8, 0, tzinfo=ist))
    check("an 08:00 IST breakfast reads as hour 8",
          daytime.local_hour(breakfast, user) == 8)

    # Grouping: one local day must be one bucket. The meals that straddle the
    # UTC boundary in IST are the EARLY ones - UTC midnight is 05:30 local -
    # so an early breakfast and a mid-morning snack land on different UTC days
    # despite being two hours apart on the same morning.
    morning = [Row(as_utc(datetime(2026, 8, 9, h, 0, tzinfo=ist)))
               for h in (4, 5, 7, 20)]
    buckets = daytime.group_by_local_day(morning, "logged_at", user)
    check("four meals on one IST day group into one day",
          len(buckets) == 1 and date(2026, 8, 9) in buckets,
          sorted(buckets))

    utc_days = {r.logged_at.date() for r in morning}
    check("grouping by UTC would have split that day (the old bug)",
          len(utc_days) > 1, sorted(utc_days))

    check("local_dates_between agrees with group_by_local_day",
          daytime.local_dates_between(morning, "logged_at", user) == set(buckets))


def test_streak_across_midnight():
    """A streak must not break or inflate because of the boundary."""
    from app.services import daytime
    print(f"\n{BOLD}6. Streaks across the boundary{RESET}")

    ist = ZoneInfo("Asia/Kolkata")
    user = FakeUser("Asia/Kolkata")

    # Seven consecutive local days, each logged late at night - the worst case
    # for UTC-day grouping.
    rows = [Row(as_utc(datetime(2026, 8, d, 23, 30, tzinfo=ist))) for d in range(1, 8)]
    days = daytime.local_dates_between(rows, "logged_at", user)
    check("7 late-night meals on 7 days count as 7 days", len(days) == 7, sorted(days))
    check("they are consecutive",
          sorted(days) == [date(2026, 8, d) for d in range(1, 8)])

    # Two meals either side of one local midnight are two days, not one.
    pair = [Row(as_utc(datetime(2026, 8, 9, 23, 50, tzinfo=ist))),
            Row(as_utc(datetime(2026, 8, 10, 0, 10, tzinfo=ist)))]
    check("20 minutes apart across midnight is two days",
          len(daytime.local_dates_between(pair, "logged_at", user)) == 2)

    # ...and 20 minutes apart within one day is one.
    same = [Row(as_utc(datetime(2026, 8, 9, 12, 0, tzinfo=ist))),
            Row(as_utc(datetime(2026, 8, 9, 12, 20, tzinfo=ist)))]
    check("20 minutes apart inside a day is one day",
          len(daytime.local_dates_between(same, "logged_at", user)) == 1)


def test_ranges():
    """`days_ago_start` must land on a boundary, not partway through a day."""
    from app.services import daytime
    print(f"\n{BOLD}7. Multi-day ranges start on a day boundary{RESET}")

    for name in ZONES:
        user = FakeUser(name)
        for span in (7, 21, 30):
            start = daytime.days_ago_start(span, user)
            expected_day = daytime.local_date(user) - timedelta(days=span)
            day_start, _ = daytime.day_bounds(expected_day, user)
            check(f"{name}: {span} days ago starts at that day's midnight",
                  start == day_start, f"{start} vs {day_start}")


def test_fallbacks():
    """A missing or hostile timezone must never raise."""
    from app.services import daytime
    print(f"\n{BOLD}8. Missing and invalid timezones{RESET}")

    for value in [None, "", "   ", "Mars/Olympus", "Not/A/Zone", "'; DROP TABLE users;--",
                  "UTC+5:30", 12345, True]:
        try:
            bounds = daytime.day_bounds(date(2026, 8, 9), FakeUser(value))
            ok = isinstance(bounds, tuple) and bounds[0] < bounds[1]
        except Exception as e:                          # noqa: BLE001
            ok = False
            bounds = repr(e)
        check(f"timezone {value!r} falls back instead of raising", ok, bounds)

    check("a user object with no timezone attribute at all works",
          daytime.day_bounds(date(2026, 8, 9), object())[0] is not None)
    check("no user at all works", daytime.day_bounds(date(2026, 8, 9))[0] is not None)

    # normalise_timezone is what guards the column, so it must reject.
    for bad in [None, "", "Mars/Olympus", "UTC+5:30", 12345, "  "]:
        check(f"normalise_timezone rejects {bad!r}",
              daytime.normalise_timezone(bad) is None)
    for good in ["Asia/Kolkata", "UTC", "America/New_York"]:
        check(f"normalise_timezone accepts {good!r}",
              daytime.normalise_timezone(good) == good)


def test_utcnow_is_utc():
    """Everything is stored in UTC. The helper must actually return UTC."""
    from app.services import daytime
    print(f"\n{BOLD}9. utcnow really is UTC{RESET}")

    now = daytime.utcnow()
    check("naive, matching the naive DateTime columns", now.tzinfo is None)
    drift = abs((now - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds())
    check("within a second of true UTC", drift < 2, f"{drift}s off")

    # The trap this replaces: datetime.now() is only equal to UTC by accident.
    local_drift = abs((datetime.now() - now).total_seconds())
    if local_drift > 60:
        print(f"        {DIM}note: this machine is {local_drift/3600:.1f}h from UTC, "
              f"which is exactly what broke the comparisons.{RESET}")


def test_midnight_countdown():
    """The client schedules its refresh off this."""
    from app.services import daytime
    print(f"\n{BOLD}10. Seconds until local midnight{RESET}")

    for name in ZONES:
        user = FakeUser(name)
        seconds = daytime.seconds_until_local_midnight(user)
        check(f"{name}: within a day and positive",
              0 < seconds <= 86400, seconds)

        # It must point at the NEXT local midnight, not the next UTC one.
        target = daytime.local_now(user) + timedelta(seconds=seconds)
        check(f"{name}: lands on the next local day",
              target.date() == daytime.local_date(user) + timedelta(days=1),
              f"{target} vs {daytime.local_date(user)}")


def test_no_utc_dates_left_in_frontend():
    """
    toISOString() for a day is the bug in one call. Guard against it coming
    back, since it looks entirely reasonable in review.
    """
    print(f"\n{BOLD}11. The frontend no longer derives a day from UTC{RESET}")

    src = ROOT / "frontend/src"
    offenders = []
    for path in list(src.rglob("*.js")) + list(src.rglob("*.jsx")):
        if path.name == "localDay.js":
            continue    # where the rule is explained
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r"toISOString\(\)\s*(\.split\(\s*['\"]T|\.slice\(\s*0\s*,\s*10)", line):
                offenders.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()}")

    check("no toISOString() date extraction outside localDay.js",
          not offenders, "\n".join(offenders))

    helper = (src / "localDay.js").read_text()
    check("localDay exports the pieces the app needs",
          all(name in helper for name in
              ("localDateString", "browserTimezone", "syncTimezone", "onLocalDayChange")))


def main():
    test_the_original_bug()
    test_rollover_is_at_local_midnight()
    test_no_day_lost_or_double_counted()
    test_dst()
    test_local_hour_and_grouping()
    test_streak_across_midnight()
    test_ranges()
    test_fallbacks()
    test_utcnow_is_utc()
    test_midnight_countdown()
    test_no_utc_dates_left_in_frontend()

    print(f"\n{BOLD}{GREEN if not failed else RED}"
          f"{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
