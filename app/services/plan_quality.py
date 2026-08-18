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
#
# "field" deliberately excluded as its own bare marker: it matches inside
# "on-field performance", "off-field conditioning" and similar phrases that
# describe a SPORT, not equipment the session itself requires. "pitch",
# "cone drill" etc. carry the same signal without that false-positive shape.
# "shuttle" is excluded for the same kind of reason - a shuttle run / pro
# agility shuttle is routine gym-floor or indoor-court programming
# (basketball, tennis, football conditioning all use it indoors), not
# something that actually implies grass or an outdoor field.
_EQUIPMENT_MARKERS = {
    "gym": ("barbell", "cable machine", "cable row", "leg press", "lat pulldown",
            "smith machine", "bench press", "squat rack", "treadmill",
            "rowing machine", "elliptical", "pec deck", "hack squat"),
    "field": ("pitch", "cone drill", "ladder drill", "agility ladder",
              "hill sprint", "on grass", "on turf"),
    "pool": ("swim", "pool", "aqua"),
    # What "home" equipment means, per this app's OWN /fitness/equipment-
    # options description: "Basic equipment like dumbbells, resistance
    # bands". These used to sit in the "gym" list above, which meant a plan
    # correctly built for equipment="home" and mentioning a dumbbell - the
    # thing home equipment IS - was flagged as assuming gym-only kit it
    # explicitly did not have.
    "home": ("dumbbell", "kettlebell", "resistance band", "bench"),
}

_EQUIPMENT_ALLOWED = {
    "none": set(),
    "home": {"home"},
    "gym": {"gym", "home"},
}

_EQUIPMENT_NEGATION = r"(?:no|not|without|skip|avoid(?:ing)?|don'?t|do\s+not|isn'?t|is\s+not)"
_EQUIPMENT_OPTIONAL = r"(?:optional|if\s+you\s+have|if\s+available|where\s+available|not\s+required|not\s+needed)"


def _mentions_required(lowered: str, marker: str) -> bool:
    """
    Does the plan actually assume this piece of kit, rather than just
    mentioning it to say it is not needed or is optional?

    Checked per occurrence, both directions: "no dumbbells required" and
    "dumbbells optional" both name the word without requiring it. A plain
    substring search could not tell "assumes a barbell" from "no barbell
    needed" apart - both simply contain the word "barbell".
    """
    pattern = re.escape(marker)
    for m in re.finditer(rf"\b{pattern}\b", lowered):
        window_before = lowered[max(0, m.start() - 24):m.start()]
        window_after = lowered[m.end():m.end() + 24]
        if re.search(rf"{_EQUIPMENT_NEGATION}\s*(?:[a-z]+\s+){{0,3}}$", window_before):
            continue
        if re.search(rf"^\s*(?:[a-z]+\s+){{0,2}}{_EQUIPMENT_OPTIONAL}", window_after):
            continue
        if re.search(_EQUIPMENT_OPTIONAL, window_before):
            continue
        return True
    return False

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

# Patterns a goal legitimately hits over and over, exempt from the
# "repetitive" check but NOT counted as evidence the goal was addressed.
#
# Separate from _GOAL_EXPECTATIONS on purpose, because the two answer
# different questions: that one asks "does this plan address the goal at
# all", this one asks "is repeating this pattern a problem". A hypertrophy
# week reaches knee_extension through the back squat, the lunge, the leg
# press AND the leg extension - four occurrences, which tripped the
# repetition check even though accumulating exactly that volume is the
# entire point of the goal. Adding it to _GOAL_EXPECTATIONS instead would
# have meant a plan of nothing but leg extensions counted as "addresses
# muscle gain".
_GOAL_ACCESSORY = {
    "muscle_gain": {"knee_extension", "knee_flexion", "elbow_flexion",
                    "elbow_extension", "hip_extension", "calf_raise",
                    "shoulder_rotation", "axial_load", "lunge"},
    "strength": {"knee_extension", "hip_extension", "axial_load", "lunge",
                 "elbow_extension"},
}

# Movement patterns that represent actual resistance-training stimulus, in
# movement_ontology's own vocabulary rather than a second taxonomy. Used to
# answer one question: does this week contain enough loaded work to serve a
# muscle-gain or strength goal? Conditioning, mobility and stance/context
# descriptors are deliberately absent - running hard is training, but it is
# not the stimulus a hypertrophy goal asked for.
_RESISTANCE_PATTERNS = {
    "hip_hinge", "squat", "lunge", "knee_flexion", "knee_extension",
    "calf_raise", "hip_abduction", "hip_adduction", "hip_extension",
    "vertical_push", "horizontal_push", "vertical_pull", "horizontal_pull",
    "elbow_flexion", "elbow_extension", "shoulder_rotation", "axial_load",
    "spinal_flexion", "spinal_extension", "spinal_rotation", "anti_rotation",
}

# Goals whose whole point is a resistance stimulus. For these, a week that
# has been hollowed out - typically by treating sport practices and matches
# as if they replaced the gym work - is a failure of the plan, not a
# training decision.
_RESISTANCE_GOALS = {"muscle_gain", "strength"}

# Below this the week is not a muscle-gain week by any reading, whatever the
# schedule looks like. Deliberately low: it is a floor for "the resistance
# work was removed", not a prescription for optimal volume, because
# plan_quality cannot see the user's stated training days and must not
# force a regeneration on someone who genuinely trains twice a week.
MIN_RESISTANCE_EXERCISES = 8

# What a week should realistically contain at each level. Reported as
# advisory only - missing it is worth telling the user about, but it is not
# grounds for spending a regeneration when the schedule may simply not allow
# it.
TARGET_RESISTANCE_EXERCISES = {
    "beginner": 10,
    "intermediate": 14,
    "advanced": 18,
}

# What a sport's performance actually depends on, expressed in the same
# movement-pattern vocabulary movement_ontology already uses - not a second
# taxonomy, just this module reusing the one that exists. Matched by substring
# against whatever free text the user typed as their sport, so "football",
# "American football" and "5-a-side football" all resolve without listing
# every phrasing.
#
# Deliberately archetypal rather than exhaustive: most sports converge onto a
# handful of physical demands (repeat-sprint invasion sports, rotational
# racquet sports, steady-state endurance, grappling/striking combat sports,
# strength/power sports), and a sport this dict has never heard of is meant to
# fall through cleanly - see sport_qualities() below - not be treated as
# needing nothing.
SPORT_QUALITIES = {
    # field/court invasion sports - repeat sprint, cutting, jumping
    "football": {"high_speed", "cutting", "hip_hinge"},
    "soccer": {"high_speed", "cutting", "hip_hinge"},
    "rugby": {"high_speed", "cutting", "hip_hinge"},
    "basketball": {"jumping", "cutting", "high_speed"},
    "hockey": {"high_speed", "cutting"},
    "handball": {"jumping", "cutting", "high_speed"},
    "volleyball": {"jumping", "vertical_push"},
    "cricket": {"high_speed", "spinal_rotation"},
    # racquet / rotational sports
    "tennis": {"cutting", "spinal_rotation", "unilateral"},
    "badminton": {"cutting", "high_speed"},
    "squash": {"cutting", "high_speed"},
    "table tennis": {"spinal_rotation"},
    # endurance
    "running": {"running", "hip_hinge", "calf_raise"},
    "marathon": {"running", "hip_hinge", "calf_raise"},
    "triathlon": {"running", "horizontal_pull"},
    "cycling": {"squat", "hip_hinge"},
    "swimming": {"horizontal_pull", "vertical_pull", "overhead"},
    # combat
    "boxing": {"gripping", "hip_hinge", "cardio_intensity"},
    "mma": {"gripping", "hip_hinge", "cardio_intensity"},
    "wrestling": {"gripping", "hip_hinge"},
    "judo": {"gripping", "hip_hinge"},
    "kickboxing": {"cutting", "cardio_intensity"},
    # strength/power/other
    "powerlifting": {"squat", "hip_hinge", "horizontal_push"},
    "weightlifting": {"squat", "hip_hinge", "vertical_push"},
    "crossfit": {"squat", "hip_hinge", "cardio_intensity"},
    "climbing": {"gripping", "vertical_pull"},
    "golf": {"spinal_rotation", "hip_hinge"},
}


def sport_qualities(sport: Optional[str]) -> Optional[Set[str]]:
    """
    The movement patterns a named sport's performance depends on.

    Returns None - not an empty set - for free text that matches nothing,
    and callers MUST treat that as "skip this check", never as "this sport
    needs no particular qualities". An empty set would silently pass any
    plan; None makes the absence of an opinion explicit and unmissable.
    """
    if not sport or not sport.strip():
        return None
    lowered = sport.lower()
    matched: Set[str] = set()
    for key, qualities in SPORT_QUALITIES.items():
        if key in lowered:
            matched |= qualities
    return matched or None


# Movements that ask more of an unpracticed nervous system and connective
# tissue than a beginner has built up, regardless of how good the coaching
# cues are. Keyword match on purpose - the point is catching the model
# reaching for these AT ALL for a beginner, not classifying every variant.
_ADVANCED_ONLY_MARKERS = (
    "snatch", "clean and jerk", "clean pull", "power clean", "clean & jerk",
    "muscle-up", "muscle up", "depth jump", "box jump (high)", "plyometric",
    "contrast set", "1rm", "max effort", "maximal effort",
)

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
    # How many exercises in the week are actual loaded resistance work.
    # Only populated for goals whose point is that stimulus.
    resistance_exercises: Optional[int] = None
    progression_measurable: Optional[bool] = None
    score: int = 100
    issues: List[str] = field(default_factory=list)
    # Reported, but never gates `adequate` or drives regeneration - unlike
    # `issues`. Per-day duration and exercise-count live here specifically
    # because they depend on split_days() correctly finding day headings in
    # free-form model markdown, which - tested live, repeatedly, against a
    # variety of real FitMentor output - is not reliable enough to trust as a
    # hard gate: a plan that is actually fine can get misjudged as absurdly
    # over-length purely from a heading style the splitter did not recognise,
    # and regenerating against a measurement error fixes nothing while
    # tripling real Groq token cost for no benefit. Keeping the number
    # visible (logged, returned to the caller) is still worth doing; forcing
    # a doomed regeneration attempt on it is not.
    advisory: List[str] = field(default_factory=list)

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
            "resistance_exercises": self.resistance_exercises,
            "progression_measurable": self.progression_measurable,
            "score": self.score,
            "adequate": self.adequate,
            "issues": list(self.issues),
            "advisory": list(self.advisory),
        }


# A genuine table row: at least two "| ... |" cells, not just a stray pipe
# character inside a sentence.
_TABLE_ROW = re.compile(r"^\s*\|.+\|.*\|\s*$", re.M)


def exercise_lines(plan_text: str) -> List[str]:
    """
    The lines that actually prescribe something.

    A thin wrapper over plan_structure.quality_subjects() - the single
    canonical parser for "is this a prescribed item, a heading, an
    instruction, or commentary" - see that module's docstring for why
    splitting that question from movement classification mattered. This
    used to be its own independent regex-based parser; keeping two meant
    they could (and did) disagree.

    quality_subjects() includes AMBIGUOUS leaves alongside definite
    prescriptions (never definite containers, whose own decorated label
    text - "Vertical Push (25 min)" - must not inflate the count while its
    nested exercises are already being counted independently), so a
    decorated unknown exercise like "Power Pull (2 min)" is still counted
    as one exercise even though plan_structure could not prove what it was.
    """
    from app.services import plan_structure as structure

    items = structure.parse(plan_text)
    return [item.body for item in structure.quality_subjects(items)]


# A heading that starts a new day. Both formats FitMentor actually produces:
# "Day 1" and plain weekday names.
#
# Weekday names were missing, and the gap was not cosmetic - it silently
# disabled every per-week check for a whole common output format. A
# "### Monday / ### Tuesday" plan split into ONE section, so
# `is_multi_day` was False and the weekly resistance-volume gate never ran:
# a severely under-programmed strength week could bypass it entirely just by
# labelling its days the ordinary way.
#
# Full weekday names only, deliberately not three-letter abbreviations:
# "### Sun Salutations" is a real yoga heading and `\bsun\b` would split the
# plan on it. Requiring the "day" suffix costs nothing real - a model
# writing "### Mon" is rare - and removes that whole class of false split.
#
# Still anchored to HEADING shapes (optional #'s or bold markers), so a
# bulleted "- Monday: rest" stays a list item rather than becoming a day
# boundary.
_DAY_HEADING = re.compile(
    r"^\s*#{0,6}\s*\*{0,2}\s*"
    r"(?:day\s*\d+|(?:mon|tues|wednes|thurs|fri|satur|sun)day)"
    r"\b",
    re.I | re.M,
)


def split_days(plan_text: str) -> List[str]:
    """
    Break a multi-day plan into one chunk per day.

    WHY THIS EXISTS
    ----------------
    requested_minutes and the beginner exercise-count limit are PER-DAY
    budgets, but FitMentor always generates a full 7-day plan in one string.
    Summing exercise_lines() across the whole text and comparing that against
    a single day's minute budget makes any realistic week look absurd - a
    genuinely well-formed 30-minutes/day plan, 7 days of it, reads as "550
    minutes will not fit in 30" purely from being added up wrong, not from
    being wrong. This was never caught because every existing test plan is
    single-session text with no day structure at all.

    A plan with fewer than two recognisable day headings comes back as one
    section - i.e. unchanged behaviour for exactly the single-session shape
    every existing test and the injury-repair path already use.
    """
    text = plan_text or ""
    marks = list(_DAY_HEADING.finditer(text))
    if len(marks) < 2:
        return [text]
    sections = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        sections.append(text[m.start():end])
    return sections


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

        # "3 sets of 8-12 reps", "3x8", "4 x 6" - but NOT "8x100m" or
        # "6x400m", which are distance intervals in the same "NxM" shape.
        # Treating "100m" as 100 reps at ~3.5s each overcounted a single
        # sprint-interval line by 45+ minutes; distance/pace notation is
        # routine for running, swimming, cycling and sprint drills, so this
        # needs its own case rather than silently falling into reps.
        sets = reps = None
        m = re.search(
            r"(\d+)\s*(?:sets?\s*(?:of|x)?|x)\s*(\d+)\s*(m|km|meters|metres|miles|yards?)?",
            lowered,
        )
        if m and not m.group(3):
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
    allowed = _EQUIPMENT_ALLOWED.get(equipment, {"gym", "home"})

    violations = []
    for kind, markers in _EQUIPMENT_MARKERS.items():
        if kind in allowed:
            continue
        # "gym" users legitimately have a pool at many gyms; field access is
        # the one that genuinely cannot be assumed.
        if kind == "pool" and equipment == "gym":
            continue
        found = sorted({m for m in markers if _mentions_required(lowered, m)})
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

    # Duration and the beginner exercise-count limit are PER-DAY budgets.
    # requested_minutes is "how long is today's session", not "how long is
    # the whole week" - split into days first (see split_days()) and use the
    # single busiest day, not the week summed. A plan with no day structure
    # (one section, per split_days()) behaves exactly as before: the busiest
    # "day" is just the whole text, unchanged from the old flat calculation.
    day_sections = split_days(plan_text)
    per_day_lines = [exercise_lines(section) for section in day_sections]
    per_day_minutes = [estimate_minutes(day) for day in per_day_lines]
    busiest_day_minutes = max(per_day_minutes, default=0)
    busiest_day_exercises = max((len(day) for day in per_day_lines), default=0)
    quality.estimated_minutes = busiest_day_minutes

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

    # Computed once here, reused below for both the repetition exemption and
    # the goal/sport alignment checks, rather than twice.
    goal_key = (goal or "").lower()
    expected = _GOAL_EXPECTATIONS.get(goal_key)
    accessory = _GOAL_ACCESSORY.get(goal_key, set())
    sport_needs = sport_qualities(sport)

    # A pattern the goal or sport actually REQUIRES appearing often is not
    # repetition, it is the point - a runner's week is running on most days
    # by design, and flagging that as "repetitive: running" would regenerate
    # a plan that is already correct. Only penalise a pattern repeating that
    # nothing about the stated goal or sport called for. `accessory` covers
    # the patterns a goal legitimately accumulates volume in without them
    # counting as evidence the goal was addressed.
    required_repeats = (expected or set()) | accessory | (sport_needs or set())
    quality.duplicate_patterns = sorted(
        p for p, n in counts.items()
        if n >= 4 and p not in contextual and p not in required_repeats
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
    # A plan whose patterns are entirely accounted for by what the stated
    # sport/goal actually calls for is narrow BECAUSE that is correct, not
    # because it lacks range - a pure running week for an endurance goal is
    # supposed to be mostly "running", not evidence the plan is thin.
    non_required_patterns = set(counts) - contextual - required_repeats
    narrow_on_purpose = bool(required_repeats) and not non_required_patterns
    if (quality.exercises >= MIN_EXERCISES and quality.distinct_patterns < MIN_DISTINCT_PATTERNS
            and not narrow_on_purpose):
        quality.issues.append(
            f"only {quality.distinct_patterns} distinct movement patterns - "
            "the session trains too narrow a range"
        )
    if quality.duplicate_patterns:
        quality.issues.append(
            f"repetitive: {', '.join(quality.duplicate_patterns)} appears in most of the plan"
        )
    if requested_minutes and quality.estimated_minutes < requested_minutes * UNDERUSE_FRACTION:
        quality.advisory.append(
            f"about {quality.estimated_minutes} minutes of actual work on the "
            f"busiest day against {requested_minutes} available - under-programmed"
        )
    if requested_minutes and quality.estimated_minutes > requested_minutes * OVERUSE_FRACTION:
        quality.advisory.append(
            f"about {quality.estimated_minutes} minutes of work on the busiest "
            f"day will not fit in {requested_minutes}"
        )

    # --- equipment ------------------------------------------------------
    quality.equipment_violations = _equipment_issues(plan_text, equipment)
    if quality.equipment_violations:
        quality.issues.append(
            "assumes equipment that was not available: "
            + "; ".join(quality.equipment_violations)
        )

    # --- resistance volume -------------------------------------------------
    # A muscle-gain or strength week has to actually contain loaded work.
    #
    # The failure this catches: a plan for someone who plays a sport AND
    # asked for muscle gain, where the sport's practices and matches were
    # treated as if they replaced the gym sessions - the week comes back as
    # two light sessions and five rest/practice days. Sport IS training load,
    # but it is not the resistance stimulus the goal asked for, and the fix
    # is to distribute the gym work around the fixed commitments rather than
    # delete it.
    #
    # Counted per EXERCISE across the whole week, not per day: it uses
    # exercise_lines() and the movement ontology, neither of which depends on
    # split_days() correctly recognising the model's day-heading style - the
    # unreliability that made the duration checks advisory-only.
    # Only meaningful for a plan that IS a week. split_days() is used here for
    # the one thing it is reliable at - noticing whether day headings exist at
    # all - not for the per-day budget arithmetic that made the duration
    # checks advisory-only. A single-session plan (one section, no day
    # headings) genuinely cannot be judged against a WEEKLY floor: five
    # resistance exercises is a complete strength session and a gutted week,
    # and nothing here can tell which was asked for.
    is_multi_day = len(day_sections) >= 2

    if goal_key in _RESISTANCE_GOALS and is_multi_day:
        resistance = sum(
            1 for line in lines
            if ontology.classify_prescribed(line).patterns & _RESISTANCE_PATTERNS
        )
        quality.resistance_exercises = resistance

        if resistance < MIN_RESISTANCE_EXERCISES:
            quality.issues.append(
                f"only {resistance} resistance exercises in the week - a "
                f"{goal_key.replace('_', ' ')} plan needs loaded work, and sport "
                f"practice does not replace it"
            )
        else:
            wanted = TARGET_RESISTANCE_EXERCISES.get((level or "").lower())
            if wanted and resistance < wanted:
                # Advisory, not gating: plan_quality cannot see how many days
                # a week the person actually said they can train, so a light
                # week may be exactly right. Worth surfacing, never worth
                # forcing a regeneration over.
                quality.advisory.append(
                    f"{resistance} resistance exercises is light for an "
                    f"{level} {goal_key.replace('_', ' ')} week "
                    f"(around {wanted} would be typical)"
                )

    # --- goal alignment --------------------------------------------------
    if expected and counts:
        if not (set(counts) & expected):
            quality.issues.append(
                f"nothing in the plan addresses the stated goal ({goal})"
            )

    # --- sport alignment ---------------------------------------------------
    # A different check from goal alignment on purpose: goal is what the plan
    # is FOR, sport is a floor that has to survive regardless of goal - a
    # footballer training for muscle gain still needs to be able to play
    # football. sport_qualities() returns None for anything unrecognised, and
    # that is treated as "no opinion", not "needs nothing" - an unmatched
    # sport is never penalised for it.
    if sport_needs and counts:
        if not (set(counts) & sport_needs):
            quality.issues.append(
                f"nothing in the plan trains the qualities {sport} actually depends on"
            )

    # --- level -----------------------------------------------------------
    if (level or "").lower() == "beginner":
        if busiest_day_exercises > 12:
            quality.advisory.append(
                f"{busiest_day_exercises} exercises in one day is a lot for a beginner"
            )
        lowered_lines = " ".join(lines).lower()
        advanced_found = sorted({m for m in _ADVANCED_ONLY_MARKERS if m in lowered_lines})
        if advanced_found:
            quality.issues.append(
                f"beginner session includes advanced work: {', '.join(advanced_found)}"
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

    # --- formatting --------------------------------------------------------
    # The prompt already says never to use a Markdown table, explicitly and
    # more than once - this catches the times that gets ignored anyway,
    # deterministically, instead of trusting compliance. The app's renderer
    # and PDF export have no table support at all, so a table here is not a
    # style problem, it renders as broken pipe-delimited text on screen.
    if _TABLE_ROW.search(plan_text or ""):
        quality.issues.append(
            "contains a Markdown table, which the app cannot render - use "
            "headings and bullet/numbered lists instead"
        )

    # --- score -------------------------------------------------------------
    # Transparent and blunt: every issue costs, weighted by how much it
    # affects whether the plan is worth following. This never gates safety;
    # it is reported alongside it. Advisory items cost less and separately -
    # they inform the score without ever being able to flip `adequate`
    # (which reads only `issues`), for the reasons on the `advisory` field.
    weights = {
        "remain": 20, "removed": 15, "distinct": 12, "repetitive": 10,
        "equipment": 10, "goal": 15, "depends on": 15, "advanced work": 15,
        "resistance exercises": 20,
        "beginner": 5, "progression": 8, "markdown table": 12,
    }
    penalty = sum(next((w for k, w in weights.items() if k in issue), 8)
                  for issue in quality.issues)
    penalty += sum(4 for _ in quality.advisory)
    quality.score = max(0, 100 - penalty)

    return quality
