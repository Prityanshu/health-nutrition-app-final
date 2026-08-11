#!/usr/bin/env python3
"""
One definition of a streak, and the two bugs that came from having two.

There were two implementations. `adherence` counted consecutive DAYS on
target, correctly. `enhanced_challenges_router` had its own inline loop that
counted consecutive ROWS of a progress table, which produced two failures that
both flattered the user:

  * progress_date is a DateTime, so no two rows share a value. Three
    challenges finished in one evening counted as a three-day streak.
  * A day with no row cannot break a run, because it is not in the list. One
    real account had a run spanning September to November across weeks of
    gaps - and it was still being reported as *current* nine months later,
    because the count simply ended at the last row rather than at today.

Both come from counting records instead of days. These tests pin the shared
implementation and make sure neither can come back.

    python scripts/test_streaks.py
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services import streaks   # noqa: E402

GREEN, RED, DIM, BOLD, RESET = (
    "\033[92m", "\033[91m", "\033[2m", "\033[1m", "\033[0m"
)
passed = failed = 0

TODAY = date(2026, 8, 10)


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  {GREEN}pass{RESET}  {label}")
    else:
        failed += 1
        print(f"  {RED}FAIL{RESET}  {label}")
        for line in str(detail).splitlines()[:8]:
            print(f"        {DIM}{line}{RESET}")


def days_ago(*offsets):
    return [TODAY - timedelta(days=n) for n in offsets]


# ---------------------------------------------------------------------------

def test_contiguous_counting():
    print(f"\n{BOLD}1. Counting over a contiguous run of days{RESET}")

    def run(flags):
        seq = [(TODAY - timedelta(days=len(flags) - 1 - i), f)
               for i, f in enumerate(flags)]
        return streaks.over(seq)

    for flags, cur, best, label in [
        ([True] * 5,                    5, 5, "five in a row"),
        ([True, True, False, True, True], 2, 2, "a break in the middle"),
        ([True, True, True, False],     0, 3, "the run ended yesterday"),
        ([False] * 4,                   0, 0, "never"),
        ([True],                        1, 1, "a single day"),
        ([],                            0, 0, "no days at all"),
    ]:
        s = run(flags)
        check(f"{label}: current {cur}, best {best}",
              (s.current, s.best) == (cur, best), f"got ({s.current}, {s.best})")


def test_same_day_counts_once():
    """The bug: three challenges in one evening read as a three-day streak."""
    print(f"\n{BOLD}2. Several completions on one day are still one day{RESET}")

    # Exactly the shape of the real rows for user 1.
    same_evening = [TODAY - timedelta(days=1)] * 3 + [TODAY]
    s = streaks.from_dates(same_evening, today=TODAY)

    check("four rows across two days is a 2-day streak, not 4",
          s.current == 2, f"current {s.current}")
    check("...and the best is also 2", s.best == 2, f"best {s.best}")

    # The old implementation, for contrast - it counted rows.
    old = len([1 for _ in same_evening])
    check(f"the old row-counting version would have said {old}",
          old == 4 and s.current != old)


def test_gaps_break_the_run():
    """The other bug: absent days were invisible, so nothing broke a streak."""
    print(f"\n{BOLD}3. Missing days break a run{RESET}")

    # Four completions spread over two months, like user 4's real data.
    scattered = [date(2025, 9, 22), date(2025, 10, 12),
                 date(2025, 11, 20), date(2025, 11, 25)]
    s = streaks.from_dates(scattered, today=TODAY)

    check("weeks apart is not a 4-day streak", s.best == 1, f"best {s.best}")
    check("...and none of it is current", s.current == 0, f"current {s.current}")

    # Consecutive days DO count.
    s2 = streaks.from_dates(days_ago(3, 2, 1), today=TODAY)
    check("three consecutive days is a 3-day streak",
          s2.current == 3 and s2.best == 3, f"({s2.current}, {s2.best})")


def test_stale_runs_are_not_current():
    print(f"\n{BOLD}4. A run that ended months ago is not 'current'{RESET}")

    old_run = [date(2025, 11, 20), date(2025, 11, 21), date(2025, 11, 22)]
    s = streaks.from_dates(old_run, today=TODAY)
    check("a 3-day run from last year is not current", s.current == 0, s.current)
    check("...but it is still the best", s.best == 3, s.best)

    # Today unfinished must not zero a live run - the grace day.
    live = streaks.from_dates(days_ago(2, 1), today=TODAY)
    check("a run ending yesterday IS current", live.current == 2, live.current)

    ended = streaks.from_dates(days_ago(3, 2), today=TODAY)
    check("a run ending two days ago is not", ended.current == 0, ended.current)

    including_today = streaks.from_dates(days_ago(2, 1, 0), today=TODAY)
    check("a run including today is current", including_today.current == 3,
          including_today.current)


def test_messy_input():
    print(f"\n{BOLD}5. Real data is unordered and has duplicates{RESET}")

    jumbled = days_ago(1, 3, 2, 1, 2)      # out of order, repeated
    s = streaks.from_dates(jumbled, today=TODAY)
    check("order does not matter", s.current == 3, f"current {s.current}")
    check("duplicates do not inflate it", s.best == 3, f"best {s.best}")

    check("an empty set is zero, not a crash",
          streaks.from_dates([], today=TODAY).current == 0)
    check("Nones are ignored",
          streaks.from_dates([None, TODAY], today=TODAY).current == 1)


def test_adherence_still_agrees():
    """The dashboard streak must be unchanged by the refactor."""
    print(f"\n{BOLD}6. The adherence streak is unchanged{RESET}")

    from app.services import adherence

    class FakeDay:
        def __init__(self, day, hit):
            self.day = day
            self.hit = hit

    def run(flags):
        return adherence._streaks(
            [FakeDay(TODAY - timedelta(days=len(flags) - 1 - i), f)
             for i, f in enumerate(flags)])

    for flags, cur, best, label in [
        ([True] * 5,                      5, 5, "five on-target days"),
        ([True, True, False, True, True], 2, 2, "a miss in the middle"),
        ([True] * 4 + [False],            0, 4, "yesterday unlogged"),
        ([False] * 5,                     0, 0, "never on target"),
    ]:
        s = run(flags)
        check(f"{label}: ({cur}, {best})",
              (s.current, s.best) == (cur, best), f"got ({s.current}, {s.best})")

    check("adherence delegates rather than duplicating",
          "streaks.over" in (ROOT / "app/services/adherence.py").read_text(),
          "the shared implementation is the point")


def test_no_inline_streak_loops_remain():
    print(f"\n{BOLD}7. No second implementation crept back{RESET}")

    import re
    offenders = []
    for path in (ROOT / "app").rglob("*.py"):
        if path.name == "streaks.py":
            continue
        text = path.read_text(errors="ignore")
        # The tell: a counter incremented inside a loop over progress rows.
        if re.search(r"temp_streak\s*\+=\s*1", text):
            offenders.append(str(path.relative_to(ROOT)))
        if re.search(r"longest_streak\s*=\s*max\(", text):
            offenders.append(str(path.relative_to(ROOT)))
    check("no hand-rolled streak loops outside services/streaks.py",
          not offenders, sorted(set(offenders)))

    users = [p.name for p in (ROOT / "app").rglob("*.py")
             if "streaks." in p.read_text(errors="ignore") and p.name != "streaks.py"]
    check(f"both callers use the shared module ({', '.join(sorted(users))})",
          len(set(users)) >= 2, users)


def test_no_orphan_tests():
    print(f"\n{BOLD}8. No test is defined and then forgotten{RESET}")
    import inspect
    body = inspect.getsource(main)
    defined = {n for n, o in globals().items()
               if n.startswith("test_") and inspect.isfunction(o)}
    missing = sorted(n for n in defined if f"{n}()" not in body)
    check(f"all {len(defined)} test functions are called", not missing, missing)


def main():
    test_contiguous_counting()
    test_same_day_counts_once()
    test_gaps_break_the_run()
    test_stale_runs_are_not_current()
    test_messy_input()
    test_adherence_still_agrees()
    test_no_inline_streak_loops_remain()
    test_no_orphan_tests()

    print(f"\n{BOLD}{'-' * 62}{RESET}")
    print(f"{GREEN}{passed} passed{RESET}, {RED if failed else DIM}{failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
