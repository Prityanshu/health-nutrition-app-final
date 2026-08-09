"""
Injuries as structure, not strings.

WHY THIS REPLACES THE EXERCISE LISTS
------------------------------------
The previous model was `injury -> list of banned exercise names`. It failed
three times in the same way, because names are unbounded: "sprinting" missed
"Sprints", "shuttle runs" missed "Pro Agility Shuttle", "bent-over barbell
rows" missed "Bent Over Dumbbell Rows". Each fix was another string, and the
next unseen phrasing got through.

Here an injury is described by what it cannot tolerate:

    body region  ->  tissue  ->  condition
                                    |
                                    v
                       restricted MOVEMENT PATTERNS, by stage

and movements are classified independently (movement_ontology). The two meet
in the middle, so an exercise nobody anticipated is still judged correctly
provided its shape is recognisable.

COVERAGE, HONESTLY
------------------
This does not contain every diagnosis, and should not try to. The regions and
tissues below cover what a general fitness app realistically sees, and an
unrecognised condition still gets classified by region keyword and treated
cautiously rather than waved through.

This is a decision-support layer for exercise selection. It is not diagnosis
and not medical clearance: red-flag findings escalate to a clinician instead
of producing a modified plan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# recovery stages
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Stage:
    key: str
    label: str
    guidance: str
    # Fraction of the condition's restricted patterns that still apply. Stages
    # relax in a defined order rather than everything reopening at once, which
    # is how people re-tear things.
    tiers: tuple          # which restriction tiers are active
    prescribe: bool


# Restrictions are held in three tiers so they can be lifted progressively:
#   primary   - directly loads the injured tissue
#   secondary - loads it indirectly, or at length
#   speed     - impact, velocity and maximal effort
STAGES: List[Stage] = [
    Stage("medical", "Needs assessment before training",
          "This is beyond what a training plan should work around. Get it looked at.",
          ("primary", "secondary", "speed"), False),
    Stage("acute", "Acute - protect it",
          "Static, pain-free work only. Nothing that moves the injured tissue under load.",
          ("primary", "secondary", "speed"), True),
    Stage("controlled", "Controlled loading",
          "Shortened, controlled range. No lengthening under load and nothing fast.",
          ("primary", "speed"), True),
    Stage("strength", "Building strength",
          "Progressive loading through range, including controlled lengthening. Still no speed work.",
          ("speed",), True),
    Stage("return", "Returning to sport",
          "Rebuild speed and impact gradually. Stop if symptoms return during or after.",
          (), True),
]

_STAGE_BY_SEVERITY = {
    10: "medical", 9: "medical", 8: "medical",
    7: "acute", 6: "acute",
    5: "controlled", 4: "controlled",
    3: "strength", 2: "strength",
    1: "return", 0: "return",
}


def stage_for_severity(severity: Optional[int]) -> Stage:
    """Which stage a 0-10 severity falls into. Unknown severity is cautious."""
    if severity is None:
        severity = 5
    severity = max(0, min(10, int(severity)))
    key = _STAGE_BY_SEVERITY[severity]
    return next(s for s in STAGES if s.key == key)


# ---------------------------------------------------------------------------
# conditions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Condition:
    key: str
    label: str
    region: str
    tissue: str
    triggers: List[str]

    # Movement patterns this condition cannot tolerate, by tier.
    primary: Set[str] = field(default_factory=set)
    secondary: Set[str] = field(default_factory=set)
    speed: Set[str] = field(default_factory=set)

    # Patterns that remain fine and are worth actively recommending, so a plan
    # is not left with nothing to do.
    keep: Set[str] = field(default_factory=set)
    substitutions: List[str] = field(default_factory=list)

    def restricted(self, stage: Stage) -> Set[str]:
        out: Set[str] = set()
        if "primary" in stage.tiers:
            out |= self.primary
        if "secondary" in stage.tiers:
            out |= self.secondary
        if "speed" in stage.tiers:
            out |= self.speed
        return out


# Ordered general -> specific within each region. `triggers` are matched
# against the user's own words, so they include lay phrasing as well as
# clinical terms.
CONDITIONS: List[Condition] = [
    # ---------------------------------------------------------------- thigh
    Condition(
        "hamstring", "hamstring injury", "thigh", "muscle",
        ["hamstring", "back of thigh", "sit bone", "ischial", "proximal hamstring",
         "biceps femoris"],
        primary={"knee_flexion", "hip_hinge"},
        secondary={"squat", "lunge", "end_range_stretch", "spinal_flexion"},
        speed={"high_speed", "running", "jumping", "cutting", "impact", "maximal_effort"},
        keep={"horizontal_pull", "horizontal_push", "vertical_push", "low_impact",
              "calf_raise", "anti_rotation", "isometric"},
        substitutions=["chest-supported or seated rows in place of anything bent over",
                       "bent-knee core work instead of straight-leg work",
                       "cycling or swimming for conditioning",
                       "upper-body sessions while the leg settles"],
    ),
    Condition(
        "quadriceps", "quadriceps injury", "thigh", "muscle",
        ["quad", "quadriceps", "rectus femoris", "front of thigh", "vastus"],
        primary={"knee_extension", "squat", "lunge"},
        secondary={"jumping", "end_range_stretch"},
        speed={"high_speed", "running", "cutting", "impact", "maximal_effort"},
        keep={"horizontal_pull", "vertical_pull", "horizontal_push", "low_impact",
              "hip_hinge", "anti_rotation"},
        substitutions=["hip-hinge patterns instead of knee-dominant work",
                       "cycling with a high saddle and low resistance",
                       "upper body and core"],
    ),
    Condition(
        "adductor", "groin / adductor injury", "hip_groin", "muscle",
        ["groin", "adductor", "inner thigh", "osteitis pubis", "athletic pubalgia",
         "sports hernia", "pubic"],
        primary={"hip_adduction", "cutting", "lunge"},
        secondary={"squat", "end_range_stretch", "hip_abduction"},
        speed={"high_speed", "running", "jumping", "impact", "maximal_effort"},
        keep={"horizontal_pull", "horizontal_push", "vertical_push", "low_impact",
              "anti_rotation", "calf_raise"},
        substitutions=["straight-line low-impact cardio rather than anything lateral",
                       "isometric adductor holds only once a physio has cleared them",
                       "upper body and anti-rotation core work"],
    ),

    # ----------------------------------------------------------------- knee
    Condition(
        "knee_ligament", "knee ligament injury", "knee", "ligament",
        ["acl", "mcl", "lcl", "pcl", "knee ligament", "knee sprain", "knee gave way",
         "knee instability"],
        primary={"cutting", "jumping", "lunge", "squat", "dorsiflexion"},
        secondary={"knee_extension", "knee_flexion", "unilateral", "spinal_rotation",
                   "loaded_stance"},
        speed={"high_speed", "running", "impact", "maximal_effort"},
        keep={"horizontal_pull", "vertical_pull", "horizontal_push", "vertical_push",
              "low_impact", "anti_rotation", "isometric"},
        substitutions=["straight-line low-impact cardio, no pivoting",
                       "leg work through a shortened, pain-free range",
                       "upper body and core"],
    ),
    Condition(
        "meniscus", "meniscus injury", "knee", "cartilage",
        ["meniscus", "meniscal", "cartilage", "knee locking", "knee catching"],
        primary={"squat", "spinal_rotation", "cutting"},
        secondary={"lunge", "knee_flexion", "jumping"},
        speed={"high_speed", "running", "impact", "maximal_effort"},
        keep={"horizontal_pull", "horizontal_push", "low_impact", "calf_raise",
              "anti_rotation", "isometric", "hip_hinge"},
        substitutions=["partial-range leg work rather than deep flexion",
                       "cycling with the saddle high",
                       "no twisting on a planted foot"],
    ),
    Condition(
        "patellar", "patellar / kneecap pain", "knee", "tendon",
        ["patella", "patellar", "kneecap", "jumper's knee", "runner's knee",
         "patellofemoral", "chondromalacia"],
        primary={"jumping", "squat", "lunge"},
        secondary={"knee_extension", "impact"},
        speed={"high_speed", "running", "cutting", "maximal_effort"},
        keep={"hip_hinge", "horizontal_pull", "horizontal_push", "low_impact",
              "hip_abduction", "isometric", "anti_rotation"},
        substitutions=["isometric holds, which usually reduce tendon pain",
                       "hip-hinge and glute work instead of knee-dominant loading",
                       "cycling or swimming"],
    ),

    Condition(
        "it_band", "IT band syndrome", "knee", "fascia",
        ["it band", "iliotibial", "itbs", "outside of my knee", "lateral knee"],
        primary={"lunge", "running", "impact"},
        secondary={"squat", "knee_flexion", "end_range_stretch"},
        speed={"high_speed", "jumping", "cutting", "maximal_effort"},
        keep={"horizontal_pull", "horizontal_push", "vertical_push", "low_impact",
              "hip_abduction", "anti_rotation", "isometric"},
        substitutions=["glute medius work - clamshells, banded walks, side-lying raises",
                       "swimming or upper-body conditioning",
                       "short-range leg work rather than deep knee bending"],
    ),

    # ------------------------------------------------------ lower leg, foot
    Condition(
        "achilles", "Achilles injury", "lower_leg", "tendon",
        ["achilles", "heel cord", "calf tendon"],
        primary={"calf_raise", "jumping", "plantarflexion", "repetitive_ankle"},
        secondary={"end_range_stretch", "lunge", "dorsiflexion", "loaded_stance",
                   "weight_bearing"},
        speed={"high_speed", "running", "cutting", "impact", "maximal_effort"},
        keep={"horizontal_pull", "horizontal_push", "vertical_push", "vertical_pull",
              "non_weight_bearing", "seated_supported", "hip_extension",
              "anti_rotation"},
        substitutions=["swimming rather than cycling - a bike still works the ankle",
                       "seated leg work",
                       "upper body"],
    ),
    Condition(
        "bone_stress", "bone stress injury", "lower_leg", "bone",
        ["shin splint", "shin splints", "stress fracture", "stress reaction",
         "medial tibial", "tibial stress", "metatarsal stress", "navicular"],
        primary={"impact", "jumping", "running", "repetitive_ankle"},
        secondary={"calf_raise", "plantarflexion", "weight_bearing"},
        speed={"high_speed", "cutting", "maximal_effort"},
        keep={"horizontal_pull", "horizontal_push", "vertical_push", "vertical_pull",
              "non_weight_bearing", "seated_supported", "hip_hinge", "squat",
              "hip_extension", "anti_rotation"},
        substitutions=["cycling, swimming or the elliptical - no ground impact at all",
                       "strength work is usually fine; it is repetitive loading that hurts",
                       "a gradual return to running once symptoms settle"],
    ),
    Condition(
        "plantar", "plantar fascia pain", "foot", "fascia",
        ["plantar fasciitis", "plantar fascia", "heel pain", "arch pain"],
        primary={"impact", "jumping", "running", "weight_bearing", "plantarflexion"},
        secondary={"calf_raise", "end_range_stretch", "loaded_stance",
                   "repetitive_ankle"},
        speed={"high_speed", "cutting", "maximal_effort"},
        keep={"horizontal_pull", "horizontal_push", "vertical_pull",
              "non_weight_bearing", "seated_supported", "hip_extension",
              "anti_rotation", "isometric"},
        substitutions=["cycling or swimming",
                       "seated and machine-based leg work",
                       "supportive footwear for anything on your feet"],
    ),
    Condition(
        "ankle", "ankle injury", "ankle", "ligament",
        ["ankle", "atfl", "syndesmosis", "high ankle", "rolled my ankle",
         "ankle sprain", "ankle instability"],
        # Case A. Every one of these loads the ankle, and none of them were
        # restricted before because the model had no way to say so:
        #   seated calf raise  -> direct plantarflexion, zero impact
        #   leg press          -> foot force against a platform
        #   cycling            -> continuous ankle motion under load
        #   deadlift / RDL     -> standing under external load
        # calf_raise moved from secondary to primary: it is the single most
        # direct ankle loading there is, and filing it as secondary meant it
        # was permitted at 5/10.
        primary={"cutting", "jumping", "unilateral", "plantarflexion",
                 "calf_raise", "loaded_stance", "repetitive_ankle"},
        secondary={"lunge", "squat", "dorsiflexion", "weight_bearing"},
        speed={"high_speed", "running", "impact", "maximal_effort"},
        # Note what is NOT here: low_impact. Cycling is low impact and high
        # ankle load, so whitelisting "low impact" was whitelisting the bike.
        keep={"horizontal_pull", "horizontal_push", "vertical_push",
              "vertical_pull", "non_weight_bearing", "seated_supported",
              "anti_rotation", "hip_extension", "elbow_flexion", "elbow_extension"},
        substitutions=["swimming or an upper-body ergometer rather than a bike",
                       "seated and lying work where the foot is not pushing",
                       "bilateral, stable leg work before anything single-leg",
                       "balance work only once it is pain-free"],
    ),

    # ------------------------------------------------------------- shoulder
    Condition(
        "rotator_cuff", "rotator cuff injury", "shoulder", "tendon",
        ["rotator cuff", "supraspinatus", "infraspinatus", "subscapularis",
         "impingement", "swimmer's shoulder", "shoulder tendinopathy"],
        primary={"vertical_push", "overhead"},
        secondary={"horizontal_push", "shoulder_rotation", "vertical_pull",
                   "end_range_stretch"},
        speed={"maximal_effort"},
        keep={"running", "high_speed", "jumping", "cutting", "impact", "low_impact",
              "squat", "hip_hinge", "lunge", "calf_raise", "anti_rotation"},
        substitutions=["neutral-grip and landmine pressing below shoulder height",
                       "cable work inside a pain-free arc",
                       "lower body and conditioning are unaffected"],
    ),
    Condition(
        "shoulder_instability", "shoulder instability", "shoulder", "ligament",
        ["shoulder dislocation", "subluxation", "shoulder instability", "labrum",
         "slap tear", "bankart"],
        primary={"overhead", "vertical_push", "end_range_stretch"},
        secondary={"horizontal_push", "vertical_pull", "shoulder_rotation"},
        speed={"maximal_effort", "jumping"},
        keep={"running", "high_speed", "cutting", "impact", "low_impact",
              "squat", "hip_hinge", "lunge", "anti_rotation"},
        substitutions=["pressing kept in front of the body and below shoulder height",
                       "no combined abduction and external rotation",
                       "lower body and conditioning are unaffected"],
    ),

    # ------------------------------------------------------- elbow to hand
    Condition(
        "elbow_tendon", "elbow tendinopathy", "elbow", "tendon",
        ["tennis elbow", "golfer's elbow", "golfers elbow", "epicondyl", "elbow pain",
         "elbow tendon"],
        primary={"gripping", "elbow_flexion"},
        secondary={"vertical_pull", "horizontal_pull", "elbow_extension"},
        speed={"maximal_effort"},
        keep={"running", "high_speed", "jumping", "cutting", "impact", "low_impact",
              "squat", "hip_hinge", "lunge", "calf_raise", "anti_rotation"},
        substitutions=["straps to take the grip out of pulling",
                       "machine and neutral-grip variations",
                       "lower body and conditioning are unaffected"],
    ),
    Condition(
        "wrist", "wrist injury", "wrist", "joint",
        ["wrist", "tfcc", "scaphoid", "carpal tunnel", "wrist sprain"],
        primary={"gripping", "horizontal_push"},
        secondary={"vertical_push", "elbow_flexion", "end_range_stretch"},
        speed={"maximal_effort"},
        keep={"running", "high_speed", "jumping", "cutting", "impact", "low_impact",
              "squat", "hip_hinge", "lunge", "calf_raise"},
        substitutions=["push-ups on dumbbells or parallettes to keep the wrist neutral",
                       "forearm planks instead of hand planks",
                       "straps for anything you have to hold"],
    ),

    # ----------------------------------------------------------- back, hip
    Condition(
        "lumbar", "lower back pain", "lumbar", "spine",
        ["lower back", "low back", "lumbar", "back pain", "disc", "slipped disc",
         "herniated", "facet", "spondylo", "si joint", "sacroiliac"],
        primary={"hip_hinge", "spinal_flexion", "axial_load"},
        secondary={"spinal_rotation", "squat", "spinal_extension", "end_range_stretch",
                   "overhead"},
        speed={"impact", "jumping", "maximal_effort", "high_speed"},
        keep={"horizontal_pull", "horizontal_push", "low_impact", "anti_rotation",
              "calf_raise", "isometric"},
        substitutions=["chest-supported rows and machine pressing",
                       "dead bugs and bird dogs instead of sit-ups",
                       "glute bridges for the posterior chain",
                       "walking or cycling within comfort"],
    ),
    Condition(
        "nerve", "nerve irritation", "lumbar", "nerve",
        ["sciatica", "sciatic", "radiculopathy", "nerve pain", "shooting down my leg",
         "pins and needles", "numbness", "tingling"],
        primary={"spinal_flexion", "hip_hinge", "end_range_stretch", "axial_load"},
        secondary={"squat", "spinal_rotation", "impact"},
        speed={"jumping", "high_speed", "maximal_effort", "running"},
        keep={"horizontal_pull", "horizontal_push", "low_impact", "anti_rotation",
              "isometric"},
        substitutions=["walking within a pain-free distance",
                       "standing rather than seated work",
                       "nothing that reproduces the symptoms down the leg"],
    ),
    Condition(
        "hip_joint", "hip joint pain", "hip_groin", "joint",
        ["hip impingement", "fai", "hip labral", "hip labrum", "hip arthritis",
         "hip pain", "hip flexor"],
        primary={"squat", "lunge", "hip_adduction"},
        secondary={"hip_hinge", "end_range_stretch", "hip_abduction", "cutting"},
        speed={"high_speed", "running", "jumping", "impact", "maximal_effort"},
        keep={"horizontal_pull", "horizontal_push", "vertical_push", "low_impact",
              "calf_raise", "anti_rotation"},
        substitutions=["shallower range on anything that bends the hip",
                       "no deep or wide stances",
                       "upper body and machine-based leg work"],
    ),
    Condition(
        "abdominal", "abdominal wall injury", "abdomen", "muscle",
        ["hernia", "abdominal strain", "oblique strain", "core strain",
         "rectus abdominis", "abdominal wall"],
        primary={"spinal_flexion", "spinal_rotation", "axial_load"},
        secondary={"hip_hinge", "squat", "overhead", "gripping"},
        speed={"maximal_effort", "jumping", "impact"},
        keep={"low_impact", "horizontal_pull", "calf_raise", "isometric"},
        substitutions=["breathe out through the effort rather than bracing hard",
                       "light machine work only",
                       "medical clearance before loaded training"],
    ),

    # ------------------------------------------------------------ neck etc.
    Condition(
        "cervical", "neck injury", "neck", "spine",
        ["neck", "cervical", "whiplash", "trap strain"],
        primary={"axial_load", "overhead", "vertical_push"},
        secondary={"vertical_pull", "gripping", "end_range_stretch"},
        speed={"impact", "jumping", "maximal_effort"},
        keep={"low_impact", "horizontal_pull", "hip_hinge", "squat", "calf_raise",
              "anti_rotation"},
        substitutions=["supported and machine-based movements",
                       "keeping load off the upper traps",
                       "lower body and steady cardio"],
    ),

    # Not an injury - a condition that caps intensity rather than excluding a
    # movement. Included because the app must not treat it as orthopaedic.
    Condition(
        "asthma", "asthma", "respiratory", "systemic",
        ["asthma", "asthmatic", "inhaler", "exercise-induced broncho", "wheez"],
        primary=set(),
        secondary={"cardio_intensity"},
        speed={"cardio_intensity", "high_speed", "maximal_effort"},
        keep={"squat", "hip_hinge", "horizontal_push", "horizontal_pull",
              "vertical_push", "low_impact", "isometric"},
        substitutions=["longer warm-ups, built up gradually",
                       "intervals with generous recovery rather than continuous hard effort",
                       "keep a reliever inhaler to hand"],
    ),
]


# Region keywords, so an unrecognised condition still lands somewhere sensible
# rather than being treated as no injury at all.
_REGION_HINTS = {
    "shoulder": ["shoulder", "delt", "ac joint", "clavicle"],
    "knee": ["knee", "patella"],
    "thigh": ["thigh", "quad", "hamstring"],
    "lower_leg": ["shin", "calf", "achilles", "tibia"],
    "foot": ["foot", "heel", "toe", "arch", "plantar"],
    "ankle": ["ankle"],
    "lumbar": ["back", "lumbar", "spine", "disc"],
    "hip_groin": ["hip", "groin", "adductor", "pelvis"],
    "elbow": ["elbow"],
    "wrist": ["wrist", "hand", "finger", "thumb"],
    "neck": ["neck", "cervical"],
    "abdomen": ["abdomen", "abdominal", "core", "oblique", "hernia"],
}

# When only the region is known, restrict everything that loads it. Cautious
# by design - an unknown shoulder problem should not be handed overhead work.
_REGION_FALLBACK = {
    "shoulder": {"overhead", "vertical_push", "horizontal_push", "vertical_pull",
                 "shoulder_rotation"},
    "knee": {"squat", "lunge", "jumping", "cutting", "knee_extension", "knee_flexion"},
    "thigh": {"squat", "lunge", "knee_flexion", "knee_extension", "hip_hinge",
              "high_speed", "running"},
    "lower_leg": {"running", "jumping", "impact", "calf_raise", "high_speed"},
    "foot": {"running", "jumping", "impact", "calf_raise"},
    "ankle": {"running", "jumping", "cutting", "impact", "unilateral"},
    "lumbar": {"hip_hinge", "spinal_flexion", "axial_load", "spinal_rotation"},
    "hip_groin": {"squat", "lunge", "hip_adduction", "hip_abduction", "cutting"},
    "elbow": {"gripping", "elbow_flexion", "elbow_extension"},
    "wrist": {"gripping", "horizontal_push"},
    "neck": {"axial_load", "overhead", "vertical_push"},
    "abdomen": {"spinal_flexion", "spinal_rotation", "axial_load"},
}


# Symptoms that need a person, not a substitute exercise.
RED_FLAGS = (
    "numbness", "tingling", "pins and needles", "loss of sensation", "weakness",
    "gave way", "giving way", "gives way", "locked", "locking", "unable to bear weight",
    "can't bear weight", "cannot bear weight", "can't put weight", "deformity",
    "dislocat", "suspected fracture", "broken", "severe swelling", "rapid swelling",
    "sharp pain", "shooting pain", "getting worse", "worsening", "popped",
    "heard a pop", "felt a pop", "loss of consciousness", "concussion",
    "dizzy", "blurred vision", "chest pain", "shortness of breath",
    "bladder", "bowel", "fever",
)


@dataclass
class InjuryProfile:
    """A structured injury, resolved from whatever the user typed."""
    raw: str
    condition: Optional[Condition]
    region: Optional[str]
    severity: int
    side: Optional[str]          # left | right | bilateral | None
    stage: Stage
    red_flags: List[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.condition:
            return self.condition.label
        if self.region:
            return f"{self.region.replace('_', ' ')} problem"
        return "stated injury"

    @property
    def needs_medical(self) -> bool:
        return bool(self.red_flags) or not self.stage.prescribe

    def restricted_patterns(self) -> Set[str]:
        if self.condition:
            return self.condition.restricted(self.stage)

        # Unrecognised condition. Two levels of caution, because "I don't know
        # what this is" must never mean "so anything goes":
        #   known region -> restrict what that region loads
        #   no region    -> restrict speed and maximal effort only, which are
        #                   the things that hurt almost any healing tissue
        restricted: Set[str] = set()
        if "speed" in self.stage.tiers:
            restricted |= {"high_speed", "jumping", "impact", "cutting",
                           "maximal_effort", "cardio_intensity"}
        if self.region and ("primary" in self.stage.tiers or "secondary" in self.stage.tiers):
            restricted |= _REGION_FALLBACK.get(self.region, set())
        return restricted

    def keep_patterns(self) -> Set[str]:
        return set(self.condition.keep) if self.condition else set()


def _detect_side(text: str) -> Optional[str]:
    lowered = (text or "").lower()
    left = re.search(r"(?<!\w)left(?!\w)", lowered) is not None
    right = re.search(r"(?<!\w)right(?!\w)", lowered) is not None
    if left and right:
        return "bilateral"
    if re.search(r"\b(?:both|bilateral|either side|each side)\b", lowered):
        return "bilateral"
    if left:
        return "left"
    if right:
        return "right"
    return None


def _detect_severity(text: str, default: Optional[int] = None) -> Optional[int]:
    match = re.search(r"severity\s*(\d{1,2})\s*/\s*10", (text or "").lower())
    if match:
        return int(match.group(1))
    match = re.search(r"(\d{1,2})\s*/\s*10", (text or "").lower())
    if match:
        return int(match.group(1))
    return default


def parse(text: str, severity: Optional[int] = None) -> Optional[InjuryProfile]:
    """
    Turn a free-text injury description into structure.

    Returns None only when the text says nothing injury-like at all. An
    unrecognised condition still returns a profile with a region, because
    "some shoulder thing I can't name" must not be treated as no injury.
    """
    if not text or not text.strip():
        return None

    lowered = text.lower()
    resolved_severity = _detect_severity(text, severity)

    condition = None
    for candidate in CONDITIONS:
        if any(t in lowered for t in candidate.triggers):
            condition = candidate
            break

    region = condition.region if condition else None
    if not region:
        for name, hints in _REGION_HINTS.items():
            if any(re.search(rf"(?<!\w){re.escape(h)}", lowered) for h in hints):
                region = name
                break

    flags = [f for f in RED_FLAGS if f in lowered]

    if not condition and not region and not flags:
        # Nothing recognisable. Treat it as an injury anyway if the text reads
        # like one OR carries a severity rating - somebody typing
        # "costochondritis 6/10" has told us they are hurt even though no rule
        # here knows the word, and waving that through unguarded is the worst
        # possible default.
        looks_like_injury = re.search(
            r"injur|pain|strain|sprain|tear|torn|hurt|sore|ache|itis\b|"
            r"syndrome|condition|surgery|rehab|recovering",
            lowered,
        )
        if not looks_like_injury and resolved_severity is None:
            return None

    resolved = resolved_severity if resolved_severity is not None else 5
    return InjuryProfile(
        raw=text.strip(),
        condition=condition,
        region=region,
        severity=resolved,
        side=_detect_side(text),
        stage=stage_for_severity(resolved),
        red_flags=flags,
    )


# ---------------------------------------------------------------------------
# prompt guidance
# ---------------------------------------------------------------------------

def brief(profiles: List[InjuryProfile]) -> str:
    """
    Turn parsed injuries into instructions a model can actually follow.

    Severity previously reached only the repair stage: the model generated
    blind, then unsafe work was stripped or swapped afterwards. That is safe
    but wasteful - a 7/10 hamstring and a 2/10 hamstring produced the same
    first draft, and the difference was made entirely by deletion. Telling the
    model the stage up front means the first plan is usually right, and repair
    goes back to being a backstop rather than the mechanism.

    Movement patterns are named in plain language, because "avoid hip_hinge"
    means nothing to a language model but "avoid bending forward at the hips
    under load" does.
    """
    from app.services.movement_ontology import describe

    if not profiles:
        return ""

    lines: List[str] = []
    for p in profiles:
        side = f"{p.side} " if p.side and p.side != "bilateral" else ""
        both = " (both sides)" if p.side == "bilateral" else ""
        restricted = p.restricted_patterns()
        keep = p.keep_patterns() - restricted

        lines.append(f"- {side}{p.label}{both}, rated {p.severity}/10.")
        lines.append(f"  Stage: {p.stage.label}. {p.stage.guidance}")
        if restricted:
            lines.append(f"  Avoid any movement that involves: {describe(restricted)}.")
        if keep:
            lines.append(f"  Still safe to train hard: {describe(keep)}.")
        if p.red_flags:
            lines.append(f"  They also reported: {', '.join(p.red_flags)}.")

    return "\n            ".join(lines)


def parse_all(constraints) -> List[InjuryProfile]:
    """Parse a list of constraint strings, dropping anything unrecognisable."""
    out = []
    for c in constraints or []:
        p = parse(str(c))
        if p:
            out.append(p)
    return out
