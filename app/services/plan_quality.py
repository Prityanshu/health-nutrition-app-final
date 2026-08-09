"""
Is this plan still worth giving someone?

SCOPE - READ THIS FIRST
-----------------------
This module has NO safety authority. It never decides what is dangerous, never
overrides the audit, and cannot cause an unsafe exercise to be kept. It answers
one question: after safety filtering, is what remains a usable workout?

Safety beats completeness. A sparse plan is a bad plan; an unsafe plan is a
harmful one. So when the two conflict, the caller ships the sparse one.

WHY RATIOS AND STRUCTURE, NOT A COUNT
-------------------------------------
"More than 3 removed" behaves badly across plan sizes: removing 3 of 20 is
noise, removing 3 of 5 is a gutted session. The checks below are proportional,
and combined with structural ones - does the plan still train a range of
patterns, does it still fill the requested time - because a plan can have
enough exercises and still be six variations of the same movement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

# A session with fewer than this is not a session, whatever the ratio says.
MIN_EXERCISES = 4
# Removing more than this share of a plan means what remains was not designed.
MAX_REMOVED_FRACTION = 0.34
# Distinct movement patterns expected in a full-body session.
MIN_DISTINCT_PATTERNS = 3
# Fallback when a line gives no sets or reps to work from.
MINUTES_PER_EXERCISE = 6

# Time estimation. A plan that SAYS "60 minutes" and contains 25 minutes of
# work is under-programmed, and the only way to know is to add up the work.
SECONDS_PER_REP = 3.5          # a controlled rep with its eccentric
DEFAULT_REST_SECONDS = 75
TRANSITION_SECONDS = 60        # setup, moving between stations

# Under-use is a real problem; forcing the full time is not. Someone asking
# for 120 minutes does not need 120 minutes of exercise - but 45 minutes of
# work against a 120-minute request is under-programming.
UNDERUSE_FRACTION = 0.6
OVERUSE_FRACTION = 1.4

# Equipment implied by particular words. Used to catch a "home" plan that
# quietly assumes a cable stack, or a "gym" plan that needs a football pitch.
_EQUIPMENT_MARKERS = {
    "gym": ("barbell", "cable", "machine", "leg press", "lat pulldown", "smith",
            "bench press", "squat rack", "dumbbell", "kettlebell", "treadmill",
            "rowing machine", "elliptical", "pec deck", "hack squat"),
    "field": ("pitch", "field", "cones", "cone drill", "ladder drill", "track",
              "shuttle", "agility ladder", "grass", "turf", "hill sprint"),
    "pool": ("swim", "pool", "aqua"),
}

# Goals and the movement patterns a plan for them should actually contain.
# Deliberately loose - this catches a plan that ignores the goal entirely,
# not one that weights it differently from how I would.
_GOAL_EXPECTATIONS = {
    "muscle_gain": {"horizontal_push", "horizontal_pull", "squat", "hip_hinge",
                    "vertical_push", "vertical_pull"},
    "strength": {"squat", "hip_hinge", "horizontal_push", "horizontal_pull"},
    "endurance": {"running", "low_impact", "cardio_intensity"},
    "weight_loss": {"low_impact", "cardio_intensity", "squat", "horizontal_push"},
    "general_fitness": {"squat", "horizontal_push", "horizontal_pull", "low_impact"},
}

# Progression language that can actually be followed.
_MEASURABLE_PROGRESSION = (
    "rpe", "%", "1rm", "add ", "increase to", "week 1", "week 2", "week 3",
    "sets of", "reps at", "seconds", "kg", "deload", "same weight",
)
_VAGUE_PROGRESSION = (
    "if too easy", "as you get stronger", "when comfortable", "gradually increase",
    "push yourself", "listen to your body", "increase weight if",
)


@dataclass
class Quality:
    exercises: int = 0
    removed: int = 0
    replaced: int = 0
    distinct_patterns: int = 0
    duplicate_patterns: List[str] = field(default_factory=list)
    estimated_minutes: int = 0
    has_warm_up: bool = False
    has_cool_down: bool = False
    equipment_violations: List[str] = field(default_factory=list)
    progression_measurable: Optional[bool] = None
    score: int = 100
    issues: List[str] = field(default_factory=list)

    @property
    def removed_fraction(self) -> float:
        total = self.exercises + self.removed
        return (self.removed / total) if total else 0.0

    @property
    def adequate(self) -> bool:
        return not self.issues

    def as_dict(self) -> Dict:
        return {
            "exercises": self.exercises,
            "removed": self.removed,
            "replaced": self.replaced,
            "removed_fraction": round(self.removed_fraction, 2),
            "distinct_patterns": self.distinct_patterns,
            "estimated_minutes": self.estimated_minutes,
            "has_warm_up": self.has_warm_up,
            "has_cool_down": self.has_cool_down,
            "equipment_violations": list(self.equipment_violations),
            "progression_measurable": self.progression_measurable,
            "score": self.score,
            "adequate": self.adequate,
            "issues": list(self.issues),
        }


# Lines that are structure, not exercises. Counting a day heading as an
# exercise would make a two-exercise plan look like a six-exercise one.
_STRUCTURAL = re.compile(
    r"^\s*(?:#{1,6}\s|\*\*|day\s*\d|week\s|rest day|progression|nutrition|"
    r"warm[\s-]?up\s*:?\s*$|cool[\s-]?down\s*:?\s*$|notes?\s*:|tips?\s*:|"
    r"removed|important|overview|summary|plan\b)",
    re.I,
)
_EXERCISE_LINE = re.compile(r"^\s*(?:[-*•+]|\d+[.)])\s*\S")


def exercise_lines(plan_text: str) -> List[str]:
    """
    The lines that actually prescribe something.

    Deliberately conservative: a line has to look like a list item AND not
    look like a heading. Over-counting would hide sparsity, which is the exact
    failure this module exists to catch.
    """
    out = []
    for raw in (plan_text or "").splitlines():
        line = raw.strip()
        if not line or not _EXERCISE_LINE.match(line):
            continue
        body = re.sub(r"^\s*(?:[-*•+]|\d+[.)])\s*", "", line)
        if _STRUCTURAL.match(body):
            continue
        out.append(body)
    return out


def estimate_minutes(lines: List[str]) -> int:
    """
    How long this session realistically takes.

    Reads sets and reps where the plan states them and falls back to a flat
    figure where it does not. A plan that claims 60 minutes while containing
    four sets of eight is not a 60-minute session, and the only way to know is
    to add the work up rather than trusting the label.
    """
    total_seconds = 0.0
    for line in lines:
        lowered = line.lower()

        # "3 sets of 8-12 reps", "3x8", "4 x 6"
        sets = reps = None
        m = re.search(r"(\d+)\s*(?:sets?\s*(?:of|x)?|x)\s*(\d+)", lowered)
        if m:
            sets, reps = int(m.group(1)), int(m.group(2))

        # Timed work: "20 min", "3x45s", "30-60 seconds"
        minutes = re.search(r"(\d+)\s*(?:-\s*\d+\s*)?(?:min|minute)", lowered)
        seconds = re.search(r"(\d+)\s*(?:-\s*\d+\s*)?(?:s\b|sec|second)", lowered)

        if minutes:
            total_seconds += int(minutes.group(1)) * 60
        elif sets and seconds:
            total_seconds += sets * int(seconds.group(1))
            total_seconds += sets * DEFAULT_REST_SECONDS
        elif sets and reps:
            total_seconds += sets * reps * SECONDS_PER_REP
            total_seconds += sets * DEFAULT_REST_SECONDS
        else:
            total_seconds += MINUTES_PER_EXERCISE * 60
            continue
        total_seconds += TRANSITION_SECONDS

    return int(round(total_seconds / 60))


def _progression_section(plan_text: str) -> str:
    """
    Just the progression guidance, lowercased.

    Scanning the whole plan made "4 sets of 8" in an exercise line look like
    measurable progression, so "increase weight if too easy" passed.
    """
    lines = (plan_text or "").splitlines()
    collected, capturing = [], False
    for raw in lines:
        line = raw.strip()
        if re.search(r"progress", line, re.I):
            capturing = True
            collected.append(line)
            continue
        if capturing:
            # Stop at the next heading.
            if re.match(r"^\s*(?:#{1,6}\s|\*\*|day\s*\d)", line, re.I):
                break
            if line:
                collected.append(line)
    return " ".join(collected).lower()


def _equipment_issues(plan_text: str, equipment: Optional[str]) -> List[str]:
    """Kit the plan assumes but the user did not say they have."""
    if not equipment:
        return []
    lowered = (plan_text or "").lower()
    allowed = {"none": set(), "home": set(), "gym": {"gym"}}.get(equipment, {"gym"})

    violations = []
    for kind, markers in _EQUIPMENT_MARKERS.items():
        if kind in allowed:
            continue
        # "gym" users legitimately have a pool at many gyms; field access is
        # the one that genuinely cannot be assumed.
        if kind == "pool" and equipment == "gym":
            continue
        found = sorted({m for m in markers if m in lowered})
        if found:
            violations.append(f"{kind}: {', '.join(found[:4])}")
    return violations


def evaluate(
    plan_text: str,
    removed_count: int = 0,
    replaced_count: int = 0,
    requested_minutes: Optional[int] = None,
    goal: Optional[str] = None,
    sport: Optional[str] = None,
    equipment: Optional[str] = None,
    level: Optional[str] = None,
) -> Quality:
    """
    Assess a filtered plan. Returns issues; the caller decides what to do.

    Note what is NOT here: nothing about injuries, restrictions or danger.
    Those belong to the audit, and mixing them in is how a completeness rule
    ends up quietly overruling a safety rule.
    """
    from app.services import movement_ontology as ontology

    lines = exercise_lines(plan_text)
    quality = Quality(
        exercises=len(lines),
        removed=removed_count,
        replaced=replaced_count,
    )

    lowered = (plan_text or "").lower()
    quality.has_warm_up = bool(re.search(r"warm[\s-]?up", lowered))
    quality.has_cool_down = bool(re.search(r"cool[\s-]?down|stretch", lowered))
    quality.estimated_minutes = estimate_minutes(lines)

    # Pattern spread - a plan can have eight exercises and train one thing.
    counts: Dict[str, int] = {}
    for line in lines:
        for pattern in ontology.classify_prescribed(line).patterns:
            counts[pattern] = counts.get(pattern, 0) + 1
    # Stance and context descriptors are not training patterns. Almost every
    # gym exercise is weight_bearing, so counting it made every plan look
    # repetitive and every plan look diverse - useless in both directions.
    contextual = {"unilateral", "isometric", "weight_bearing", "loaded_stance",
                  "seated_supported", "non_weight_bearing", "impact", "low_impact"}
    quality.distinct_patterns = len(set(counts) - contextual)
    quality.duplicate_patterns = sorted(
        p for p, n in counts.items() if n >= 4 and p not in contextual
    )

    # --- issues ---------------------------------------------------------
    if quality.exercises < MIN_EXERCISES:
        quality.issues.append(
            f"only {quality.exercises} exercises remain (minimum {MIN_EXERCISES})"
        )
    if quality.removed and quality.removed_fraction > MAX_REMOVED_FRACTION:
        quality.issues.append(
            f"{quality.removed_fraction:.0%} of the plan was removed "
            f"({quality.removed} of {quality.exercises + quality.removed})"
        )
    if quality.exercises >= MIN_EXERCISES and quality.distinct_patterns < MIN_DISTINCT_PATTERNS:
        quality.issues.append(
            f"only {quality.distinct_patterns} distinct movement patterns - "
            "the session trains too narrow a range"
        )
    if quality.duplicate_patterns:
        quality.issues.append(
            f"repetitive: {', '.join(quality.duplicate_patterns)} appears in most of the plan"
        )
    if requested_minutes and quality.estimated_minutes < requested_minutes * UNDERUSE_FRACTION:
        quality.issues.append(
            f"about {quality.estimated_minutes} minutes of actual work against "
            f"{requested_minutes} available - under-programmed"
        )
    if requested_minutes and quality.estimated_minutes > requested_minutes * OVERUSE_FRACTION:
        quality.issues.append(
            f"about {quality.estimated_minutes} minutes of work will not fit in "
            f"{requested_minutes}"
        )

    # --- equipment ------------------------------------------------------
    quality.equipment_violations = _equipment_issues(plan_text, equipment)
    if quality.equipment_violations:
        quality.issues.append(
            "assumes equipment that was not available: "
            + "; ".join(quality.equipment_violations)
        )

    # --- goal alignment --------------------------------------------------
    expected = _GOAL_EXPECTATIONS.get((goal or "").lower())
    if expected and counts:
        if not (set(counts) & expected):
            quality.issues.append(
                f"nothing in the plan addresses the stated goal ({goal})"
            )

    # --- level -----------------------------------------------------------
    if (level or "").lower() == "beginner" and quality.exercises > 12:
        quality.issues.append(
            f"{quality.exercises} exercises is a lot for a beginner session"
        )

    # --- progression ------------------------------------------------------
    progression_text = _progression_section(plan_text)
    if progression_text:
        measurable = any(t in progression_text for t in _MEASURABLE_PROGRESSION)
        vague = any(t in progression_text for t in _VAGUE_PROGRESSION)
        # Vague wording beats measurable wording: "increase weight if too easy"
        # next to "3 sets of 8" is still an unfollowable instruction.
        quality.progression_measurable = measurable and not vague
        if not quality.progression_measurable:
            quality.issues.append(
                "progression is not measurable - it says to increase load without "
                "saying by how much or against what"
            )

    # --- score -------------------------------------------------------------
    # Transparent and blunt: every issue costs, weighted by how much it
    # affects whether the plan is worth following. This never gates safety;
    # it is reported alongside it.
    weights = {
        "remain": 20, "removed": 15, "distinct": 12, "repetitive": 10,
        "under-programmed": 12, "will not fit": 8, "equipment": 10,
        "goal": 15, "beginner": 5, "progression": 8,
    }
    penalty = 0
    for issue in quality.issues:
        penalty += next((w for k, w in weights.items() if k in issue), 8)
    quality.score = max(0, 100 - penalty)

    return quality
