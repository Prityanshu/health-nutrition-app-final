"""
What a valid 7-day meal plan IS, deterministically.

WHY THIS EXISTS
---------------
The planner used to treat "the model returned parseable JSON" as "the model
returned a meal plan". `[]`, `{}`, a single day, seven days with the wrong
number of meals, and meals with no ingredients or macros all came back as
`success: True` and were handed to the frontend.

This module is the one place that decides validity, and both generation and
adaptation go through it. Duplicating any of these checks into either caller
would recreate the original problem in a new place: two definitions of valid
that drift.

THE PIPELINE
------------
    LLM text
      -> extract_json_object()      one JSON object, unambiguously
      -> validate_structure()       the contract below
      -> dietary_rules.audit_plan() forbidden ingredients
      -> verify_calories()          per-day calories actually add up
      -> (macro_targets)            all four macros, when strict mode is on
      -> PlanCandidate              scored, comparable, fail-closed
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.services import dietary_rules

# The plan is always a week. Not configurable: the schema, the prompt and the
# frontend all assume seven, and "however many days the model felt like" was
# one of the bugs.
REQUIRED_DAYS = tuple(f"day_{n}" for n in range(1, 8))

# How far a day's summed calories may sit from the request. Matches
# macro_targets.CALORIE_TOLERANCE so strict and standard mode do not disagree
# about what "on target" means.
CALORIE_TOLERANCE = 0.10


# ---------------------------------------------------------------------------
# 1. canonical JSON extraction
# ---------------------------------------------------------------------------

EMPTY = "empty"
MALFORMED = "malformed"
TRUNCATED = "truncated"
NOT_OBJECT = "not_object"
AMBIGUOUS = "ambiguous"

_FENCE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n?|\n?\s*```\s*$")

_ROOT_OBJECT_RULE = (
    "  - Return exactly ONE JSON object as the entire response.\n"
    "  - Put meta, plan (containing day_1 through day_7) and summary inside "
    "that SAME root object.\n"
    "  - Do NOT emit one object per day or per meal, and do NOT emit "
    "JSON Lines (one object per line).\n"
    "  - Do NOT include an example or partial object before the real one.\n"
    "  - Do NOT re-send fragments or patches of the previous attempt; write "
    "the whole plan again from scratch."
)

_FORMAT_BRIEF_GENERIC = (
    "Fix the output format:\n" + _ROOT_OBJECT_RULE +
    "\n  - No commentary and no Markdown code fences around the JSON."
)

_FORMAT_BRIEFS = {
    TRUNCATED: (
        "The response stopped mid-way, so the JSON never closed. This is a "
        "LENGTH problem, not a structure problem:\n"
        "  - Keep every field, but write compactly - short recipe_name "
        "values, no prose notes, no whitespace padding.\n"
        "  - Do not add optional fields beyond the schema.\n"
        "  - Close every brace and bracket; the last character of your "
        "response must be the closing brace of the root object.\n"
        + _ROOT_OBJECT_RULE
    ),
    MALFORMED: (
        "The JSON is invalid. Most often this is a trailing comma before a "
        "closing brace or bracket, a single-quoted string, an unquoted key, "
        "or a comment:\n"
        "  - Use double quotes for every key and string value.\n"
        "  - No trailing comma after the last item of any object or array.\n"
        "  - No comments, no NaN, no Infinity.\n"
        + _ROOT_OBJECT_RULE
    ),
    AMBIGUOUS: (
        "Several separate top-level JSON objects arrived, so there was no "
        "single answer to use:\n" + _ROOT_OBJECT_RULE
    ),
    NOT_OBJECT: (
        "The top level was the wrong JSON type. An array of days is not "
        "accepted - the days belong under the 'plan' key of one root "
        "object:\n" + _ROOT_OBJECT_RULE
    ),
    EMPTY: (
        "The response was empty. Return the plan itself, not an "
        "acknowledgement:\n" + _ROOT_OBJECT_RULE
    ),
}

_TRUNCATED_MESSAGE = (
    "The plan was cut off before it finished. This happens when the week is "
    "too large to generate in one go - try fewer meals per day, then add "
    "snacks separately."
)


def strip_code_fences(text: str) -> str:
    """Remove a surrounding markdown fence, if present."""
    if not text:
        return ""
    cleaned = str(text).strip()
    if cleaned.startswith("```"):
        newline = cleaned.find("\n")
        cleaned = cleaned[newline + 1:] if newline != -1 else cleaned[3:]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    return cleaned.strip()


def _top_level_starts(text: str, respect_strings: bool = True
                      ) -> Tuple[List[int], List[int], bool]:
    """
    Positions of `{` and `[` that open a TOP-LEVEL value, plus whether the
    text ended before its structure closed.

    This is a lexer, not a parser: it tracks nesting depth and (by default)
    string literals with their escapes, and reports only the openers found at
    depth 0. raw_decode still does all real parsing - this decides only WHERE
    a top-level value could start.

    Why it is needed: the previous version treated every `{` in the response
    as a candidate start. That is correct only while the enclosing object
    decodes, because a successful decode skipped its own interior. The moment
    the outer object failed - one trailing comma, one truncation - the scan
    fell INTO it and reported each nested day/meal/macro dictionary as a
    separate top-level answer. A single malformed plan came back as "19
    separate JSON objects". Depth is what distinguishes "the model sent two
    plans" from "the model sent one broken plan"; nothing else can.

    An unbalanced opener leaves depth above 0 for the rest of the text, which
    is exactly right: everything after a truncated root IS inside it.
    """
    objects: List[int] = []
    arrays: List[int] = []
    depth = 0
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if respect_strings and char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                objects.append(index)
            depth += 1
        elif char == "[":
            if depth == 0:
                arrays.append(index)
            depth += 1
        elif char in "}]":
            depth = max(0, depth - 1)

    # Ending at depth > 0, or inside an unterminated string, means the text
    # stopped before its structure closed. That is a deterministic truncation
    # signal - far sounder than matching decoder error strings, because a
    # response cut mid-string reports the error at the string's START, which
    # is nowhere near the end of the text.
    return objects, arrays, depth > 0 or in_string


def _decode_at(cleaned: str, starts: List[int]) -> Tuple[List[dict], Optional[json.JSONDecodeError]]:
    """Decode each candidate start; return the objects and the first error."""
    decoder = json.JSONDecoder()
    found: List[dict] = []
    first_error: Optional[json.JSONDecodeError] = None
    for position in starts:
        try:
            value, _end = decoder.raw_decode(cleaned, position)
        except json.JSONDecodeError as exc:
            if first_error is None:
                first_error = exc
            continue
        if isinstance(value, dict):
            found.append(value)
    return found, first_error


def extract_json_object(text: Any, meals_per_day: Optional[int] = None
                        ) -> Tuple[Optional[dict], Optional[str], str]:
    """
    Pull exactly one JSON OBJECT out of a model response.

    Returns (object, error_code, message). Exactly one of object/error_code is
    set.

    Only TOP-LEVEL objects are candidates (see `_top_level_starts`). Nested
    day, meal, macro and ingredient dictionaries are never candidates, so a
    malformed or truncated plan is diagnosed as malformed or truncated rather
    than mistaken for a pile of competing answers.

    Prose either side of one complete object is tolerated, because models
    routinely add "Here is your plan:".

    When several genuine top-level objects arrive, the choice is never made on
    position or size - "first" and "largest" are arbitrary rules that silently
    discard half the response. If `meals_per_day` is supplied, the canonical
    structural validator is asked which of them is a complete week; a single
    complete plan beside example or metadata objects is then recoverable
    without spending a generation. Two complete plans stay AMBIGUOUS, because
    at that point the model really did send two answers and picking one would
    be a guess. Without `meals_per_day` no selection is attempted at all.
    """
    cleaned = strip_code_fences(text)
    if not cleaned:
        return None, EMPTY, "The model returned nothing."

    starts, arrays, unclosed = _top_level_starts(cleaned)
    if not starts and "{" in cleaned:
        # Prose containing an odd number of quote characters can desynchronise
        # the string tracker and hide a perfectly good object. Rescan ignoring
        # quotes; depth still prevents descending into nested fragments, so
        # this can only ever recover candidates, never invent extra ones.
        starts, arrays, unclosed = _top_level_starts(cleaned, respect_strings=False)

    if not starts:
        # No top-level object anywhere. If the whole thing is valid JSON of
        # another shape, say so precisely - "[]" is a different bug from
        # "hello", and an array of days is a different bug from either.
        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError:
            if arrays and unclosed:
                return None, TRUNCATED, _TRUNCATED_MESSAGE
            return None, MALFORMED, "The model did not return JSON."
        return None, NOT_OBJECT, (
            f"Expected a JSON object, got {type(value).__name__}."
        )

    found, first_error = _decode_at(cleaned, starts)

    if not found:
        # Truncated vs malformed: a response cut off mid-generation ends with
        # its structure still open, while genuinely broken JSON - a trailing
        # comma, a bare word - closes properly and fails somewhere inside.
        # The two need different advice: one is "the week was too big", the
        # other is "the model wrote invalid JSON". Both diagnoses were
        # unreachable before, because some nested fragment always decoded and
        # turned the whole thing into AMBIGUOUS.
        if unclosed or (first_error is not None
                        and first_error.pos >= len(cleaned) - 2):
            return None, TRUNCATED, _TRUNCATED_MESSAGE
        detail = f" ({first_error.msg})" if first_error else ""
        return None, MALFORMED, f"Could not parse the model's JSON{detail}."

    if len(found) == 1:
        return found[0], None, ""

    if meals_per_day:
        complete = [obj for obj in found
                    if validate_structure(obj, meals_per_day).ok]
        if len(complete) == 1:
            return complete[0], None, ""
        if len(complete) > 1:
            return None, AMBIGUOUS, (
                f"The model returned {len(complete)} complete 7-day plans; "
                f"refusing to guess which one to use."
            )

    return None, AMBIGUOUS, (
        f"The model returned {len(found)} separate top-level JSON objects and "
        f"none of them is a complete 7-day plan on its own."
        if meals_per_day else
        f"The model returned {len(found)} separate top-level JSON objects; "
        f"refusing to guess which one is the plan."
    )


# ---------------------------------------------------------------------------
# 2. structural contract
# ---------------------------------------------------------------------------

def _finite_number(value: Any, field_name: str) -> float:
    """
    A real, finite, non-boolean number.

    `bool` is explicitly rejected even though it is an int subclass in Python:
    `{"calories": true}` would otherwise validate as 1 kcal, which is not a
    parse of anything the model meant.

    Numeric STRINGS are accepted and coerced - models emit "350" constantly
    and the value is unambiguous - but a non-numeric string is a hard error.
    NaN and Infinity are rejected explicitly because json.loads accepts both
    by default, and they poison every downstream sum silently.
    """
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number, got a boolean")
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be a number, got {value!r}")
    if not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number, got "
                         f"{type(value).__name__}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be a finite number")
    return number


def _non_negative(value: Any, field_name: str) -> float:
    number = _finite_number(value, field_name)
    if number < 0:
        raise ValueError(f"{field_name} must not be negative")
    return number


class Macros(BaseModel):
    model_config = ConfigDict(extra="allow")

    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float

    @field_validator("calories", "protein_g", "carbs_g", "fat_g", mode="before")
    @classmethod
    def _check(cls, value, info):
        return _non_negative(value, info.field_name)


class Ingredient(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    # Required, not optional. A plan whose ingredients carry no quantities is
    # not actionable: there is no portion basis behind the macros, the
    # shopping list cannot be built, and the numbers become unfalsifiable
    # assertions. The schema has always advertised qty; it simply was not
    # enforced, and the test fixtures quietly omitted it.
    qty: str
    est_cost: Optional[float] = None

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, value):
        if value is None or not str(value).strip():
            raise ValueError("ingredient name must not be empty")
        return str(value).strip()

    @field_validator("qty", mode="before")
    @classmethod
    def _qty(cls, value):
        if value is None or not str(value).strip():
            raise ValueError("ingredient qty must not be empty "
                             "(e.g. '80g', '1 cup')")
        return str(value).strip()

    @field_validator("est_cost", mode="before")
    @classmethod
    def _cost(cls, value):
        if value is None or value == "":
            return None
        return _non_negative(value, "est_cost")


class Meal(BaseModel):
    model_config = ConfigDict(extra="allow")

    meal_label: str
    recipe_name: str
    ingredients: List[Ingredient] = Field(min_length=1)
    macros: Macros
    prep_time_min: Optional[float] = None

    @field_validator("meal_label", "recipe_name", mode="before")
    @classmethod
    def _text(cls, value, info):
        if value is None or not str(value).strip():
            raise ValueError(f"{info.field_name} must not be empty")
        return str(value).strip()

    @field_validator("prep_time_min", mode="before")
    @classmethod
    def _prep(cls, value):
        if value is None or value == "":
            return None
        return _non_negative(value, "prep_time_min")


@dataclass
class StructureResult:
    ok: bool
    errors: List[str] = field(default_factory=list)
    days: int = 0
    meals: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "errors": list(self.errors),
                "days": self.days, "meals": self.meals}


def _describe(error: Dict[str, Any]) -> str:
    location = ".".join(str(part) for part in error.get("loc", ()))
    message = error.get("msg", "invalid")
    message = message.replace("Value error, ", "")
    return f"{location}: {message}" if location else message


def validate_structure(plan: Any, meals_per_day: int) -> StructureResult:
    """
    Does this object actually describe a usable week?

    Everything here is a hard requirement, because each one has been observed
    passing as success: an empty object, a one-day plan, a week missing day_4,
    a stray day_8, days with the wrong number of meals, and meals with no
    ingredients or no macros.

    Unknown extra fields are allowed throughout - the model adds "notes",
    "make_ahead" and "tags" freely, and rejecting a plan for being MORE
    informative than the schema would be brittle for no safety gain.
    """
    errors: List[str] = []

    if not isinstance(plan, dict):
        return StructureResult(False, [f"top level must be a JSON object, got "
                                       f"{type(plan).__name__}"])
    if not plan:
        return StructureResult(False, ["the plan object is empty"])

    for key in ("meta", "plan", "summary"):
        value = plan.get(key)
        if value is None:
            errors.append(f"missing required top-level key {key!r}")
        elif not isinstance(value, dict):
            errors.append(f"{key!r} must be an object, got "
                          f"{type(value).__name__}")

    days = plan.get("plan")
    if not isinstance(days, dict):
        return StructureResult(False, errors or ["'plan' must be an object"])

    present = set(days.keys())
    missing = [d for d in REQUIRED_DAYS if d not in present]
    unexpected = sorted(present - set(REQUIRED_DAYS))
    if missing:
        errors.append(f"missing day(s): {', '.join(missing)}")
    if unexpected:
        errors.append(f"unexpected day key(s): {', '.join(unexpected)}")

    total_meals = 0
    for day_name in REQUIRED_DAYS:
        if day_name not in present:
            continue
        meals = days.get(day_name)
        if not isinstance(meals, list):
            errors.append(f"{day_name}: must be a list of meals, got "
                          f"{type(meals).__name__}")
            continue
        if not meals:
            errors.append(f"{day_name}: has no meals")
            continue
        if meals_per_day and len(meals) != meals_per_day:
            errors.append(f"{day_name}: has {len(meals)} meals, expected "
                          f"{meals_per_day}")
        for index, meal in enumerate(meals, start=1):
            if not isinstance(meal, dict):
                errors.append(f"{day_name} meal {index}: must be an object, got "
                              f"{type(meal).__name__}")
                continue
            try:
                Meal.model_validate(meal)
            except ValidationError as exc:
                for issue in exc.errors():
                    errors.append(f"{day_name} meal {index}: {_describe(issue)}")
        total_meals += len(meals)

    # Keep the report readable when a plan is broken in many places at once.
    if len(errors) > 24:
        remaining = len(errors) - 24
        errors = errors[:24] + [f"...and {remaining} more structural problems"]

    return StructureResult(ok=not errors, errors=errors,
                           days=len(present & set(REQUIRED_DAYS)),
                           meals=total_meals)


# ---------------------------------------------------------------------------
# 3. calories
# ---------------------------------------------------------------------------

def day_totals(plan: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """
    Per-day macro totals, summed from the meals themselves.

    Never reads meta.total_daily_calories or summary.avg_daily_calories: those
    are numbers the model asserted, and the whole point is to check the plan
    against itself rather than against its own claims.
    """
    out: Dict[str, Dict[str, float]] = {}
    days = (plan or {}).get("plan") or {}
    if not isinstance(days, dict):
        return out
    for day_name, meals in days.items():
        if not isinstance(meals, list):
            continue
        totals = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
        for meal in meals:
            if not isinstance(meal, dict):
                continue
            macros = meal.get("macros")
            if not isinstance(macros, dict):
                continue
            totals["calories"] += _safe(macros.get("calories"))
            totals["protein"] += _safe(macros.get("protein_g", macros.get("protein")))
            totals["carbs"] += _safe(macros.get("carbs_g", macros.get("carbs")))
            totals["fat"] += _safe(macros.get("fat_g", macros.get("fat")))
        out[day_name] = totals
    return out


def _safe(value: Any) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def verify_calories(plan: Dict[str, Any], target_calories: Optional[float],
                    tolerance: float = CALORIE_TOLERANCE) -> Dict[str, Any]:
    """
    Did each day actually land near the requested calories?

    Runs whether or not strict macro mode is on. target_calories is a required
    field on the request, so a standard plan asking for 2000 kcal and
    returning 500 kcal days was previously never checked at all - the calorie
    number the user typed had no effect on anything.
    """
    if not target_calories or target_calories <= 0:
        return {"checked": False, "reason": "No target calories supplied.",
                "days": []}

    totals = day_totals(plan)
    if not totals:
        return {"checked": False, "reason": "No days with macros to total.",
                "days": []}

    low = target_calories * (1 - tolerance)
    high = target_calories * (1 + tolerance)
    days: List[Dict[str, Any]] = []
    for day_name in sorted(totals):
        value = totals[day_name]["calories"]
        if value < low:
            status, delta = "under", value - low
        elif value > high:
            status, delta = "over", value - high
        else:
            status, delta = "on_target", 0.0
        days.append({
            "day": day_name, "total": round(value), "target": round(target_calories),
            "low": round(low), "high": round(high), "status": status,
            "delta": round(delta), "unit": "kcal",
        })

    off = [d for d in days if d["status"] != "on_target"]
    return {
        "checked": True,
        "hit": not off,
        "days_on_target": len(days) - len(off),
        "days_total": len(days),
        "days": days,
        "summary": (f"All {len(days)} days within {tolerance:.0%} of "
                    f"{target_calories:.0f} kcal."
                    if not off else
                    f"{len(days) - len(off)} of {len(days)} days within "
                    f"{tolerance:.0%} of {target_calories:.0f} kcal; worst off by "
                    f"{max(abs(d['delta']) for d in off):.0f} kcal."),
    }


def calorie_distance(calories: Optional[Dict[str, Any]]) -> float:
    """Mean relative calorie miss across the week. 0.0 when on target."""
    if not calories or not calories.get("checked"):
        return 0.0
    days = calories.get("days") or []
    if not days:
        return 0.0
    total = 0.0
    for day in days:
        target = day.get("target") or 0
        if target:
            total += abs(day.get("delta") or 0) / target
    return total / len(days)


# ---------------------------------------------------------------------------
# 4. the candidate
# ---------------------------------------------------------------------------

@dataclass
class PlanCandidate:
    """One attempt at a plan, fully assessed and comparable to another."""
    plan: Optional[Dict[str, Any]]
    raw_text: str = ""
    parse_error: Optional[str] = None
    parse_code: Optional[str] = None
    structure: Optional[StructureResult] = None
    dietary: Optional[dietary_rules.DietaryAudit] = None
    calories: Optional[Dict[str, Any]] = None
    macro: Optional[Dict[str, Any]] = None
    retried: bool = False

    @property
    def parsed(self) -> bool:
        return self.plan is not None and self.parse_error is None

    @property
    def structurally_complete(self) -> bool:
        return bool(self.structure and self.structure.ok)

    @property
    def hard_safe(self) -> bool:
        """No explicitly forbidden ingredient. Never traded against macros."""
        return self.dietary is None or self.dietary.hard_safe

    @property
    def usable(self) -> bool:
        """
        The gate for returning success at all.

        Structural completeness and hard dietary safety, both required. Macro
        and calorie misses are reported honestly rather than blocking - a plan
        that is 200 kcal light is still a plan; a vegan plan containing milk
        is not.
        """
        return self.parsed and self.structurally_complete and self.hard_safe

    @property
    def macro_distance(self) -> float:
        from app.services import macro_targets as mt
        return mt.macro_distance(self.macro)

    @property
    def quality(self) -> float:
        """
        Lower is better. Only meaningful between two usable candidates.

        Sums only the dimensions that were actually REQUESTED. In standard
        (calorie-only) mode `self.macro` is None, and `macro_distance` scores
        an unchecked verification as infinity - deliberately, so a plan we
        could not verify never wins on a score of zero. Adding that
        unconditionally made every standard-mode candidate score `inf`, so
        `better()` could never separate them and the corrective calorie retry
        could never be selected: two model calls, and the 501 kcal first
        attempt returned anyway.

        Macro distance is therefore only part of the score when macro
        matching was asked for. Within one comparison both candidates are
        assessed the same way, so the dimensions stay commensurable.
        """
        total = calorie_distance(self.calories)
        if self.macro is not None:
            total += self.macro_distance
        return total

    def failure_reason(self) -> str:
        if self.parse_error:
            return self.parse_error
        if not self.structurally_complete and self.structure:
            head = "; ".join(self.structure.errors[:4])
            more = (f" (+{len(self.structure.errors) - 4} more)"
                    if len(self.structure.errors) > 4 else "")
            return f"The generated plan was not a complete 7-day plan — {head}{more}"
        if not self.hard_safe and self.dietary:
            return self.dietary.summary()
        return "The plan could not be validated."

    def issues_brief(self) -> str:
        """One combined retry instruction covering every validator at once."""
        parts: List[str] = []
        if self.parse_error:
            # Without this a response that never parsed produced an EMPTY
            # brief, so the one corrective generation was skipped entirely -
            # the caller got the parse failure back having spent no retry on
            # the most recoverable failure there is.
            #
            # The instruction is chosen by parse code, because the retry only
            # helps if it names the failure that actually happened. Telling a
            # model that emitted ONE truncated plan to "stop sending multiple
            # objects" - which is what a single generic brief did - describes
            # a problem it does not have, and the second attempt fails the
            # same way as the first.
            parts.append(f"OUTPUT FORMAT - {self.parse_error}")
            parts.append(_FORMAT_BRIEFS.get(self.parse_code, _FORMAT_BRIEF_GENERIC))
        if self.structure and self.structure.errors:
            parts.append("STRUCTURE - the plan must be a JSON object with meta, "
                         "plan and summary; plan must contain exactly day_1 to "
                         "day_7; every meal needs meal_label, recipe_name, a "
                         "non-empty ingredients list and a macros object with "
                         "calories, protein_g, carbs_g and fat_g. Problems found:")
            parts.extend(f"  - {e}" for e in self.structure.errors[:12])
        if self.dietary and self.dietary.violations:
            parts.append("DIETARY - these are hard restrictions and the plan "
                         "broke them. Replace the ingredient, do not just rename "
                         "the dish:")
            for violation in self.dietary.violations[:12]:
                parts.append(
                    f"  - {violation.day} {violation.meal}: "
                    f"{violation.ingredient!r} is not "
                    f"{violation.restriction.replace('_', ' ')}"
                )
        if self.calories and self.calories.get("checked") and not self.calories.get("hit"):
            parts.append("CALORIES - every day must land within "
                         f"{CALORIE_TOLERANCE:.0%} of the target:")
            for day in self.calories.get("days", []):
                if day["status"] != "on_target":
                    parts.append(f"  - {day['day']}: {day['total']} kcal is "
                                 f"{day['status']} (needs {day['low']}-{day['high']})")
        if self.macro and self.macro.get("checked") and not self.macro.get("hit"):
            from app.services import macro_targets as mt
            parts.append(mt.retry_brief_structured(self.macro, None))
        return "\n".join(parts)

    def verification_dict(self) -> Dict[str, Any]:
        return {
            "structure": self.structure.as_dict() if self.structure else None,
            "dietary": self.dietary.as_dict() if self.dietary else None,
            "calories": self.calories,
            "macros": self.macro,
            "usable": self.usable,
            "retried": self.retried,
        }


def better(candidate: PlanCandidate, incumbent: PlanCandidate) -> bool:
    """
    Is `candidate` genuinely better than `incumbent`?

    Ordered so the things that cannot be traded away come first:

      1. usable (structurally complete AND hard dietary safe) beats not usable.
         This is what stops a retry containing one correct day from replacing a
         complete seven-day plan, and stops a plan whose macros improved but
         which introduced milk into a vegan week from ever winning.
      2. between two usable candidates, compare macro + calorie DISTANCE, not
         raw days_on_target. Counting days treats "one perfect day out of one"
         as better than "six of seven", which is how a one-day retry used to
         win.
    """
    if candidate.usable != incumbent.usable:
        return candidate.usable
    if not candidate.usable:
        # Neither is shippable; keep whichever we already had rather than
        # churning between two unusable plans.
        return False
    return candidate.quality < incumbent.quality - 1e-9
