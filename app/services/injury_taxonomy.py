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
    # Thoracic must be tested BEFORE lumbar: "thoracic spine" and "upper back"
    # both contain a lumbar hint ("spine", "back"), so a later entry would
    # never win. "lower back" contains neither thoracic hint, so it still
    # resolves to lumbar.
    # Unambiguous thoracic wording only. "rib" and "scapula" were tempting but
    # belong to other complaints as often as this one, and these hints now
    # pre-empt the CONDITIONS scan (see parse), so a loose entry here would
    # suppress a real diagnosis elsewhere.
    "thoracic": ["thoracic", "t-spine", "t spine", "mid back", "mid-back",
                 "midback", "upper back", "upper-back"],
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
    # No diagnosis is claimed from the word "thoracic" - this is the same
    # cautious region fallback every other region gets, built from existing
    # movement-pattern identifiers. Rotation and axial load are what a painful
    # mid-back actually objects to; overhead work drives it into extension.
    "thoracic": {"spinal_rotation", "axial_load", "overhead", "vertical_push"},
    "lumbar": {"hip_hinge", "spinal_flexion", "axial_load", "spinal_rotation"},
    # hip_hinge belongs here: a Romanian deadlift is a maximal loaded hip
    # hinge and was leaking past a correctly-identified hip injury because
    # only squat/lunge patterns were listed.
    "hip_groin": {"squat", "lunge", "hip_adduction", "hip_abduction", "cutting",
                  "hip_hinge"},
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
    # Movement patterns explicitly named as restricted in the SAME free text,
    # independent of whatever condition/region also matched - see
    # parse_explicit_restriction() below. "wrist pain (severity 0/10); avoid
    # jumping" must keep BOTH: the wrist finding (which may carry no
    # restrictions of its own at severity 0) and the explicit "no jumping"
    # restriction, which is not graded by severity at all. Merged in by
    # restricted_patterns() below, never in place of the condition's own.
    extra_restricted: Set[str] = field(default_factory=set)

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
            return self.condition.restricted(self.stage) | self.extra_restricted

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
        return restricted | self.extra_restricted

    def keep_patterns(self) -> Set[str]:
        """
        Patterns this condition considers definitely safe - used elsewhere to
        let a specific "this is fine" override a broader fallback
        restriction (a shoulder injury's keep list must not lose to its own
        region fallback and end up blocking squats).

        Explicitly restricted patterns are subtracted out here rather than
        left to win by coincidence: a condition's keep list is a MEDICAL
        judgement about that condition, and must never be read as also
        overriding a stated, non-medical preference like "avoid jumping" -
        the wrist condition's keep list legitimately includes "jumping"
        (a wrist injury does not care about jumping), which said nothing
        about whether THIS user wants to jump.
        """
        keep = set(self.condition.keep) if self.condition else set()
        return keep - self.extra_restricted


# ---------------------------------------------------------------------------
# explicit, non-medical restrictions - "no jumping", "avoid overhead"
# ---------------------------------------------------------------------------
#
# A stated preference like this is not a diagnosis and must not be run
# through the condition/region/stage machinery above, which exists to model
# how an injury's tolerance changes as it heals - there is no healing curve
# for "I don't want to jump". But it still needs to carry deterministic
# authority in the same audit, not live only as a hint in the prompt, or it
# is exactly as easy for the model to ignore as anything else in free text.
#
# The mechanism is deliberately the smallest one that works: a negation word
# next to a recognised movement WORD (not an exercise name) maps straight to
# the pattern(s) that word already means in movement_ontology's own
# vocabulary. No new taxonomy, no invented severity or recovery stage.

_EXPLICIT_STAGE = Stage(
    "explicit", "Explicit restriction",
    "The user asked to avoid this movement outright - not a graduated "
    "recovery, just don't include it.",
    (), True,
)

_NEGATION = r"(?:no|not|avoid(?:ing)?|don'?t|do\s+not|can'?t|cannot|skip|without)"

# word -> the movement_ontology pattern(s) it means. Deliberately short and
# direct rather than exhaustive - see the module docstring's own stance on
# coverage: an unrecognised phrase falls through to no restriction here,
# same as an unrecognised condition falls through to a cautious default
# above, not to a fabricated one.
_RESTRICTION_WORDS: Dict[str, Set[str]] = {
    "jump": {"jumping"}, "jumping": {"jumping"}, "hop": {"jumping"}, "hopping": {"jumping"},
    "overhead": {"overhead", "vertical_push"},
    "run": {"running", "high_speed"}, "running": {"running", "high_speed"},
    "sprint": {"high_speed"}, "sprinting": {"high_speed"},
    "squat": {"squat"}, "squatting": {"squat"}, "squats": {"squat"},
    "lunge": {"lunge"}, "lunging": {"lunge"}, "lunges": {"lunge"},
    "deadlift": {"hip_hinge"}, "deadlifting": {"hip_hinge"},
    "hinge": {"hip_hinge"}, "hinging": {"hip_hinge"},
    "twist": {"spinal_rotation"}, "twisting": {"spinal_rotation"}, "rotation": {"spinal_rotation"},
    "cutting": {"cutting"},
    "impact": {"impact"},
}

# Words that mean the negation governs a SYMPTOM or a meta-concept, not the
# movement that happens to follow it in the same clause - "no PAIN when
# jumping" negates pain, not jumping; "no RESTRICTION on jumping" negates
# the restriction itself, which is the opposite of stating one. Proximity
# alone could not tell these apart from "no jumping", because in both cases
# a negation word and a movement word sit a few tokens apart in the same
# clause - only what sits BETWEEN them says which one is actually negated.
_BLOCKING_WORDS = (
    "pain", "discomfort", "hurt", "hurts", "hurting", "ache", "aches",
    "aching", "sore", "soreness", "issue", "issues", "problem", "problems",
    "trouble", "difficulty", "restriction", "restrictions", "symptom",
    "symptoms", "avoiding", "avoided",
)

# "not avoiding jumping" - AVOIDING is itself one of the negation triggers,
# so without this check the same sentence gets read twice: once correctly
# rejected ("not" governs "avoiding", not "jumping" - caught by
# _BLOCKING_WORDS above, since "avoiding" is itself a blocking word) and
# once WRONGLY accepted, because "avoiding jumping" on its own reads as a
# direct, ungoverned negation-then-movement pair. This catches that second
# reading: an "avoid(ing)" trigger immediately preceded by another negation
# word is itself negated, so it does not restrict anything.
_META_NEGATED_AVOID = re.compile(r"\b(?:not|no|never|isn'?t|is\s+not)\s*$")


def _negates(lowered: str, word: str) -> bool:
    """
    Does a negation word DIRECTLY govern `word` in the same clause - not
    merely appear somewhere before it?

    Checked per known restriction word rather than by capturing "the phrase
    after the negation" as one generic group - a capture group has to guess
    where the phrase ends, and a short non-greedy guess matches the first
    word after the negation ("cannot DO squats" capturing "do") rather than
    the one that actually matters. Searching for each candidate word within a
    short distance of a negation finds the pair; the checks below then rule
    out the pairs where something between them - a symptom noun, a negated
    "avoiding" - means the negation was never actually about the movement:
    "no pain when jumping", "not avoiding jumping" and "no restriction on
    jumping" all put a negation word and "jumping" in the same short clause,
    exactly like "no jumping" does, and proximity alone cannot tell them
    apart.
    """
    pattern = re.compile(
        rf"\b(?P<neg>{_NEGATION})\b(?P<gap>[^.?!;]{{0,20}}?)\b{re.escape(word)}\b"
    )
    for m in pattern.finditer(lowered):
        gap = m.group("gap")
        if any(re.search(rf"\b{b}\b", gap) for b in _BLOCKING_WORDS):
            continue
        neg = m.group("neg")
        if neg.startswith("avoid"):
            preceding = lowered[max(0, m.start() - 12):m.start()]
            if _META_NEGATED_AVOID.search(preceding):
                continue
        return True
    return False


@dataclass
class ExplicitRestriction(InjuryProfile):
    """
    A user-stated movement restriction with no diagnosis behind it.

    Deliberately an InjuryProfile subclass rather than a new interface:
    contraindications.py and plan_repair.py already know how to read
    `.label`, `.severity`, `.stage.key`, `.restricted_patterns()` and
    `.keep_patterns()` - reusing that shape means the audit/repair pipeline
    needs zero changes to also enforce this. `restricted_patterns()` is
    overridden because there is no condition/region/stage to derive it from;
    it is exactly what the user's words meant, nothing inferred.
    """
    explicit_label: str = "stated restriction"
    explicit_patterns: Set[str] = field(default_factory=set)

    @property
    def label(self) -> str:
        return self.explicit_label

    def restricted_patterns(self) -> Set[str]:
        return set(self.explicit_patterns)

    def keep_patterns(self) -> Set[str]:
        return set()


def parse_explicit_restriction(text: str) -> Optional[ExplicitRestriction]:
    """
    "no jumping", "avoid overhead exercise", "no running" -> a restriction
    with the same deterministic authority a diagnosed injury has, without
    treating a preference as a diagnosis.
    """
    if not text or not text.strip():
        return None
    lowered = text.lower()
    matched: Set[str] = set()
    hit_words: List[str] = []
    for word, patterns in _RESTRICTION_WORDS.items():
        if _negates(lowered, word):
            matched |= patterns
            hit_words.append(word)
    if not matched:
        return None
    return ExplicitRestriction(
        raw=text.strip(), condition=None, region=None, severity=10, side=None,
        stage=_EXPLICIT_STAGE, red_flags=[],
        explicit_label=f"avoid {'/'.join(sorted(hit_words))}",
        explicit_patterns=matched,
    )


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


# injury_service.as_constraints() appends machine-generated prose after the
# injury itself: the stage guidance, an "Avoid: ..." exclusion list and a
# "Use instead: ..." substitution list, all looked up from CONTRAINDICATIONS
# by body part. That prose is full of anatomy words, and diagnosing from it
# read the wrong injury entirely:
#
#   "shoulder pain"  + "Avoid: ... behind-the-neck work"     -> cervical/neck
#   "sore elbow"     + "Avoid: ... wrist curls"              -> wrist/wrist
#   "sciatica"       + "Avoid: ... seated hamstring stretch" -> hamstring/thigh
#   "hip pain"       + "Avoid: ... groin ..."                -> adductor
#
# Every one of those then applied the wrong restriction set and the final
# audit reported clean. The diagnosis must come from what the USER said, so
# the generated tail is cut before any condition or region matching. The full
# text is still kept as `raw`, and severity is still read from the generated
# severity clause because that value is factual rather than inferred.
# as_constraints() always writes "(severity N/10, <stage label>)" - the stage
# label after the comma is what marks the clause as machine-written, and
# everything from there on is generated. A severity a USER typed has no stage
# label, so only the clause itself is dropped and the rest of their sentence
# survives: "knee pain (severity 5/10) and shoulder pain" must keep the
# shoulder.
# The marker must be the EXACT grammar as_constraints() writes - a severity
# followed by one of the real stage labels - and nothing looser. Accepting any
# text after the comma treated "knee pain (severity 5/10, improving) and
# shoulder pain" as machine-generated and silently deleted the shoulder.
# Built from STAGES so a renamed stage cannot quietly stop matching.
_GENERATED_CLAUSE_RE: Optional[re.Pattern] = None


def _stage_labels() -> set:
    """
    Every stage label the app can write into a constraint.

    There are two stage vocabularies: injury_taxonomy.STAGES drives the
    profile, while injury_service.as_constraints() writes the label from
    contraindications.stage_for(). Both are enumerated from their own
    definitions, so renaming a stage cannot silently stop the marker matching.
    """
    labels = {s.label for s in STAGES}
    try:  # lazy: contraindications imports this module inside its functions
        from app.services.contraindications import stage_for
        labels |= {stage_for(s)["label"] for s in range(0, 11)}
    except Exception:  # pragma: no cover - import guard
        pass
    return {label for label in labels if label}


def _generated_clause() -> re.Pattern:
    global _GENERATED_CLAUSE_RE
    if _GENERATED_CLAUSE_RE is None:
        alternatives = "|".join(
            re.escape(label) for label in sorted(_stage_labels(), key=len, reverse=True))
        _GENERATED_CLAUSE_RE = re.compile(
            r"\s*\(\s*severity\s*\d+\s*/\s*10\s*,\s*(?:" + alternatives
            + r")\s*\).*$", re.I | re.S)
    return _GENERATED_CLAUSE_RE

# A severity a user typed, with no stage label. Only the clause is removed;
# whatever they wrote around it survives.
_PLAIN_SEVERITY = re.compile(r"\s*\(\s*severity\s*\d+\s*/\s*10\s*\)", re.I)

_GENERATED_TAIL = re.compile(
    r"\s(?:Avoid:|Use instead:|This is the (?:left|right) side only\b)", re.I)


def diagnostic_subject(text: str, keep_severity: bool = False) -> str:
    """
    The part of a constraint that describes the INJURY, with any machine
    generated guidance removed.

    Text a user typed themselves is left intact apart from a bare severity
    clause, so "wrist pain; avoid jumping" keeps both halves.

    `keep_severity` leaves user-typed severity clauses in place, which
    parse_many() needs: "wrist pain (severity 2/10) and knee pain (severity
    7/10)" has a different severity per injury, and stripping them first threw
    that away.
    """
    if not text:
        return ""
    subject = _generated_clause().sub("", text)
    if not keep_severity:
        subject = _PLAIN_SEVERITY.sub(" ", subject)
    subject = _GENERATED_TAIL.split(subject, maxsplit=1)[0]
    return subject.strip() or text.strip()


def parse(text: str, severity: Optional[int] = None) -> Optional[InjuryProfile]:
    """
    Turn a free-text injury description into structure.

    Returns None only when the text says nothing injury-like at all. An
    unrecognised condition still returns a profile with a region, because
    "some shoulder thing I can't name" must not be treated as no injury.

    Condition and region come from `diagnostic_subject(text)`, never from the
    generated guidance that may follow it - see the comment above.
    """
    if not text or not text.strip():
        return None

    subject = diagnostic_subject(text)
    lowered = subject.lower()
    resolved_severity = _detect_severity(text, severity)

    # An explicit thoracic phrase wins over the CONDITIONS scan. "upper back
    # pain" and "mid back pain" contain the lumbar trigger "back pain", so the
    # condition scan claimed them first and applied lumbar rules - which at
    # the controlled stage restrict neither spinal_rotation nor overhead,
    # while the thoracic fallback restricts both. A mid-back complaint was
    # therefore handed thoracic rotation with audit_clean=True. No diagnosis
    # is claimed here; the region fallback is the whole point.
    thoracic = any(re.search(rf"(?<!\w){re.escape(h)}", lowered)
                   for h in _REGION_HINTS.get("thoracic", ()))

    condition = None
    if not thoracic:
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
        # Nothing recognisable as a medical condition. Before giving up
        # entirely, check whether this is an explicit, non-medical
        # restriction instead - "no jumping", "avoid overhead exercise" says
        # something real and actionable even though it is not an injury.
        explicit = parse_explicit_restriction(text)
        if explicit:
            return explicit

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
    profile = InjuryProfile(
        raw=text.strip(),
        condition=condition,
        region=region,
        severity=resolved,
        side=_detect_side(subject),
        stage=stage_for_severity(resolved),
        red_flags=flags,
    )

    # A recognised condition/region does not preclude the SAME text ALSO
    # stating an explicit, non-medical restriction - "wrist pain (severity
    # 0/10); avoid jumping" must keep both. This used to be checked only
    # inside the "nothing else recognised at all" branch above, so a
    # recognised injury silently swallowed any explicit restriction stated
    # alongside it - a severity-0 complaint on one joint could erase an
    # unrelated "avoid jumping" the user stated in the same breath.
    explicit = parse_explicit_restriction(text)
    if explicit:
        profile.extra_restricted = set(explicit.explicit_patterns)

    return profile


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


# One constraint string can name more than one injury. parse() returns the
# FIRST match, so "shoulder impingement and knee pain" became a shoulder
# problem and the knee was silently lost - a leg press then sailed through
# with audit_clean=True. Splitting the diagnostic subject into clauses and
# parsing each keeps both.
_CLAUSE_SPLIT = re.compile(
    r"\s*(?:[;,]|\band\b|\bbut\b|\bwith\b|\bplus\b|\balso\b|\bas well as\b)\s+", re.I)

# A clause that says an injury is ABSENT must not create one.
_NEGATED_CLAUSE = re.compile(r"^\s*(?:no|not|without|never|nothing)\b", re.I)

# Circumstance, not injury: in "knee pain after a shoulder workout" the
# shoulder is where they were training, not what hurts. Everything from the
# context word on is dropped before matching, so the anatomy that owns the
# complaint is the one that wins.
_CONTEXT_CLAUSE = re.compile(
    r"\b(?:after|following|during|since|from|because\s+of|due\s+to|while)\b", re.I)


def _split_clauses(subject: str) -> List[str]:
    """
    Split on separators that sit OUTSIDE parentheses.

    Severity clauses are carried through the split so each injury keeps its
    own rating, and "(severity 5/10, improving)" contains a comma that must
    not become a clause boundary.
    """
    def scan(respect_parens: bool):
        parts: List[str] = []
        depth = start = index = 0
        while index < len(subject):
            char = subject[index]
            if respect_parens and char == "(":
                depth += 1
            elif respect_parens and char == ")":
                depth = max(0, depth - 1)
            elif depth == 0:
                match = _CLAUSE_SPLIT.match(subject, index)
                if match and match.end() > match.start():
                    parts.append(subject[start:index])
                    start = index = match.end()
                    continue
            index += 1
        parts.append(subject[start:])
        return [p for p in parts if p.strip()], depth

    parts, depth = scan(True)
    if depth:
        # An unclosed parenthesis would swallow every later separator, and
        # "knee pain (severity 5/10 and shoulder pain" then resolved to the
        # shoulder alone - the knee vanished. Malformed input must not cost an
        # injury, so rescan without paren tracking.
        parts, _ = scan(False)
    return parts


def parse_many(text: str, severity: Optional[int] = None) -> List[InjuryProfile]:
    """
    Every injury named in one constraint string, not just the first.

    Falls back to the single-profile parse when clause splitting finds
    nothing, so a description that does not decompose behaves exactly as it
    did before.
    """
    if not text or not str(text).strip():
        return []

    text = str(text)
    # Severity clauses are kept while splitting, because each injury may carry
    # its own: "wrist pain (severity 2/10) and knee pain (severity 7/10)" gave
    # the knee the wrist's 2/10, and at 2/10 a knee has speed restrictions
    # only - a leg press walked straight through.
    subject = diagnostic_subject(text, keep_severity=True)
    fallback_severity = _detect_severity(text, severity)
    overall_side = _detect_side(subject)

    profiles: List[InjuryProfile] = []
    seen = set()
    negated_only = False
    for clause in _split_clauses(subject):
        clause = clause.strip()
        if not clause:
            continue
        if _NEGATED_CLAUSE.match(clause):
            negated_only = True
            continue
        core = _CONTEXT_CLAUSE.split(clause, maxsplit=1)[0].strip() or clause
        # This clause's own severity wins; the string-level or supplied value
        # is only a fallback for a clause that states none.
        clause_severity = _detect_severity(core, None)
        profile = parse(core, clause_severity if clause_severity is not None
                        else fallback_severity)
        if profile is None:
            continue
        # A fragment must actually resolve to something. "left and right knee
        # pain" splits into "left" and "right knee pain"; the bare side word
        # inherits the severity and would otherwise become a second, empty
        # injury. An unrecognised whole description ("costochondritis 6/10")
        # is still kept, by the single-parse fallback below.
        if not (profile.condition or profile.region or profile.red_flags
                or getattr(profile, "explicit_patterns", None)):
            continue
        key = (getattr(profile.condition, "key", None), profile.region,
               tuple(sorted(getattr(profile, "explicit_patterns", ()) or ())))
        if key in seen:
            continue
        seen.add(key)
        profiles.append(profile)

    if not profiles:
        if negated_only:
            # Every clause said an injury was ABSENT. Falling through to the
            # single parse ignored the negation and invented the very injury
            # the user had just ruled out ("no knee pain" -> a knee injury).
            # An explicit restriction stated alongside it still counts.
            explicit_only = parse_explicit_restriction(text)
            return [explicit_only] if explicit_only else []
        single = parse(text, severity)
        return [single] if single else []

    # "left and right knee pain" splits into "left" and "right knee pain": the
    # bare side word resolves to nothing, so only the whole subject knows both
    # sides are involved. Promote to bilateral ONLY when every profile is the
    # same region - in "left wrist pain and right knee pain" the two sides
    # belong to different injuries, and marking both bilateral would restrict
    # two healthy limbs for no reason.
    regions = {profile.region for profile in profiles}
    if overall_side == "bilateral" and len(regions) == 1:
        for profile in profiles:
            profile.side = "bilateral"
    elif overall_side and len(profiles) == 1 and not profiles[0].side:
        profiles[0].side = overall_side

    # An explicit restriction stated alongside an injury ("wrist pain; avoid
    # jumping") is carried by parse() as extra_restricted on every profile
    # built from the full text. Re-apply it here, because the clause-level
    # parses only ever saw their own fragment.
    explicit = parse_explicit_restriction(text)
    if explicit:
        for profile in profiles:
            if not isinstance(profile, ExplicitRestriction):
                profile.extra_restricted = (
                    set(profile.extra_restricted or set())
                    | set(explicit.explicit_patterns))

    return profiles


def parse_all(constraints) -> List[InjuryProfile]:
    """Parse a list of constraint strings, dropping anything unrecognisable."""
    out: List[InjuryProfile] = []
    for c in constraints or []:
        out.extend(parse_many(str(c)))
    return out


def profiles_for(constraints) -> List[InjuryProfile]:
    """
    THE way to turn constraint strings into injury profiles.

    fitmentor_service, contraindications and plan_repair each used to build
    this list themselves - two of them with a bare `parse()` comprehension,
    which is how the multi-injury and generated-guidance bugs reached some
    paths but not others. One helper means one behaviour everywhere.
    """
    return parse_all(constraints)
