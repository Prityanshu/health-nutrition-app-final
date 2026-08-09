"""
Challenge generation and scoring, built from what the user actually does.

WHAT WAS WRONG BEFORE
---------------------
The previous generator produced challenges that looked personalised and were
not. It never read the user's calorie or protein target, so "eat more protein"
was measured against a constant rather than their own number. It never read
their injuries, so it could cheerfully suggest a running streak to somebody
with a torn hamstring. It never read their goal, so a cutting user and a
bulking user were offered the same thing. And progress only moved when a meal
was logged through one specific code path, so most challenges sat at 0%
forever and looked broken.

HOW THIS WORKS INSTEAD
----------------------
1. Read the situation once: goal targets, 21 days of logged meals, weight
   trend, active injuries, dietary preferences, saved plans.
2. Pick challenges that address what is actually weak, sized against the
   user's own baseline rather than a fixed number - if they average 62g of
   protein, the challenge is 80g, not 150g.
3. Refuse to offer anything an active injury rules out.
4. Score progress by querying the source data on read, so it is correct
   whatever route the user took to log something.

Everything here is deterministic. Challenges are a scoring problem, not a
language problem, and a model would only make them inconsistent and expensive.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database import FoodItem, Goal, Injury, MealLog, SavedPlan, User, WeightLog
from app.models.enhanced_challenge_models import (
    ChallengeDifficulty, ChallengeType, PersonalizedChallenge,
)
from app.services import daytime

logger = logging.getLogger(__name__)

BASELINE_DAYS = 21
DEFAULT_DURATION_DAYS = 7
# Below this many logged days there is no baseline worth personalising
# against, so new users get habit-forming challenges instead of targets.
MIN_DAYS_FOR_TARGETS = 3
MAX_ACTIVE = 4


# ---------------------------------------------------------------------------
# reading the situation
# ---------------------------------------------------------------------------

@dataclass
class Situation:
    """Everything that should influence what we ask of someone."""

    user_id: int
    name: str = ""

    # Targets they are working to
    goal_type: Optional[str] = None
    calorie_target: Optional[float] = None
    protein_target: Optional[float] = None

    # What they actually do
    days_logged: int = 0
    avg_calories: float = 0.0
    avg_protein: float = 0.0
    avg_fiber: float = 0.0
    logging_rate: float = 0.0        # fraction of the last 7 days with a log
    meals_per_day: float = 0.0
    distinct_foods: int = 0
    over_target_days: int = 0

    # Direction of travel
    weight_change_kg: Optional[float] = None
    weigh_ins: int = 0

    # When they eat, not just what
    breakfast_rate: float = 0.0      # logged days with something before 11am
    late_night_rate: float = 0.0     # logged days with something after 10pm
    weekend_avg_calories: float = 0.0
    weekday_avg_calories: float = 0.0
    weekend_days: int = 0

    # Constraints
    injuries: List[Injury] = field(default_factory=list)
    injury_parts: List[str] = field(default_factory=list)
    dietary_preferences: List[str] = field(default_factory=list)
    has_workout_plan: bool = False

    # Rotation state, read from ChallengeOutcome
    levels: Dict[str, int] = field(default_factory=dict)
    recent_keys: Dict[str, int] = field(default_factory=dict)   # key -> days ago
    total_points: int = 0
    streak: int = 0

    @property
    def is_vegetarian(self) -> bool:
        joined = " ".join(self.dietary_preferences).lower()
        return any(w in joined for w in ("vegetarian", "vegan", "veg"))

    @property
    def weekend_gap(self) -> float:
        """How much bigger weekend days are than weekdays, as a fraction."""
        if not self.weekday_avg_calories or not self.weekend_avg_calories:
            return 0.0
        return (self.weekend_avg_calories - self.weekday_avg_calories) / self.weekday_avg_calories

    @property
    def stalled(self) -> bool:
        """
        In a deficit, logging well, and the scale has not moved.

        The usual cause is under-logging rather than an insufficient deficit,
        which is why this triggers a completeness challenge instead of telling
        someone to eat less.
        """
        if not self.goal_type or "loss" not in (self.goal_type or "").lower():
            return False
        if self.weigh_ins < 2 or self.weight_change_kg is None:
            return False
        return abs(self.weight_change_kg) < 0.4 and self.logging_rate >= 0.5

    @property
    def is_new(self) -> bool:
        return self.days_logged < MIN_DAYS_FOR_TARGETS

    @property
    def injured(self) -> bool:
        return bool(self.injuries)

    @property
    def worst_injury_severity(self) -> int:
        return max((i.severity or 0) for i in self.injuries) if self.injuries else 0


def read_situation(db: Session, user_id: int) -> Situation:
    """One pass over the user's data. Never raises; a thin Situation still works."""
    s = Situation(user_id=user_id)
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            s.name = user.full_name or user.username or ""
            raw = user.dietary_preferences or ""
            if raw:
                import json
                try:
                    parsed = json.loads(raw)
                    s.dietary_preferences = parsed if isinstance(parsed, list) else [str(parsed)]
                except (ValueError, TypeError):
                    s.dietary_preferences = [raw]

        goal = (
            db.query(Goal)
            .filter(Goal.user_id == user_id, Goal.is_active == True)  # noqa: E712
            .order_by(Goal.created_at.desc())
            .first()
        )
        if goal:
            s.goal_type = goal.goal_type
            s.calorie_target = goal.target_calories
            s.protein_target = goal.target_protein

        # Everything below groups meals into days. That has to be the USER's
        # day: on UTC days an IST evening meal falls into tomorrow, so a
        # single evening could read as two days logged and the streak, the
        # weekend split and the calorie averages were all off.
        tz = daytime.zone_for(user)
        since = daytime.days_ago_start(BASELINE_DAYS, tz=tz)
        meals = (
            db.query(MealLog)
            .filter(MealLog.user_id == user_id, MealLog.logged_at >= since)
            .all()
        )
        if meals:
            by_day: Dict[Any, List[MealLog]] = daytime.group_by_local_day(
                meals, "logged_at", tz=tz)

            s.days_logged = len(by_day)
            if by_day:
                s.avg_calories = sum(m.calories or 0 for m in meals) / len(by_day)
                s.avg_protein = sum(m.protein or 0 for m in meals) / len(by_day)
                s.meals_per_day = len(meals) / len(by_day)
                if s.calorie_target:
                    s.over_target_days = sum(
                        1 for day_meals in by_day.values()
                        if sum(m.calories or 0 for m in day_meals) > s.calorie_target * 1.1
                    )

            week_ago = daytime.local_date(tz=tz) - timedelta(days=7)
            s.logging_rate = len([d for d in by_day if d >= week_ago]) / 7.0

            # When they eat. Both of these are already in logged_at and were
            # never looked at, yet skipped breakfasts and late-night eating are
            # two of the most common patterns worth naming.
            breakfast_days = sum(
                1 for day_meals in by_day.values()
                if any((daytime.local_hour(m.logged_at, tz=tz) or 0) < 11
                       for m in day_meals if m.logged_at)
            )
            late_days = sum(
                1 for day_meals in by_day.values()
                if any((daytime.local_hour(m.logged_at, tz=tz) or 0) >= 22
                       for m in day_meals if m.logged_at)
            )
            s.breakfast_rate = breakfast_days / len(by_day)
            s.late_night_rate = late_days / len(by_day)

            # Weekday against weekend. Most people's weekends are a different
            # diet entirely, and nothing in the app has ever said so.
            weekend, weekday = [], []
            for day, day_meals in by_day.items():
                total = sum(m.calories or 0 for m in day_meals)
                (weekend if day.weekday() >= 5 else weekday).append(total)
            s.weekend_days = len(weekend)
            if weekend:
                s.weekend_avg_calories = sum(weekend) / len(weekend)
            if weekday:
                s.weekday_avg_calories = sum(weekday) / len(weekday)

            food_ids = {m.food_item_id for m in meals if m.food_item_id}
            s.distinct_foods = len(food_ids)
            if food_ids:
                fibre_rows = (
                    db.query(FoodItem.id, FoodItem.fiber_g)
                    .filter(FoodItem.id.in_(food_ids))
                    .all()
                )
                fibre_by_id = {fid: (f or 0) for fid, f in fibre_rows}
                total_fibre = sum(
                    fibre_by_id.get(m.food_item_id, 0) * (m.quantity or 1) for m in meals
                )
                s.avg_fiber = total_fibre / max(1, len(by_day))

        weights = (
            db.query(WeightLog)
            .filter(WeightLog.user_id == user_id)
            .order_by(WeightLog.logged_at.desc())
            .limit(8)
            .all()
        )
        s.weigh_ins = len(weights)
        if len(weights) >= 2:
            s.weight_change_kg = round(weights[0].weight_kg - weights[-1].weight_kg, 1)

        s.injuries = (
            db.query(Injury)
            .filter(Injury.user_id == user_id, Injury.status == "active")
            .all()
        )
        s.injury_parts = [i.body_part for i in s.injuries]

        s.has_workout_plan = bool(
            db.query(SavedPlan)
            .filter(SavedPlan.user_id == user_id, SavedPlan.plan_type == "workout")
            .first()
        )

        _load_rotation_state(db, user_id, s)
    except Exception as e:
        logger.error("read_situation failed for user %s: %s", user_id, e, exc_info=True)

    return s


# ---------------------------------------------------------------------------
# rotation: difficulty progression and cooldowns
# ---------------------------------------------------------------------------

# How far a challenge can escalate. Beyond this the numbers stop being
# achievable and start being discouraging.
MAX_LEVEL = 4
# A key that was just attempted should not come straight back.
COOLDOWN_DAYS_AFTER_SUCCESS = 3
COOLDOWN_DAYS_AFTER_FAILURE = 6
# Each level asks this much more. Small on purpose - progression people
# actually stick to is barely perceptible week to week.
LEVEL_STEP = 0.12


def _load_rotation_state(db: Session, user_id: int, s: Situation) -> None:
    """
    Read outcome history into levels, cooldowns, points and streak.

    Level is derived rather than stored on the user: a completion moves a key
    up, a failure moves it down, and it is clamped. Deriving it means the
    history is the single source of truth and nothing can drift out of sync.
    """
    from app.database import ChallengeOutcome

    try:
        outcomes = (
            db.query(ChallengeOutcome)
            .filter(ChallengeOutcome.user_id == user_id)
            .order_by(ChallengeOutcome.ended_at.asc())
            .all()
        )
    except Exception as e:
        logger.warning("Could not read challenge history for %s: %s", user_id, e)
        return

    now = datetime.utcnow()
    for outcome in outcomes:
        key = outcome.challenge_key
        level = s.levels.get(key, 0)
        s.levels[key] = max(0, min(MAX_LEVEL, level + (1 if outcome.completed else -1)))

        if outcome.ended_at:
            days = max(0, (now - outcome.ended_at).days)
            s.recent_keys[key] = min(s.recent_keys.get(key, 10 ** 6), days)

        if outcome.completed:
            s.total_points += outcome.points_awarded or 0

    # Streak: consecutive completions counting back from the most recent.
    for outcome in reversed(outcomes):
        if outcome.completed:
            s.streak += 1
        else:
            break


def _on_cooldown(s: Situation, key: str, completed_recently: bool = False) -> bool:
    """Whether a key was attempted too recently to offer again."""
    days_ago = s.recent_keys.get(key)
    if days_ago is None:
        return False
    limit = COOLDOWN_DAYS_AFTER_SUCCESS if completed_recently else COOLDOWN_DAYS_AFTER_FAILURE
    return days_ago < limit


def _apply_level(s: Situation, candidate: Candidate) -> Candidate:
    """
    Scale a candidate to the user's demonstrated level with that challenge.

    Only the numeric target moves. The wording is regenerated from it, so a
    level-3 protein challenge reads as a bigger ask rather than the same
    sentence with a different badge.
    """
    level = s.levels.get(candidate.key, 0)
    if level <= 0:
        return candidate

    # Day-count targets grow by whole days; value targets grow proportionally.
    if candidate.unit in ("days", "check-ins", "sessions", "new foods"):
        grown = min(7, candidate.target + level)
        if grown != candidate.target:
            # Replace the number TOGETHER WITH ITS UNIT. Replacing the bare
            # digit would corrupt titles where the number appears earlier for
            # a different reason - "Hit 155g of protein for 5 days" would
            # become "Hit 175g of protein for 5 days", silently changing the
            # protein target instead of the day count.
            old_phrase = f"{candidate.target:.0f} {candidate.unit}"
            new_phrase = f"{grown:.0f} {candidate.unit}"
            if old_phrase in candidate.title:
                candidate.title = candidate.title.replace(old_phrase, new_phrase, 1)
            else:
                # Title does not spell the count out ("...twice this week").
                # Rewriting it safely is not possible, so state the new figure
                # rather than leaving the words and the target disagreeing.
                candidate.title = f"{candidate.title} ({new_phrase})"
            candidate.target = grown
    else:
        old = candidate.target
        candidate.target = round(old * (1 + LEVEL_STEP * level), 1)
        # Keep the wording honest. A standalone-number match avoids the same
        # trap as above, where a substring replace would hit the wrong figure.
        pattern = rf"(?<!\d){old:.0f}(?!\d)"
        if re.search(pattern, candidate.title):
            candidate.title = re.sub(
                pattern, f"{candidate.target:.0f}", candidate.title, count=1
            )
        else:
            candidate.title = f"{candidate.title} ({candidate.target:.0f} {candidate.unit})"

    candidate.points = int(candidate.points * (1 + 0.25 * level))
    if level >= 2:
        candidate.difficulty = ChallengeDifficulty.HARD
    elif level == 1 and candidate.difficulty == ChallengeDifficulty.EASY:
        candidate.difficulty = ChallengeDifficulty.MEDIUM

    candidate.reason += f" You've cleared this {level} time{'s' if level != 1 else ''} — stepping it up."
    return candidate


def _outcome_exists(db: Session, challenge: PersonalizedChallenge) -> bool:
    """
    Has this particular attempt already been banked?

    refresh_progress runs on every read, so without this a completed challenge
    would award its points again on each page load and inflate the difficulty
    level several steps in a single afternoon.
    """
    from app.database import ChallengeOutcome

    factors = challenge.personalization_factors or {}
    key = factors.get("key") if isinstance(factors, dict) else None
    if not key or not challenge.start_date:
        return False
    try:
        return bool(
            db.query(ChallengeOutcome)
            .filter(
                ChallengeOutcome.user_id == challenge.user_id,
                ChallengeOutcome.challenge_key == key,
                ChallengeOutcome.started_at == challenge.start_date,
            ).first()
        )
    except Exception:
        # If the check fails, assume it was recorded. Skipping an award is a
        # far smaller problem than awarding it repeatedly.
        return True


def record_outcome(db: Session, challenge: PersonalizedChallenge, completed: bool) -> None:
    """Write what happened, so the next generation can respond to it."""
    from app.database import ChallengeOutcome

    factors = challenge.personalization_factors or {}
    key = factors.get("key") if isinstance(factors, dict) else None
    if not key:
        return

    try:
        db.add(ChallengeOutcome(
            user_id=challenge.user_id,
            challenge_key=key,
            challenge_type=challenge.challenge_type.value if challenge.challenge_type else None,
            level=int(factors.get("level", 0)) if isinstance(factors, dict) else 0,
            target_value=challenge.target_value,
            achieved_value=challenge.current_value,
            completed=completed,
            points_awarded=challenge.points_reward if completed else 0,
            started_at=challenge.start_date,
            ended_at=datetime.utcnow(),
        ))
    except Exception as e:
        logger.error("Could not record challenge outcome: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# candidate challenges
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    key: str
    title: str
    description: str
    challenge_type: ChallengeType
    difficulty: ChallengeDifficulty
    target: float
    unit: str
    metric: str                    # how progress is measured - see score_progress
    points: int = 100
    days: int = DEFAULT_DURATION_DAYS
    # Higher wins. Set from how badly this addresses a real weakness.
    priority: float = 0.0
    reason: str = ""               # shown to the user: why this challenge
    badge: Optional[str] = None


def _round_to(value: float, step: int) -> float:
    return max(step, round(value / step) * step)


def _injury_candidates(s: Situation) -> List[Candidate]:
    """
    Challenges for someone who is currently injured.

    Kept separate so it can run for every user, new or established. While an
    injury is active the useful thing to ask for is recovery behaviour, not
    performance - and asking for performance would be actively harmful.
    """
    if not s.injured:
        return []

    worst = max(s.injuries, key=lambda i: i.severity or 0)
    label = (worst.description or worst.body_part.replace("_", " ")).strip()

    out = [
        Candidate(
            key="recovery_checkins",
            title=f"Check in on your {label} twice this week",
            description=(
                "Tracking how it changes is what lets your plans open back up "
                "safely - and tells you early if it is going the wrong way."
            ),
            challenge_type=ChallengeType.WORKOUT,
            difficulty=ChallengeDifficulty.EASY,
            # Pinned to this injury's id, so check-ins on anything else do not
            # count towards it.
            target=2, unit="check-ins", metric=f"injury_checkins:{worst.id}",
            points=100, priority=120,   # above onboarding: safety leads
            reason=f"You are managing a {label} injury at {worst.severity}/10.",
            badge="patient",
        )
    ]

    # Protein matters more while healing, but only ask for it if we know what
    # their target is - otherwise the number would be invented.
    if s.protein_target:
        out.append(Candidate(
            key="protein_recovery",
            title=f"Reach {s.protein_target * 0.9:.0f}g of protein on 4 days",
            description="Healing tissue needs protein more than usual, not less.",
            challenge_type=ChallengeType.NUTRITION,
            difficulty=ChallengeDifficulty.MEDIUM,
            target=4, unit="days",
            metric=f"days_protein_over:{s.protein_target * 0.9:.0f}",
            points=150, priority=88,
            reason="Protein matters more while you are recovering.",
        ))

    return out


def build_candidates(s: Situation) -> List[Candidate]:
    """
    Every challenge worth offering this user, scored by relevance.

    Deliberately generous - the caller picks the top few. A candidate is only
    added when the data says it addresses something real, so an empty list
    means there is genuinely nothing useful to ask for.
    """
    out: List[Candidate] = []

    # --- injuries come first, always -------------------------------------
    # An injury is relevant no matter how long someone has been logging food.
    # This block used to sit after the new-user early return, so a brand new
    # user with a torn hamstring got onboarding challenges and nothing about
    # their injury at all.
    out.extend(_injury_candidates(s))

    # --- brand new: build the habit before measuring anything ------------
    if s.is_new:
        out.append(Candidate(
            key="first_logs",
            title="Log meals for 5 days",
            description="Everything else in the app gets better once there is data to work from.",
            challenge_type=ChallengeType.CONSISTENCY,
            difficulty=ChallengeDifficulty.EASY,
            target=5, unit="days", metric="days_logged",
            points=100, priority=100,
            reason="You are just getting started - this unlocks personalised targets.",
            badge="first_steps",
        ))
        if not s.calorie_target:
            out.append(Candidate(
                key="set_goal",
                title="Set your goal",
                description="Pick an objective so your calorie and protein targets can be worked out.",
                challenge_type=ChallengeType.GOAL_ORIENTED,
                difficulty=ChallengeDifficulty.EASY,
                target=1, unit="goal", metric="has_goal",
                points=50, priority=95,
                reason="Without a goal there is nothing to measure against.",
            ))
        out.sort(key=lambda c: c.priority, reverse=True)
        return out

    # --- protein ---------------------------------------------------------
    # Skipped while injured: _injury_candidates already asks for protein, and
    # two overlapping protein challenges read as a bug rather than emphasis.
    if s.protein_target and s.avg_protein and not s.injured:
        shortfall = (s.protein_target - s.avg_protein) / s.protein_target
        if shortfall > 0.12:
            # Ask for a step towards the target, not the target itself -
            # a jump from 60g to 140g gets abandoned on day two.
            step = s.avg_protein + (s.protein_target - s.avg_protein) * 0.5
            target = _round_to(step, 5)
            # A vegetarian short on protein needs a route, not just a number.
            # This is the first use of the dietary preference the app has
            # collected at registration since the beginning.
            veg_note = (
                " Dal, paneer, curd, soya and eggs are the ones that move this "
                "needle without much bulk."
                if s.is_vegetarian else ""
            )
            out.append(Candidate(
                key="protein_step",
                title=f"Hit {target:.0f}g of protein for 5 days",
                description=(
                    f"You average {s.avg_protein:.0f}g against a target of "
                    f"{s.protein_target:.0f}g. This closes half the gap." + veg_note
                ),
                challenge_type=ChallengeType.NUTRITION,
                difficulty=ChallengeDifficulty.MEDIUM if shortfall > 0.3 else ChallengeDifficulty.EASY,
                target=5, unit="days", metric=f"days_protein_over:{target}",
                points=150, priority=90 * min(1.5, shortfall * 3),
                reason=f"Protein is running {shortfall * 100:.0f}% under your target.",
                badge="protein_pro",
            ))

    # --- calories against the goal --------------------------------------
    if s.calorie_target and s.days_logged >= MIN_DAYS_FOR_TARGETS:
        direction = (s.goal_type or "").lower()
        if "loss" in direction or "cut" in direction:
            if s.over_target_days >= 2:
                out.append(Candidate(
                    key="calorie_discipline",
                    title=f"Stay under {s.calorie_target:.0f} kcal for 5 days",
                    description="Five clean days is what turns a deficit into weight change.",
                    challenge_type=ChallengeType.GOAL_ORIENTED,
                    difficulty=ChallengeDifficulty.MEDIUM,
                    target=5, unit="days",
                    metric=f"days_calories_under:{s.calorie_target}",
                    points=200, priority=85,
                    reason=f"You went over target on {s.over_target_days} of the last {s.days_logged} logged days.",
                    badge="disciplined",
                ))
        elif "gain" in direction or "bulk" in direction or "muscle" in direction:
            if s.avg_calories < s.calorie_target * 0.92:
                out.append(Candidate(
                    key="calorie_surplus",
                    title=f"Reach {s.calorie_target:.0f} kcal on 5 days",
                    description="Muscle needs the surplus actually eaten, not just planned.",
                    challenge_type=ChallengeType.GOAL_ORIENTED,
                    difficulty=ChallengeDifficulty.MEDIUM,
                    target=5, unit="days",
                    metric=f"days_calories_over:{s.calorie_target * 0.95:.0f}",
                    points=200, priority=85,
                    reason=f"You average {s.avg_calories:.0f} kcal, under your {s.calorie_target:.0f} target.",
                ))

    # --- consistency -----------------------------------------------------
    if s.logging_rate < 0.7:
        out.append(Candidate(
            key="logging_streak",
            title="Log something every day for a week",
            description="Gaps in the log make every target and suggestion less accurate.",
            challenge_type=ChallengeType.CONSISTENCY,
            difficulty=ChallengeDifficulty.EASY,
            target=7, unit="days", metric="days_logged",
            points=120, priority=80 * (1 - s.logging_rate),
            reason=f"You logged on {s.logging_rate * 7:.0f} of the last 7 days.",
            badge="consistent",
        ))

    if s.meals_per_day and s.meals_per_day < 2.5:
        out.append(Candidate(
            key="log_all_meals",
            title="Log 3 meals a day for 4 days",
            description="Partial days make the daily totals look better than they are.",
            challenge_type=ChallengeType.CONSISTENCY,
            difficulty=ChallengeDifficulty.EASY,
            target=4, unit="days", metric="days_with_3_meals",
            points=100, priority=60,
            reason=f"You log about {s.meals_per_day:.1f} meals on the days you log.",
        ))

    # --- variety and fibre ----------------------------------------------
    if s.distinct_foods and s.distinct_foods < 12 and s.days_logged >= 7:
        out.append(Candidate(
            key="variety",
            title="Log 5 foods you have not eaten recently",
            description="A wider range covers more micronutrients and keeps meals interesting.",
            challenge_type=ChallengeType.VARIETY,
            difficulty=ChallengeDifficulty.EASY,
            target=5, unit="new foods", metric="new_foods",
            points=120, priority=55,
            reason=f"You have eaten {s.distinct_foods} different foods in {BASELINE_DAYS} days.",
            badge="explorer",
        ))

    if s.avg_fiber and s.avg_fiber < 22:
        target = _round_to(min(30, s.avg_fiber + 8), 5)
        out.append(Candidate(
            key="fibre",
            title=f"Reach {target:.0f}g of fibre on 4 days",
            description="Fibre is the most common shortfall, and it drives fullness and digestion.",
            challenge_type=ChallengeType.NUTRITION,
            difficulty=ChallengeDifficulty.EASY,
            target=4, unit="days", metric=f"days_fiber_over:{target}",
            points=120, priority=50,
            reason=f"You average about {s.avg_fiber:.0f}g of fibre a day.",
        ))

    # --- weighing in -----------------------------------------------------
    if s.weigh_ins < 2 and s.goal_type:
        out.append(Candidate(
            key="weigh_in",
            title="Weigh in twice this week",
            description="Two readings is the minimum for a trend, which is what targets adjust against.",
            challenge_type=ChallengeType.GOAL_ORIENTED,
            difficulty=ChallengeDifficulty.EASY,
            target=2, unit="check-ins", metric="weigh_ins",
            points=80, priority=65,
            reason="Your targets are still based on your registration weight.",
        ))

    # --- when they eat, not just what ------------------------------------
    # All of this comes from logged_at, which was already being written and
    # never read. Timing patterns are among the most personal things the app
    # can notice, and among the easiest to act on.
    if s.days_logged >= 5 and s.breakfast_rate < 0.5:
        out.append(Candidate(
            key="breakfast",
            title="Eat something before 11am on 4 days",
            description=(
                "Skipping breakfast tends to push the day's eating later and "
                "makes the evening harder to control."
            ),
            challenge_type=ChallengeType.CONSISTENCY,
            difficulty=ChallengeDifficulty.EASY,
            target=4, unit="days", metric="days_with_breakfast",
            points=120, priority=72,
            reason=f"You had breakfast on only {s.breakfast_rate * 100:.0f}% of your logged days.",
            badge="early_start",
        ))

    if s.days_logged >= 5 and s.late_night_rate > 0.4:
        out.append(Candidate(
            key="no_late_meals",
            title="Finish eating before 10pm on 4 days",
            description="Late meals are usually the unplanned ones, and they are rarely the good ones.",
            challenge_type=ChallengeType.CONSISTENCY,
            difficulty=ChallengeDifficulty.MEDIUM,
            target=4, unit="days", metric="days_without_late_meal",
            points=140, priority=68,
            reason=f"You ate after 10pm on {s.late_night_rate * 100:.0f}% of your logged days.",
        ))

    # --- weekends ---------------------------------------------------------
    if s.weekend_days >= 2 and s.calorie_target and s.weekend_gap > 0.2:
        out.append(Candidate(
            key="weekend_hold",
            title=f"Keep both weekend days under {s.calorie_target:.0f} kcal",
            description="Two loose days can undo five disciplined ones. This is where most plans quietly fail.",
            challenge_type=ChallengeType.GOAL_ORIENTED,
            difficulty=ChallengeDifficulty.HARD,
            target=2, unit="days",
            metric=f"weekend_days_under:{s.calorie_target}",
            points=220, priority=87,
            reason=(
                f"Your weekends average {s.weekend_avg_calories:.0f} kcal against "
                f"{s.weekday_avg_calories:.0f} on weekdays — {s.weekend_gap * 100:.0f}% higher."
            ),
            badge="weekend_warrior",
        ))

    # --- the scale has stopped moving -------------------------------------
    if s.stalled:
        out.append(Candidate(
            key="log_completeness",
            title="Log everything for 5 days — snacks, drinks, oil included",
            description=(
                "When weight stalls in a deficit, the usual cause is what is not "
                "getting logged rather than the deficit being too small."
            ),
            challenge_type=ChallengeType.CONSISTENCY,
            difficulty=ChallengeDifficulty.MEDIUM,
            target=5, unit="days", metric="days_with_3_meals",
            points=200, priority=93,
            reason=(
                f"Your weight has moved {abs(s.weight_change_kg or 0):.1f} kg despite a deficit — "
                "worth checking the log is complete before changing anything else."
            ),
            badge="honest_log",
        ))

    # --- training ---------------------------------------------------------
    if not s.injured:
        # Only offered when nothing is injured. This is the check the old
        # generator lacked entirely.
        out.append(Candidate(
            key="train_sessions",
            title="Complete 3 training sessions",
            description="Three sessions a week is where consistency starts to compound.",
            challenge_type=ChallengeType.WORKOUT,
            difficulty=ChallengeDifficulty.MEDIUM,
            target=3, unit="sessions", metric="workouts_completed",
            points=180, priority=70 if s.has_workout_plan else 40,
            reason=(
                "You have a training plan saved - this keeps you on it."
                if s.has_workout_plan
                else "Regular training makes every nutrition target easier to hit."
            ),
            badge="committed",
        ))

    # Scale each candidate to how well the user has done with it before, then
    # push anything attempted very recently down the queue so the list changes
    # week to week instead of repeating.
    scaled = []
    for candidate in out:
        candidate = _apply_level(s, candidate)
        days_ago = s.recent_keys.get(candidate.key)
        if days_ago is not None:
            if days_ago < COOLDOWN_DAYS_AFTER_SUCCESS:
                # Just attempted. Only offer it if nothing else is available.
                candidate.priority *= 0.15
            elif days_ago < COOLDOWN_DAYS_AFTER_FAILURE:
                candidate.priority *= 0.6
        scaled.append(candidate)

    scaled.sort(key=lambda c: c.priority, reverse=True)
    return scaled


# ---------------------------------------------------------------------------
# progress, computed from source data
# ---------------------------------------------------------------------------

def score_progress(db: Session, user_id: int, challenge: PersonalizedChallenge) -> float:
    """
    Current progress, recomputed from the underlying data.

    Deliberately not a stored counter. The old design incremented progress from
    one hook on the meal-logging path, so a meal logged through the chatbot, the
    barcode scanner or the planner never counted - and challenges sat at zero
    while the user was doing exactly what was asked. Recomputing on read cannot
    drift, and cannot miss a route.
    """
    metric = ((challenge.personalization_factors or {}).get("metric")
              if isinstance(challenge.personalization_factors, dict) else None)
    if not metric:
        return challenge.current_value or 0.0

    # The user's timezone decides which day a meal counts toward, and every
    # metric below is a count of DAYS. On UTC days an IST user logging dinner
    # at 20:00 had it credited to the next day - so a "log 5 days running"
    # challenge could show 6 days from 5 evenings, or break a streak that was
    # never broken.
    user = db.query(User).filter(User.id == user_id).first()
    tz = daytime.zone_for(user)

    start = challenge.start_date or daytime.days_ago_start(7, tz=tz)
    name, _, argument = metric.partition(":")

    try:
        if name in ("days_logged", "days_with_3_meals", "days_protein_over",
                    "days_calories_under", "days_calories_over", "days_fiber_over",
                    "days_with_breakfast", "days_without_late_meal", "weekend_days_under"):
            meals = (
                db.query(MealLog)
                .filter(MealLog.user_id == user_id, MealLog.logged_at >= start)
                .all()
            )
            by_day: Dict[Any, List[MealLog]] = daytime.group_by_local_day(
                meals, "logged_at", tz=tz)

            if name == "days_logged":
                return float(len(by_day))
            if name == "days_with_3_meals":
                return float(sum(1 for v in by_day.values() if len(v) >= 3))
            if name == "days_with_breakfast":
                return float(sum(
                    1 for v in by_day.values()
                    if any(m.logged_at and (daytime.local_hour(m.logged_at, tz=tz) or 0) < 11
                           for m in v)
                ))
            if name == "days_without_late_meal":
                # Only days they actually logged count - a day with no data is
                # not evidence of an early finish.
                return float(sum(
                    1 for v in by_day.values()
                    if v and not any(
                        m.logged_at and (daytime.local_hour(m.logged_at, tz=tz) or 0) >= 22
                        for m in v)
                ))
            if name == "weekend_days_under":
                threshold = float(argument or 0)
                return float(sum(
                    1 for day, v in by_day.items()
                    if day.weekday() >= 5 and 0 < sum(m.calories or 0 for m in v) <= threshold
                ))

            threshold = float(argument or 0)
            if name == "days_protein_over":
                return float(sum(1 for v in by_day.values()
                                 if sum(m.protein or 0 for m in v) >= threshold))
            if name == "days_calories_under":
                return float(sum(1 for v in by_day.values()
                                 if 0 < sum(m.calories or 0 for m in v) <= threshold))
            if name == "days_calories_over":
                return float(sum(1 for v in by_day.values()
                                 if sum(m.calories or 0 for m in v) >= threshold))
            if name == "days_fiber_over":
                food_ids = {m.food_item_id for m in meals if m.food_item_id}
                fibre = dict(
                    db.query(FoodItem.id, FoodItem.fiber_g)
                    .filter(FoodItem.id.in_(food_ids)).all()
                ) if food_ids else {}
                return float(sum(
                    1 for v in by_day.values()
                    if sum((fibre.get(m.food_item_id) or 0) * (m.quantity or 1) for m in v) >= threshold
                ))

        if name == "new_foods":
            before = {
                r[0] for r in db.query(MealLog.food_item_id)
                .filter(MealLog.user_id == user_id, MealLog.logged_at < start).all()
            }
            during = {
                r[0] for r in db.query(MealLog.food_item_id)
                .filter(MealLog.user_id == user_id, MealLog.logged_at >= start).all()
            }
            return float(len(during - before))

        if name == "weigh_ins":
            return float(
                db.query(WeightLog)
                .filter(WeightLog.user_id == user_id, WeightLog.logged_at >= start)
                .count()
            )

        if name == "injury_checkins":
            # Scoped to the specific injury the challenge is about. Counting
            # every check-in the user has ever made would let updates on an
            # unrelated - or already recovered - injury complete this one,
            # which is how it managed to sit at 3/2 without being touched.
            from app.database import InjuryCheckIn

            query = (
                db.query(InjuryCheckIn)
                .filter(InjuryCheckIn.user_id == user_id, InjuryCheckIn.logged_at >= start)
            )
            if argument:
                query = query.filter(InjuryCheckIn.injury_id == int(argument))
            return float(query.count())

        if name == "has_goal":
            return float(bool(
                db.query(Goal).filter(
                    Goal.user_id == user_id, Goal.is_active == True  # noqa: E712
                ).first()
            ))

        if name == "workouts_completed":
            # No workout-completion log exists yet, so a saved plan generated
            # during the window is the best available proxy. Honest and
            # replaceable once sessions are tracked properly.
            return float(
                db.query(SavedPlan)
                .filter(
                    SavedPlan.user_id == user_id,
                    SavedPlan.plan_type == "workout",
                    SavedPlan.created_at >= start,
                ).count()
            )

    except Exception as e:
        logger.error("score_progress failed for metric %r: %s", metric, e, exc_info=True)

    return challenge.current_value or 0.0


# ---------------------------------------------------------------------------
# creating and refreshing
# ---------------------------------------------------------------------------

def generate_for_user(db: Session, user_id: int, limit: int = 3) -> List[PersonalizedChallenge]:
    """Create challenges for whatever this user most needs right now."""
    situation = read_situation(db, user_id)
    candidates = build_candidates(situation)

    existing = (
        db.query(PersonalizedChallenge)
        .filter(
            PersonalizedChallenge.user_id == user_id,
            PersonalizedChallenge.is_active == True,  # noqa: E712
            PersonalizedChallenge.end_date > datetime.utcnow(),
        ).all()
    )
    taken = {
        (c.personalization_factors or {}).get("key")
        for c in existing if isinstance(c.personalization_factors, dict)
    }
    room = max(0, MAX_ACTIVE - len(existing))
    if room == 0:
        return []

    created: List[PersonalizedChallenge] = []
    for candidate in candidates:
        if len(created) >= min(limit, room):
            break
        if candidate.key in taken:
            continue

        challenge = PersonalizedChallenge(
            user_id=user_id,
            challenge_type=candidate.challenge_type,
            difficulty=candidate.difficulty,
            title=candidate.title,
            description=candidate.description,
            target_value=candidate.target,
            current_value=0.0,
            unit=candidate.unit,
            baseline_data={
                "avg_protein": round(situation.avg_protein, 1),
                "avg_calories": round(situation.avg_calories, 1),
                "avg_fiber": round(situation.avg_fiber, 1),
                "days_logged": situation.days_logged,
                "logging_rate": round(situation.logging_rate, 2),
            },
            personalization_factors={
                "key": candidate.key,
                "metric": candidate.metric,
                "reason": candidate.reason,
                "level": situation.levels.get(candidate.key, 0),
                "injuries": situation.injury_parts,
                "goal": situation.goal_type,
            },
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=candidate.days),
            is_active=True,
            points_reward=candidate.points,
            badge_reward=candidate.badge,
            motivational_messages=[candidate.reason],
        )
        db.add(challenge)
        created.append(challenge)

    if created:
        db.commit()
        for c in created:
            db.refresh(c)
        logger.info("Created %d challenges for user %s", len(created), user_id)

    return created


def refresh_progress(db: Session, user_id: int) -> List[PersonalizedChallenge]:
    """
    Recompute every active challenge, completing and expiring as needed.

    Called on read, which is what keeps the numbers honest regardless of how
    the user logged their data.
    """
    challenges = (
        db.query(PersonalizedChallenge)
        .filter(
            PersonalizedChallenge.user_id == user_id,
            PersonalizedChallenge.is_active == True,  # noqa: E712
        ).all()
    )

    changed = False
    for challenge in challenges:
        value = score_progress(db, user_id, challenge)
        percentage = (
            min(100.0, (value / challenge.target_value) * 100)
            if challenge.target_value else 0.0
        )
        if challenge.current_value != value or challenge.completion_percentage != percentage:
            challenge.current_value = value
            challenge.completion_percentage = percentage
            changed = True

        expired = bool(challenge.end_date and challenge.end_date <= datetime.utcnow())
        recorded = _outcome_exists(db, challenge)

        # Completing banks the points and steps the difficulty up next time.
        # The challenge stays visible until it expires, though - hiding it the
        # moment it completes would mean the user never sees the tick they
        # just earned.
        if percentage >= 100 and not recorded:
            record_outcome(db, challenge, completed=True)
            changed = True
        elif expired:
            if not recorded:
                record_outcome(db, challenge, completed=False)
            challenge.is_active = False
            changed = True

    if changed:
        db.commit()

    return [c for c in challenges if c.is_active]
