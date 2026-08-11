#!/usr/bin/env python3
"""
Is the target weight actually being reached?

Setting a target was already possible; nothing ever answered whether it was
working. The temptation is to divide the remaining distance by the average rate
and print a date - which is wrong in three ways that all flatter the user:

  * Body weight swings a kilo or two a day on water. Two readings describe
    yesterday's dinner, not a direction.
  * Averaging over the whole history says someone who lost 4 kg in month one
    and nothing since is on track. They are not.
  * A trend pointing away from the target has no arrival date, and a flat one
    has an infinite one. Both need words, not a number.

These tests exist mostly to pin down the cases where the honest answer is "I
cannot tell you yet". A projection that is absent is a feature.

    python scripts/test_weight_progress.py
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services import weight_progress as wp   # noqa: E402

GREEN, RED, DIM, BOLD, RESET = (
    "\033[92m", "\033[91m", "\033[2m", "\033[1m", "\033[0m"
)
passed = failed = 0

NOW = datetime(2026, 8, 10, 12, 0)


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


def series(*, start_kg, kg_per_week, weeks, readings_per_week=1, end=NOW):
    """
    A believable run of weigh-ins, oldest first, ending now.

    `kg_per_week` is the rate of LOSS, so a positive number means the weight
    goes down over time. Index 0 is the oldest reading and sits at `start_kg`;
    the last reading is `start_kg - kg_per_week * weeks`.

    An earlier version had this inverted and generated a gain when asked for a
    loss, which failed the service for the helper's mistake.
    """
    out = []
    total = int(weeks * readings_per_week)
    for i in range(total + 1):
        days_ago = (total - i) * (7 / readings_per_week)
        weeks_elapsed = i / readings_per_week
        kg = start_kg - kg_per_week * weeks_elapsed
        out.append((end - timedelta(days=days_ago), round(kg, 2)))
    return out


# ---------------------------------------------------------------------------

def test_no_target():
    print(f"\n{BOLD}1. Without a target there is nothing to report{RESET}")
    r = wp.compute(target_kg=None, weigh_ins=[(NOW, 80.0)], now=NOW)
    check("has_target is False", not r.has_target)
    check("...and it says so rather than guessing",
          "No target" in r.note, r.note)
    check("...and the summary is honest", "No target" in r.summary(), r.summary())


def test_needs_enough_data():
    print(f"\n{BOLD}2. A trend needs more than two points{RESET}")

    one = wp.compute(target_kg=70, weigh_ins=[(NOW, 80.0)], now=NOW)
    check("a single reading gives no rate", one.rate_kg_per_week is None)
    check("...and no projected date", one.projected_date is None)
    check("...and explains what is needed",
          "more times" in one.note.lower() or "readings" in one.note.lower(), one.note)

    # Two readings a day apart. A naive implementation happily extrapolates
    # this to a confident arrival date; it is water weight.
    fast = wp.compute(
        target_kg=70,
        weigh_ins=[(NOW - timedelta(days=1), 81.5), (NOW, 80.0)],
        now=NOW,
    )
    check("two readings one day apart produce NO projection",
          fast.projected_date is None,
          f"projected {fast.projected_date} from a 1.5kg overnight swing")

    # Enough readings, but crammed into a few days.
    crammed = wp.compute(
        target_kg=70,
        weigh_ins=[(NOW - timedelta(days=d), 80 - d * 0.3) for d in (4, 3, 2, 1, 0)],
        now=NOW,
    )
    check("five readings over four days still produce no projection",
          crammed.projected_date is None, crammed.note)
    check("...and the reason names the timespan",
          "days" in crammed.note, crammed.note)


def test_steady_loss_projects():
    print(f"\n{BOLD}3. A real trend gets a real projection{RESET}")

    # 12 weeks losing 0.5 kg/week, from 86 down to 80. Target 74 - so 6 kg to
    # go at 0.5/week is about 12 weeks.
    r = wp.compute(target_kg=74, weigh_ins=series(start_kg=86, kg_per_week=0.5, weeks=12), now=NOW)

    check("current weight is the latest reading",
          abs(r.current_kg - 80.0) < 0.05, r.current_kg)
    check("direction is losing", r.direction == "losing", r.direction)
    check("rate is about -0.5 kg/week",
          r.rate_kg_per_week is not None and abs(r.rate_kg_per_week + 0.5) < 0.05,
          r.rate_kg_per_week)
    check("it is on track", r.on_track is True)
    check("about 6 kg to go", abs(r.to_go_kg + 6.0) < 0.1, r.to_go_kg)
    # Derived from the target and rate, never hardcoded - a literal here would
    # be wrong the moment a constant changes.
    expected_weeks = abs(r.to_go_kg) / abs(r.rate_kg_per_week)
    check(f"projection matches distance/rate ({expected_weeks:.0f} weeks)",
          abs(r.projected_weeks - expected_weeks) < 0.1, r.projected_weeks)
    check("a date is given", bool(r.projected_date), r.projected_date)
    check("the date is in the future",
          r.projected_date > NOW.date().isoformat(), r.projected_date)


def test_stalled():
    print(f"\n{BOLD}4. Flat is flat, and says so{RESET}")

    r = wp.compute(target_kg=74, weigh_ins=series(start_kg=80, kg_per_week=0.0, weeks=12), now=NOW)
    check("direction is stalled", r.direction == "stalled", r.direction)
    check("not on track", r.on_track is False)
    check("no projected date - it would be infinite", r.projected_date is None)
    check("the note suggests what to do",
          "calorie" in r.note.lower(), r.note)


def test_going_backwards():
    print(f"\n{BOLD}5. Moving away from the target{RESET}")

    # Wants to lose to 74, but has been gaining.
    r = wp.compute(target_kg=74, weigh_ins=series(start_kg=78, kg_per_week=-0.4, weeks=12), now=NOW)
    check("direction is gaining", r.direction == "gaining", r.direction)
    check("not on track", r.on_track is False)
    check("no projection - the trend never arrives", r.projected_date is None)
    check("it says which way is wanted", "go down" in r.note, r.note)
    check("...and warns", bool(r.warnings), r.warnings)

    # The mirror case: wants to gain, but is losing.
    g = wp.compute(target_kg=85, weigh_ins=series(start_kg=80, kg_per_week=0.4, weeks=12), now=NOW)
    check("gaining goal + losing trend is also off track", g.on_track is False)
    check("...and says go up", "go up" in g.note, g.note)


def test_reached():
    print(f"\n{BOLD}6. Arriving{RESET}")
    r = wp.compute(target_kg=74, weigh_ins=[(NOW - timedelta(days=d), 74.2) for d in (30, 20, 10, 0)], now=NOW)
    check("within tolerance counts as reached", r.reached, r.to_go_kg)
    check("percent complete is 100", r.percent_complete == 100.0)
    check("the summary says so", "reached" in r.summary().lower(), r.summary())

    # Just outside tolerance is NOT reached - the boundary matters.
    near = wp.compute(target_kg=74, weigh_ins=[(NOW, 74 + wp.REACHED_TOLERANCE_KG + 0.1)], now=NOW)
    check("just outside the tolerance is not 'reached'", not near.reached, near.to_go_kg)


def test_only_recent_readings_count():
    """Old progress must not make a current plateau look like success."""
    print(f"\n{BOLD}7. The trend window ignores ancient history{RESET}")

    old = [(NOW - timedelta(days=d), 90 - (200 - d) * 0.05)
           for d in range(200, 100, -7)]      # rapid loss, months ago
    recent = [(NOW - timedelta(days=d), 80.0) for d in range(56, -1, -7)]  # flat since

    r = wp.compute(target_kg=74, weigh_ins=old + recent, now=NOW)
    check("the recent plateau wins over the old loss",
          r.direction == "stalled", f"{r.direction}, rate {r.rate_kg_per_week}")
    check("no projection from stale progress", r.projected_date is None)
    check("but the total change still reflects everything",
          r.changed_kg is not None and r.changed_kg < -5, r.changed_kg)


def test_a_single_bad_reading_does_not_invert_the_trend():
    """
    Endpoints are where one bloated morning does the most damage.

    A last-minus-first calculation would read this as gaining. The regression
    weighs every point, so one outlier cannot flip the direction.
    """
    print(f"\n{BOLD}8. One bad weigh-in does not reverse everything{RESET}")

    clean = series(start_kg=86, kg_per_week=0.5, weeks=12)
    spiked = clean[:-1] + [(clean[-1][0], clean[-1][1] + 2.0)]   # +2kg on the last day

    r = wp.compute(target_kg=74, weigh_ins=spiked, now=NOW)
    naive = (spiked[-1][1] - spiked[0][1]) / max(1, (spiked[-1][0] - spiked[0][0]).days) * 7

    check("the regression still sees a loss",
          r.direction == "losing", f"{r.direction}, rate {r.rate_kg_per_week}")
    check("...even though the endpoints alone still look like a loss here",
          naive < 0, f"naive endpoint rate {naive:.3f}")
    check("the rate is dampened, not inverted",
          r.rate_kg_per_week < 0, r.rate_kg_per_week)


def test_days_since_weigh_in():
    print(f"\n{BOLD}9. Nudging{RESET}")
    r = wp.compute(target_kg=74,
                   weigh_ins=[(NOW - timedelta(days=21), 80.0)], now=NOW)
    check("it knows how long since the last weigh-in",
          r.days_since_weigh_in == 21, r.days_since_weigh_in)

    none_yet = wp.compute(target_kg=74, weigh_ins=[], fallback_weight_kg=80.0, now=NOW)
    check("with no weigh-ins it falls back to the profile weight",
          none_yet.current_kg == 80.0, none_yet.current_kg)
    check("...and reports no days-since", none_yet.days_since_weigh_in is None)


def test_serialisation():
    print(f"\n{BOLD}10. The shape the UI receives{RESET}")
    r = wp.compute(target_kg=74, weigh_ins=series(start_kg=86, kg_per_week=0.5, weeks=12), now=NOW)
    d = r.as_dict()
    for key in ("has_target", "target_kg", "current_kg", "to_go_kg", "direction",
                "rate_kg_per_week", "on_track", "reached", "projected_date",
                "percent_complete", "note"):
        check(f"as_dict has {key}", key in d, sorted(d))
    check("numbers are rounded for display",
          d["rate_kg_per_week"] == round(d["rate_kg_per_week"], 2), d["rate_kg_per_week"])
    check("the summary is one line", "\n" not in r.summary(), r.summary())


def test_no_orphan_tests():
    print(f"\n{BOLD}11. No test is defined and then forgotten{RESET}")
    import inspect
    body = inspect.getsource(main)
    defined = {n for n, o in globals().items()
               if n.startswith("test_") and inspect.isfunction(o)}
    missing = sorted(n for n in defined if f"{n}()" not in body)
    check(f"all {len(defined)} test functions are called", not missing, missing)


def main():
    test_no_target()
    test_needs_enough_data()
    test_steady_loss_projects()
    test_stalled()
    test_going_backwards()
    test_reached()
    test_only_recent_readings_count()
    test_a_single_bad_reading_does_not_invert_the_trend()
    test_days_since_weigh_in()
    test_serialisation()
    test_no_orphan_tests()

    print(f"\n{BOLD}{'-' * 62}{RESET}")
    print(f"{GREEN}{passed} passed{RESET}, {RED if failed else DIM}{failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
