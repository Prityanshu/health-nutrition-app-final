"""
Did they hit their targets - today, yesterday, and across the last week?

The app could answer "how many calories today" and nothing else. It could not
say whether yesterday was a good day, whether this week had been consistent, or
which macro keeps slipping. So every recommendation was made as if each day
existed on its own, and the assistant could tell someone they were "doing well"
on the fourth day running of missing protein by 40g.

WHAT COUNTS AS A HIT
--------------------
All four macros in band. Calories and carbs and fat within a tolerance either
side of target; protein at or above a floor, with over never counting against
you - nobody has ever been harmed by an extra 20g of protein, and a symmetric
band on protein would punish exactly the behaviour the app is trying to build.

This is a deliberately strict definition. Four independent bands means an
ordinary day often fails, so every result carries WHICH macro missed and by how
much. "You missed" is useless; "you were 38g short on protein" is actionable.

DAYS WITH NOTHING LOGGED
------------------------
Not a miss. A miss means "logged, and the numbers were wrong", which is a
statement about eating. An empty day is a statement about logging, and
conflating the two produces a screen that scolds people for going on holiday.
They are reported separately as `unlogged`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database import Goal, MealLog, User
from app.services import daytime, streaks

logger = logging.getLogger(__name__)

# --- what "in band" means --------------------------------------------------
# Tuned once, here. These are judgement calls, not physiology: a day inside
# these bounds is "close enough that nothing needs to change", which is a
# different question from what is optimal.

CALORIE_TOLERANCE = 0.15      # +/-15% of target
CARB_TOLERANCE = 0.15
FAT_TOLERANCE = 0.15
PROTEIN_FLOOR = 0.70          # at least 70% of target; more is never a miss

# Below this fraction of the calorie target, a day is treated as incompletely
# logged rather than a genuine 400 kcal day. People forget dinner far more
# often than they eat 400 kcal.
PARTIAL_LOG_FRACTION = 0.25

MACROS = ("calories", "protein", "carbs", "fat")


@dataclass
class MacroResult:
    """One macro on one day."""
    name: str
    eaten: float
    target: Optional[float]
    low: Optional[float] = None
    high: Optional[float] = None

    @property
    def assessable(self) -> bool:
        return bool(self.target)

    @property
    def hit(self) -> bool:
        if not self.assessable:
            return True          # nothing to miss
        if self.low is not None and self.eaten < self.low:
            return False
        if self.high is not None and self.eaten > self.high:
            return False
        return True

    @property
    def delta(self) -> float:
        """Signed distance from the nearest edge of the band. 0 when inside."""
        if not self.assessable or self.hit:
            return 0.0
        if self.low is not None and self.eaten < self.low:
            return self.eaten - self.low
        return self.eaten - (self.high or 0)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "eaten": round(self.eaten, 1),
            "target": round(self.target, 1) if self.target else None,
            "low": round(self.low, 1) if self.low is not None else None,
            "high": round(self.high, 1) if self.high is not None else None,
            "hit": self.hit,
            "delta": round(self.delta, 1),
            "assessable": self.assessable,
        }


@dataclass
class DayResult:
    """One day's verdict."""
    day: date
    meals: int = 0
    macros: Dict[str, MacroResult] = field(default_factory=dict)
    has_goal: bool = True
    partial: bool = False
    # Today is not a verdict. Calling a day "missed" at 2pm because dinner has
    # not happened yet is wrong on the facts and demoralising on top of it -
    # and it is exactly what a naive implementation does, because a day in
    # progress looks identical to a day that fell short.
    in_progress: bool = False

    @property
    def unlogged(self) -> bool:
        return self.meals == 0

    @property
    def assessable(self) -> bool:
        """Can this day be judged at all?"""
        return ((not self.unlogged) and self.has_goal
                and not self.partial and not self.in_progress)

    @property
    def hit(self) -> bool:
        return self.assessable and all(m.hit for m in self.macros.values())

    @property
    def missed(self) -> List[str]:
        """Which macros fell outside the band, worst first."""
        if not self.assessable:
            return []
        out = [m for m in self.macros.values() if not m.hit and m.assessable]
        return [m.name for m in sorted(out, key=lambda m: -abs(m.delta))]

    @property
    def status(self) -> str:
        """One word for the UI: hit | missed | partial | unlogged | no_goal."""
        if self.in_progress:
            # An in-progress day CAN already be a definite miss - once you are
            # over the calorie ceiling, no further eating brings you back - so
            # say so rather than hiding it behind optimism.
            over = [m for m in self.macros.values()
                    if m.assessable and m.high is not None and m.eaten > m.high]
            return "over_already" if over else "in_progress"
        if self.unlogged:
            return "unlogged"
        if not self.has_goal:
            return "no_goal"
        if self.partial:
            return "partial"
        return "hit" if self.hit else "missed"

    def summary(self) -> str:
        """A short human sentence. Empty when there is nothing to say."""
        if self.status == "over_already":
            over = [m for m in self.macros.values()
                    if m.assessable and m.high is not None and m.eaten > m.high]
            worst = max(over, key=lambda m: abs(m.delta))
            unit = "kcal" if worst.name == "calories" else "g"
            return f"already over on {worst.name} by {abs(worst.delta):.0f}{unit}"
        if self.status == "in_progress":
            remaining = self.macros.get("calories")
            if remaining and remaining.assessable and remaining.target:
                left = remaining.target - remaining.eaten
                if left > 0:
                    return f"{left:.0f} kcal still to go"
            return "still in progress"
        if self.status == "unlogged":
            return "nothing logged"
        if self.status == "no_goal":
            return "no target set"
        if self.status == "partial":
            return "only partly logged"
        if self.hit:
            return "on target"
        parts = []
        for name in self.missed[:2]:
            macro = self.macros[name]
            unit = "kcal" if name == "calories" else "g"
            direction = "short on" if macro.delta < 0 else "over on"
            parts.append(f"{direction} {name} by {abs(macro.delta):.0f}{unit}")
        return ", ".join(parts)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "date": self.day.isoformat(),
            "status": self.status,
            "hit": self.hit,
            "meals": self.meals,
            "missed": self.missed,
            "summary": self.summary(),
            "macros": {n: m.as_dict() for n, m in self.macros.items()},
        }


# ---------------------------------------------------------------------------
# evaluation
# ---------------------------------------------------------------------------

def _band(target: Optional[float], tolerance: float):
    if not target:
        return (None, None)
    return (target * (1 - tolerance), target * (1 + tolerance))


def evaluate_day(day: date, rows: List[MealLog], goal: Optional[Goal]) -> DayResult:
    """
    Judge one day from its meals. Pure - no database, so it is fully testable.
    """
    result = DayResult(day=day, meals=len(rows), has_goal=goal is not None)

    eaten = {
        "calories": sum(r.calories or 0 for r in rows),
        "protein": sum(r.protein or 0 for r in rows),
        "carbs": sum(r.carbs or 0 for r in rows),
        "fat": sum(r.fat or 0 for r in rows),
    }

    targets = {
        "calories": getattr(goal, "target_calories", None) if goal else None,
        "protein": getattr(goal, "target_protein", None) if goal else None,
        "carbs": getattr(goal, "target_carbs", None) if goal else None,
        "fat": getattr(goal, "target_fat", None) if goal else None,
    }

    calorie_target = targets["calories"]
    if rows and calorie_target and eaten["calories"] < calorie_target * PARTIAL_LOG_FRACTION:
        # One logged apple is not a 90-calorie day. Calling it a miss would
        # punish partial logging as though it were undereating.
        result.partial = True

    lo, hi = _band(calorie_target, CALORIE_TOLERANCE)
    result.macros["calories"] = MacroResult("calories", eaten["calories"],
                                            calorie_target, lo, hi)

    # Protein is a floor, not a band. Over target is not a failure.
    protein_target = targets["protein"]
    result.macros["protein"] = MacroResult(
        "protein", eaten["protein"], protein_target,
        low=protein_target * PROTEIN_FLOOR if protein_target else None,
        high=None,
    )

    for name, tolerance in (("carbs", CARB_TOLERANCE), ("fat", FAT_TOLERANCE)):
        lo, hi = _band(targets[name], tolerance)
        result.macros[name] = MacroResult(name, eaten[name], targets[name], lo, hi)

    return result


def active_goal(db: Session, user_id: int) -> Optional[Goal]:
    return (
        db.query(Goal)
        .filter(Goal.user_id == user_id, Goal.is_active == True)  # noqa: E712
        .order_by(Goal.created_at.desc())
        .first()
    )


def history(db: Session, user: User, days: int = 7,
            include_today: bool = False) -> List[DayResult]:
    """
    The last `days` complete days, oldest first.

    Today is excluded by default: it is still in progress, and marking a day
    "missed" at 10am because dinner has not happened yet is both wrong and
    demoralising.
    """
    goal = active_goal(db, user.id)
    tz = daytime.zone_for(user)
    today = daytime.local_date(tz=tz)

    last_day = today if include_today else today - timedelta(days=1)
    first_day = last_day - timedelta(days=days - 1)

    window_start, _ = daytime.day_bounds(first_day, tz=tz)
    _, window_end = daytime.day_bounds(last_day, tz=tz)

    rows = (
        db.query(MealLog)
        .filter(
            MealLog.user_id == user.id,
            MealLog.logged_at >= window_start,
            MealLog.logged_at < window_end,
        )
        .all()
    )
    buckets = daytime.group_by_local_day(rows, "logged_at", tz=tz)

    out = []
    day = first_day
    while day <= last_day:
        out.append(evaluate_day(day, buckets.get(day, []), goal))
        day += timedelta(days=1)
    return out


def today(db: Session, user: User) -> DayResult:
    """Today so far, flagged as in progress so it is never scored as a miss."""
    goal = active_goal(db, user.id)
    tz = daytime.zone_for(user)
    start, end = daytime.today_bounds(tz=tz)
    rows = (
        db.query(MealLog)
        .filter(MealLog.user_id == user.id,
                MealLog.logged_at >= start, MealLog.logged_at < end)
        .all()
    )
    result = evaluate_day(daytime.local_date(tz=tz), rows, goal)
    result.in_progress = True
    # `partial` means "logged too little to judge"; for today that is simply
    # the normal state of the morning, and both flags at once reads oddly.
    result.partial = False
    return result


# ---------------------------------------------------------------------------
# summarising a week
# ---------------------------------------------------------------------------

@dataclass
class Streak:
    """A run of consecutive days, counted back from the most recent."""
    current: int = 0
    best: int = 0


def _streaks(results: List[DayResult]) -> Streak:
    """
    Consecutive hits, counting backwards from the latest day.

    Unlogged days BREAK the streak rather than being skipped. A streak claims
    consecutive days of hitting targets, and a gap means we do not know - so
    carrying the count across it would be asserting something unevidenced.

    The counting itself lives in services/streaks.py, shared with the challenge
    analytics endpoint. That endpoint used to have its own inline version which
    counted table ROWS rather than days, and reported three challenges finished
    in one evening as a three-day streak. One implementation, one definition.

    `history()` returns a contiguous range of days, which is what `over()`
    requires - every day in the window is present, hit or not.
    """
    counted = streaks.over([(r.day, r.hit) for r in results])
    return Streak(current=counted.current, best=counted.best)


def summarise(results: List[DayResult]) -> Dict[str, Any]:
    """
    The week in numbers, plus the one fact worth acting on.

    Rates are over ASSESSABLE days only. Dividing hits by 7 when three days had
    nothing logged reports a 57% failure that is really a logging gap - and
    that number would then drive recommendations.
    """
    assessable = [r for r in results if r.assessable]
    hits = [r for r in assessable if r.hit]
    streak = _streaks(results)

    # Which macro fails most often, and by how much on average. This is what
    # feeds the recommendation engine: "protein, 4 of 5 days, averaging 35g
    # short" is enough to change what gets suggested.
    tally: Dict[str, List[float]] = {}
    for result in assessable:
        for name in result.missed:
            tally.setdefault(name, []).append(result.macros[name].delta)

    weak_points = sorted(
        (
            {
                "macro": name,
                "days": len(deltas),
                "of": len(assessable),
                "average_delta": round(sum(deltas) / len(deltas), 1),
                "direction": "short" if sum(deltas) < 0 else "over",
            }
            for name, deltas in tally.items()
        ),
        key=lambda d: (-d["days"], -abs(d["average_delta"])),
    )

    # The targets themselves, so consumers can judge "45g short" as a
    # FRACTION of target rather than as an absolute that means different
    # things at 60g and 200g of protein.
    targets = {}
    for result in results:
        for name, macro in result.macros.items():
            if macro.target:
                targets[name] = macro.target
        if targets:
            break

    return {
        "days": len(results),
        "targets": targets,
        "assessable_days": len(assessable),
        "unlogged_days": sum(1 for r in results if r.unlogged),
        "partial_days": sum(1 for r in results if r.partial),
        "hits": len(hits),
        "hit_rate": round(len(hits) / len(assessable), 2) if assessable else None,
        "logging_rate": round(
            sum(1 for r in results if not r.unlogged) / len(results), 2
        ) if results else None,
        "current_streak": streak.current,
        "best_streak": streak.best,
        "weak_points": weak_points,
        "headline": _headline(results, assessable, hits, weak_points),
    }


def _headline(results, assessable, hits, weak_points) -> str:
    """One sentence. What a person would actually say about the week."""
    if not results:
        return "No history yet."
    if not assessable:
        logged = sum(1 for r in results if not r.unlogged)
        if not logged:
            return "Nothing logged in this period."
        if any(not r.has_goal for r in results):
            return "No nutrition target set, so days can't be scored."
        return "Not enough complete days to judge yet."

    n = len(assessable)
    if len(hits) == n:
        return f"On target every one of the last {n} logged days."
    if not hits:
        worst = weak_points[0] if weak_points else None
        if worst:
            return (f"None of the last {n} logged days hit target - "
                    f"{worst['macro']} was the problem on {worst['days']} of them.")
        return f"None of the last {n} logged days hit target."

    line = f"{len(hits)} of {n} logged days on target"
    if weak_points:
        worst = weak_points[0]
        unit = "kcal" if worst["macro"] == "calories" else "g"
        line += (f"; {worst['macro']} was {worst['direction']} on "
                 f"{worst['days']}, by {abs(worst['average_delta']):.0f}{unit} on average")
    return line + "."


def week_context(db: Session, user: User, days: int = 7) -> Dict[str, Any]:
    """History plus summary, for the API and the recommendation engine."""
    results = history(db, user, days=days)
    return {
        "days": [r.as_dict() for r in results],
        "summary": summarise(results),
    }
