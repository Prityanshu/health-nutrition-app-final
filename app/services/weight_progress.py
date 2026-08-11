"""
Am I actually getting to my target weight?

Setting a target weight was already possible; nothing ever answered whether it
was being reached. A number you set once and never see again is decoration.

THE HONEST VERSION OF THIS IS HARDER THAN IT LOOKS
--------------------------------------------------
The naive answer - (target - current) / (rate since the first weigh-in) - is
wrong in three ways that all flatter the user:

  * Body weight swings 1-2 kg a day on water alone. Two weigh-ins can show a
    "trend" that is entirely noise, and the projection built on it will be
    confidently absurd.
  * The rate that matters is the RECENT one. Someone who lost 4 kg in month one
    and nothing since is not "on track"; averaging over the whole period says
    they are.
  * A projection is meaningless when the trend points away from the target, and
    infinite when the trend is flat. Both need saying in words, not as a date.

So this reports a projection only when there is enough data over enough time
for one to mean anything, and otherwise says why not. A blank is better than a
number that will be wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# A trend needs a run of measurements over a real stretch of time. Two
# weigh-ins a day apart describe yesterday's dinner, not a direction.
MIN_ENTRIES_FOR_TREND = 3
MIN_DAYS_FOR_TREND = 10

# Only the recent past predicts the near future. Eight weeks is long enough to
# average out water swings and short enough that an old, abandoned effort stops
# counting.
TREND_WINDOW_DAYS = 56

# Under this, weight is not meaningfully moving. 0.05 kg/week is 2.6 kg a year
# - below the noise floor of a bathroom scale over any useful window.
STALLED_KG_PER_WEEK = 0.05

# Within this of the target, call it reached. Chasing the last few hundred
# grams of a number that fluctuates by more than that is not a goal.
REACHED_TOLERANCE_KG = 0.5

# Projections beyond this stop being information.
MAX_PROJECTION_WEEKS = 260  # five years


@dataclass
class WeightProgress:
    """What is knowable about the journey to a target weight."""

    has_target: bool = False
    target_kg: Optional[float] = None
    current_kg: Optional[float] = None
    start_kg: Optional[float] = None

    to_go_kg: Optional[float] = None          # signed: negative means lose
    changed_kg: Optional[float] = None        # since the first weigh-in
    percent_complete: Optional[float] = None  # 0-100, of the original distance

    direction: str = "unknown"    # losing | gaining | stalled | unknown
    rate_kg_per_week: Optional[float] = None
    on_track: Optional[bool] = None           # is the trend pointing the right way
    reached: bool = False

    projected_weeks: Optional[float] = None
    projected_date: Optional[str] = None      # ISO date

    entries_used: int = 0
    days_span: int = 0
    days_since_weigh_in: Optional[int] = None
    # Why a projection is absent, in words a person can act on.
    note: str = ""
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        def r(v, places=1):
            return round(v, places) if isinstance(v, (int, float)) else v
        return {
            "has_target": self.has_target,
            "target_kg": r(self.target_kg),
            "current_kg": r(self.current_kg),
            "start_kg": r(self.start_kg),
            "to_go_kg": r(self.to_go_kg),
            "changed_kg": r(self.changed_kg),
            "percent_complete": r(self.percent_complete, 0),
            "direction": self.direction,
            "rate_kg_per_week": r(self.rate_kg_per_week, 2),
            "on_track": self.on_track,
            "reached": self.reached,
            "projected_weeks": r(self.projected_weeks, 1),
            "projected_date": self.projected_date,
            "entries_used": self.entries_used,
            "days_span": self.days_span,
            "days_since_weigh_in": self.days_since_weigh_in,
            "note": self.note,
            "warnings": list(self.warnings),
        }

    def summary(self) -> str:
        """One line, for a prompt or a card subtitle."""
        if not self.has_target:
            return "No target weight set."
        if self.reached:
            return f"Target of {self.target_kg:.0f} kg reached."

        bits = [f"{abs(self.to_go_kg):.1f} kg to go to {self.target_kg:.0f} kg"]
        if self.direction == "stalled":
            bits.append("weight is flat over the last few weeks")
        elif self.rate_kg_per_week:
            way = "toward" if self.on_track else "away from"
            bits.append(
                f"moving {abs(self.rate_kg_per_week):.2f} kg/week {way} it"
            )
        if self.projected_date:
            bits.append(f"on track for about {self.projected_date}")
        return "; ".join(bits) + "."


def _rate_kg_per_week(entries: List[tuple]) -> Optional[float]:
    """
    Least-squares slope over (timestamp, kg), in kg per week.

    A regression rather than (last - first) / days, because endpoints are
    exactly where a single bad weigh-in does the most damage: measure on a
    bloated morning and the whole trend inverts. Every point contributes here.
    """
    if len(entries) < 2:
        return None

    t0 = entries[0][0]
    xs = [(t - t0).total_seconds() / 86400.0 for t, _ in entries]   # days
    ys = [kg for _, kg in entries]

    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:          # every measurement on the same instant
        return None

    slope_per_day = sum(
        (x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)
    ) / denominator
    return slope_per_day * 7.0


def compute(
    *,
    target_kg: Optional[float],
    weigh_ins: List[tuple],
    fallback_weight_kg: Optional[float] = None,
    now: Optional[datetime] = None,
) -> WeightProgress:
    """
    Work out where someone is against their target weight.

    `weigh_ins` is [(datetime, kg), ...] in any order; it is sorted here so
    callers cannot get it subtly wrong.
    """
    now = now or datetime.utcnow()
    result = WeightProgress()

    entries = sorted((t, float(kg)) for t, kg in weigh_ins if kg)
    result.entries_used = len(entries)

    current = entries[-1][1] if entries else fallback_weight_kg
    result.current_kg = current
    result.start_kg = entries[0][1] if entries else fallback_weight_kg

    if entries:
        result.days_since_weigh_in = max(0, (now - entries[-1][0]).days)
        result.days_span = max(0, (entries[-1][0] - entries[0][0]).days)
        if len(entries) > 1:
            result.changed_kg = entries[-1][1] - entries[0][1]

    if not target_kg or current is None:
        result.note = (
            "No target weight set." if not target_kg
            else "No weight recorded yet."
        )
        return result

    result.has_target = True
    result.target_kg = float(target_kg)
    result.to_go_kg = result.target_kg - current

    if abs(result.to_go_kg) <= REACHED_TOLERANCE_KG:
        result.reached = True
        result.direction = "stalled"
        result.percent_complete = 100.0
        result.note = "Target reached."
        return result

    # How much of the original journey is done. Uses the FIRST weigh-in as the
    # start, so it does not silently reset every time someone steps on a scale.
    if result.start_kg is not None:
        total = result.target_kg - result.start_kg
        if abs(total) > 0.01:
            done = (current - result.start_kg) / total
            result.percent_complete = max(0.0, min(100.0, done * 100.0))

    # --- the trend ---------------------------------------------------------
    recent = [e for e in entries if (now - e[0]).days <= TREND_WINDOW_DAYS]
    span_days = (recent[-1][0] - recent[0][0]).days if len(recent) > 1 else 0

    if len(recent) < MIN_ENTRIES_FOR_TREND:
        result.note = (
            f"Weigh in a few more times - {MIN_ENTRIES_FOR_TREND} readings are "
            "needed before a trend means anything."
        )
        return result

    if span_days < MIN_DAYS_FOR_TREND:
        result.note = (
            f"Readings so far cover {span_days} days. Body weight swings by a "
            "kilo or two daily, so a trend needs at least "
            f"{MIN_DAYS_FOR_TREND}."
        )
        return result

    rate = _rate_kg_per_week(recent)
    if rate is None:
        result.note = "Not enough spread in the readings to see a trend."
        return result

    result.rate_kg_per_week = rate

    if abs(rate) < STALLED_KG_PER_WEEK:
        result.direction = "stalled"
        result.on_track = False
        result.note = (
            "Weight has been flat for the last few weeks. If that is not "
            "intended, the calorie target may need revisiting."
        )
        return result

    result.direction = "losing" if rate < 0 else "gaining"

    # Is the trend pointing at the target, or away from it?
    needs_to_lose = result.to_go_kg < 0
    result.on_track = (rate < 0) if needs_to_lose else (rate > 0)

    if not result.on_track:
        want = "down" if needs_to_lose else "up"
        result.note = (
            f"Weight is moving the wrong way - {abs(rate):.2f} kg/week "
            f"{result.direction}, when the target needs it to go {want}."
        )
        result.warnings.append("The current trend does not reach the target.")
        return result

    weeks = abs(result.to_go_kg) / abs(rate)
    if weeks > MAX_PROJECTION_WEEKS:
        result.note = (
            f"At {abs(rate):.2f} kg/week this would take over "
            f"{MAX_PROJECTION_WEEKS // 52} years - too far out to be a useful "
            "estimate."
        )
        return result

    result.projected_weeks = weeks
    result.projected_date = (now + timedelta(weeks=weeks)).date().isoformat()
    result.note = (
        f"On the last {min(len(recent), result.entries_used)} readings, about "
        f"{weeks:.0f} weeks to go."
    )
    return result


def prompt_block(progress: "WeightProgress", goal_type: Optional[str] = None) -> str:
    """
    The weight goal, phrased for a plan generator.

    Macro targets already tell the model what a day should add up to. They do
    not tell it WHY, and the why changes the food: someone cutting to 74 kg
    wants volume and satiety at that calorie count, someone gaining wants
    calorie density at the same number. Same arithmetic, different plan.

    The current trend is included deliberately. A plan for someone who has been
    stalled for six weeks should not look like a plan for someone losing
    steadily - and the model can only account for that if it is told.

    Returns "" when there is no target, so callers can concatenate blindly.
    """
    if not progress.has_target:
        return ""

    goal_words = {
        "weight_loss": "losing fat",
        "muscle_gain": "gaining muscle",
        "maintenance": "maintaining weight",
    }.get(goal_type or "", None)

    lines = ["WHY THESE NUMBERS - the person's actual goal:"]
    if goal_words:
        lines.append(f"            - They are {goal_words}.")
    lines.append(
        f"            - Currently {progress.current_kg:.1f} kg, "
        f"target {progress.target_kg:.0f} kg "
        f"({abs(progress.to_go_kg):.1f} kg to "
        f"{'lose' if progress.to_go_kg < 0 else 'gain'})."
    )

    if progress.reached:
        lines.append(
            "            - They have REACHED the target. Build to hold it, "
            "not to keep changing."
        )
    elif progress.direction == "stalled":
        lines.append(
            "            - Their weight has been FLAT for several weeks despite "
            "the goal. Favour higher-satiety, higher-volume choices so the "
            "calorie target is easier to actually stick to."
        )
    elif progress.on_track is False:
        lines.append(
            "            - Their weight is currently moving the WRONG WAY. "
            "Prioritise foods that make the target easy to keep to over "
            "variety or indulgence."
        )
    elif progress.rate_kg_per_week:
        lines.append(
            f"            - They are on track at "
            f"{abs(progress.rate_kg_per_week):.2f} kg/week. Keep the plan "
            "consistent with what is already working."
        )

    if progress.to_go_kg < 0:
        lines.append(
            "            - Because they are in a deficit, protein and fibre "
            "matter more than usual: they protect muscle and manage hunger."
        )
    elif progress.to_go_kg > 0:
        lines.append(
            "            - Because they are in a surplus, calorie-dense foods "
            "help; a plan that is technically correct but impossible to finish "
            "eating is not usable."
        )

    return "\n".join(lines) + "\n"


def for_user(db, user, goal=None, now: Optional[datetime] = None) -> WeightProgress:
    """Convenience wrapper that does the querying."""
    from app.database import Goal, WeightLog

    if goal is None:
        goal = (
            db.query(Goal)
            .filter(Goal.user_id == user.id, Goal.is_active == True)  # noqa: E712
            .order_by(Goal.created_at.desc())
            .first()
        )

    logs = (
        db.query(WeightLog)
        .filter(WeightLog.user_id == user.id)
        .order_by(WeightLog.logged_at.asc())
        .all()
    )

    return compute(
        target_kg=getattr(goal, "target_weight", None),
        weigh_ins=[(l.logged_at, l.weight_kg) for l in logs],
        fallback_weight_kg=user.weight,
        now=now,
    )
