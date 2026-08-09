"""
Points: what they are worth, and why.

THE PROBLEM WITH MOST POINT SYSTEMS
-----------------------------------
Reward only outcomes and you punish honesty: a day where somebody logged every
meal accurately and went 200 kcal over earns nothing, so the rational move is
to stop logging the bad days. The leaderboard then measures who eats perfectly,
which is mostly who is willing to under-report.

Reward only effort and the leaderboard measures who taps the most buttons.

So: effort earns the base, outcome earns a bonus, and effort is weighted high
enough that a bad-but-honest day still beats a day you hid from. Showing up is
the behaviour worth building; hitting macros is the behaviour worth celebrating.

THE FORMULA
-----------
Per local day:

    meal_logged        4 each, capped at 4 meals      up to  16
    day_complete      12  three or more meals logged         12
    day_on_target     25  all four macros in band            25
    macro_partial      4 each  per macro in band       up to 16
    workout_done      30  trained                            30
    workout_effort     0-15  scaled by minutes and RPE  up to 15
    rest_day           8  honest rest, still an answer         8
    weight_logged      6  a check-in                           6
    streak_bonus       3 x streak day, capped             up to 30
    challenge_done    40  a challenge finished                40

A perfect day is roughly 130 points before streak and challenge bonuses; a day
where you logged everything and missed every macro still earns 28, which is the
point. Nothing is ever deducted - see NO NEGATIVE POINTS below.

IDEMPOTENCY
-----------
Every award is keyed (user, local_date, reason) with a unique constraint in the
database. `award_for_day` recomputes the whole day and writes only what is
missing, so it can run on every meal log, every page load, or as a nightly
backfill, in any order, any number of times, and the total is identical.

NO NEGATIVE POINTS
------------------
Points are never removed once given. Partly this is fairness - a day's award
should not change because of something you did later - and partly it is
practical: a leaderboard where scores can fall is one where people stop
logging to protect their position, which defeats the entire purpose.

The one exception is deletion of the underlying data, which is handled by
recomputing rather than by subtracting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import MealLog, PointsLedger, User, WeightLog, WorkoutLog
from app.services import adherence, daytime

logger = logging.getLogger(__name__)


# --- the tariff ------------------------------------------------------------
# One place. Changing a number here changes it everywhere, and `backfill`
# can re-run history against the new values.

POINTS = {
    "meal_logged": 4,          # per meal, capped by MAX_SCORED_MEALS
    "day_complete": 12,        # 3+ meals in a day
    "day_on_target": 25,       # all four macros in band
    "macro_in_band": 4,        # per macro, when the day as a whole missed
    "workout_done": 30,
    "workout_effort": 15,      # maximum; scaled below
    "rest_day": 8,
    "weight_logged": 6,
    "streak_day": 3,           # per day of an active streak
    "challenge_done": 40,
}

MAX_SCORED_MEALS = 4           # logging 11 snacks is not four times the effort
MAX_STREAK_BONUS = 30          # a 30-day streak should not dwarf everything else

# Effort scaling. 45 minutes at RPE 7 is treated as a full session; below that
# scales down, above it does not scale up - rewarding ever-longer sessions is
# how a points system talks somebody into overtraining.
FULL_EFFORT_MINUTES = 45
FULL_EFFORT_INTENSITY = 7

REASONS = {
    "meal_logged": "Meals logged",
    "day_complete": "Full day logged",
    "day_on_target": "All macros on target",
    "macro_in_band": "Macros in band",
    "workout_done": "Workout completed",
    "workout_effort": "Workout effort",
    "rest_day": "Rest day taken",
    "weight_logged": "Weight check-in",
    "streak_day": "Streak bonus",
    "challenge_done": "Challenge completed",
}


# --- levels ----------------------------------------------------------------
# Thresholds widen as they go, so early levels arrive quickly - the first week
# should produce visible movement - and later ones stay meaningful.

LEVELS = [
    (0, "Getting started"),
    (150, "Finding a rhythm"),
    (450, "Consistent"),
    (1000, "Committed"),
    (2000, "Dialled in"),
    (3500, "Disciplined"),
    (5500, "Relentless"),
    (8000, "Formidable"),
    (12000, "Elite"),
]


def level_for(total: int) -> Dict[str, Any]:
    """Which level a total sits in, and how far to the next."""
    index = 0
    for i, (threshold, _) in enumerate(LEVELS):
        if total >= threshold:
            index = i
    floor, title = LEVELS[index]
    if index + 1 < len(LEVELS):
        ceiling = LEVELS[index + 1][0]
        span = ceiling - floor
        return {
            "level": index + 1,
            "title": title,
            "points": total,
            "floor": floor,
            "next_at": ceiling,
            "to_next": ceiling - total,
            "progress": round((total - floor) / span, 3) if span else 1.0,
            "next_title": LEVELS[index + 1][1],
        }
    return {
        "level": index + 1, "title": title, "points": total, "floor": floor,
        "next_at": None, "to_next": None, "progress": 1.0, "next_title": None,
    }


# --- computing a day -------------------------------------------------------

@dataclass
class Award:
    reason: str
    points: int
    detail: str


def _effort_points(workout: WorkoutLog) -> Optional[Award]:
    """
    Extra for a harder session, bounded.

    Missing minutes or intensity is not zero effort - it means they used the
    one-tap path, which is the path we WANT to be easy. Treat unknown as a
    moderate session rather than penalising the quick answer.
    """
    minutes = workout.minutes if workout.minutes else FULL_EFFORT_MINUTES * 0.6
    intensity = workout.intensity if workout.intensity else FULL_EFFORT_INTENSITY * 0.7

    time_factor = min(1.0, minutes / FULL_EFFORT_MINUTES)
    effort_factor = min(1.0, intensity / FULL_EFFORT_INTENSITY)
    scaled = round(POINTS["workout_effort"] * time_factor * effort_factor)

    if scaled <= 0:
        return None
    detail = f"{int(minutes)} min" if workout.minutes else "session logged"
    if workout.intensity:
        detail += f" at {workout.intensity}/10"
    return Award("workout_effort", scaled, detail)


def compute_day(db: Session, user: User, day: date,
                streak: Optional[int] = None) -> List[Award]:
    """
    Everything earned on one local day. Pure of side effects - it reads, it
    does not write, so it can be used for previews and "what would I get".
    """
    awards: List[Award] = []
    tz = daytime.zone_for(user)
    start, end = daytime.day_bounds(day, tz=tz)

    meals = (
        db.query(MealLog)
        .filter(MealLog.user_id == user.id,
                MealLog.logged_at >= start, MealLog.logged_at < end)
        .all()
    )

    # --- effort: logging at all -------------------------------------------
    if meals:
        scored = min(len(meals), MAX_SCORED_MEALS)
        awards.append(Award(
            "meal_logged", POINTS["meal_logged"] * scored,
            f"{len(meals)} meal{'s' if len(meals) != 1 else ''} logged"
            + (f" ({MAX_SCORED_MEALS} scored)" if len(meals) > MAX_SCORED_MEALS else ""),
        ))
        if len(meals) >= 3:
            awards.append(Award("day_complete", POINTS["day_complete"],
                                "breakfast, lunch and dinner all logged"))

    # --- outcome: did the day land ----------------------------------------
    goal = adherence.active_goal(db, user.id)
    result = adherence.evaluate_day(day, meals, goal)

    if result.assessable:
        if result.hit:
            awards.append(Award("day_on_target", POINTS["day_on_target"],
                                "every macro inside its band"))
        else:
            # Partial credit per macro. Without this, being 2g over on fat
            # scores identically to eating nothing but chips, and the second
            # day of that is when people stop trying.
            in_band = [m for m in result.macros.values() if m.assessable and m.hit]
            if in_band:
                awards.append(Award(
                    "macro_in_band", POINTS["macro_in_band"] * len(in_band),
                    f"{', '.join(m.name for m in in_band)} in band",
                ))

    # --- workout -----------------------------------------------------------
    workout = (
        db.query(WorkoutLog)
        .filter(WorkoutLog.user_id == user.id, WorkoutLog.local_date == day)
        .first()
    )
    if workout and workout.status == "done":
        label = workout.workout_type or "session"
        awards.append(Award("workout_done", POINTS["workout_done"],
                            f"{label} completed"))
        effort = _effort_points(workout)
        if effort:
            awards.append(effort)
    elif workout and workout.status == "rest":
        # A declared rest day earns less than training and more than silence.
        # Rest is part of a programme, and a system that only rewards training
        # is one that quietly punishes recovery.
        awards.append(Award("rest_day", POINTS["rest_day"], "rest day taken"))

    # --- weight check-in ---------------------------------------------------
    weighed = (
        db.query(WeightLog)
        .filter(WeightLog.user_id == user.id,
                WeightLog.logged_at >= start, WeightLog.logged_at < end)
        .first()
    )
    if weighed:
        awards.append(Award("weight_logged", POINTS["weight_logged"],
                            "weight recorded"))

    # --- streak ------------------------------------------------------------
    if streak and streak >= 2 and result.hit:
        bonus = min(POINTS["streak_day"] * streak, MAX_STREAK_BONUS)
        awards.append(Award("streak_day", bonus, f"{streak} days on target in a row"))

    return awards


# --- writing ---------------------------------------------------------------

def award_for_day(db: Session, user: User, day: date,
                  streak: Optional[int] = None) -> Dict[str, Any]:
    """
    Persist the day's awards, writing only what is not already there.

    Safe to call repeatedly. The unique constraint is the real guard - the
    pre-check below is an optimisation, and a race between two requests
    resolves to one row because the second INSERT fails and is swallowed.
    """
    computed = compute_day(db, user, day, streak=streak)

    existing = {
        row.reason: row
        for row in db.query(PointsLedger).filter(
            PointsLedger.user_id == user.id, PointsLedger.local_date == day
        ).all()
    }

    added, updated = [], []
    for award in computed:
        current = existing.get(award.reason)
        if current is None:
            db.add(PointsLedger(
                user_id=user.id, local_date=day, reason=award.reason,
                points=award.points, detail=award.detail,
            ))
            added.append(award)
        elif award.points > current.points:
            # Points can go UP within a day - logging lunch after breakfast
            # earns more - but never down. See NO NEGATIVE POINTS.
            current.points = award.points
            current.detail = award.detail
            updated.append(award)

    if added or updated:
        try:
            db.commit()
        except IntegrityError:
            # Another request awarded the same day first. Its row is just as
            # correct as ours, so take theirs.
            db.rollback()
            logger.info("points for %s on %s were awarded concurrently", user.id, day)

    return {
        "date": day.isoformat(),
        "awarded": [{"reason": a.reason, "points": a.points, "detail": a.detail}
                    for a in computed],
        "total": sum(a.points for a in computed),
        "new": sum(a.points for a in added),
    }


def sync(db: Session, user: User, days: int = 3) -> int:
    """
    Bring the last few days up to date.

    Called after a meal or workout is logged, and on the profile screen. A
    short window rather than one day because a meal can be logged for
    yesterday, and because a day's streak bonus depends on days after it.
    """
    tz = daytime.zone_for(user)
    today = daytime.local_date(tz=tz)
    results = adherence.history(db, user, days=max(days, 7), include_today=True)
    by_day = {r.day: r for r in results}

    total = 0
    for offset in range(days):
        day = today - timedelta(days=offset)
        # Streak as of that day, counting backwards.
        streak = 0
        cursor = day
        while by_day.get(cursor) and by_day[cursor].hit:
            streak += 1
            cursor -= timedelta(days=1)
        total += award_for_day(db, user, day, streak=streak)["new"]
    return total


def backfill(db: Session, user: User, days: int = 365) -> Dict[str, Any]:
    """
    Award points for history that predates this feature.

    Without this, everybody starts at zero regardless of months of logging,
    which reads as the app forgetting what they did.
    """
    tz = daytime.zone_for(user)
    today = daytime.local_date(tz=tz)
    results = adherence.history(db, user, days=days, include_today=True)
    by_day = {r.day: r for r in results}

    awarded = 0
    touched = 0
    for offset in range(days, -1, -1):
        day = today - timedelta(days=offset)
        streak = 0
        cursor = day
        while by_day.get(cursor) and by_day[cursor].hit:
            streak += 1
            cursor -= timedelta(days=1)
        result = award_for_day(db, user, day, streak=streak)
        if result["total"]:
            touched += 1
        awarded += result["new"]

    return {"days_scanned": days, "days_with_points": touched, "points_added": awarded}


# --- reading ---------------------------------------------------------------

def total_points(db: Session, user_id: int) -> int:
    return int(
        db.query(func.coalesce(func.sum(PointsLedger.points), 0))
        .filter(PointsLedger.user_id == user_id)
        .scalar() or 0
    )


def breakdown(db: Session, user_id: int, days: Optional[int] = None,
              user: Optional[User] = None) -> List[Dict[str, Any]]:
    """Points grouped by reason, biggest first - 'where did these come from'."""
    query = db.query(
        PointsLedger.reason,
        func.sum(PointsLedger.points).label("points"),
        func.count(PointsLedger.id).label("times"),
    ).filter(PointsLedger.user_id == user_id)

    if days and user is not None:
        query = query.filter(PointsLedger.local_date >= daytime.local_date(user) - timedelta(days=days))

    rows = query.group_by(PointsLedger.reason).all()
    return sorted(
        [
            {
                "reason": r.reason,
                "label": REASONS.get(r.reason, r.reason.replace("_", " ").capitalize()),
                "points": int(r.points or 0),
                "times": int(r.times or 0),
            }
            for r in rows
        ],
        key=lambda d: -d["points"],
    )


def daily_series(db: Session, user: User, days: int = 30) -> List[Dict[str, Any]]:
    """Points per day, oldest first. Feeds the sparkline on the profile."""
    tz = daytime.zone_for(user)
    today = daytime.local_date(tz=tz)
    first = today - timedelta(days=days - 1)

    rows = (
        db.query(PointsLedger.local_date, func.sum(PointsLedger.points).label("points"))
        .filter(PointsLedger.user_id == user.id, PointsLedger.local_date >= first)
        .group_by(PointsLedger.local_date)
        .all()
    )
    totals = {r.local_date: int(r.points or 0) for r in rows}
    return [
        {"date": (first + timedelta(days=i)).isoformat(),
         "points": totals.get(first + timedelta(days=i), 0)}
        for i in range(days)
    ]


def leaderboard(db: Session, days: Optional[int] = None,
                limit: int = 20) -> List[Dict[str, Any]]:
    """
    Ranked totals. One grouped SUM - this is what the ledger buys.

    `days` is a rolling window rather than a calendar one, because an all-time
    board is unwinnable for anybody who joins late, and that is the fastest way
    to make a leaderboard demotivating.
    """
    query = db.query(
        PointsLedger.user_id,
        func.sum(PointsLedger.points).label("points"),
        func.count(func.distinct(PointsLedger.local_date)).label("active_days"),
    )
    if days:
        # Uses UTC today as the cutoff rather than each user's local date.
        # A rolling board cannot have a per-user boundary without making the
        # ranking incomparable, and one day of slack at the edge is harmless.
        query = query.filter(
            PointsLedger.local_date >= daytime.utcnow().date() - timedelta(days=days)
        )

    rows = query.group_by(PointsLedger.user_id).order_by(
        func.sum(PointsLedger.points).desc()
    ).limit(limit).all()

    users = {
        u.id: u for u in db.query(User).filter(
            User.id.in_([r.user_id for r in rows])
        ).all()
    } if rows else {}

    out = []
    for rank, row in enumerate(rows, start=1):
        user = users.get(row.user_id)
        points = int(row.points or 0)
        out.append({
            "rank": rank,
            "user_id": row.user_id,
            "name": (user.full_name or user.username) if user else "Unknown",
            "points": points,
            "active_days": int(row.active_days or 0),
            "level": level_for(points)["level"],
            "title": level_for(points)["title"],
        })
    return out


def rank_of(db: Session, user_id: int, days: Optional[int] = None) -> Optional[int]:
    """Where one user sits, without loading the whole board."""
    mine = total_points(db, user_id) if not days else int(
        db.query(func.coalesce(func.sum(PointsLedger.points), 0))
        .filter(PointsLedger.user_id == user_id,
                PointsLedger.local_date >= daytime.utcnow().date() - timedelta(days=days))
        .scalar() or 0
    )
    if not mine:
        return None

    subquery = db.query(
        PointsLedger.user_id, func.sum(PointsLedger.points).label("points")
    )
    if days:
        subquery = subquery.filter(
            PointsLedger.local_date >= daytime.utcnow().date() - timedelta(days=days)
        )
    subquery = subquery.group_by(PointsLedger.user_id).subquery()

    ahead = db.query(func.count()).select_from(subquery).filter(
        subquery.c.points > mine
    ).scalar() or 0
    return int(ahead) + 1
