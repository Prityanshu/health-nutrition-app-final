"""
The user's real situation, compressed into something the assistant can read.

WHY THIS EXISTS
---------------
The assistant knew a user's height, weight and calorie target - the things they
typed once at registration - and nothing about what they actually do. It could
not answer "what should I eat tonight?" with anything better than a stranger
could, because it had never seen a single logged meal.

Everything here is already in the database. The work is selecting the few facts
that change an answer, and phrasing them so a language model uses them naturally
instead of reciting them.

DESIGN CONSTRAINTS
------------------
1. Cheap. One request per chat message, so this is a handful of indexed queries
   over small per-user tables. No model calls.
2. Small. Groq's free tier bills input tokens, and this rides along on every
   message. The rendered block is capped at roughly 200 tokens - facts only, no
   prose, no JSON.
3. Honest about absence. A new user with nothing logged produces a short block
   saying so, rather than zeros that read as "ate nothing today".
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import FoodItem, Goal, MealLog, SavedPlan, User, WeightLog
from app.services import daytime

logger = logging.getLogger(__name__)

# How far back to look for habits. Long enough to see a pattern, short enough
# that a change in diet shows up within a couple of weeks.
_HABIT_DAYS = 21
# A weight trend needs at least this many check-ins to mean anything.
_MIN_WEIGHTS_FOR_TREND = 2
# Foods named in the prompt. More than this and the model starts listing them
# back at the user.
_TOP_FOODS = 5


@dataclass
class ChatContext:
    """Facts about one user at one moment. All fields optional by design."""

    # Today
    calories_today: float = 0.0
    protein_today: float = 0.0
    meals_today: int = 0
    meal_types_today: List[str] = field(default_factory=list)
    calorie_target: Optional[float] = None
    protein_target: Optional[float] = None

    # Habits
    top_foods: List[str] = field(default_factory=list)
    days_logged_recently: int = 0
    avg_daily_calories: Optional[float] = None
    avg_daily_protein: Optional[float] = None
    last_logged_days_ago: Optional[int] = None

    # Direction of travel
    goal_type: Optional[str] = None
    current_weight: Optional[float] = None
    target_weight: Optional[float] = None
    weight_change_kg: Optional[float] = None
    weight_window_days: Optional[int] = None

    # What has already been produced for them
    last_plan_type: Optional[str] = None
    last_plan_title: Optional[str] = None
    last_plan_days_ago: Optional[int] = None
    typical_budget: Optional[float] = None

    # Injuries. Safety-critical, so these are carried verbatim rather than
    # summarised - the assistant needs the exclusions, not the gist.
    injury_lines: List[str] = field(default_factory=list)
    injury_needs_attention: bool = False
    injury_checkin_due: bool = False

    # How the completed days went. Previously the assistant knew today's
    # numbers and a 21-day average, and nothing in between - so it could not
    # tell a good week from a bad one, and told people they were "doing well"
    # on the fourth straight day of missing protein.
    days_on_target: Optional[int] = None
    days_assessable: Optional[int] = None
    current_streak: int = 0
    adherence_headline: Optional[str] = None
    weak_points: List[Dict[str, Any]] = field(default_factory=list)
    yesterday_status: Optional[str] = None
    yesterday_summary: Optional[str] = None

    # Situation
    local_hour: int = 12
    weekday: str = ""

    @property
    def calories_remaining(self) -> Optional[float]:
        if self.calorie_target is None:
            return None
        return self.calorie_target - self.calories_today

    @property
    def protein_remaining(self) -> Optional[float]:
        if self.protein_target is None:
            return None
        return max(0.0, self.protein_target - self.protein_today)

    @property
    def has_any_history(self) -> bool:
        return self.days_logged_recently > 0 or self.meals_today > 0


# ---------------------------------------------------------------------------
# building
# ---------------------------------------------------------------------------

def _start_of_today(user=None) -> datetime:
    """UTC start of the user's local day - not of the UTC day."""
    start, _ = daytime.today_bounds(user)
    return start


def _meal_slot(hour: int) -> str:
    if hour < 11:
        return "breakfast"
    if hour < 16:
        return "lunch"
    if hour < 22:
        return "dinner"
    return "a late snack"


def build_chat_context(user_id: int, db: Session, now: Optional[datetime] = None) -> ChatContext:
    """
    Gather everything worth knowing about this user right now.

    Never raises: a context failure must not take the chat down with it. A
    partial context is more useful than none, and none is still usable.
    """
    ctx = ChatContext()

    # The user is needed for their timezone. Previously `local_hour` came from
    # datetime.now() - the SERVER's clock - while the "today" window came from
    # utcnow(). Two different days in one context: the chatbot could greet
    # somebody with "good evening" while counting tomorrow's meals.
    user = db.query(User).filter(User.id == user_id).first()
    tz = daytime.zone_for(user)

    now = now or daytime.local_now(tz=tz)
    ctx.local_hour = now.hour
    ctx.weekday = now.strftime("%A")

    try:
        # --- today -------------------------------------------------------
        today_start = _start_of_today(user)
        today_rows = (
            db.query(MealLog)
            .filter(MealLog.user_id == user_id, MealLog.logged_at >= today_start)
            .all()
        )
        ctx.calories_today = sum(r.calories or 0 for r in today_rows)
        ctx.protein_today = sum(r.protein or 0 for r in today_rows)
        ctx.meals_today = len(today_rows)
        ctx.meal_types_today = sorted({r.meal_type for r in today_rows if r.meal_type})

        # --- targets -----------------------------------------------------
        goal = (
            db.query(Goal)
            .filter(Goal.user_id == user_id, Goal.is_active == True)  # noqa: E712
            .order_by(Goal.created_at.desc())
            .first()
        )
        if goal:
            ctx.goal_type = goal.goal_type
            ctx.calorie_target = goal.target_calories
            ctx.protein_target = goal.target_protein
            ctx.target_weight = goal.target_weight

        # --- the last week against target ---------------------------------
        try:
            from app.services import adherence as adherence_service

            results = adherence_service.history(db, user, days=7)
            summary = adherence_service.summarise(results)
            ctx.days_on_target = summary["hits"]
            ctx.days_assessable = summary["assessable_days"]
            ctx.current_streak = summary["current_streak"]
            ctx.adherence_headline = summary["headline"]
            ctx.weak_points = summary["weak_points"]
            if results:
                yesterday = results[-1]
                ctx.yesterday_status = yesterday.status
                ctx.yesterday_summary = yesterday.summary()
        except Exception as e:
            # Adherence is enrichment. A failure here must not cost the user
            # their injury lines or today's numbers.
            logger.warning("adherence context unavailable: %s", e)

        # --- habits ------------------------------------------------------
        since = daytime.days_ago_start(_HABIT_DAYS, user)
        recent = (
            db.query(MealLog)
            .filter(MealLog.user_id == user_id, MealLog.logged_at >= since)
            .all()
        )
        if recent:
            # Local days, not UTC days - otherwise an IST evening meal counts
            # toward tomorrow and "days logged" is wrong by up to one per day.
            days = daytime.local_dates_between(recent, "logged_at", tz=tz)
            ctx.days_logged_recently = len(days)
            if days:
                ctx.avg_daily_calories = sum(r.calories or 0 for r in recent) / len(days)
                ctx.avg_daily_protein = sum(r.protein or 0 for r in recent) / len(days)

            # Most-eaten foods by frequency, resolved in one query.
            counts: Dict[int, int] = {}
            for row in recent:
                if row.food_item_id:
                    counts[row.food_item_id] = counts.get(row.food_item_id, 0) + 1
            if counts:
                ranked = sorted(counts, key=counts.get, reverse=True)[:_TOP_FOODS]
                names = {
                    f.id: f.name
                    for f in db.query(FoodItem).filter(FoodItem.id.in_(ranked)).all()
                }
                ctx.top_foods = [names[i] for i in ranked if i in names]

        last = (
            db.query(func.max(MealLog.logged_at))
            .filter(MealLog.user_id == user_id)
            .scalar()
        )
        if last:
            ctx.last_logged_days_ago = max(0, (datetime.utcnow() - last).days)

        # --- weight ------------------------------------------------------
        weights = (
            db.query(WeightLog)
            .filter(WeightLog.user_id == user_id)
            .order_by(WeightLog.logged_at.desc())
            .limit(8)
            .all()
        )
        if weights:
            ctx.current_weight = weights[0].weight_kg
            if len(weights) >= _MIN_WEIGHTS_FOR_TREND:
                oldest = weights[-1]
                ctx.weight_change_kg = round(weights[0].weight_kg - oldest.weight_kg, 1)
                if oldest.logged_at and weights[0].logged_at:
                    ctx.weight_window_days = max(
                        1, (weights[0].logged_at - oldest.logged_at).days
                    )
        else:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                ctx.current_weight = user.weight

        # --- what they have already been given ---------------------------
        plan = (
            db.query(SavedPlan)
            .filter(SavedPlan.user_id == user_id)
            .order_by(SavedPlan.created_at.desc())
            .first()
        )
        if plan:
            ctx.last_plan_type = plan.plan_type
            ctx.last_plan_title = plan.title
            if plan.created_at:
                ctx.last_plan_days_ago = max(0, (datetime.utcnow() - plan.created_at).days)

        # Budget is not a profile field; it is whatever they last asked for.
        ctx.typical_budget = _recent_budget(user_id, db)

        # --- injuries ----------------------------------------------------
        # The whole point of storing injuries was that every part of the app
        # should see them. This is the part that was missing: the assistant
        # still had no idea, so it would happily build a plan around a leg the
        # user had told it was torn.
        try:
            from app.services import injury_service
            ctx.injury_lines = injury_service.as_constraints(db, user_id)
            state = injury_service.summary(db, user_id)
            ctx.injury_needs_attention = state.get("needs_attention", False)
            ctx.injury_checkin_due = state.get("checkin_due", False)
        except Exception as e:
            logger.error("Could not load injuries for chat context: %s", e)

    except Exception as e:
        logger.error("chat_context build failed for user %s: %s", user_id, e, exc_info=True)

    return ctx


def _recent_budget(user_id: int, db: Session) -> Optional[float]:
    """Median daily budget across recent plans, if they have ever set one."""
    try:
        rows = (
            db.query(SavedPlan.params)
            .filter(SavedPlan.user_id == user_id, SavedPlan.params.isnot(None))
            .order_by(SavedPlan.created_at.desc())
            .limit(10)
            .all()
        )
        values: List[float] = []
        for (raw,) in rows:
            try:
                params = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(params, dict):
                continue
            for key in ("budget_per_day", "daily_budget", "budget"):
                v = params.get(key)
                if isinstance(v, (int, float)) and v > 0:
                    values.append(float(v))
                    break
        if not values:
            return None
        values.sort()
        return values[len(values) // 2]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def render_for_prompt(ctx: ChatContext) -> str:
    """
    Turn the context into prompt text.

    Deliberately terse and factual. Anything phrased as a suggestion tends to
    get repeated back to the user verbatim, which is the opposite of feeling
    personal - the aim is for the assistant to *know* these things, not to
    announce that it knows them.
    """
    lines: List[str] = []

    # --- injuries first --------------------------------------------------
    # Placed at the top of the block deliberately. This is the only
    # safety-critical item here, and it must not be something the model skims
    # past after four lines about calories.
    if ctx.injury_lines:
        lines.append(
            "- CURRENTLY INJURED. This applies to every plan, workout and "
            "suggestion you produce, without being asked:"
        )
        for line in ctx.injury_lines:
            lines.append(f"    * {line}")
        if ctx.injury_needs_attention:
            lines.append(
                "    * They reported it worsening. Do not hand over a modified plan "
                "as though it were solved - say plainly it needs looking at."
            )
        if ctx.injury_checkin_due:
            lines.append(
                "    * A check-in is overdue. If it fits naturally, ask how it is "
                "doing - once, briefly, not as an interrogation."
            )

    # --- right now -------------------------------------------------------
    part_of_day = (
        "morning" if ctx.local_hour < 12
        else "afternoon" if ctx.local_hour < 17
        else "evening" if ctx.local_hour < 22
        else "late evening"
    )
    lines.append(f"- It is {ctx.weekday} {part_of_day}, {ctx.local_hour:02d}:00 their time.")

    # --- today -----------------------------------------------------------
    if ctx.meals_today:
        eaten = f"- Today: {ctx.meals_today} meal(s) logged, {ctx.calories_today:.0f} kcal"
        if ctx.protein_today:
            eaten += f", {ctx.protein_today:.0f}g protein"
        if ctx.meal_types_today:
            eaten += f" ({', '.join(ctx.meal_types_today)})"
        lines.append(eaten + ".")

        remaining = ctx.calories_remaining
        if remaining is not None:
            if remaining > 0:
                lines.append(f"- {remaining:.0f} kcal left against their target today.")
            else:
                lines.append(f"- Already {abs(remaining):.0f} kcal over target today.")
        if ctx.protein_remaining:
            lines.append(f"- {ctx.protein_remaining:.0f}g of protein still to go today.")

        # The gap that a suggestion should fill.
        expected = _meal_slot(ctx.local_hour)
        if expected not in ctx.meal_types_today and expected != "a late snack":
            lines.append(f"- They have not logged {expected} yet.")
    else:
        lines.append("- Nothing logged today yet.")

    # --- how the week has actually gone -----------------------------------
    # This is the difference between an assistant that knows today's calorie
    # count and one that knows whether the week is going well. Stated as fact,
    # not as a suggestion, so the model uses it rather than reading it out.
    if ctx.days_assessable:
        lines.append(
            f"- Hit every macro target on {ctx.days_on_target} of the last "
            f"{ctx.days_assessable} completed days they logged."
        )
        if ctx.current_streak >= 2:
            lines.append(
                f"- On target {ctx.current_streak} days running. Worth acknowledging "
                "once, briefly, if it fits - not every message."
            )
        if ctx.yesterday_status == "missed" and ctx.yesterday_summary:
            lines.append(f"- Yesterday: {ctx.yesterday_summary}.")
        elif ctx.yesterday_status == "hit":
            lines.append("- Yesterday was on target.")

        # The single most useful line in this block: a repeated miss tells the
        # assistant what to steer toward without being asked.
        for weak in ctx.weak_points[:2]:
            unit = "kcal" if weak["macro"] == "calories" else "g"
            lines.append(
                f"- {weak['macro'].capitalize()} was {weak['direction']} on "
                f"{weak['days']} of {weak['of']} days, by "
                f"{abs(weak['average_delta']):.0f}{unit} on average. Favour "
                f"suggestions that correct this."
            )
    elif ctx.yesterday_status == "unlogged":
        lines.append("- Nothing logged yesterday either.")

    # --- habits ----------------------------------------------------------
    if ctx.top_foods:
        lines.append(f"- Eats most often: {', '.join(ctx.top_foods)}.")
    if ctx.avg_daily_calories and ctx.days_logged_recently:
        habit = (
            f"- Over the last {_HABIT_DAYS} days they logged on "
            f"{ctx.days_logged_recently} day(s), averaging {ctx.avg_daily_calories:.0f} kcal"
        )
        if ctx.avg_daily_protein:
            habit += f" and {ctx.avg_daily_protein:.0f}g protein"
        lines.append(habit + " per logged day.")

        # Chronic protein shortfall is worth surfacing; it is the single most
        # common gap and the assistant can act on it without being asked.
        if ctx.protein_target and ctx.avg_daily_protein:
            if ctx.avg_daily_protein < ctx.protein_target * 0.75:
                lines.append(
                    f"- Their protein has been running well under target "
                    f"({ctx.avg_daily_protein:.0f}g vs {ctx.protein_target:.0f}g)."
                )

    if ctx.last_logged_days_ago is not None and ctx.last_logged_days_ago >= 3:
        lines.append(
            f"- Has not logged anything for {ctx.last_logged_days_ago} days. "
            "Do not scold; if it comes up, be light about it."
        )

    # --- progress --------------------------------------------------------
    if ctx.goal_type:
        goal_line = f"- Goal: {ctx.goal_type.replace('_', ' ')}"
        if ctx.current_weight:
            goal_line += f", currently {ctx.current_weight:.1f} kg"
        if ctx.target_weight:
            goal_line += f", target {ctx.target_weight:.1f} kg"
        lines.append(goal_line + ".")

    if ctx.weight_change_kg is not None and ctx.weight_window_days:
        direction = (
            "down" if ctx.weight_change_kg < 0
            else "up" if ctx.weight_change_kg > 0
            else "unchanged"
        )
        if direction == "unchanged":
            lines.append(
                f"- Weight has not moved in {ctx.weight_window_days} days."
            )
        else:
            lines.append(
                f"- Weight is {direction} {abs(ctx.weight_change_kg)} kg "
                f"over {ctx.weight_window_days} days."
            )

    # --- already given ---------------------------------------------------
    if ctx.last_plan_type:
        when = (
            "today" if ctx.last_plan_days_ago == 0
            else "yesterday" if ctx.last_plan_days_ago == 1
            else f"{ctx.last_plan_days_ago} days ago"
        )
        label = (ctx.last_plan_title or ctx.last_plan_type.replace("_", " "))
        lines.append(
            f"- You already gave them \"{label}\" ({ctx.last_plan_type.replace('_', ' ')}) {when}. "
            "Build on it rather than producing a near-identical one."
        )

    if ctx.typical_budget:
        lines.append(f"- Typically budgets around ₹{ctx.typical_budget:.0f} a day for food.")

    if not ctx.has_any_history:
        lines.append(
            "- They are new and have logged nothing yet, so you have no eating history. "
            "Do not pretend otherwise or invent habits."
        )

    return "\n".join(lines)


def build_and_render(user_id: int, db: Session) -> str:
    """Convenience wrapper - the one call the chat router needs."""
    return render_for_prompt(build_chat_context(user_id, db))


def opening_line(ctx: ChatContext, name: str = "") -> str:
    """
    A grounded first line for an empty chat window.

    Deterministic on purpose: it costs nothing, cannot hallucinate, and is
    ready before the screen paints. The assistant takes over from the second
    message onward.
    """
    who = name.split(" ")[0] if name else ""
    greeting = (
        "Morning" if ctx.local_hour < 12
        else "Afternoon" if ctx.local_hour < 17
        else "Evening"
    )
    hello = f"{greeting}{', ' + who if who else ''}."

    if not ctx.has_any_history:
        return (
            f"{hello} I can put together meals, workouts and weekly plans around "
            "your goals. What would be useful right now?"
        )

    remaining = ctx.calories_remaining
    slot = _meal_slot(ctx.local_hour)

    if ctx.meals_today == 0 and ctx.local_hour >= 11:
        return f"{hello} Nothing logged yet today — want a hand with {slot}?"

    if remaining is not None and remaining > 250 and slot not in ctx.meal_types_today:
        return (
            f"{hello} You've got about {remaining:.0f} kcal left today and no "
            f"{slot} logged. Want an idea?"
        )

    if remaining is not None and remaining < 0:
        return (
            f"{hello} You're a bit over target today — no drama. "
            "Want to plan tomorrow instead?"
        )

    if ctx.last_plan_type == "workout" and ctx.last_plan_days_ago is not None and ctx.last_plan_days_ago <= 7:
        return f"{hello} How's the training plan going? Happy to adjust it."

    return f"{hello} What can I help with today?"
