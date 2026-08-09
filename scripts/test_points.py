#!/usr/bin/env python3
"""
Points must be trustworthy, or the leaderboard is worthless.

A points system fails in ways that are invisible until somebody notices their
score is wrong, at which point they stop believing any of it. The properties
that matter:

  * awarding twice awards once - enforced by the database, not by care
  * a score never falls
  * the order of events does not change the total
  * a backfill produces exactly what live awarding would have
  * unlogged days are worth nothing, and honest bad days are worth something

Runs against a temporary SQLite file, so it never touches real data.

    python scripts/test_points.py
"""

import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_DB = Path(tempfile.mkdtemp()) / "points_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

GREEN, RED, DIM, BOLD, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[1m", "\033[0m"
passed = failed = 0

TZ = "Asia/Kolkata"


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


# ---------------------------------------------------------------------------

def fresh_db():
    """A clean database with the tables this feature needs."""
    from app.database import Base, SessionLocal, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def make_user(db, username="tester"):
    from app.database import Goal, User
    user = User(email=f"{username}@test", username=username,
                hashed_password="x", full_name="Test User",
                age=25, height=180, weight=75, timezone=TZ)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(Goal(user_id=user.id, goal_type="muscle_gain", target_calories=2000,
                target_protein=150, target_carbs=200, target_fat=60,
                is_active=True, created_at=datetime.utcnow()))
    db.commit()
    return user


def log_meals(db, user, day, count=3, per_meal=None):
    """Meals on a given LOCAL day, stored as UTC the way the app does."""
    from zoneinfo import ZoneInfo

    from app.database import MealLog
    tz = ZoneInfo(TZ)
    macros = per_meal or {"calories": 2000 / count, "protein": 150 / count,
                          "carbs": 200 / count, "fat": 60 / count}
    for i in range(count):
        # Spread across waking hours without ever leaving the local day. The
        # naive `8 + i * 4` overflowed past five meals and raised, which is
        # how the meal-spam test found this.
        minute_of_day = 7 * 60 + int(i * (15 * 60) / max(1, count))
        local = datetime(day.year, day.month, day.day,
                         minute_of_day // 60, minute_of_day % 60, tzinfo=tz)
        db.add(MealLog(
            user_id=user.id, food_item_id=None, meal_type="meal",
            calories=macros["calories"], protein=macros["protein"],
            carbs=macros["carbs"], fat=macros["fat"],
            logged_at=local.astimezone(timezone.utc).replace(tzinfo=None),
        ))
    db.commit()


def days_ago(n):
    """
    A local date n days back from now.

    Fixed calendar dates broke this suite: `sync` deliberately only looks at
    the last few days, so a fixture pinned to 2026-08-01 fell outside its
    window and produced a backfill/live mismatch that looked like an engine
    bug and was really a test that could not be satisfied.
    """
    from app.services import daytime
    from zoneinfo import ZoneInfo
    return daytime.local_date(tz=ZoneInfo(TZ)) - timedelta(days=n)


def log_workout(db, user, day, status="done", minutes=45, intensity=7):
    from app.database import WorkoutLog
    db.add(WorkoutLog(user_id=user.id, local_date=day, status=status,
                      minutes=minutes, intensity=intensity))
    db.commit()


# ---------------------------------------------------------------------------

def test_idempotency():
    """The property everything else depends on."""
    from app.services import points_engine
    print(f"\n{BOLD}1. Awarding twice awards once{RESET}")

    db = fresh_db()
    user = make_user(db)
    day = days_ago(1)
    log_meals(db, user, day, 3)
    log_workout(db, user, day)

    first = points_engine.award_for_day(db, user, day)
    total_after_first = points_engine.total_points(db, user.id)
    check("first award writes points", total_after_first > 0, total_after_first)

    for i in range(5):
        points_engine.award_for_day(db, user, day)
    check("awarding 5 more times changes nothing",
          points_engine.total_points(db, user.id) == total_after_first,
          f"{total_after_first} -> {points_engine.total_points(db, user.id)}")
    check("...and reports 0 new the second time",
          points_engine.award_for_day(db, user, day)["new"] == 0)

    from app.database import PointsLedger
    rows = db.query(PointsLedger).filter(PointsLedger.local_date == day).all()
    reasons = [r.reason for r in rows]
    check("one ledger row per reason", len(reasons) == len(set(reasons)), reasons)

    # The database is the real guard, not the pre-check in award_for_day.
    from sqlalchemy.exc import IntegrityError
    db.add(PointsLedger(user_id=user.id, local_date=day,
                        reason=rows[0].reason, points=999))
    try:
        db.commit()
        duplicated = True
    except IntegrityError:
        db.rollback()
        duplicated = False
    check("the unique constraint rejects a duplicate at the database level",
          not duplicated)

    db.close()


def test_never_decreases():
    """A score that can fall is a score people stop logging to protect."""
    from app.services import points_engine
    print(f"\n{BOLD}2. Points never go down{RESET}")

    db = fresh_db()
    user = make_user(db)
    day = days_ago(1)

    log_meals(db, user, day, 1, {"calories": 700, "protein": 50, "carbs": 70, "fat": 20})
    points_engine.award_for_day(db, user, day)
    after_one = points_engine.total_points(db, user.id)

    log_meals(db, user, day, 2, {"calories": 650, "protein": 50, "carbs": 65, "fat": 20})
    points_engine.award_for_day(db, user, day)
    after_three = points_engine.total_points(db, user.id)

    check("logging more in the same day increases the total",
          after_three > after_one, f"{after_one} -> {after_three}")

    # Now make the day worse by adding a huge meal that blows every band.
    log_meals(db, user, day, 1, {"calories": 3000, "protein": 10, "carbs": 400, "fat": 150})
    points_engine.award_for_day(db, user, day)
    after_blowout = points_engine.total_points(db, user.id)
    check("blowing the day out does not remove points already given",
          after_blowout >= after_three, f"{after_three} -> {after_blowout}")

    db.close()


def test_order_independence():
    """Two histories with the same facts must produce the same total."""
    from app.services import points_engine
    print(f"\n{BOLD}3. Order of awarding does not matter{RESET}")

    days = [days_ago(i) for i in range(1, 6)]

    db = fresh_db()
    user = make_user(db, "forward")
    for day in days:
        log_meals(db, user, day, 3)
        log_workout(db, user, day)
    for day in days:
        points_engine.award_for_day(db, user, day)
    forward = points_engine.total_points(db, user.id)
    db.close()

    db = fresh_db()
    user = make_user(db, "backward")
    for day in days:
        log_meals(db, user, day, 3)
        log_workout(db, user, day)
    for day in reversed(days):
        points_engine.award_for_day(db, user, day)
    backward = points_engine.total_points(db, user.id)
    db.close()

    check("forward and reverse awarding agree", forward == backward,
          f"forward={forward} backward={backward}")
    check("both are non-zero", forward > 0, forward)


def test_backfill_matches_live():
    """
    Backfill must produce what live awarding would have.

    If it does not, existing users get a different score from new ones for
    identical behaviour - which is the kind of unfairness that is invisible
    until somebody compares.
    """
    from app.services import points_engine
    print(f"\n{BOLD}4. Backfill equals live awarding{RESET}")

    days = [days_ago(i) for i in range(1, 7)]

    db = fresh_db()
    live = make_user(db, "live")
    for day in days:
        log_meals(db, live, day, 3)
        log_workout(db, live, day)
        points_engine.sync(db, live, days=8)
    live_total = points_engine.total_points(db, live.id)

    lazy = make_user(db, "lazy")
    for day in days:
        log_meals(db, lazy, day, 3)
        log_workout(db, lazy, day)
    points_engine.backfill(db, lazy, days=400)
    lazy_total = points_engine.total_points(db, lazy.id)

    check("a backfilled user scores the same as one awarded live",
          live_total == lazy_total, f"live={live_total} backfilled={lazy_total}")
    check("backfilling again adds nothing",
          points_engine.backfill(db, lazy, days=400)["points_added"] == 0)
    db.close()


def test_the_tariff():
    """The formula, day by day, so the numbers are pinned down."""
    from app.services import points_engine
    print(f"\n{BOLD}5. What each behaviour is worth{RESET}")

    db = fresh_db()
    user = make_user(db)
    day = days_ago(1)

    def points_for(setup):
        from app.database import MealLog, PointsLedger, WorkoutLog
        db.query(MealLog).delete()
        db.query(WorkoutLog).delete()
        db.query(PointsLedger).delete()
        db.commit()
        setup()
        return sum(a.points for a in points_engine.compute_day(db, user, day))

    nothing = points_for(lambda: None)
    check("a day with nothing logged is worth 0", nothing == 0, nothing)

    one_meal = points_for(lambda: log_meals(db, user, day, 1,
                                            {"calories": 700, "protein": 50,
                                             "carbs": 70, "fat": 20}))
    check("one meal earns something", one_meal > 0, one_meal)

    perfect = points_for(lambda: log_meals(db, user, day, 3))
    check("a perfect food day beats one meal", perfect > one_meal,
          f"{one_meal} -> {perfect}")

    def bad_but_logged():
        log_meals(db, user, day, 3, {"calories": 1200, "protein": 20,
                                     "carbs": 180, "fat": 45})
    honest = points_for(bad_but_logged)
    check("an honest bad day still scores", honest > 0, honest)
    check("...but less than a good day", honest < perfect, f"{honest} vs {perfect}")
    check("...and more than not logging at all", honest > nothing)

    def perfect_plus_workout():
        log_meals(db, user, day, 3)
        log_workout(db, user, day, minutes=45, intensity=7)
    with_workout = points_for(perfect_plus_workout)
    check("a workout is worth a lot", with_workout - perfect >= 40,
          f"{perfect} -> {with_workout}")

    def rest():
        log_meals(db, user, day, 3)
        log_workout(db, user, day, status="rest")
    rested = points_for(rest)
    check("a declared rest day earns less than training",
          perfect < rested < with_workout, f"rest={rested}")
    check("...but more than saying nothing", rested > perfect)

    # Effort scaling, bounded so the system never rewards overtraining.
    def session(minutes, intensity):
        return points_for(lambda: log_workout(db, user, day,
                                              minutes=minutes, intensity=intensity))
    short_easy = session(15, 3)
    full = session(45, 7)
    marathon = session(180, 10)
    check("a longer, harder session scores more than a short easy one",
          full > short_easy, f"{short_easy} vs {full}")
    check("effort is capped - 3 hours does not beat 45 min by much",
          marathon - full <= points_engine.POINTS["workout_effort"] * 0.5,
          f"45min={full} 180min={marathon}")

    # Meal spam.
    spam = points_for(lambda: log_meals(db, user, day, 20,
                                        {"calories": 100, "protein": 7.5,
                                         "carbs": 10, "fat": 3}))
    four = points_for(lambda: log_meals(db, user, day, 4,
                                        {"calories": 500, "protein": 37.5,
                                         "carbs": 50, "fat": 15}))
    check("logging 20 tiny meals does not beat logging 4 real ones",
          spam <= four, f"20 meals={spam}, 4 meals={four}")

    db.close()


def test_levels():
    from app.services import points_engine
    print(f"\n{BOLD}6. Levels{RESET}")

    check("zero points is level 1", points_engine.level_for(0)["level"] == 1)
    check("progress at zero is 0", points_engine.level_for(0)["progress"] == 0)

    previous = 0
    for total in (0, 100, 200, 500, 1500, 3000, 6000, 20000):
        level = points_engine.level_for(total)["level"]
        check(f"{total} pts -> level {level}, never going backwards",
              level >= previous, f"was {previous}")
        previous = level

    top = points_engine.level_for(999999)
    check("the top level has no next", top["next_at"] is None and top["to_next"] is None)
    check("...and reports full progress", top["progress"] == 1.0)

    # Every threshold must produce progress in [0, 1].
    bad = [t for t in range(0, 15000, 137)
           if not 0 <= points_engine.level_for(t)["progress"] <= 1]
    check("progress is always between 0 and 1", not bad, bad[:5])


def test_timezone_days():
    """
    Points are per local day. A 00:30 IST meal must score today, not yesterday
    - the exact bug the timezone work fixed.
    """
    from zoneinfo import ZoneInfo

    from app.database import MealLog
    from app.services import points_engine
    print(f"\n{BOLD}7. Points use the user's day{RESET}")

    db = fresh_db()
    user = make_user(db)
    tz = ZoneInfo(TZ)
    day = date(2026, 8, 9)

    late = datetime(2026, 8, 9, 0, 30, tzinfo=tz)
    db.add(MealLog(user_id=user.id, meal_type="dinner", calories=2000,
                   protein=150, carbs=200, fat=60,
                   logged_at=late.astimezone(timezone.utc).replace(tzinfo=None)))
    db.commit()

    today_points = sum(a.points for a in points_engine.compute_day(db, user, day))
    yesterday_points = sum(a.points for a in points_engine.compute_day(
        db, user, day - timedelta(days=1)))

    check("a 00:30 IST meal scores on the 9th", today_points > 0, today_points)
    check("...and not on the 8th", yesterday_points == 0, yesterday_points)
    db.close()


def test_leaderboard():
    from app.services import points_engine
    print(f"\n{BOLD}8. Leaderboard{RESET}")

    db = fresh_db()
    days = [days_ago(i) for i in range(1, 5)]

    heavy = make_user(db, "heavy")
    light = make_user(db, "light")
    absent = make_user(db, "absent")

    for day in days:
        log_meals(db, heavy, day, 3)
        log_workout(db, heavy, day)
    log_meals(db, light, days[0], 1, {"calories": 600, "protein": 40,
                                      "carbs": 60, "fat": 18})
    for user in (heavy, light, absent):
        points_engine.backfill(db, user, days=400)

    board = points_engine.leaderboard(db, days=None, limit=10)
    check("the board is ranked highest first",
          [e["points"] for e in board] == sorted((e["points"] for e in board), reverse=True),
          [(e["name"], e["points"]) for e in board])
    check("the heavy logger is first",
          board and board[0]["user_id"] == heavy.id,
          [(e["user_id"], e["points"]) for e in board])
    check("someone with no points is not listed",
          absent.id not in [e["user_id"] for e in board])
    check("ranks are 1..n with no gaps",
          [e["rank"] for e in board] == list(range(1, len(board) + 1)))

    check("rank_of agrees with the board",
          points_engine.rank_of(db, heavy.id) == 1)
    check("a user with no points has no rank",
          points_engine.rank_of(db, absent.id) is None)

    # The sum must equal the ledger, or the board is lying.
    total = points_engine.total_points(db, heavy.id)
    check("board points equal the user's ledger total",
          board[0]["points"] == total, f"{board[0]['points']} vs {total}")
    db.close()


def test_breakdown_adds_up():
    """'Where did these come from' must actually account for all of them."""
    from app.services import points_engine
    print(f"\n{BOLD}9. The breakdown accounts for every point{RESET}")

    db = fresh_db()
    user = make_user(db)
    for i in range(5):
        day = days_ago(i + 1)
        log_meals(db, user, day, 3)
        if i % 2 == 0:
            log_workout(db, user, day)
    points_engine.backfill(db, user, days=400)

    total = points_engine.total_points(db, user.id)
    parts = points_engine.breakdown(db, user.id)
    check("the parts sum to the total",
          sum(p["points"] for p in parts) == total,
          f"{sum(p['points'] for p in parts)} vs {total}")
    check("every part has a human label",
          all(p["label"] and not p["label"].islower() or " " in p["label"] for p in parts),
          [p["label"] for p in parts])
    check("the biggest contributor is listed first",
          parts == sorted(parts, key=lambda p: -p["points"]))

    series = points_engine.daily_series(db, user, days=30)
    check("the daily series covers the requested window", len(series) == 30)
    check("the series is ordered oldest first",
          [d["date"] for d in series] == sorted(d["date"] for d in series))
    db.close()


def main():
    test_idempotency()
    test_never_decreases()
    test_order_independence()
    test_backfill_matches_live()
    test_the_tariff()
    test_levels()
    test_timezone_days()
    test_leaderboard()
    test_breakdown_adds_up()

    print(f"\n{BOLD}{GREEN if not failed else RED}"
          f"{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
