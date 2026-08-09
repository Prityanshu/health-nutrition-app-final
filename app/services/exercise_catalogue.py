"""
Candidate exercises for replacement. Data only - no safety authority.

WHY THIS IS NOT A SECOND SAFETY SYSTEM
--------------------------------------
Replacement needs actual exercise names to propose. The existing data cannot
supply them: `Condition.substitutions` holds prose like "chest-supported or
seated rows in place of anything bent over", which is guidance for a human,
not something that can be classified into one movement.

So this file lists names. It decides nothing:

    catalogue PROPOSES  ->  movement_ontology CLASSIFIES
                        ->  injury_taxonomy JUDGES
                        ->  contraindications.audit CONFIRMS

If an entry here were unsafe for a given injury, the audit would reject it
exactly as it rejects an unsafe exercise from the model. There is a test that
runs every entry against every condition at every stage, so a bad entry fails
the suite rather than reaching a user.

The patterns below are NOT declared - they are computed by the ontology at
import time. Declaring them here would create the second source of truth this
module exists to avoid.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class Candidate:
    name: str
    # What this exercise is for, in the user's terms. Used only for wording the
    # replacement note - never for safety decisions.
    purpose: str
    # Equipment needed, so a bodyweight user is not handed a cable machine.
    equipment: str = "none"          # none | home | gym
    patterns: Set[str] = field(default_factory=set)   # filled by the ontology


# Grouped by the training purpose they serve, because a replacement has to keep
# the session's intent. Purpose here means "what slot in a workout does this
# fill", not "which muscle" - the ontology already encodes the mechanics.
_RAW: List[Candidate] = [
    # --- horizontal pull (back) ------------------------------------------
    Candidate("Chest-supported dumbbell row", "back", "gym"),
    Candidate("Seated cable row", "back", "gym"),
    Candidate("Machine row", "back", "gym"),
    Candidate("Inverted row with feet on the floor", "back", "home"),
    Candidate("Band seated row", "back", "home"),

    # --- vertical pull ----------------------------------------------------
    Candidate("Lat pulldown", "back", "gym"),
    Candidate("Assisted pull-up", "back", "gym"),
    Candidate("Band lat pulldown", "back", "home"),

    # --- horizontal push --------------------------------------------------
    Candidate("Floor press", "chest", "gym"),
    Candidate("Machine chest press", "chest", "gym"),
    Candidate("Push-up on dumbbells", "chest", "home"),
    Candidate("Incline push-up", "chest", "none"),

    # --- vertical push ----------------------------------------------------
    Candidate("Landmine press", "shoulders", "gym"),
    Candidate("Seated dumbbell shoulder press", "shoulders", "gym"),

    # --- knee dominant ----------------------------------------------------
    Candidate("Leg extension machine", "quads", "gym"),
    Candidate("Box squat to a comfortable depth", "quads", "gym"),
    Candidate("Wall sit", "quads", "none"),
    Candidate("Spanish squat with a band", "quads", "home"),

    # --- hip / glute without a hinge --------------------------------------
    Candidate("Glute bridge", "glutes", "none"),
    Candidate("Hip thrust from a bench", "glutes", "gym"),
    Candidate("Standing cable hip extension", "glutes", "gym"),
    Candidate("Clamshell with a band", "glutes", "home"),
    Candidate("Side-lying hip abduction raise", "glutes", "none"),

    # --- calves -----------------------------------------------------------
    Candidate("Seated calf raise", "calves", "gym"),
    Candidate("Standing calf raise", "calves", "none"),

    # --- arms -------------------------------------------------------------
    Candidate("Cable tricep pushdown", "arms", "gym"),
    Candidate("Seated dumbbell curl", "arms", "gym"),
    Candidate("Band tricep extension", "arms", "home"),

    # --- trunk, braced rather than flexed ---------------------------------
    Candidate("Front plank", "core", "none"),
    Candidate("Side plank", "core", "none"),
    Candidate("Dead bug", "core", "none"),
    Candidate("Bird dog", "core", "none"),
    Candidate("Pallof press with a band", "core", "home"),
    Candidate("Suitcase carry", "core", "gym"),

    # --- conditioning without impact --------------------------------------
    Candidate("Stationary bike, steady pace", "conditioning", "gym"),
    Candidate("Swimming, easy pace", "conditioning", "gym"),
    Candidate("Rowing machine, steady pace", "conditioning", "gym"),
    Candidate("Elliptical, steady pace", "conditioning", "gym"),
    Candidate("Brisk walk", "conditioning", "none"),
    Candidate("Upper-body ergometer", "conditioning", "gym"),

    # --- isometric / early rehab ------------------------------------------
    Candidate("Isometric wall push hold", "isometric", "none"),
    Candidate("Isometric split squat hold", "isometric", "none"),
    Candidate("Static glute bridge hold", "isometric", "none"),
]


def _build() -> List[Candidate]:
    """Classify every candidate once, at import, using the ontology."""
    try:
        from app.services import movement_ontology as ontology
    except Exception as e:  # pragma: no cover
        logger.error("Ontology unavailable, catalogue will be inert: %s", e)
        return []

    built = []
    for candidate in _RAW:
        candidate.patterns = ontology.classify(candidate.name).patterns
        if not candidate.patterns:
            # An unclassifiable candidate cannot be validated, so it must not
            # be offered. Loud, because it means the catalogue and the ontology
            # have drifted apart.
            logger.warning(
                "Catalogue entry %r does not classify - excluded from candidates. "
                "Either the name or the ontology needs attention.", candidate.name,
            )
            continue
        built.append(candidate)
    return built


CATALOGUE: List[Candidate] = _build()

# Equipment tiers, so a "home" request can still use bodyweight options.
_EQUIPMENT_ALLOWS = {
    "none": {"none"},
    "home": {"none", "home"},
    "gym": {"none", "home", "gym"},
}


def candidates_for(
    purpose: Optional[str] = None,
    equipment: str = "gym",
    require_patterns: Optional[Set[str]] = None,
    forbid_patterns: Optional[Set[str]] = None,
) -> List[Candidate]:
    """
    Shortlist candidates. Filtering only - the caller must still audit them.

    `require_patterns` preserves the purpose of the removed exercise: a bent
    over row is removed for its hip hinge, but its job was horizontal pulling,
    so the replacement must still pull horizontally or the session loses a
    movement it needed.
    """
    allowed = _EQUIPMENT_ALLOWS.get(equipment, _EQUIPMENT_ALLOWS["gym"])
    out = []
    for candidate in CATALOGUE:
        if candidate.equipment not in allowed:
            continue
        if purpose and candidate.purpose != purpose:
            continue
        if require_patterns and not (candidate.patterns & require_patterns):
            continue
        if forbid_patterns and (candidate.patterns & forbid_patterns):
            continue
        out.append(candidate)
    return out


def purposes() -> List[str]:
    return sorted({c.purpose for c in CATALOGUE})
