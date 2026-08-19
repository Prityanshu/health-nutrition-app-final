"""
Plan structure, and nothing else.

WHY THIS EXISTS
---------------
Two different questions were being answered by one tangle of regexes spread
across plan_quality.py and contraindications.py:

    1. Is this line a prescribed plan item (an exercise), or is it a
       heading, a container label, an instruction, or commentary?
    2. What movement does a prescribed item represent?

This module answers question 1 ONLY: structure. It has no opinion on
biomechanics, injuries or safety, and - as of this revision - it does not
even ask movement_ontology for a second opinion. An earlier version did,
specifically to tell a decorated container label ("- **Vertical Push (25
min)** - 🏋️") apart from a decorated exercise ("- **Push-up (2 min)** -
🏋️") that happens to share a vocabulary word. That worked for "Push-up"
and "Pull-up", and then immediately failed for "Power Pull" or "Leg Pull" -
any name the ontology had never seen - because it was still, underneath,
trying to answer "is this an exercise" from inside the structural layer.

WHAT CHANGED: AMBIGUOUS IS A VALID ANSWER
------------------------------------------
A decorated bullet with a duration and nothing else CANNOT be proven, from
Markdown structure alone, to be a container or a prescription - "Vertical
Push (25 min)" and "Power Pull (2 min)" have the identical shape. Rather
than guessing (via vocabulary or via a second ontology lookup), this module
now says so: such a line is AMBIGUOUS, a first-class structural result, not
a parsing failure.

Two pieces of PURELY STRUCTURAL evidence still resolve the ambiguity
without ever asking what the words mean:

  - reserved container grammar ("Warm-up", "Circuit 1", "Main Workout") is
    still definite - these are section-shaped names by convention, not by
    movement classification;
  - a decorated label that turns out to have independently-parsed CHILD
    items nested beneath it (parse() runs a second pass for this) is a
    container BECAUSE it has children, not because of what it is called.

Everything else stays AMBIGUOUS, and downstream consumers decide what to do
about it - see `safety_subjects()` and `quality_subjects()` below. Safety
fails closed: an active injury/restriction pulls every AMBIGUOUS item into
the same audit a definite prescription gets, so an unrecognised movement
can never silently escape by being mistaken for a label. A healthy user
sees the plan untouched either way.

WHAT THIS IS NOT
----------------
Not a markdown parser and not a general document model. It recognises the
handful of shapes a generated workout plan actually uses - bullets, numbered
items, a few heading styles, a bullet that is itself just a group label
("Warm-up", "Circuit 1"), and a line indented under a prescription with no
marker of its own as that prescription's dosage - and nothing else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# structural interpretations
# ---------------------------------------------------------------------------
#
# Five results, from most to least certain. AMBIGUOUS is not a failure mode
# - it is the honest answer when Markdown shape alone cannot settle the
# question, and safety/quality consumers each resolve it their own way (see
# safety_subjects()/quality_subjects() below) rather than plan_structure
# guessing on their behalf.

DEFINITE_CONTAINER = "definite_container"
DEFINITE_INSTRUCTION = "definite_instruction"
DEFINITE_NON_EXERCISE = "definite_non_exercise"
PRESCRIPTION_LIKE = "prescription_like"
AMBIGUOUS = "ambiguous"
HEADING = "heading"
PROSE = "prose"

# Backward-compatible aliases - identical values, for code and tests written
# against the original (pre-AMBIGUOUS) vocabulary. `item.role == CONTAINER`
# and `item.role == DEFINITE_CONTAINER` are the same comparison; nothing
# here is a second, competing set of states.
CONTAINER = DEFINITE_CONTAINER
INSTRUCTION = DEFINITE_INSTRUCTION
NON_EXERCISE = DEFINITE_NON_EXERCISE
PRESCRIPTION_CANDIDATE = PRESCRIPTION_LIKE


@dataclass
class PlanItem:
    """One structural unit of a plan."""
    role: str
    line_numbers: List[int]
    raw_lines: List[str]
    body: str
    dosage_lines: List[str] = field(default_factory=list)
    section: Optional[str] = None
    marker: Optional[str] = None
    # Why this interpretation was reached - for debugging/tests, never
    # consulted for a decision.
    evidence: str = ""
    # Structural parent/children, keyed by the parent's primary line number
    # (line_numbers[0]) - stable and unique within one parse() call, and
    # simpler than threading object identity through dataclasses.
    parent_id: Optional[int] = None
    child_ids: List[int] = field(default_factory=list)
    indent: int = 0

    @property
    def interpretation(self) -> str:
        """Alias for `role`, in the vocabulary this module's docstring
        uses. Never a second field - there is exactly one classification
        per item, so there is nothing for this to drift out of sync with."""
        return self.role


# ---------------------------------------------------------------------------
# list items
# ---------------------------------------------------------------------------

# A real bullet or numbered item: marker, at least one space, then content.
# The required space is what tells "* Cossack flow" (a bullet) apart from
# "**Bold heading**" (two asterisks, no space between them) - a plain "\s*"
# would match both.
_BULLET_OR_NUMBERED = re.compile(r"^\s*(?P<marker>[-*•+]|\d+[.)])\s+\S")
_MARKER_PREFIX = re.compile(r"^\s*(?:[-*•+]|\d+[.)])\s*")
# Outer Markdown emphasis only - for classification. "**Squat to Chair** -
# **12 reps**" keeps its inner emphasis; only the very start and very end of
# the string are stripped, since that is all a bullet's own name/heading ever
# wraps in practice and movement_ontology's own normaliser already discards
# any "*" left over regardless.
_EMPHASIS = re.compile(r"^[*_]{1,2}\s*|\s*[*_]{1,2}$")

# ---------------------------------------------------------------------------
# headings
# ---------------------------------------------------------------------------

_MARKDOWN_HEADING = re.compile(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$")
# A whole line wrapped in emphasis and nothing else - "**Warm-up (5 min)**",
# "*30 minutes per day*". Requires the closing marker at the very end, so a
# line like "**Progression tip:** Add 2 reps..." (text continues past the
# closing "**") is correctly NOT a heading - it is prose that happens to open
# with a bolded label.
_BOLD_HEADING = re.compile(r"^\s*\*{1,2}([^*]+?)\*{1,2}\s*:?\s*$")
# A bare heading word/phrase with nothing else on the line - "Warm-up",
# "Cool-down:", "Day 3", "Progression". No bullet marker: a heading is never
# itself a list item.
_BARE_HEADING = re.compile(
    r"^\s*(day\s*\d+|week\s*\d+|warm[\s-]?up|cool[\s-]?down|progression|"
    r"nutrition|safety|warnings?|disclaimer|general\s+tips?|"
    r"about this plan|before you (?:start|begin)|"
    r"things to (?:know|remember)|notes?|tips?|how to use|overview|summary|"
    r"goal)\s*:?\s*$",
    re.I,
)

# ---------------------------------------------------------------------------
# non-exercise heading CATEGORY - a whole-heading judgement, never a
# substring search
# ---------------------------------------------------------------------------
#
# A heading qualifies as non-exercise only if EVERY word in it, once
# parenthetical asides are stripped, is either a recognised category root
# (nutrition, safety, progression, notes...) or a generic modifier (general,
# guidance...), AND at least one of those words is an actual category root -
# "General Notes" and "Progression Notes" both pass; "Day 3 - Progression
# Run" and "Running Progression Session" both fail, because "day"/"run"/
# "running"/"session" belong to neither set.
_CATEGORY_PHRASES = (
    "about this plan", "before you start", "before you begin",
    "things to know", "things to remember",
    "how to use this plan", "how to use",
)
_CATEGORY_ROOTS = {
    "nutrition", "safety", "progression", "disclaimer", "warning", "warnings",
    "goal", "note", "notes", "tip", "tips",
}
_CATEGORY_MODIFIERS = {
    "general", "guidance", "info", "information", "overview", "summary",
    "optional", "important",
    "adjustment", "adjustments",
    "and", "the", "a", "an",
}
_HEADING_WORD = re.compile(r"[a-z]+")


def _phrase_match(lowered: str, phrase: str) -> bool:
    """
    True only if `lowered` IS the complete idiom, or the idiom followed by
    nothing but recognised category modifier words - never a substring
    test: "before you start" must not match merely because it appears
    somewhere inside "before you start workout".
    """
    if lowered == phrase:
        return True
    if not lowered.startswith(phrase):
        return False
    remainder = lowered[len(phrase):].strip(" :-")
    if not remainder:
        return True
    words = _HEADING_WORD.findall(remainder)
    return bool(words) and all(w in _CATEGORY_MODIFIERS for w in words)


def _is_non_exercise_heading(text: str) -> bool:
    """Whole-heading category match - never a substring search, for either
    the single-word category roots or the multi-word idiomatic phrases."""
    lowered = text.lower()
    lowered = re.sub(r"\([^)]*\)", " ", lowered)  # "(optional)" is decoration
    lowered = re.sub(r"\s+", " ", lowered).strip().rstrip(":").strip()

    if any(_phrase_match(lowered, phrase) for phrase in _CATEGORY_PHRASES):
        return True

    words = _HEADING_WORD.findall(lowered)
    if not words:
        return False
    if not all(w in _CATEGORY_ROOTS or w in _CATEGORY_MODIFIERS for w in words):
        return False
    return any(w in _CATEGORY_ROOTS for w in words)


_WARM_UP_HEADING = re.compile(r"warm[\s-]?up", re.I)
_COOL_DOWN_HEADING = re.compile(r"cool[\s-]?down|stretch", re.I)

# ---------------------------------------------------------------------------
# reserved container grammar - a bullet that names a section, not an
# exercise, by STRUCTURAL convention (a recognised section-type word, an
# optional generic suffix, an optional short identifier) - never by asking
# what the words mean.
# ---------------------------------------------------------------------------
_SECTION_WORD = (
    r"warm[\s-]?up|cool[\s-]?down|main|mobility|activation|strength|"
    r"conditioning|finisher|circuit|block|superset|recovery|cardio|core|"
    r"accessory|primer|workout|session"
)

# A section label may carry a TIME ALLOCATION - "Warm-up - 10 min", "Main
# lifts - 55 min". Without this the trailing duration read as dosage, the
# label became a prescription candidate, and (with an injury active) repair
# swapped it for a conditioning exercise: "Main lifts - 55 min" came back as
# "Elliptical, steady pace: 55 min". Only a BARE duration qualifies - a line
# with sets, reps, "x" or an RPE is prescribing something and is left alone.
# Minutes and hours only. A section allocation is measured in minutes;
# SECONDS are a rest interval, and allowing them turned the instruction
# "Recovery: 60 seconds" into a structural container.
_ALLOCATION = (
    r"(?:\s*[-–—:]?\s*(?:\(\s*)?\d+\s*(?:-\s*\d+\s*)?"
    r"(?:min(?:ute)?s?|hrs?|hours?)\b\s*\)?)?"
)

_GROUP_LABEL = re.compile(
    r"^(?:" + _SECTION_WORD + r")"
    # "Accessory & Core", "Strength + Conditioning", "Mobility Circuit"
    r"(?:\s*(?:&|\+|and|\s)\s*(?:" + _SECTION_WORD + r"))*"
    r"(?:\s+(?:workout|block|session|sequence|phase|segment|part|section|"
    r"routine|lifts|lift|work|exercises|drills))?"
    # A short block identifier - "Block A", "Circuit 1". Capped at two
    # characters: at three it began eating real words, so "Recovery run:
    # 20 minutes" parsed as the section "Recovery" with identifier "run".
    r"(?:\s+[a-z0-9]{1,2})?"
    + _ALLOCATION +
    r"\s*:?\s*$",
    re.I,
)


def _is_group_label(body: str) -> bool:
    return bool(_GROUP_LABEL.match(body))


# ---------------------------------------------------------------------------
# DECORATED labels - "- **Warm-up (10 min)** - 🏋️‍♂️", "- **Power Pull (2
# min)** - 🏋️‍♂️"
# ---------------------------------------------------------------------------
#
# A generated plan routinely writes a session label - or, just as often, a
# single decorated exercise - as its own bullet, bold-wrapped, with a
# duration in parentheses and a trailing "- emoji" flourish. Structurally
# these are IDENTICAL: "**Vertical Push (25 min)**" and "**Power Pull (2
# min)**" cannot be told apart by shape, vocabulary, or (as a previous
# revision tried) an ontology lookup - "Power Pull" and "Leg Pull" are
# exercises the ontology has never heard of, so that check simply failed
# open, the exact same class of bug in a different key.
#
# What genuinely differs is one structural fact this module CAN observe: a
# real container almost always has independently-parsed exercises nested
# beneath it; a decorated single exercise almost never has children of its
# own. parse() resolves this in a second pass, once the whole document's
# parent/child relationships are known.
#
# A CLEAN bold-wrap with nothing else - "**Ankle pogo**", "**Warm-up**" -
# is not entered into this ambiguity at all: `_is_group_label` (via
# `_clean_body`'s ordinary leading+trailing "**" strip) and `_role_for_body`
# already resolve it definitely, with nothing structurally uncertain about
# it. Ambiguity is reserved for the case that actually produced the bug -
# a duration parenthetical INSIDE the bold wrap, and/or trailing "- emoji"
# decoration OUTSIDE it - either of which is required before this module
# even considers "container vs. exercise" an open question.
_EMOJI = (
    r"[\U0001F000-\U0001FFFF☀-➿←-⇿⌀-⏿"
    r"️‍]"
)
_BOLD_LABEL_LINE = re.compile(
    rf"^\*{{1,2}}(?P<inner>[^*]+?)\*{{1,2}}"
    rf"(?P<decoration>\s*[-–—]\s*(?:{_EMOJI}\s*)+)?"
    rf"\s*:?\s*$"
)
_LABEL_DURATION = re.compile(
    r"\(\s*\d+\s*(?:[-–—]\s*\d+\s*)?(?:min(?:ute)?s?|sec(?:ond)?s?)\s*\)",
    re.I,
)


def _decorated_label_shape(marker_stripped: str) -> Optional[str]:
    """
    None unless this line is bold-wrapped with nothing else on it AND
    carries a duration parenthetical and/or trailing "- emoji" decoration -
    the two signals that actually distinguish a session-block bullet from
    an ordinary bold exercise name. A clean "**Ankle pogo**" (no duration,
    no decoration) returns None here and is left to the ordinary
    `_is_group_label`/`_role_for_body` pipeline, which already resolves it
    definitely; nothing about it is structurally uncertain.

    Otherwise returns the duration/dash-stripped inner label text, for the
    reserved-grammar check the caller runs next - real exercise dosage
    ("3 x 12", "6 x 200m") always sits OUTSIDE the bold wrapper, sharing the
    line with it, so a line where the bold wrapper (plus optional duration
    and decoration) consumes the WHOLE line is never real dosage.
    """
    m = _BOLD_LABEL_LINE.match(marker_stripped.strip())
    if not m:
        return None
    inner = m.group("inner").strip()
    has_duration = bool(_LABEL_DURATION.search(inner))
    has_decoration = bool(m.group("decoration"))
    if not has_duration and not has_decoration:
        return None
    remainder = _LABEL_DURATION.sub(" ", inner)
    remainder = re.sub(r"[-–—]", " ", remainder)
    remainder = re.sub(r"\s+", " ", remainder).strip()
    return remainder


# ---------------------------------------------------------------------------
# instructions, dosage, and other non-prescription bullet content
# ---------------------------------------------------------------------------

# Each keyword pattern requires the shape an instruction actually takes (a
# colon, or a number) immediately after it, rather than matching the bare
# word - "Rest 90 seconds" is an instruction, "Rest-pause squat" is an
# exercise, and both start with "rest".
_INSTRUCTION_LINE = re.compile(
    r"^(?:"
    r"rest(?:[\s:]+\d|\s*:)"
    r"|recover(?:y(?!\s+day))?(?:[\s:]+\d|\s*:)"
    r"|tempo\s*:"
    r"|rpe\s*:?\s*\d"
    r"|note\s*:"
    r"|tip\s*:"
    r"|progression\s*(?:tip|note|notes)?\s*:"
    r"|duration\s*:"
    r"|total\s*:"
    r"|focus\s*(?:on\b|:)"
    r"|remember\s*:"
    r"|aim\s*(?:for\b|:)"
    r"|target\s*:"
    r"|cue\s*:"
    r"|breathe\b"
    r"|hydrat"
    r")",
    re.I,
)

# A line that OPENS by naming what is being left out is stating an exclusion,
# not prescribing it: "Removed: any jogging or dynamic leg swings" was read as
# a prescription of jogging.
#
# This is applied ONLY to lines that carry no dosage (see _role_for_body),
# the same guard every other whole-sentence instruction rule uses. Without it
# the rule swallowed real exercises whose names simply begin with one of these
# words - "Skip drills: 3x20", "No hands burpees: 3x10" - and they left the
# safety pipeline entirely. Anchored at the start on purpose: "Romanian
# deadlift, no jumping" still prescribes the deadlift.
_AVOIDANCE_LINE = re.compile(
    r"^(?:"
    r"(?:removed|excluded|omitted|dropped|skipped|swapped\s+out)\b"
    r"|(?:avoid(?:ing)?|omit|exclude|skip|no|not)\s+(?:any\s+|all\s+)?[a-z]"
    r")",
    re.I,
)

# "Rest day" and "Take a rest day" are not exercises; "Rest-pause dumbbell
# press" is - the phrase "rest day" itself is the signal, not the bare word
# "rest".
_REST_DAY = re.compile(r"\brest\s+day\b|\brecovery\s+day\b", re.I)

# Safety-cue sentences - "Stop if sharp pain occurs" - are conditional/
# imperative clauses ABOUT a symptom, not exercise names. The "stop" branch
# requires actual conditional/symptom syntax after the word - a bare
# "^stop\b" caught "Stop-and-go runs" and "Stop-start sprint drill" (real
# drill names) purely because they start with the same word.
_SAFETY_CUE = re.compile(
    r"^\s*stop\b(?:\s+\w+){0,3}?\s+(?:if|when)\b|"
    r"sharp\s+pain|seek\s+medical|consult\s+(?:a|your)\b|"
    r"if\s+(?:you\s+feel|it\s+hurts|pain|discomfort)",
    re.I,
)

# Coaching cues - "Keep movements controlled", "Keep the spine neutral",
# "Use a controlled tempo" - name a form correction, not a movement.
_COACHING_CUE = re.compile(
    r"\b(?:keep|use)\b.{0,30}\b(controlled|steady|neutral|tight|engaged|"
    r"strict|stable|braced|slow|smooth|aligned|straight|level|square|"
    r"balanced)\b",
    re.I,
)

# ---------------------------------------------------------------------------
# General coaching instructions - "Choose a comfortable range of motion",
# "Perform each exercise with controlled form", "Work at a conversational
# pace"
# ---------------------------------------------------------------------------
#
# These are whole instructional SENTENCES, and the previous default sent
# every one of them to PRESCRIPTION_LIKE - so during an active injury they
# became CONDITIONAL and got "repaired" into a stationary bike, destroying
# genuinely useful guidance.
#
# The grammar is deliberately anchored at BOTH ends rather than keyed off a
# keyword anywhere in the line:
#
#   1. an instructional VERB at the very start, followed by WHITESPACE, and
#   2. an instructional OBJECT - an abstraction about HOW to train (form,
#      range of motion, pace, tempo, effort...), never a movement.
#
# Both halves are load-bearing against the collision cases:
#
#   "Perform Romanian deadlifts: 3x8"  verb ok, but "Romanian deadlifts" is
#                                      not an instructional object     -> exercise
#   "Work capacity shuttle: 5 rounds"  verb ok, "capacity shuttle" is not
#                                      an instructional object          -> exercise
#   "Choose-your-pace run: 20 minutes" contains "pace", but the verb is
#                                      hyphenated into a NAME, so the
#                                      required whitespace never matches -> exercise
#   "Run 5 km" / "Press overhead: 3x8" "run"/"press" are movements and are
#                                      deliberately absent from the verb
#                                      list                             -> exercise
#
# The dosage guard below is a second, independent line of defence: anything
# carrying real sets/reps/distance/duration is prescribing work, whatever
# its wording, so it is never reduced to an instruction.
_INSTRUCTION_VERB = (
    r"(?:choose|select|pick|perform|execute|work|maintain|keep|use|focus|"
    r"move|control|adjust|listen|ensure|breathe|prioritis|prioritiz)"
)
_INSTRUCTION_OBJECT = (
    r"(?:form|technique|posture|alignment|range\s+of\s+motion|\brom\b|"
    r"pace|tempo|breathing|control|effort|intensity|depth|position|"
    r"conversational|comfortable|pain[\s-]free|full\s+range)"
)
_GENERAL_INSTRUCTION = re.compile(
    rf"^{_INSTRUCTION_VERB}\w*\s+.{{0,60}}?\b{_INSTRUCTION_OBJECT}\b",
    re.I,
)
# Real prescribed work - sets/reps, a distance, a duration. A line carrying
# any of this is programming, not commentary, so it never qualifies as a
# general instruction however it is phrased.
_PRESCRIBES_WORK = re.compile(
    r"\d+\s*[x×]\s*\d+"
    r"|\b\d+\s*(?:reps?|sets?|rounds?|min(?:ute)?s?|sec(?:ond)?s?|"
    r"km|kms|m|miles?|yards?)\b",
    re.I,
)


# Breathing and relaxation cues, which are the cooldown's own commentary -
# "Breathing/relaxation", "Relax your shoulders". Guarded by the SAME
# dosage test as every other instruction rule, which is what keeps a
# genuinely prescribed breathing drill a prescription: "Breathing drill: 3
# sets of 5 breaths" and "Diaphragmatic breathing: 2 minutes" both carry
# real dosage and are exercises, so neither reaches this rule. Anchored at
# the start of the line, so "Focus on slow breathing" is handled by the
# ordinary FOCUS instruction rule rather than by anything about breathing.
_RECOVERY_CUE = re.compile(r"^(?:relax|relaxation|breathing|breathe)\b", re.I)


def _is_general_instruction(body: str) -> bool:
    """A whole instructional sentence about HOW to train, not what to do."""
    if _PRESCRIBES_WORK.search(body):
        return False
    if _RECOVERY_CUE.match(body):
        return True
    return bool(_GENERAL_INSTRUCTION.match(body))

# A line made ENTIRELY of numbers and dosage vocabulary - "3 sets", "3 sets
# x 8 reps", "20 seconds", "8 reps each side", "8 x 100m" - carries no
# exercise of its own.
_DOSAGE_WORDS = {
    "set", "sets", "rep", "reps", "second", "seconds", "sec", "secs",
    "minute", "minutes", "min", "mins", "round", "rounds", "time", "times",
    "each", "side", "sides", "per", "of", "at", "x", "rpe", "kg", "kgs",
    "lb", "lbs", "pound", "pounds", "rest", "hold", "for",
    "m", "km", "mi", "mile", "miles", "yd", "yds", "yard", "yards", "cm",
    "meter", "meters", "metre", "metres", "contacts", "lap", "laps",
    "cal", "cals", "calorie", "calories",
}
_DOSAGE_WORD = re.compile(r"[a-z]+")
_DOSAGE_NUMBER = re.compile(r"\d")


def _is_dosage_shaped(body: str) -> bool:
    if not _DOSAGE_NUMBER.search(body):
        return False
    words = _DOSAGE_WORD.findall(body.lower())
    return bool(words) and all(w in _DOSAGE_WORDS for w in words)


def _heading_text(line: str) -> Optional[str]:
    """The heading's own text, if this line structurally IS a heading."""
    m = _MARKDOWN_HEADING.match(line)
    if m:
        return m.group(1).strip()
    m = _BOLD_HEADING.match(line)
    if m:
        return m.group(1).strip()
    if _BARE_HEADING.match(line):
        return line.strip().rstrip(":").strip()
    return None


def _section_for_heading(text: str) -> str:
    if _is_non_exercise_heading(text):
        return NON_EXERCISE
    if _WARM_UP_HEADING.search(text):
        return "warm_up"
    if _COOL_DOWN_HEADING.search(text):
        return "cool_down"
    return "general"


def _clean_body(raw: str) -> str:
    """List marker and outer emphasis stripped - for classification. The raw
    line is kept separately on the PlanItem; nothing here is destructive."""
    body = _MARKER_PREFIX.sub("", raw).strip()
    body = _EMPHASIS.sub("", body).strip()
    return body


def _role_for_body(body: str) -> str:
    if _INSTRUCTION_LINE.match(body):
        return INSTRUCTION
    # Exclusion prose, but only when it prescribes no work of its own.
    if _AVOIDANCE_LINE.match(body) and not _PRESCRIBES_WORK.search(body):
        return INSTRUCTION
    if _REST_DAY.search(body) or _SAFETY_CUE.search(body) or _COACHING_CUE.search(body):
        return INSTRUCTION
    if _is_dosage_shaped(body):
        return INSTRUCTION
    if _is_general_instruction(body):
        return INSTRUCTION
    # Safety-conservative default, unchanged: anything not PROVEN to be
    # commentary is treated as prescribed work, so an unrecognised exercise
    # fails closed rather than being waved through as prose.
    return PRESCRIPTION_LIKE


def _is_dosage_or_context(body: str) -> bool:
    """
    Proven dosage/metadata ("3 sets x 20 contacts", "RPE 7") or proven
    coaching/context ("Keep the spine neutral", "Stop if sharp pain
    occurs") - the only content a bare, marker-less indented line is
    allowed to attach to the item above it as.
    """
    return _role_for_body(body) == INSTRUCTION


def _classify_bullet_body(body: str, section: str, marker_stripped: str = "") -> Tuple[str, str]:
    """
    Returns (role, evidence). AMBIGUOUS is returned - never guessed away -
    for a decorated label with no reserved-grammar match; parse()'s second
    pass promotes it to DEFINITE_CONTAINER if independently-parsed children
    turn up beneath it.
    """
    if section == NON_EXERCISE:
        return NON_EXERCISE, "non-exercise section"

    if _is_group_label(body):
        return CONTAINER, "reserved container grammar"

    remainder = _decorated_label_shape(marker_stripped or body)
    if remainder is not None and _GROUP_LABEL.match(remainder):
        return CONTAINER, "reserved container grammar (decorated)"

    role = _role_for_body(body)
    if role == INSTRUCTION:
        return INSTRUCTION, "instruction pattern"

    if remainder is not None:
        return AMBIGUOUS, "decorated label shape, no reserved grammar, no children yet"

    return PRESCRIPTION_LIKE, "exercise-shaped"


def classify_single_line(line: str) -> str:
    """
    Structural role for one line, with no plan-wide section or sibling
    context. Used where only a single line is available - contraindications.
    classify_line() judges one line at a time, and the safety audit
    validates one candidate exercise name at a time (never a full plan).

    Without a document, a decorated label can never gain "children" - so a
    bold-wrapped, no-reserved-grammar single line always resolves AMBIGUOUS
    here, exactly as it should: this function is not the place ambiguity
    gets resolved, `safety_subjects()`/`quality_subjects()` are.
    """
    text = (line or "").strip()
    if not text:
        return PROSE
    if _heading_text(text) is not None:
        return HEADING
    marker_stripped = _MARKER_PREFIX.sub("", text).strip()
    body = _clean_body(text)
    role, _evidence = _classify_bullet_body(body, "general", marker_stripped)
    return role


def parse(plan_text: str) -> List[PlanItem]:
    """
    Break a plan into structural items, in original order.

    Two passes. The first walks lines top to bottom, exactly as before,
    building one PlanItem per bulleted/numbered line plus one per bare
    (marker-less) indented line that is not proven dosage/coaching context
    for the item above it - and additionally records parent/child
    relationships using an ancestor stack, so a decorated label bullet
    followed by independently-parsed nested exercises knows it has them.

    The second pass promotes any item still AMBIGUOUS after the first pass
    to DEFINITE_CONTAINER if it gained child items - the only thing that
    turns "Power Pull (2 min)" (no children: stays ambiguous) into the same
    verdict as "Vertical Push (25 min)" followed by real nested exercises
    (has children: a container). Nothing here asks what "Power Pull" means.
    """
    lines = (plan_text or "").splitlines()
    items: List[PlanItem] = []
    section = "general"
    i = 0
    n = len(lines)

    # Ancestor stack for parent/child linkage: (indent, item) pairs, deepest
    # last. A new bulleted item pops every entry at >= its own indent (those
    # are siblings-or-shallower, not ancestors) before attaching to whatever
    # remains - which is what lets two sibling bullets at the same indent
    # (two exercises under one label) both end up as children of the SAME
    # parent, rather than the second nesting under the first.
    stack: List[Tuple[int, PlanItem]] = []

    # `owner`/`block_floor` are a SEPARATE, simpler mechanism for dosage-fold
    # eligibility only - deliberately not derived from the stack. A bare
    # coaching-cue line ("Keep the knee aligned") sitting at the SAME indent
    # as the exercise it describes (both indented once under a container)
    # must still fold into that exercise; the stack's sibling-popping logic
    # would otherwise treat it as a new sibling and lose the association.
    # `block_floor` is the indent of whatever bulleted/numbered line most
    # recently opened the current indented run and stays pinned there;
    # `owner` is whichever eligible item most recently became a candidate to
    # receive dosage within that run.
    owner: Optional[PlanItem] = None
    block_floor = -1

    def attach_to_parent(item: PlanItem) -> None:
        while stack and stack[-1][0] >= item.indent:
            stack.pop()
        if stack:
            parent = stack[-1][1]
            item.parent_id = parent.line_numbers[0]
            parent.child_ids.append(item.line_numbers[0])
        stack.append((item.indent, item))

    while i < n:
        raw = lines[i]
        stripped = raw.strip()

        if not stripped:
            owner = None
            block_floor = -1
            i += 1
            continue

        heading_text = _heading_text(raw)
        if heading_text is not None:
            section = _section_for_heading(heading_text)
            owner = None
            block_floor = -1
            i += 1
            continue

        indent = len(raw) - len(raw.lstrip())
        bullet_match = _BULLET_OR_NUMBERED.match(raw)

        if bullet_match:
            marker = bullet_match.group("marker")
            body = _clean_body(raw)
            marker_stripped = _MARKER_PREFIX.sub("", raw).strip()
            role, evidence = _classify_bullet_body(body, section, marker_stripped)
            item = PlanItem(role=role, line_numbers=[i], raw_lines=[raw],
                            body=body, dosage_lines=[], section=section,
                            marker=marker, evidence=evidence, indent=indent)
            attach_to_parent(item)
            items.append(item)
            owner = item if role in (PRESCRIPTION_LIKE, AMBIGUOUS) else None
            block_floor = indent
            i += 1
            continue

        # No marker. Only relevant while inside an indented run opened by a
        # preceding bulleted/numbered line - unindented, unopened bare text
        # is ordinary prose and can never become a candidate.
        if block_floor < 0 or indent <= block_floor:
            owner = None
            block_floor = -1
            i += 1
            continue

        body = _clean_body(raw)
        if owner is not None and _is_dosage_or_context(body):
            owner.line_numbers.append(i)
            owner.raw_lines.append(raw)
            owner.dosage_lines.append(stripped)
            if owner.role == AMBIGUOUS:
                # Dosage/context continuation owned by the item is strong
                # prescription evidence on its own - it no longer needs
                # pass 2's children check.
                owner.role = PRESCRIPTION_LIKE
                owner.evidence = "owns dosage/context continuation"
            i += 1
            continue

        # Title-like / not proven continuation - its own independent item,
        # even though it carries no marker of its own.
        role, evidence = _classify_bullet_body(body, section, stripped)
        item = PlanItem(role=role, line_numbers=[i], raw_lines=[raw],
                        body=body, dosage_lines=[], section=section,
                        marker=None, evidence=evidence, indent=indent)
        attach_to_parent(item)
        items.append(item)
        owner = item if role in (PRESCRIPTION_LIKE, AMBIGUOUS) else None
        i += 1

    # Pass 2: an AMBIGUOUS item that groups actual prescription WORK is
    # structurally a container, not a leaf.
    #
    # The test is the TYPE of its children, never merely that it has some.
    # `bool(child_ids)` was a real safety bypass: a decorated unknown
    # exercise with nothing beneath it but its own dosage bullet
    # ("- **Power Pull (2 min)**" / "  - 3 sets x 8 reps") was promoted to a
    # container purely because that dosage line existed as a child item -
    # which dropped it out of safety_subjects() entirely and let an
    # unclassifiable movement reach the user with audit_clean=True.
    # Dosage, coaching cues and other commentary say nothing about whether
    # their parent is a section; only nested prescription work does.
    by_id = _items_by_id(items)
    for item in items:
        if item.role == AMBIGUOUS and _contains_prescription_work(item, by_id):
            item.role = CONTAINER
            item.evidence = "groups independently-parsed nested prescription work"

    return items


def _items_by_id(items: List[PlanItem]) -> dict:
    return {it.line_numbers[0]: it for it in items}


def _contains_prescription_work(item: PlanItem, by_id: dict,
                                seen: Optional[set] = None) -> bool:
    """
    Does this item group any actual prescribed work, directly or through a
    nested container?

    Recursive rather than a single flat check so an intermediate container
    resolves correctly - "Power Segment" > "Pull Focus" > "Seated cable row"
    must make BOTH outer labels containers - and order-independent, so it
    does not matter that pass 2 walks items in document order: an AMBIGUOUS
    child already counts as prescription work in its own right (it is
    exactly the "might be an exercise" case), so no child needs to have
    been promoted first for its parent to see it.

    DEFINITE_INSTRUCTION / DEFINITE_NON_EXERCISE children are deliberately
    NOT evidence - see the pass-2 comment above.
    """
    seen = seen if seen is not None else set()
    key = item.line_numbers[0]
    if key in seen:          # parents are always earlier lines, so this is
        return False         # unreachable in practice - kept as a guard.
    seen.add(key)

    for child_id in item.child_ids:
        child = by_id.get(child_id)
        if child is None:
            continue
        if child.role in (PRESCRIPTION_LIKE, AMBIGUOUS):
            return True
        if child.role == CONTAINER and _contains_prescription_work(child, by_id, seen):
            return True
    return False


# Roles a child may have for its lines to belong to its PARENT's block -
# dosage, coaching cues, notes. Anything else (a prescription, an ambiguous
# leaf, a nested container) is an independent item that must survive its
# parent being removed, and must be audited in its own right.
_OWNED_CONTEXT_ROLES = (DEFINITE_INSTRUCTION, DEFINITE_NON_EXERCISE)


def owned_block_lines(item: PlanItem, items: List[PlanItem]) -> List[int]:
    """
    THE canonical answer to "which lines belong to this item's block?", for
    plan_repair's removal and replacement.

    An item owns its own lines (the primary line plus any marker-less
    dosage/context continuations already folded in by parse()), PLUS the
    lines of any child items that are themselves definite dosage/context -
    a nested "- 3 sets x 8 reps" or "- Keep the spine neutral" bullet
    belongs to the exercise above it and must disappear with it, rather
    than being left behind as orphaned dosage under nothing.

    It never owns a child that is prescription work: removing an ambiguous
    parent label must not silently delete an independently-parsed exercise
    nested under it, which would take that exercise out of the plan without
    it ever being audited on its own terms.

    One helper, one definition - plan_repair must not derive block
    membership any other way.
    """
    by_id = _items_by_id(items)
    owned = set(item.line_numbers)
    stack = list(item.child_ids)
    seen = set()
    while stack:
        child_id = stack.pop()
        if child_id in seen:
            continue
        seen.add(child_id)
        child = by_id.get(child_id)
        if child is None or child.role not in _OWNED_CONTEXT_ROLES:
            continue
        owned.update(child.line_numbers)
        stack.extend(child.child_ids)
    return sorted(owned)


def prescription_candidates(items: List[PlanItem]) -> List[PlanItem]:
    """Convenience filter for definite prescriptions only. Most callers
    that used to want this now want `safety_subjects()` or
    `quality_subjects()` instead, which also account for AMBIGUOUS items."""
    return [it for it in items if it.role == PRESCRIPTION_LIKE]


def safety_subjects(items: List[PlanItem], constraints_active: bool = True) -> List[PlanItem]:
    """
    The canonical, single set of items any safety entry point
    (contraindications.assess_plan, audit_against_profiles) may act on.

    PRESCRIPTION_LIKE items are always included. AMBIGUOUS items - a
    decorated leaf this module could not structurally resolve either way -
    are included only when a constraint is actually active: for a healthy
    user there is nothing to fail closed against, so an ambiguous item is
    simply left alone rather than forced through movement classification it
    does not need. Definite containers, instructions and non-exercise
    content are never included - that is exactly what "definite" means.

    This is the ONLY place that policy is decided. Nothing downstream
    should filter `item.role` directly for a safety purpose.
    """
    subjects = [it for it in items if it.role == PRESCRIPTION_LIKE]
    if constraints_active:
        subjects += [it for it in items if it.role == AMBIGUOUS]
    subjects.sort(key=lambda it: it.line_numbers[0])
    return subjects


def quality_subjects(items: List[PlanItem]) -> List[PlanItem]:
    """
    The canonical set plan_quality should count as prescribed work:
    definite prescriptions, plus ambiguous items - which, after parse()'s
    second pass, are by construction always LEAVES with no children, so a
    decorated container is never double-counted through its own label and
    then again through its (already independently counted) children.

    Never definite containers, non-exercise content or instructions.
    """
    subjects = [it for it in items if it.role in (PRESCRIPTION_LIKE, AMBIGUOUS)]
    subjects.sort(key=lambda it: it.line_numbers[0])
    return subjects
