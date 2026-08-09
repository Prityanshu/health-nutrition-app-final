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


def _apply(plan_text: str, decisions: Dict[int, Replacement]) -> str:
    """Rewrite the plan, keeping the original bullet formatting."""
    out = []
    for index, raw in enumerate(plan_text.splitlines()):
        decision = decisions.get(index)
        if decision is None:
            out.append(raw)
            continue
        if decision.replacement is None:
            continue  # nothing safe does this job; the line goes
        prefix = re.match(r"^\s*(?:[-*•+]|\d+[.)])?\s*", raw).group(0)
        out.append(f"{prefix}{decision.replacement}")
    return "\n".join(out)


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

    `regenerate` is a callback taking a brief and returning a new plan, so this
    module has no knowledge of the model or its client. Omit it and repair
    still runs - it simply cannot regenerate, which is exactly what the tests
    want and what an offline caller needs.
    """
    from app.services import injury_taxonomy as taxonomy
    from app.services import plan_quality
    from app.services.contraindications import audit_against_profiles

    profiles = [p for p in (taxonomy.parse(c) for c in (constraints or [])) if p]

    # Healthy user: nothing to do, and nothing that could go wrong. Returning
    # early guarantees the repair path cannot introduce a false positive.
    if not profiles:
        quality = plan_quality.evaluate(plan_text, requested_minutes=requested_minutes,
                                        goal=goal, sport=sport, equipment=equipment,
                                        level=level)
        return RepairResult(plan=plan_text, quality=quality.as_dict())

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

    # FINAL audit. Whatever happened above, nothing prohibited leaves here.
    leftover = audit_against_profiles(result.plan, profiles)
    if leftover:
        logger.error("Final audit found %d prohibited line(s) after repair - removing.",
                     len(leftover))
        bad = {f["line_no"] for f in leftover}
        result.plan = "\n".join(
            line for i, line in enumerate(result.plan.splitlines()) if i not in bad
        )
        result.removed += [f["line"] for f in leftover]
        # Re-check, so `audit_clean` is a measured fact rather than an assumption.
        result.audit_clean = not audit_against_profiles(result.plan, profiles)
    else:
        result.audit_clean = True

    result.still_inadequate = not result.quality.get("adequate", True)
    result.plan = _append_note(result)
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
        decision = _find_replacement(verdict["line"], profiles, equipment, used)
        decision.reason = ("could not be classified while an injury is active, "
                           "so it was replaced with something known to be safe")
        if decision.replacement:
            used.add(decision.replacement)
            decisions[verdict["line_no"]] = decision
        else:
            logger.warning("Unclassifiable line kept with no safe substitute: %r",
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

    The note is deliberately written so the auditor's negation handling spares
    it - it leads with "swapped"/"removed" before naming anything - but the
    caller should prefer `result.as_dict()` as the source of truth. Parsing
    this back would be exactly the mistake that made a safety note trigger the
    safety filter.
    """
    if not result.replacements and not result.removed:
        return result.plan

    parts = ["\n\n---", "**Adjusted for your injury**"]
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
