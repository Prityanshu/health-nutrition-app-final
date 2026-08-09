"""
What macros should this particular meal hit?

The generators produce food that is authentic, quick and within budget, and
have never known a single one of the user's numbers. So somebody on a 150g
protein target could ask for a full day of Kerala food and get three rice
dishes totalling 40g, which is a perfectly good meal plan and the wrong one.

Two modes, because they answer different questions:

    daily      the whole day's targets, split across the meals being asked for
    remaining  what is LEFT today after everything already logged

`remaining` is the one people actually want at 8pm - "I have 600 kcal and 70g
of protein left, feed me". Before anything is logged the two are the same
thing, so it falls back to `daily` and says so.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database import MealLog, User
from app.services import adherence, daytime

logger = logging.getLogger(__name__)

# How a day's targets divide across meals. Not equal thirds: breakfast is
# reliably the smallest meal of the day and dinner the largest, and splitting
# evenly produces a 700 kcal breakfast nobody will cook.
MEAL_SHARE = {
    "breakfast": 0.25,
    "lunch": 0.35,
    "dinner": 0.30,
    "snack": 0.10,
    "full_day": 1.0,
}

MACROS = ("calories", "protein", "carbs", "fat")

# How far outside each target still counts as hitting it. All four are
# enforced; the numbers differ because the macros behave differently, not
# because any of them is optional.
CALORIE_TOLERANCE = 0.10       # tightest - it is the sum of the other three
MACRO_TOLERANCE = 0.20         # carbs and fat, which trade against each other
PROTEIN_UNDER_TOLERANCE = 0.10  # under target by more than this is a miss
PROTEIN_OVER_TOLERANCE = 1.00   # over is never a problem

UNITS = {"calories": "kcal", "protein": "g", "carbs": "g", "fat": "g"}


@dataclass
class MacroTarget:
    """What one generated meal or plan should add up to."""
    calories: float
    protein: float
    carbs: float
    fat: float
    basis: str            # daily | remaining
    meal_type: str
    share: float
    # Set when `remaining` was asked for but nothing had been logged yet.
    fell_back: bool = False

    def as_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        for macro in MACROS:
            out[macro] = round(out[macro])
        return out

    @property
    def usable(self) -> bool:
        """Below this there is nothing sensible to cook toward."""
        return self.calories >= 120

    def describe(self) -> str:
        """One line for the UI."""
        return (f"{self.calories:.0f} kcal · {self.protein:.0f}g protein · "
                f"{self.carbs:.0f}g carbs · {self.fat:.0f}g fat")

    def bounds(self) -> Dict[str, tuple]:
        """
        The acceptable range for each macro.

        All four are binding. An earlier version called protein "the one that
        matters most" and gave the rest a soft percentage, which is wrong on
        the nutrition and wrong on the engineering: a plan that nails protein
        and lands 700 kcal over has not hit the target, it has hit a quarter of
        it. Carbs and fat are what the calorie number is actually made of.

        The tolerances differ because the macros do, not because some matter
        less:
          calories  tightest - it is the sum, so it constrains everything
          protein   asymmetric - over is fine, under is the failure
          carbs/fat wider - they trade against each other within a calorie
                    budget, so being at the edge of one is usually fine if the
                    other compensates
        """
        return {
            "calories": (self.calories * (1 - CALORIE_TOLERANCE),
                         self.calories * (1 + CALORIE_TOLERANCE)),
            # No upper bound in practice, but a number is needed for reporting.
            "protein": (self.protein * (1 - PROTEIN_UNDER_TOLERANCE),
                        self.protein * (1 + PROTEIN_OVER_TOLERANCE)),
            "carbs": (self.carbs * (1 - MACRO_TOLERANCE),
                      self.carbs * (1 + MACRO_TOLERANCE)),
            "fat": (self.fat * (1 - MACRO_TOLERANCE),
                    self.fat * (1 + MACRO_TOLERANCE)),
        }

    def prompt_block(self, per_day: bool = False, structured: bool = False) -> str:
        """
        The instruction handed to the generator.

        Every macro gets an explicit low-high range in grams rather than a
        percentage the model has to compute. Percentages get rounded, ignored,
        or applied to the wrong base; a bare pair of numbers cannot be.

        `per_day` is for the 7-day planner: the target applies to EVERY day,
        not to the week as a whole. Without saying so the model averages -
        three 3000 kcal days and four 1200 kcal ones hit the weekly mean and
        are useless as a plan.

        `structured` suits generators that already return JSON with per-meal
        macros. The numbers are then checkable by summing fields rather than
        parsing prose, so the free-text TOTAL line is unnecessary.
        """
        low = {m: v[0] for m, v in self.bounds().items()}
        high = {m: v[1] for m, v in self.bounds().items()}
        what = "plan" if self.meal_type == "full_day" else "recipe"
        scope = "EVERY SINGLE DAY of the plan" if per_day else f"The complete {what}"

        window = (
            f"NUTRITIONAL TARGET - this is a hard requirement, not a preference.\n"
            f"            {scope} must total ALL FOUR of these. "
            f"Missing any one of them means the {what} is wrong:\n"
            f"            - Calories: {low['calories']:.0f}-{high['calories']:.0f} kcal "
            f"(aim for {self.calories:.0f})\n"
            f"            - Protein:  at least {low['protein']:.0f} g "
            f"(aim for {self.protein:.0f} g; more than this is fine)\n"
            f"            - Carbs:    {low['carbs']:.0f}-{high['carbs']:.0f} g "
            f"(aim for {self.carbs:.0f})\n"
            f"            - Fat:      {low['fat']:.0f}-{high['fat']:.0f} g "
            f"(aim for {self.fat:.0f})\n"
        )
        rules = (
            "\n            How to hit them:\n"
            "            - Adjust PORTION SIZES first. Specify exact quantities in grams "
            "or standard measures for every ingredient, because a portion is what turns "
            "an authentic dish into one that fits.\n"
            "            - Choose which dishes to include based on what the numbers need: "
            "a carb-heavy cuisine still has lentil, dairy, egg, fish and meat dishes.\n"
            "            - Carbs and fat trade against each other inside the calorie "
            "budget. If one is running high, bring the other down rather than blowing "
            "the calorie total.\n"
            "            - Keep it authentic. Do not invent dishes that do not belong to "
            "the cuisine, and do not reach the protein number with a protein shake.\n"
        )

        if per_day:
            # The failure this prevents: averaging. Three 3000 kcal days and
            # four 1200 kcal days hit the weekly mean perfectly and are not a
            # usable plan for any single day.
            rules += (
                "            - Every day stands alone. Do NOT average across the week - "
                "a day outside these ranges is wrong even if the weekly mean is right.\n"
            )

        if structured:
            rules += (
                "\n            The macros object on every meal must be your real "
                "calculation for that meal, and the meals in each day must sum to the "
                "ranges above. These fields are checked against the target after "
                "generation, so a number you did not compute will be caught.\n"
            )
        else:
            rules += (
                "\n            REQUIRED FORMAT: state calories, protein, carbs and fat "
                "for EVERY dish, then finish with a line reading exactly:\n"
                "            TOTAL: <n> kcal, <n>g protein, <n>g carbs, <n>g fat\n"
                "            Add up your own numbers and check them against the ranges "
                "above before you finish. If a total is outside its range, change the "
                "portions and recompute rather than stating a number you did not "
                "calculate.\n"
            )

        if self.basis == "remaining":
            rules += ("\n            These are what remains of their targets for TODAY "
                      "after what they have already eaten, so this completes the day.\n")
        return window + rules


def _share_for(meal_type: Optional[str]) -> float:
    return MEAL_SHARE.get((meal_type or "full_day").lower(), 1.0)


def resolve(db: Session, user: User, meal_type: str = "full_day",
            basis: str = "daily") -> Optional[MacroTarget]:
    """
    The macro target for this request, or None when there is nothing to aim at.

    Returns None rather than inventing defaults: a plan built toward made-up
    numbers is worse than one built toward none, because it looks personalised.
    """
    goal = adherence.active_goal(db, user.id)
    if not goal or not goal.target_calories:
        return None

    share = _share_for(meal_type)
    targets = {
        "calories": goal.target_calories or 0,
        "protein": goal.target_protein or 0,
        "carbs": goal.target_carbs or 0,
        "fat": goal.target_fat or 0,
    }

    fell_back = False
    if basis == "remaining":
        tz = daytime.zone_for(user)
        start, end = daytime.today_bounds(tz=tz)
        eaten_rows = (
            db.query(MealLog)
            .filter(MealLog.user_id == user.id,
                    MealLog.logged_at >= start, MealLog.logged_at < end)
            .all()
        )
        if not eaten_rows:
            # Nothing logged yet, so nothing has been used up and "remaining"
            # is the whole day - which then splits by meal type exactly like
            # `daily`. It does NOT mean serving 2000 kcal as one dinner.
            # Flagged so the UI can say why the two modes look identical
            # rather than leaving it looking broken.
            fell_back = True
            basis = "daily"
        else:
            eaten = {
                "calories": sum(r.calories or 0 for r in eaten_rows),
                "protein": sum(r.protein or 0 for r in eaten_rows),
                "carbs": sum(r.carbs or 0 for r in eaten_rows),
                "fat": sum(r.fat or 0 for r in eaten_rows),
            }
            # Floor at zero. A negative target is not a smaller meal, it is a
            # nonsense instruction that produces nonsense output.
            targets = {m: max(0.0, targets[m] - eaten[m]) for m in MACROS}
            # Already over: there is no meal that helps, so the caller should
            # say so rather than generating a 0 kcal recipe.
            share = 1.0

    return MacroTarget(
        calories=targets["calories"] * share,
        protein=targets["protein"] * share,
        carbs=targets["carbs"] * share,
        fat=targets["fat"] * share,
        basis=basis,
        meal_type=meal_type or "full_day",
        share=share,
        fell_back=fell_back,
    )


def preview(db: Session, user: User) -> Dict[str, Any]:
    """
    What each mode would target right now, for the mode picker.

    Shown before generating so personalisation is never applied invisibly -
    the same principle the meal planner uses.
    """
    goal = adherence.active_goal(db, user.id)
    if not goal or not goal.target_calories:
        return {"has_goal": False}

    out: Dict[str, Any] = {"has_goal": True, "meals": {}}
    for meal_type in ("full_day", "breakfast", "lunch", "dinner", "snack"):
        target = resolve(db, user, meal_type=meal_type, basis="daily")
        if target:
            out["meals"][meal_type] = target.as_dict()

    remaining = resolve(db, user, meal_type="full_day", basis="remaining")
    if remaining:
        out["remaining"] = remaining.as_dict()
        out["remaining"]["usable"] = remaining.usable
    return out


# ---------------------------------------------------------------------------
# verification
# ---------------------------------------------------------------------------
#
# Asking a model to hit four numbers and assuming it did is not a feature, it
# is a hope. These read the totals back out of the generated text and check
# them, so the UI can say "protein came in 30g under" instead of implying
# everything worked.

_NUMBER = r"(\d[\d,]*(?:\.\d+)?)"

# The format explicitly requested. Tried first because it is unambiguous.
_TOTAL_LINE = re.compile(
    rf"total\s*:?\s*{_NUMBER}\s*(?:k?cal|calories)\b[^\n]*?"
    rf"{_NUMBER}\s*g\s*protein[^\n]*?"
    rf"{_NUMBER}\s*g\s*carb[^\n]*?"
    rf"{_NUMBER}\s*g\s*fat",
    re.I,
)

# Fallback: a labelled figure anywhere on a line that mentions a total. Models
# reformat the requested line into tables and bullet lists constantly, so
# insisting on the exact shape would report "unverifiable" most of the time.
_LABELLED = {
    # Both orders. "690 kcal" and "Calories: 690" are equally common and an
    # earlier version only matched the first, so any plan using the second
    # form reported as unverifiable.
    "calories": re.compile(
        rf"(?:{_NUMBER}\s*(?:k?cal|calories)\b|(?:calories|energy)\D{{0,12}}{_NUMBER})", re.I),
    "protein": re.compile(rf"(?:protein\D{{0,12}}{_NUMBER}\s*g|{_NUMBER}\s*g\s*(?:of\s*)?protein)", re.I),
    "carbs": re.compile(rf"(?:carb\w*\D{{0,12}}{_NUMBER}\s*g|{_NUMBER}\s*g\s*(?:of\s*)?carb)", re.I),
    "fat": re.compile(rf"(?:fat\D{{0,12}}{_NUMBER}\s*g|{_NUMBER}\s*g\s*(?:of\s*)?fat)", re.I),
}

_TOTAL_HINT = re.compile(r"\btotal|\bsum\b|\bdaily total|\bgrand total|\bfor the day\b", re.I)


def _to_float(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    try:
        return float(raw.replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_totals(text: str) -> Optional[Dict[str, float]]:
    """
    Pull the stated totals out of a generated plan.

    Returns None when they cannot be found, which is different from finding
    zeros - "we could not check" and "it scored zero" must never be conflated,
    because one is a parser problem and the other is a food problem.
    """
    if not text:
        return None

    match = _TOTAL_LINE.search(text)
    if match:
        values = [_to_float(g) for g in match.groups()]
        if all(v is not None for v in values):
            return dict(zip(("calories", "protein", "carbs", "fat"), values))

    # Search lines that look like a total, last first: the summary is at the
    # end, and an early per-dish line would otherwise be mistaken for it.
    for line in reversed([l for l in text.splitlines() if _TOTAL_HINT.search(l)]):
        found = {}
        for macro, pattern in _LABELLED.items():
            hit = pattern.search(line)
            if hit:
                value = next((_to_float(g) for g in hit.groups() if g), None)
                if value is not None:
                    found[macro] = value
        if len(found) == 4:
            return found
    return None


def verify(target: "MacroTarget", text: str) -> Dict[str, Any]:
    """
    Did the generated plan actually hit the target, macro by macro?

    Reported per macro rather than as one verdict. "It missed" is not
    actionable; "carbs came in 60g over, everything else landed" tells you what
    to change - and tells the regeneration what to say.
    """
    stated = parse_totals(text)
    if not stated:
        return {
            "checked": False,
            "reason": "Could not find stated totals in the plan.",
            "macros": {},
        }

    bounds = target.bounds()
    macros: Dict[str, Any] = {}
    for macro in MACROS:
        low, high = bounds[macro]
        value = stated[macro]
        aim = getattr(target, macro)
        if value < low:
            status, delta = "under", value - low
        elif value > high:
            status, delta = "over", value - high
        else:
            status, delta = "on_target", 0.0
        macros[macro] = {
            "stated": round(value),
            "target": round(aim),
            "low": round(low),
            "high": round(high),
            "status": status,
            "delta": round(delta),
            "unit": UNITS[macro],
        }

    missed = [m for m, r in macros.items() if r["status"] != "on_target"]
    return {
        "checked": True,
        "hit": not missed,
        "missed": missed,
        "macros": macros,
        "summary": _verify_summary(macros, missed),
    }


def _verify_summary(macros: Dict[str, Any], missed: list) -> str:
    if not missed:
        return "Every macro landed inside its range."
    parts = [
        f"{m} {abs(macros[m]['delta']):.0f}{macros[m]['unit']} {macros[m]['status'].replace('_', ' ')}"
        for m in missed
    ]
    return "Off target on " + ", ".join(parts) + "."


def retry_brief(verification: Dict[str, Any], target: "MacroTarget") -> str:
    """
    What to tell the model on a second attempt.

    Names the specific misses and the direction, because "try again" produces
    a differently wrong answer at the same cost.
    """
    lines = ["Your previous version did not meet the nutritional target. Fix these:"]
    for macro in verification.get("missed", []):
        result = verification["macros"][macro]
        direction = "too low" if result["status"] == "under" else "too high"
        lines.append(
            f"            - {macro}: you had {result['stated']}{result['unit']}, which is "
            f"{direction}. It must be between {result['low']} and {result['high']}"
            f"{result['unit']}."
        )
    lines.append("            Keep everything that was already inside its range. "
                 "Change portion sizes and dish choices, then recompute the totals.")
    return "\n            ".join(lines)


def verify_structured(target: "MacroTarget", plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check a 7-day JSON plan by SUMMING its own macro fields.

    Stronger than reading a stated total out of prose, because it uses the
    numbers the plan is actually made of. A model that writes "TOTAL: 2200
    kcal" under meals adding to 1400 passes a text check and fails this one.

    Judged per day, then rolled up. A weekly average hides exactly the failure
    that matters - three enormous days and four tiny ones average correctly and
    are unusable.
    """
    days = (plan or {}).get("plan") or {}
    if not isinstance(days, dict) or not days:
        return {"checked": False, "reason": "No days found in the plan.", "days": []}

    bounds = target.bounds()
    per_day: List[Dict[str, Any]] = []

    for name in sorted(days.keys()):
        meals = days.get(name) or []
        if not isinstance(meals, list) or not meals:
            continue

        totals = {m: 0.0 for m in MACROS}
        for meal in meals:
            macros = (meal or {}).get("macros") or {}
            totals["calories"] += _num(macros.get("calories"))
            totals["protein"] += _num(macros.get("protein_g", macros.get("protein")))
            totals["carbs"] += _num(macros.get("carbs_g", macros.get("carbs")))
            totals["fat"] += _num(macros.get("fat_g", macros.get("fat")))

        result = {"day": name, "meals": len(meals), "macros": {}}
        for macro in MACROS:
            low, high = bounds[macro]
            value = totals[macro]
            if value < low:
                status, delta = "under", value - low
            elif value > high:
                status, delta = "over", value - high
            else:
                status, delta = "on_target", 0.0
            result["macros"][macro] = {
                "total": round(value), "target": round(getattr(target, macro)),
                "low": round(low), "high": round(high),
                "status": status, "delta": round(delta), "unit": UNITS[macro],
            }
        result["missed"] = [m for m, r in result["macros"].items()
                            if r["status"] != "on_target"]
        result["hit"] = not result["missed"]
        per_day.append(result)

    if not per_day:
        return {"checked": False, "reason": "No meals with macros found.", "days": []}

    hits = [d for d in per_day if d["hit"]]
    # Which macro fails most often across the week - what a retry should fix.
    tally: Dict[str, int] = {}
    for day in per_day:
        for macro in day["missed"]:
            tally[macro] = tally.get(macro, 0) + 1
    worst = sorted(tally.items(), key=lambda kv: -kv[1])

    return {
        "checked": True,
        "hit": len(hits) == len(per_day),
        "days_on_target": len(hits),
        "days_total": len(per_day),
        "days": per_day,
        "weakest": [{"macro": m, "days": n} for m, n in worst],
        "summary": (
            f"All {len(per_day)} days inside every range."
            if len(hits) == len(per_day)
            else f"{len(hits)} of {len(per_day)} days hit every macro"
                 + (f"; {worst[0][0]} was off on {worst[0][1]}." if worst else ".")
        ),
    }


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def retry_brief_structured(verification: Dict[str, Any], target: "MacroTarget") -> str:
    """What to fix on a second attempt at a 7-day plan."""
    lines = ["Several days did not meet the nutritional target. Fix these days only, "
             "and leave the days that were already correct exactly as they are:"]
    for day in verification.get("days", []):
        if day["hit"]:
            continue
        parts = []
        for macro in day["missed"]:
            result = day["macros"][macro]
            direction = "too low" if result["status"] == "under" else "too high"
            parts.append(
                f"{macro} {result['total']}{result['unit']} is {direction} "
                f"(needs {result['low']}-{result['high']})"
            )
        lines.append(f"            - {day['day']}: " + "; ".join(parts))
    lines.append("            Change portion sizes and swap dishes, then recompute the "
                 "macros object for every meal you touch.")
    return "\n            ".join(lines)
