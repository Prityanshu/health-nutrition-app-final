"""
Personalisation built from what the user actually does in the app.

WHY THIS EXISTS
---------------
The previous "For You" page produced generic advice that would have been
identical for any account. Everything below is derived from real rows: meals
they logged, the cost and cuisine of those foods, their goal targets, their
weight trend, and their stated restrictions.

WHY IT IS NOT AN LLM CALL
-------------------------
Ranking 51 foods against a macro gap is arithmetic. Doing it in Python means
it is instant, free, identical on repeat visits, and - most importantly - every
recommendation can state exactly why it was chosen. "High protein, fits your
remaining 62 g, ₹8, similar to paneer which you log often" is more convincing
than a model's assertion, and it cannot be a hallucination.

SIGNALS ACTUALLY AVAILABLE (verified against the database)
----------------------------------------------------------
  meal_logs    - what, when, how much, which meal slot        [populated]
  food_items   - macros, cost, cuisine, tags, prep, health    [populated]
  goals        - calorie and macro targets                    [populated]
  weight_logs  - trend                                        [populated]
  users        - dietary_preferences, health_conditions       [populated]

Deliberately NOT used, because these tables are empty and anything built on
them would be fabricated: food_ratings, user_preferences, user_behaviors,
food_preference_learning, seasonal_preferences.
"""

import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database import FoodItem, Goal, MealLog, User, WeightLog

logger = logging.getLogger(__name__)

# Tags in food_items are inconsistent - "Vegetarian", "vegetarian",
# "🌱 Vegetarian" and "lacto_vegetarian" all appear. Normalise before matching.
_NON_VEG_MARKERS = ("non_veg", "meat", "chicken", "fish", "seafood", "pork",
                    "beef", "mutton", "egg", "🍗", "🐟", "🥚")
_VEG_MARKERS = ("vegetarian", "vegan", "🌱")


def _norm_tags(raw: Optional[str]) -> List[str]:
    """Lowercase, strip emoji/punctuation, split on commas."""
    if not raw:
        return []
    out = []
    for part in raw.split(","):
        cleaned = re.sub(r"[^\w\s-]", " ", part).strip().lower()
        cleaned = re.sub(r"\s+", "_", cleaned)
        if cleaned:
            out.append(cleaned)
    return out


def _is_non_veg(food: FoodItem) -> bool:
    haystack = " ".join([
        (food.name or ""), (food.tags or ""), (food.ingredients or "")
    ]).lower()
    return any(m in haystack for m in _NON_VEG_MARKERS)


def _json_list(raw) -> List[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else [parsed]
    except (json.JSONDecodeError, TypeError):
        return [raw]


# --------------------------------------------------------------------------
# Taste profile
# --------------------------------------------------------------------------

def build_profile(user: User, db: Session, days: int = 365) -> Dict[str, Any]:
    """
    Everything we can infer about this user from their own activity.

    The window is deliberately wide. Logging in this app is bursty - people
    track for a few weeks, stop, then come back - so a short window throws
    away most of the taste signal. Habit metrics below are computed per
    active day rather than per calendar day, so gaps do not distort them.
    """
    since = datetime.utcnow() - timedelta(days=days)

    rows = (
        db.query(MealLog, FoodItem)
        .outerjoin(FoodItem, MealLog.food_item_id == FoodItem.id)
        .filter(MealLog.user_id == user.id, MealLog.logged_at >= since)
        .order_by(MealLog.logged_at.desc())
        .all()
    )

    logs = [m for m, _ in rows]
    foods = [f for _, f in rows if f is not None]

    stated_diet = [d.lower() for d in _json_list(user.dietary_preferences)]
    conditions = [c.lower() for c in _json_list(user.health_conditions)]

    profile: Dict[str, Any] = {
        "log_count": len(logs),
        "has_history": len(logs) >= 3,
        "stated_diet": stated_diet,
        "health_conditions": conditions,
    }

    # --- vegetarian: stated wins, otherwise infer from what they log ---
    stated_veg = any("veg" in d and "non" not in d for d in stated_diet)
    non_veg_logs = sum(1 for f in foods if _is_non_veg(f))
    inferred_veg = len(foods) >= 5 and non_veg_logs == 0

    profile["vegetarian"] = bool(stated_veg or inferred_veg)
    profile["vegetarian_source"] = (
        "you told us" if stated_veg
        else "none of your logged meals contain meat or fish" if inferred_veg
        else None
    )

    # --- favourites ---
    name_counts = Counter(f.name for f in foods if f.name)
    profile["favourites"] = [
        {"name": n, "times": c} for n, c in name_counts.most_common(5)
    ]

    # --- cuisine affinity ---
    cuisines = Counter(
        f.cuisine_type for f in foods
        if f.cuisine_type and f.cuisine_type not in ("mixed", "ai_analyzed")
    )
    total_cuisine = sum(cuisines.values())
    profile["cuisine_affinity"] = {
        c: round(n / total_cuisine, 2) for c, n in cuisines.most_common(4)
    } if total_cuisine else {}
    profile["top_cuisine"] = cuisines.most_common(1)[0][0] if cuisines else None

    # --- budget: what they actually pick, not what they say ---
    costs = [f.cost for f in foods if f.cost and f.cost > 0]
    if costs:
        costs_sorted = sorted(costs)
        median = costs_sorted[len(costs_sorted) // 2]
        profile["budget"] = {
            "median_per_item": round(median, 1),
            "avg_per_item": round(sum(costs) / len(costs), 1),
            "max_seen": round(max(costs), 1),
            # A comfortable ceiling: median plus headroom, so suggestions are
            # not all cheaper than what they already choose.
            "comfortable_ceiling": round(max(median * 1.8, median + 3), 1),
        }
    else:
        profile["budget"] = None

    # --- prep complexity they gravitate to ---
    prep = Counter((f.prep_complexity or "").upper() for f in foods if f.prep_complexity)
    profile["prep_preference"] = prep.most_common(1)[0][0] if prep else None

    # --- meal timing: which slots they log, which they skip ---
    slots = Counter((m.meal_type or "unknown").lower() for m in logs)
    profile["meal_slots"] = dict(slots)
    days_active = len({m.logged_at.date() for m in logs}) or 1
    profile["days_active"] = days_active
    profile["logs_per_day"] = round(len(logs) / days_active, 1)

    # Only meaningful once there is enough history; with zero logs every meal
    # looks "skipped", which is a useless thing to tell someone.
    expected = ["breakfast", "lunch", "dinner"]
    profile["often_skipped"] = (
        [s for s in expected if slots.get(s, 0) < days_active * 0.4]
        if len(logs) >= 6 and days_active >= 2 else []
    )

    # --- macro habits (daily averages) ---
    by_day = defaultdict(lambda: {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0})
    for m in logs:
        d = m.logged_at.date()
        by_day[d]["calories"] += m.calories or 0
        by_day[d]["protein"] += m.protein or 0
        by_day[d]["carbs"] += m.carbs or 0
        by_day[d]["fat"] += m.fat or 0
    if by_day:
        n = len(by_day)
        profile["daily_average"] = {
            k: round(sum(d[k] for d in by_day.values()) / n)
            for k in ("calories", "protein", "carbs", "fat")
        }
    else:
        profile["daily_average"] = None

    # --- variety ---
    distinct = len(name_counts)
    profile["variety"] = {
        "distinct_foods": distinct,
        "total_logs": len(logs),
        "ratio": round(distinct / len(logs), 2) if logs else 0,
        # Same handful of foods over and over
        "in_a_rut": len(logs) >= 8 and distinct <= max(3, len(logs) * 0.35),
    }

    # --- recently eaten, so suggestions are not repeats ---
    profile["recent_food_ids"] = [f.id for f in foods[:8]]

    return profile


# --------------------------------------------------------------------------
# Today's remaining budget
# --------------------------------------------------------------------------

def todays_gap(user: User, db: Session, goal: Optional[Goal]) -> Dict[str, Any]:
    """What is left of today's targets."""
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today = (
        db.query(MealLog)
        .filter(MealLog.user_id == user.id, MealLog.logged_at >= start)
        .all()
    )
    eaten = {
        "calories": sum(m.calories or 0 for m in today),
        "protein": sum(m.protein or 0 for m in today),
        "carbs": sum(m.carbs or 0 for m in today),
        "fat": sum(m.fat or 0 for m in today),
    }
    if not goal:
        return {"eaten": eaten, "remaining": None, "meals_today": len(today)}

    remaining = {
        "calories": max(0, (goal.target_calories or 0) - eaten["calories"]),
        "protein": max(0, (goal.target_protein or 0) - eaten["protein"]),
        "carbs": max(0, (goal.target_carbs or 0) - eaten["carbs"]),
        "fat": max(0, (goal.target_fat or 0) - eaten["fat"]),
    }
    return {"eaten": eaten, "remaining": remaining, "meals_today": len(today)}


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

# Deep-fried, refined or confectionery items. The database has no field for
# this, but the names are reliable - and "Chole Bhature" scoring well on a fat
# loss plan is exactly the failure this prevents.
_REFINED_MARKERS = (
    "bhature", "bhatura", "puri", "poori", "samosa", "pakora", "bonda", "vada",
    "fried", "fries", "chips", "croissant", "cake", "pastry", "donut", "doughnut",
    "jalebi", "gulab", "halwa", "laddu", "barfi", "sweet", "candy", "chocolate",
    "biscuit", "cookie", "namkeen", "bhujia", "wafer", "soda", "cola",
)


def _is_refined(food: FoodItem) -> bool:
    text = f"{food.name or ''} {food.ingredients or ''}".lower()
    return any(m in text for m in _REFINED_MARKERS)


def _goal_direction(goal_type: Optional[str]) -> str:
    """Collapse the nine presets into the three that change food scoring."""
    g = (goal_type or "").lower()
    if "loss" in g or "recomp" in g:
        return "deficit"
    if "gain" in g or "bulk" in g or "athletic" in g:
        return "surplus"
    return "maintain"


def score_food(
    food: FoodItem, *, direction: str, need_protein: float, need_calories: float,
    profile: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Score one food for one user, right now.

    Nutritional quality dominates; taste and budget are tie-breakers. The
    previous version had that backwards - a +22 cuisine bonus meant every Indian
    dish outranked every nutritionally better option, which is how deep-fried
    bread ended up recommended on a fat-loss plan.

    Returns None if the food should not be shown at all.
    """
    calories = food.calories or 0
    protein = food.protein_g or 0
    carbs = food.carbs_g or 0
    fibre = food.fiber_g or 0
    sugar = food.sugar_g or 0
    gi = food.gi or 0

    if calories <= 0:
        return None

    reasons: List[str] = []
    score = 0.0

    # --- protein ratio: share of calories coming from protein ------------
    # The single most useful quality signal available, and it separates the
    # database cleanly (grilled chicken 75%, chole bhature 11%).
    protein_ratio = (protein * 4) / calories

    if direction == "deficit":
        # Cutting: protein density is what preserves muscle and keeps you full.
        score += protein_ratio * 70
        if protein_ratio >= 0.40:
            reasons.append(f"{protein_ratio:.0%} of its calories are protein — keeps you full while cutting")
        elif protein_ratio < 0.12:
            score -= 18  # mostly carbs or fat
    elif direction == "surplus":
        # Building: absolute protein and enough energy matter more than ratio.
        score += min(protein / 30, 1.0) * 45
        score += protein_ratio * 20
        if protein >= 20:
            reasons.append(f"{protein:.0f}g protein per serving")
    else:
        score += protein_ratio * 45
        if protein_ratio >= 0.30:
            reasons.append("good protein for its calories")

    # --- energy density ---------------------------------------------------
    if direction == "deficit":
        # Penalise calorie-dense items: they eat the daily budget fast.
        if calories > 350:
            score -= (calories - 350) / 12
        elif calories <= 200:
            score += 8
    elif direction == "surplus" and calories >= 300:
        score += 6  # easier to hit a surplus

    # --- fibre and satiety -------------------------------------------------
    fibre_per_100 = (fibre / calories) * 100 if calories else 0
    if fibre_per_100 >= 2:
        score += 12
        if fibre >= 4:
            reasons.append(f"{fibre:.0f}g fibre — slow to digest, keeps hunger down")
    elif direction == "deficit" and fibre == 0 and carbs > 25:
        score -= 6  # refined carbohydrate with nothing to slow it

    # --- glycaemic index (92% of rows have it, previously unused) ---------
    if gi > 0:
        if gi >= 70 and direction == "deficit":
            score -= 12
        elif gi <= 45:
            score += 6
            if gi <= 35 and not any("fibre" in r for r in reasons):
                reasons.append("low glycaemic — steadier energy")

    # --- sugar -------------------------------------------------------------
    if sugar > 0:
        sugar_ratio = (sugar * 4) / calories
        if sugar_ratio > 0.30:
            score -= 15
        elif sugar_ratio > 0.18:
            score -= 6

    # --- refined / deep-fried ---------------------------------------------
    if _is_refined(food):
        score -= 30 if direction == "deficit" else 15

    # --- how much of today's remaining protein it covers -------------------
    if need_protein > 0 and protein > 0:
        covers = min(protein / need_protein, 1.0)
        score += covers * 18
        if covers >= 0.15 and not reasons:
            reasons.append(f"{protein:.0f}g protein — {covers:.0%} of what's left today")

    # --- does it fit the remaining calorie budget? -------------------------
    if need_calories > 0:
        if calories > need_calories:
            score -= min(25, (calories - need_calories) / 25)
        elif calories <= need_calories * 0.45:
            score += 5

    return {"score": score, "reasons": reasons, "protein_ratio": protein_ratio}


def recommend_foods(
    user: User, db: Session, profile: Dict[str, Any],
    gap: Dict[str, Any], goal_type: Optional[str] = None, limit: int = 8,
) -> List[Dict[str, Any]]:
    """
    Rank foods for this user against their goal, today's remaining macros, and
    their tastes - in that order of importance.
    """
    # Some rows are whole dishes rather than servings (one is 2250 kcal with
    # 120 g protein). Recommending those would be nonsense.
    MAX_PLAUSIBLE_CALORIES = 900
    MAX_PLAUSIBLE_PROTEIN = 80
    candidates = [
        f for f in db.query(FoodItem).all()
        if 0 < (f.calories or 0) <= MAX_PLAUSIBLE_CALORIES
        and (f.protein_g or 0) <= MAX_PLAUSIBLE_PROTEIN
    ]

    direction = _goal_direction(goal_type)
    remaining = gap.get("remaining") or {}
    need_protein = remaining.get("protein", 0)
    need_calories = remaining.get("calories", 0)

    budget = profile.get("budget") or {}
    ceiling = budget.get("comfortable_ceiling")
    median_cost = budget.get("median_per_item")
    affinity = profile.get("cuisine_affinity") or {}
    conditions = profile.get("health_conditions") or []
    recent = set(profile.get("recent_food_ids") or [])
    favourite_names = {f["name"] for f in profile.get("favourites", [])}

    scored = []
    for food in candidates:
        # --- hard filters ---------------------------------------------------
        if profile.get("vegetarian") and _is_non_veg(food):
            continue
        if any("diabet" in c for c in conditions) and not food.diabetic_friendly:
            continue
        if any(("hypertens" in c or "blood pressure" in c) for c in conditions):
            if not food.hypertension_friendly:
                continue

        base = score_food(
            food, direction=direction, need_protein=need_protein,
            need_calories=need_calories, profile=profile,
        )
        if base is None:
            continue

        score = base["score"]
        reasons = list(base["reasons"])

        # --- taste: a tie-breaker, not a driver ------------------------------
        # Capped low deliberately. Preferring a cuisine should reorder
        # comparable options, never promote a worse food over a better one.
        if food.cuisine_type in affinity:
            score += affinity[food.cuisine_type] * 8
            if len(reasons) < 2:
                reasons.append(f"{food.cuisine_type.title()} — a cuisine you eat often")

        if food.name in favourite_names:
            score += 4

        # --- novelty ---------------------------------------------------------
        if food.id in recent:
            score -= 15
        elif profile.get("variety", {}).get("in_a_rut"):
            score += 8

        # --- budget: only when genuinely notable -----------------------------
        # Cost is recorded for barely half the catalogue and the values are
        # coarse, so it only nudges the ranking, and is only worth mentioning
        # when an item is clearly cheap or clearly a stretch.
        cost = food.cost or 0
        if ceiling and cost > 0:
            if cost > ceiling:
                score -= 8
            elif median_cost and cost <= median_cost * 0.6:
                score += 4
                if len(reasons) < 3:
                    reasons.append(f"₹{cost:.0f} — cheaper than you usually spend")

        # --- convenience -----------------------------------------------------
        if profile.get("prep_preference") == "LOW" and (food.prep_complexity or "").upper() == "LOW":
            score += 4

        if not reasons:
            reasons.append("solid all-round option for your targets")

        scored.append({
            "id": food.id,
            "name": food.name,
            "cuisine": food.cuisine_type,
            "calories": round(calories_of(food)),
            "protein_g": round(food.protein_g or 0, 1),
            "carbs_g": round(food.carbs_g or 0, 1),
            "fat_g": round(food.fat_g or 0, 1),
            "fiber_g": round(food.fiber_g or 0, 1),
            "cost": round(cost, 1) if cost else None,
            "prep_complexity": food.prep_complexity,
            "protein_ratio": round(base["protein_ratio"], 2),
            "score": round(score, 1),
            "reasons": reasons[:3],
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def calories_of(food: FoodItem) -> float:
    return food.calories or 0


# --------------------------------------------------------------------------
# Insights
# --------------------------------------------------------------------------

def build_insights(
    user: User, profile: Dict[str, Any], gap: Dict[str, Any],
    goal: Optional[Goal], weight_change: Optional[float],
) -> List[Dict[str, str]]:
    """
    Observations about this user's own behaviour.

    Each one names the evidence, because an insight the user cannot verify
    reads as filler.
    """
    out: List[Dict[str, str]] = []
    avg = profile.get("daily_average") or {}

    # Protein vs target - the most actionable gap for most goals.
    if goal and goal.target_protein and avg.get("protein"):
        pct = avg["protein"] / goal.target_protein
        if pct < 0.75:
            out.append({
                "kind": "warn",
                "title": "Protein is running low",
                "body": (
                    f"You're averaging {avg['protein']}g a day against a target of "
                    f"{round(goal.target_protein)}g. That gap matters most if you want to "
                    f"keep muscle while your weight changes."
                ),
            })
        elif pct >= 0.95:
            out.append({
                "kind": "good",
                "title": "Protein is on point",
                "body": f"You're averaging {avg['protein']}g a day — right around your {round(goal.target_protein)}g target.",
            })

    # Skipped meals.
    if profile.get("often_skipped"):
        slots = ", ".join(profile["often_skipped"])
        out.append({
            "kind": "info",
            "title": f"You rarely log {slots}",
            "body": (
                f"Over {profile['days_active']} active days, {slots} shows up in fewer than "
                "half of them. Either you're skipping it or not logging it — both are worth knowing, "
                "because untracked meals make every other number less reliable."
            ),
        })

    # Variety.
    v = profile.get("variety", {})
    if v.get("in_a_rut"):
        out.append({
            "kind": "info",
            "title": "Your meals are repeating",
            "body": (
                f"{v['distinct_foods']} different foods across {v['total_logs']} logs. "
                "Nothing wrong with that, but rotating in a few new items usually widens your "
                "micronutrient coverage."
            ),
        })
    elif v.get("distinct_foods", 0) >= 10:
        out.append({
            "kind": "good",
            "title": "Good variety",
            "body": f"{v['distinct_foods']} different foods logged — that spread tends to cover micronutrients well.",
        })

    # Budget.
    b = profile.get("budget")
    if b:
        out.append({
            "kind": "info",
            "title": f"You spend about ₹{b['median_per_item']} per item",
            "body": (
                f"Suggestions below stay near that, up to about ₹{b['comfortable_ceiling']}, "
                "rather than recommending things you'd skip on price."
            ),
        })

    # Weight trend vs goal direction.
    if weight_change is not None and goal and abs(weight_change) >= 0.3:
        losing = weight_change < 0
        wants_loss = "loss" in (goal.goal_type or "")
        wants_gain = "gain" in (goal.goal_type or "")
        if (losing and wants_loss) or (not losing and wants_gain):
            out.append({
                "kind": "good",
                "title": "Moving the right way",
                "body": f"{abs(weight_change):.1f} kg {'down' if losing else 'up'} — consistent with your goal.",
            })
        elif wants_loss or wants_gain:
            out.append({
                "kind": "warn",
                "title": "Trend doesn't match your goal",
                "body": (
                    f"You're {abs(weight_change):.1f} kg {'down' if losing else 'up'}, but your goal is to "
                    f"{'lose' if wants_loss else 'gain'}. Worth checking whether your logging is complete "
                    "before changing anything — a few unlogged meals explain most surprises."
                ),
            })

    # Vegetarian inference.
    if profile.get("vegetarian") and profile.get("vegetarian_source") == "none of your logged meals contain meat or fish":
        out.append({
            "kind": "info",
            "title": "Treating you as vegetarian",
            "body": "None of your logged meals contain meat or fish, so suggestions stay vegetarian. Change it in your profile if that's wrong.",
        })

    return out


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def personalised_feed(user: User, db: Session) -> Dict[str, Any]:
    """Everything the For You page needs, in one call."""
    goal = (
        db.query(Goal)
        .filter(Goal.user_id == user.id, Goal.is_active == True)  # noqa: E712
        .order_by(Goal.created_at.desc())
        .first()
    )

    profile = build_profile(user, db)  # wide window - see build_profile
    gap = todays_gap(user, db, goal)

    weights = (
        db.query(WeightLog)
        .filter(WeightLog.user_id == user.id)
        .order_by(WeightLog.logged_at.asc())
        .all()
    )
    weight_change = (
        weights[-1].weight_kg - weights[0].weight_kg if len(weights) > 1 else None
    )

    recommendations = recommend_foods(
        user, db, profile, gap,
        goal_type=goal.goal_type if goal else None,
        limit=8,
    )
    insights = build_insights(user, profile, gap, goal, weight_change)

    # Be explicit when there is not enough history to personalise properly,
    # rather than dressing up generic output as tailored.
    confidence = (
        "high" if profile["log_count"] >= 15
        else "medium" if profile["log_count"] >= 5
        else "low"
    )

    return {
        "profile": profile,
        "today": gap,
        "goal": {
            "type": goal.goal_type if goal else None,
            "target_calories": goal.target_calories if goal else None,
            "target_protein": goal.target_protein if goal else None,
        } if goal else None,
        "recommendations": recommendations,
        "insights": insights,
        "confidence": confidence,
        "weight_change_kg": round(weight_change, 1) if weight_change is not None else None,
    }
