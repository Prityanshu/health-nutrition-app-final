"""
Turn an unsafe plan into a safe, usable one.

THE PIPELINE THIS REPLACES
--------------------------
    LLM  ->  audit  ->  delete unsafe lines  ->  return

which is correct but frequently useless: a 6/10 hamstring removed 6 of 10
exercises and the user received four items and an apology.

    LLM  ->  audit  ->  replace where possible, remove where not
                    ->  audit the replacements
                    ->  assess plan quality
                    ->  regenerate if inadequate (bounded)
                    ->  FINAL audit
                    ->  return

ORDER OF AUTHORITY
------------------
Safety always wins. Quality can ask for a regeneration; it can never keep an
exercise the audit rejected, and if regeneration fails the sparse-but-safe
plan ships with a note saying so.

NOTHING HERE DECIDES WHAT IS DANGEROUS
--------------------------------------
Every safety judgement is delegated:

    what an exercise is        movement_ontology.classify_prescribed
    what an injury restricts   injury_taxonomy.InjuryProfile
    is this line acceptable    contraindications.audit_against_profiles

This module only sequences them.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Each attempt is a full model call, so this is a real cost as well as a
# termination guarantee.
MAX_REGENERATIONS = 2

# Patterns that say nothing about what an exercise trains, so they must not be
# treated as the "purpose" to preserve when choosing a replacement.
_NON_PURPOSE = {"unilateral", "isometric", "impact", "maximal_effort",
                "cardio_intensity", "end_range_stretch", "low_impact"}

# When an exercise IS its prohibited pattern, nothing of its purpose survives -
# an RDL is only a hip hinge. Rather than dropping straight to a bike, look for
# a pattern that trains the same area by different mechanics. This is a
# PURPOSE mapping, not a safety one: every candidate it produces is still put
# through the audit, and is discarded if that rejects it.
_RELATED_PURPOSE = {
    "hip_hinge": {"hip_extension"},          # bridges load the posterior chain
    "squat": {"knee_extension", "hip_extension"},
    "lunge": {"knee_extension", "hip_extension"},
    "knee_flexion": {"hip_extension"},
    "knee_extension": {"hip_extension"},
    "running": {"low_impact"},
    "high_speed": {"low_impact"},
    "jumping": {"low_impact"},
    "cutting": {"low_impact"},
    "vertical_push": {"horizontal_push"},    # press below shoulder height
    "horizontal_push": {"vertical_push"},
    "vertical_pull": {"horizontal_pull"},
    "horizontal_pull": {"vertical_pull"},
    "spinal_flexion": {"anti_rotation"},     # brace instead of curl
    "spinal_rotation": {"anti_rotation"},
    "calf_raise": {"low_impact"},
    "hip_adduction": {"hip_abduction"},
    "elbow_flexion": {"horizontal_pull"},
}


@dataclass
class Replacement:
    original: str
    replacement: Optional[str]
    reason: str
    prohibited: List[str] = field(default_factory=list)
    preserved: List[str] = field(default_factory=list)

    @property
    def substituted(self) -> bool:
        return self.replacement is not None


@dataclass
class RepairResult:
    plan: str
    removed: List[str] = field(default_factory=list)
    replacements: List[Replacement] = field(default_factory=list)
    regenerations: int = 0
    quality: Optional[dict] = None
    still_inadequate: bool = False
    audit_clean: bool = True

    def as_dict(self) -> dict:
        return {
            "removed": list(self.removed),
            "replacements": [
                {"original": r.original, "replacement": r.replacement,
                 "reason": r.reason, "prohibited": r.prohibited}
                for r in self.replacements
            ],
            "regenerations": self.regenerations,
            "quality": self.quality,
            "still_inadequate": self.still_inadequate,
            "audit_clean": self.audit_clean,
        }


# ---------------------------------------------------------------------------
# replacement
# ---------------------------------------------------------------------------

def _find_replacement(line: str, profiles: list, equipment: str,
                      already_used: Optional[Set[str]] = None) -> Replacement:
    """
    Find a safe exercise that does the same job as one being removed.

    Purpose is derived from the movement itself: whatever the exercise trained
    MINUS whatever made it unsafe. A bent-over row is removed for its hip
    hinge, but its job was horizontal pulling, so the replacement must still
    pull horizontally - otherwise the session silently loses a movement it
    needed and the plan degrades even though the count looks fine.
    """
    from app.services import exercise_catalogue as catalogue
    from app.services import movement_ontology as ontology
    from app.services.contraindications import audit_against_profiles

    already_used = already_used or set()
    movement = ontology.classify_prescribed(line)
    restricted: Set[str] = set()
    for profile in profiles:
        restricted |= profile.restricted_patterns()

    prohibited = movement.patterns & restricted
    purpose = movement.patterns - restricted - _NON_PURPOSE

    reason = (
        f"removes {ontology.describe(prohibited)}"
        if prohibited else "flagged by the safety audit"
    )

    if not purpose:
        # Nothing survives - the exercise WAS the prohibited pattern (a sprint
        # is only high-speed running). Try a related pattern that trains the
        # same area differently before dropping to plain conditioning.
        related: Set[str] = set()
        for pattern in prohibited:
            related |= _RELATED_PURPOSE.get(pattern, set())
        related -= restricted

        if related:
            near = catalogue.candidates_for(
                equipment=equipment, require_patterns=related,
                forbid_patterns=restricted,
            )
            near.sort(key=lambda c: (c.name in already_used, len(c.patterns - related)))
            for candidate in near:
                if audit_against_profiles(candidate.name, profiles):
                    continue
                return Replacement(
                    original=line, replacement=candidate.name,
                    reason=f"{reason}; this trains the same area without it",
                    prohibited=sorted(prohibited), preserved=sorted(related),
                )

        fallback = catalogue.candidates_for(
            purpose="conditioning", equipment=equipment, forbid_patterns=restricted,
        )
        # Prefer something not already used. Four "stationary bike" lines is
        # technically safe and obviously a worse plan, and the quality
        # evaluator flags it as repetitive - better not to create it.
        fallback.sort(key=lambda c: c.name in already_used)
        for candidate in fallback:
            if candidate.name in already_used and any(
                f.name not in already_used for f in fallback
            ):
                continue
            if not audit_against_profiles(candidate.name, profiles):
                return Replacement(
                    original=line, replacement=candidate.name,
                    reason=f"{reason}; no equivalent exists, so this keeps the "
                           f"conditioning without the risk",
                    prohibited=sorted(prohibited),
                )
        return Replacement(line, None, reason, sorted(prohibited))

    # Candidates that keep the purpose and avoid everything restricted.
    shortlist = catalogue.candidates_for(
        equipment=equipment,
        require_patterns=purpose,
        forbid_patterns=restricted,
    )
    # Prefer the closest match - most shared purpose, fewest extra patterns.
    shortlist.sort(
        key=lambda c: (c.name in already_used,
                       -len(c.patterns & purpose),
                       len(c.patterns - purpose))
    )

    for candidate in shortlist:
        # The catalogue proposes; the audit disposes. A candidate is only
        # accepted if the same engine that rejected the original clears it,
        # against ALL active injuries rather than just the one that triggered
        # the removal.
        if audit_against_profiles(candidate.name, profiles):
            logger.debug("Candidate %r rejected by audit", candidate.name)
            continue
        return Replacement(
            original=line, replacement=candidate.name, reason=reason,
            prohibited=sorted(prohibited), preserved=sorted(purpose),
        )

    return Replacement(line, None, reason, sorted(prohibited), sorted(purpose))


# Matches "Exercise Name: 4x8 @ RPE 7" or "Exercise Name - 4x8 @ RPE 7" (en/em
# dash) - the two separators real generated plans actually use between a name
# and its prescription. Deliberately NOT a plain ASCII hyphen: exercise names
# routinely contain one ("Chest-supported row", "Bench-supported row"), and
# splitting on it would cut a legitimate name in half instead of finding a
# dosage.
_DOSAGE_SPLIT = re.compile(r"^(.*?)\s*[:–—]\s*(.+)$")


def _dosage_suffix(original_line: str) -> str:
    """
    Whatever came after the exercise name - sets, reps, rest, RPE, tempo,
    side - so a substitution can carry the original prescription forward
    instead of silently dropping it. "Bench-supported row: 4x8 @ RPE 7, rest
    90 sec" keeps "4x8 @ RPE 7, rest 90 sec" regardless of which exercise
    replaces the name before the separator. Returns "" when the line never
    had a dosage to begin with - nothing is fabricated that was not there.
    """
    body = re.sub(r"^\s*(?:[-*•+]|\d+[.)])?\s*", "", original_line).strip()
    body = re.sub(r"^[*_]{1,2}", "", body).strip()
    m = _DOSAGE_SPLIT.match(body)
    if not m:
        return ""
    dosage = m.group(2).strip()
    dosage = re.sub(r"^\*+|\*+$", "", dosage).strip()  # leftover bold marker
    # Pure decoration is not a prescription. A decorated label splits on its
    # en-dash into name + "🏋️‍♂️", and carrying that forward produced
    # "Stationary bike, steady pace: 🏋️‍♂️" - a dosage of nothing. Real
    # dosage always contains a digit or a word ("4x8", "RPE 7", "each side").
    if not re.search(r"[0-9A-Za-z]", dosage):
        return ""
    return dosage


# ---------------------------------------------------------------------------
# dosage modality - a prescription only transfers to a replacement that is
# measured the same way
# ---------------------------------------------------------------------------
#
# The dosage used to be copied across verbatim, which produced prescriptions
# that cannot be performed:
#
#     "Box jumps - 3 x 5"          ->  "Brisk walk: 3 x 5"
#     "Sprint intervals - 6 x 20m" ->  "Brisk walk: 6 x 20 m"
#     "Cat-Cow: 2 x 10"            ->  "Stationary bike: 2 x 10"
#
# Sets-and-reps belong to resistance work, a duration belongs to timed work,
# and a distance belongs to locomotion. Carrying one onto the other is not a
# smaller safety problem, it is an unusable plan.

# "m" is spelt out carefully: "min" must not read as metres.
_DOSAGE_DISTANCE = re.compile(
    r"\d+\s*(?:m|km|kms|metres?|meters?|miles?|yards?|yds?)(?![a-z])", re.I)
# Sets x duration - "3 x 45 sec". Valid for anything held for time.
_DOSAGE_SETS_TIME = re.compile(
    r"\d+\s*[x×]\s*\d+\s*(?:s|sec|secs|second|seconds|min|mins|minute|minutes)"
    r"(?![a-z])", re.I)
# Sets x reps - "4 x 8". Checked after the two above, so "6 x 20 m" and
# "3 x 45 sec" are not mistaken for repetitions.
_DOSAGE_SETS_REPS = re.compile(r"\d+\s*[x×]\s*\d+|\b\d+\s*(?:reps?|sets?|rounds?)\b",
                               re.I)
_DOSAGE_TIME = re.compile(
    r"\b\d+\s*(?:s|sec|secs|second|seconds|min|mins|minute|minutes|hrs?|hours?)"
    r"(?![a-z])", re.I)

# Catalogue purposes whose exercises are prescribed by TIME, not repetitions.
# The ontology's `isometric` pattern is checked alongside it, because a plank
# is held for time whatever slot it fills - its catalogue purpose is "core".
_TIMED_PURPOSES = {"conditioning", "isometric"}


def _dosage_modality(dosage: str) -> Optional[str]:
    """
    How this dosage measures work: distance, time, or repetitions.

    None means it carries no measurement at all - "each side", "@ RPE 7" -
    which is safe to keep beside anything.
    """
    if not dosage:
        return None
    if _DOSAGE_DISTANCE.search(dosage):
        return "distance"
    if _DOSAGE_SETS_TIME.search(dosage):
        return "time"
    if _DOSAGE_SETS_REPS.search(dosage):
        return "reps"
    if _DOSAGE_TIME.search(dosage):
        return "time"
    return None


def _is_timed_exercise(exercise_name: str) -> Optional[bool]:
    """
    Is this replacement prescribed by time rather than repetitions?

    None when the name is not in the catalogue at all - the caller then
    refuses to transfer anything, because an unknown modality is not a
    licence to guess.
    """
    from app.services import exercise_catalogue as catalogue
    for candidate in catalogue._RAW:
        if candidate.name == exercise_name:
            return (candidate.purpose in _TIMED_PURPOSES
                    or "isometric" in (candidate.patterns or set()))
    return None


def _dosage_transfers(dosage: str, replacement: str) -> bool:
    """
    May this dosage be carried onto this replacement?

    Distance never transfers: nothing in the catalogue is prescribed by
    distance, and a sprint's "6 x 20 m" is meaningless on a squat or a bike.
    Time transfers only to work that is held or sustained; repetitions only
    to work that is counted. When it does not transfer the dosage is dropped
    rather than converted - inventing "10 min" for an exercise the user never
    asked for would be fabricating a prescription.
    """
    modality = _dosage_modality(dosage)
    if modality is None:
        return True
    if modality == "distance":
        return False
    timed = _is_timed_exercise(replacement)
    if timed is None:
        return False
    return timed if modality == "time" else not timed


def _apply(plan_text: str, decisions: Dict[int, Replacement]) -> str:
    """
    Rewrite the plan, keeping the original bullet formatting.

    Operates on whole prescription blocks - a bulleted line plus any dosage
    continuation lines beneath it (plan_structure.parse) - not on isolated
    lines. A removal takes its dosage lines with it instead of leaving
    "3x20 seconds" behind with nothing above it; a replacement keeps them,
    since sets/reps/tempo apply just as well to whatever exercise now heads
    the block. Plans with no continuation lines - every existing single-line
    "Name: dosage" plan - behave exactly as before.
    """
    from app.services import plan_structure as structure

    lines = plan_text.splitlines()
    items = structure.parse(plan_text)
    item_by_line: Dict[int, structure.PlanItem] = {}
    for item in items:
        for ln in item.line_numbers:
            item_by_line[ln] = item

    # Resolve every decision to the canonical owned block FIRST, then emit
    # in strict document order. `plan_structure.owned_block_lines` is the
    # single definition of block membership: the item's own lines plus any
    # nested dosage/coaching-context children, never a nested exercise.
    #
    # Emitting in document order (rather than writing a block's remaining
    # lines out immediately after its replacement) matters because an
    # item's owned context lines are not necessarily contiguous - an
    # independent exercise can sit between an exercise and a later "RPE 7"
    # bullet that still belongs to the first one - and appending eagerly
    # would silently reorder the plan.
    dropped: Set[int] = set()
    replaced: Dict[int, Replacement] = {}
    for index, decision in decisions.items():
        item = item_by_line.get(index)
        block = structure.owned_block_lines(item, items) if item else [index]
        if decision.replacement is None:
            dropped.update(block)   # nothing safe does this job; block goes
        else:
            replaced[index] = decision   # owned context lines simply survive

    out = []
    for index, raw in enumerate(lines):
        if index in dropped:
            continue
        decision = replaced.get(index)
        if decision is None:
            out.append(raw)
            continue
        prefix = re.match(r"^\s*(?:[-*•+]|\d+[.)])?\s*", raw).group(0)
        dosage = _dosage_suffix(raw)
        if dosage and not _dosage_transfers(dosage, decision.replacement):
            dosage = ""
        line = f"{decision.replacement}: {dosage}" if dosage else decision.replacement
        out.append(f"{prefix}{line}")
    return "\n".join(out)


def _strip_blocks(plan_text: str, line_numbers: Set[int]) -> str:
    """
    Remove these lines, taking any owned dosage/context lines with them.

    Used by the final audit passes below - removing just the primary line of
    a block that has separate dosage lines (folded-in continuations OR
    nested dosage bullets) would leave them orphaned in the returned plan.
    Block membership comes from the same canonical
    `plan_structure.owned_block_lines` that `_apply` uses; there is
    deliberately no second definition of what a block is.
    """
    from app.services import plan_structure as structure

    lines = plan_text.splitlines()
    items = structure.parse(plan_text)
    item_by_line = {ln: item for item in items for ln in item.line_numbers}
    to_remove: Set[int] = set()
    for ln in line_numbers:
        item = item_by_line.get(ln)
        to_remove.update(structure.owned_block_lines(item, items) if item else [ln])
    return "\n".join(line for i, line in enumerate(lines) if i not in to_remove)


# ---------------------------------------------------------------------------
# regeneration
# ---------------------------------------------------------------------------

def regeneration_brief(profiles: list, quality: Optional[dict]) -> str:
    """
    Tell the model what to avoid in terms of MOVEMENT, not exercise names.

    Naming exercises invites a synonym: forbid "Romanian deadlift" and the
    next attempt returns a stiff-leg deadlift. Describing the shape of the
    movement closes that off, and it matches how the audit actually judges.
    """
    from app.services import movement_ontology as ontology

    descriptions = {
        "hip_hinge": "loaded hip hinging - any bent-over position at the waist "
                     "under load, whatever you are holding",
        "squat": "deep knee bending under load",
        "lunge": "split-stance work loading the front leg",
        "knee_flexion": "bending the knee against resistance",
        "knee_extension": "straightening the knee against resistance",
        "high_speed": "high-speed running, sprinting, accelerations and maximal velocity work",
        "running": "running and jogging of any distance or pace",
        "jumping": "jumping, hopping, bounding and landing",
        "cutting": "changes of direction, agility drills and cutting",
        "impact": "repeated ground impact",
        "overhead": "taking the arms overhead under load",
        "vertical_push": "pressing overhead",
        "horizontal_push": "pressing away from the chest",
        "vertical_pull": "pulling down from overhead",
        "horizontal_pull": "rowing toward the torso",
        "spinal_flexion": "rounding or curling the spine under load",
        "spinal_rotation": "twisting the trunk under load",
        "axial_load": "carrying weight on the spine",
        "gripping": "hard gripping",
        "elbow_flexion": "loaded elbow bending",
        "hip_adduction": "squeezing the legs together against resistance",
        "hip_abduction": "pushing the legs apart against resistance",
        "calf_raise": "loaded calf raising",
        "end_range_stretch": "stretching into end range",
        "maximal_effort": "maximal or near-maximal effort, sets to failure",
        "cardio_intensity": "sustained high-intensity conditioning",
    }

    restricted: Set[str] = set()
    for profile in profiles:
        restricted |= profile.restricted_patterns()

    # No injury profiles means nothing was removed for safety - this is a
    # pure quality regeneration (wrong duration, wrong sport/goal alignment,
    # unmeasurable progression...). The two cases need different opening
    # wording: claiming a safety removal that never happened would send the
    # model looking for a restriction that does not exist.
    if restricted:
        lines = ["The previous plan had to have exercises removed for safety.",
                 "Produce a revised plan that AVOIDS these movement types entirely:"]
        for pattern in sorted(restricted):
            lines.append(f"  - {descriptions.get(pattern, pattern.replace('_', ' '))}")

        lines.append("")
        lines.append("This applies to warm-ups, cool-downs and recovery days too. "
                     "Avoiding a named exercise is not enough - any variation with "
                     "the same movement is equally out.")

        if quality and quality.get("issues"):
            lines.append("")
            lines.append("The filtered plan was also inadequate:")
            for issue in quality["issues"]:
                lines.append(f"  - {issue}")
            lines.append("Build a full session from what IS available rather than a short one.")
    else:
        lines = ["The previous plan did not meet the brief. Fix the following "
                 "without changing anything that already works:"]
        for issue in (quality or {}).get("issues", []):
            lines.append(f"  - {issue}")

    safe = sorted({p for prof in profiles for p in prof.keep_patterns()} - restricted)
    if safe:
        lines.append("")
        lines.append("These are available and should carry the session: "
                     + ", ".join(descriptions.get(p, p.replace("_", " ")) for p in safe[:8]))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# the orchestrator
# ---------------------------------------------------------------------------

def repair(
    plan_text: str,
    constraints: List[str],
    equipment: str = "gym",
    requested_minutes: Optional[int] = None,
    goal: Optional[str] = None,
    sport: Optional[str] = None,
    level: Optional[str] = None,
    regenerate: Optional[Callable[[str], Optional[str]]] = None,
) -> RepairResult:
    """
    Make a generated plan safe, then make it usable if it can be.

    Runs the same way whether or not there are injury profiles. There used to
    be a separate early-return for a healthy user - evaluate quality, skip
    straight to returning it - but that meant the ENTIRE quality/regeneration
    loop below (duration realism, goal and sport alignment, equipment
    violations, measurable progression) only ever ran for someone with an
    injury constraint, and silently never for anyone else. `_repair_once`
    already handles an empty profile list correctly - the injury audit just
    finds nothing to flag - so the two paths were doing the same work with
    extra code, for a worse result on the common case.

    `regenerate` is a callback taking a brief and returning a new plan, so this
    module has no knowledge of the model or its client. Omit it and repair
    still runs - it simply cannot regenerate, which is exactly what the tests
    want and what an offline caller needs.
    """
    from app.services import injury_taxonomy as taxonomy
    from app.services.contraindications import (
        VERDICT_CONDITIONAL, assess_plan, audit_against_profiles,
    )

    profiles = taxonomy.profiles_for(constraints)

    attempt = 0
    result = _repair_once(plan_text, profiles, equipment, requested_minutes, goal, sport, level)

    while (
        regenerate is not None
        and not result.quality.get("adequate", True)
        and attempt < MAX_REGENERATIONS
    ):
        attempt += 1
        brief = regeneration_brief(profiles, result.quality)
        logger.info("Plan inadequate after filtering (%s); regenerating (%d/%d)",
                    "; ".join(result.quality.get("issues", [])), attempt, MAX_REGENERATIONS)
        try:
            fresh = regenerate(brief)
        except Exception as e:
            logger.error("Regeneration attempt %d failed: %s", attempt, e, exc_info=True)
            break
        if not fresh or not fresh.strip():
            break

        candidate_result = _repair_once(fresh, profiles, equipment,
                                        requested_minutes, goal, sport, level)
        candidate_result.regenerations = attempt

        # Keep whichever is better, never whichever is newer. A regeneration
        # that comes back worse must not replace a better filtered plan.
        if _is_better(candidate_result, result):
            result = candidate_result
        else:
            result.regenerations = attempt
            logger.info("Regeneration %d was not an improvement; keeping the earlier plan.",
                        attempt)
        if result.quality.get("adequate"):
            break

    # FINAL audit, sweep one: strip whatever is still wrong from the plan
    # BEFORE the adjustment note is appended below - the note describes
    # `result.removed`/`result.replacements`, so it has to be built from the
    # final set of removals, not before them. Two separate sweeps, not one:
    # a pattern-clash violation and an unclassified prescription candidate
    # during an active injury are different failure modes, and a plan can
    # carry either without the other. `_strip_blocks` removes each finding's
    # whole prescription block (any dosage lines with it), never just the
    # one line a finding happened to point at.
    leftover = audit_against_profiles(result.plan, profiles)
    if leftover:
        logger.error("Final audit found %d prohibited line(s) after repair - removing.",
                     len(leftover))
        result.plan = _strip_blocks(result.plan, {f["line_no"] for f in leftover})
        result.removed += [f["line"] for f in leftover]

    unresolved = [v for v in assess_plan(result.plan, profiles)
                  if v["verdict"] == VERDICT_CONDITIONAL]
    if unresolved:
        logger.error("Final audit found %d unresolved conditional item(s) after "
                     "repair - removing.", len(unresolved))
        result.plan = _strip_blocks(result.plan, {v["line_no"] for v in unresolved})
        result.removed += [v["line"] for v in unresolved]

    result.still_inadequate = not result.quality.get("adequate", True)

    # The repair log is NOT appended to the workout any more. Every swap and
    # removal is already in RepairResult.as_dict(), and duplicating it inside
    # the Markdown buried the actual session under a wall of internal
    # bookkeeping. The caller decides what, if anything, to show.

    # FINAL audit: audit_clean is measured against the EXACT string this
    # function is about to return.
    result.audit_clean = (
        not audit_against_profiles(result.plan, profiles)
        and not any(v["verdict"] == VERDICT_CONDITIONAL
                    for v in assess_plan(result.plan, profiles))
    )
    return result


def _repair_once(plan_text, profiles, equipment, requested_minutes, goal, sport, level=None):
    """One pass: audit, replace what can be replaced, remove the rest, assess."""
    from app.services import plan_quality
    from app.services.contraindications import audit_against_profiles

    from app.services.contraindications import VERDICT_CONDITIONAL, assess_plan

    findings = audit_against_profiles(plan_text, profiles)
    decisions: Dict[int, Replacement] = {}
    used: Set[str] = set()
    for finding in findings:
        if finding["line_no"] in decisions:
            continue
        decision = _find_replacement(finding["line"], profiles, equipment, used)
        if decision.replacement:
            used.add(decision.replacement)
        decisions[finding["line_no"]] = decision

    # CONDITIONAL lines: the ontology could not read them and an injury is
    # active. Silently keeping them is the "unknown means safe" default, which
    # is the most likely way something genuinely dangerous reaches the user -
    # a novel name for a restricted movement classifies as nothing at all.
    # They are swapped for a known-safe exercise rather than trusted.
    conditional = [v for v in assess_plan(plan_text, profiles)
                   if v["verdict"] == VERDICT_CONDITIONAL]
    for verdict in conditional:
        if verdict["line_no"] in decisions:
            continue
        # FAIL CLOSED BY REMOVAL, never by substitution.
        #
        # A CONDITIONAL line is one the ontology could not read. Its movement
        # PURPOSE is therefore unknown, and _find_replacement() has nothing to
        # preserve - it fell through to its generic conditioning fallback and
        # invented an exercise out of nothing. That is how "Warm-up - 10 min"
        # became "Stationary bike, steady pace: 10 min" and a whole session
        # turned into four different cardio machines.
        #
        # Removing the line is the honest fail-closed action: it does not
        # pretend to know what the user was meant to be doing. Recognised
        # unsafe exercises are still substituted above, because there the
        # purpose IS known.
        decisions[verdict["line_no"]] = Replacement(
            original=verdict["line"], replacement=None,
            reason=("could not be classified while an injury is active - "
                    "removed rather than kept unverified"),
        )
        logger.info("Unclassifiable line removed under active constraint: %r",
                    verdict["line"][:60])

    repaired = _apply(plan_text, decisions)
    replacements = [d for d in decisions.values() if d.substituted]
    removed = [d.original for d in decisions.values() if not d.substituted]

    quality = plan_quality.evaluate(
        repaired, removed_count=len(removed), replaced_count=len(replacements),
        requested_minutes=requested_minutes, goal=goal, sport=sport,
        equipment=equipment, level=level,
    )
    return RepairResult(
        plan=repaired, removed=removed, replacements=replacements,
        quality=quality.as_dict(),
    )


def _is_better(candidate: RepairResult, current: RepairResult) -> bool:
    """Fewer problems first, then more exercises, then fewer removals."""
    a, b = candidate.quality or {}, current.quality or {}
    return (
        (len(a.get("issues", [])), -a.get("exercises", 0), a.get("removed", 0))
        < (len(b.get("issues", [])), -b.get("exercises", 0), b.get("removed", 0))
    )


def _append_note(result: RepairResult) -> str:
    """
    Explain what changed, in structured-enough prose.

    "Adjustment Notes" is deliberately a heading plan_structure's category
    vocabulary recognises as non-exercise (see plan_structure's
    _CATEGORY_ROOTS/_CATEGORY_MODIFIERS - "adjustment" is a modifier next to
    the "notes" root), so every bullet under it is classified NON_EXERCISE
    and can never re-enter the audit as a prescription candidate. That is the
    actual mechanism now: repair()'s final audit runs on this exact,
    note-appended string. The wording still leads with "Swapped"/"Removed"
    before naming anything, which independently spares it from
    movement_ontology's own negation handling - a second, unrelated line of
    defence, not the one doing the real work. The caller should still prefer
    `result.as_dict()` as the source of truth over parsing this text back.
    """
    if not result.replacements and not result.removed:
        return result.plan

    parts = ["\n\n---", "**Adjustment Notes**"]
    for swap in result.replacements:
        parts.append(f"- Swapped *{swap.original}* for **{swap.replacement}** — {swap.reason}.")
    for line in result.removed:
        parts.append(f"- Removed *{line}* — no safe equivalent trains the same thing right now.")
    if result.still_inadequate:
        parts.append(
            "\nThis session is lighter than usual because a lot had to change. "
            "As the injury settles, update its severity and more will open back up."
        )
    parts.append(
        "\nThis is exercise selection, not rehabilitation. A physio can tell you "
        "what your specific injury actually tolerates."
    )
    return result.plan + "\n".join(parts)
