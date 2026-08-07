"""
Injury -> movement exclusions, as data rather than prose.

WHY THIS EXISTS
---------------
The anatomy rules previously lived only inside the chatbot's system prompt.
That worked for the conversational path, but the specialist pages call
/fitness/adapt-workout-plan directly and got none of it - so telling FitMentor
"my knee hurts" produced a plan that still contained deep squats.

Holding the rules as a lookup table means:
  * both paths use identical logic
  * it is unit-testable, unlike a paragraph of instructions
  * adding an injury is a dict entry, not a prompt rewrite
  * it costs no tokens to consult

WHY THREE CATEGORIES OF EXCLUSION
---------------------------------
The obvious one - "don't contract the injured muscle" - misses most of the
risk. A hip hinge loads the hamstring hard even though it reads as a back
exercise, and a forward fold loads it at end range with no weight at all. Each
entry below therefore lists direct loading, lengthened-position loading, and
stretching separately.

This is general strength-programming guidance, not rehabilitation advice, and
the caller is expected to say so to the user.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Contraindication:
    key: str
    label: str
    # Words that indicate this injury in free text.
    triggers: List[str]
    # Exercises that directly load the injured tissue.
    direct: List[str] = field(default_factory=list)
    # Loaded positions that lengthen it - the commonly missed category.
    lengthened: List[str] = field(default_factory=list)
    # Stretching / mobility work that takes it to end range.
    stretches: List[str] = field(default_factory=list)
    # Safer replacements, so the plan keeps training the same pattern.
    substitutions: List[str] = field(default_factory=list)

    def all_excluded(self) -> List[str]:
        seen, out = set(), []
        for item in self.direct + self.lengthened + self.stretches:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out


CONTRAINDICATIONS: Dict[str, Contraindication] = {
    "hamstring": Contraindication(
        key="hamstring",
        label="hamstring injury",
        triggers=["hamstring", "back of thigh", "sit bone", "ischial", "high hamstring", "proximal hamstring"],
        direct=["leg curls", "nordic curls", "sprinting", "HIIT", "box jumps", "bounding"],
        lengthened=["squats", "deadlifts", "Romanian deadlifts", "good mornings", "lunges",
                    "leg press", "bent-over barbell rows", "T-bar rows", "kettlebell swings",
                    "straight-leg raises", "hanging leg raises"],
        stretches=["forward folds", "seated hamstring stretches", "downward dog", "pike stretches",
                   "toe touches"],
        substitutions=["chest-supported or seated rows instead of bent-over rows",
                       "bent-knee core work instead of straight-leg raises",
                       "seated calf raises and leg extensions within a pain-free range",
                       "upper-body and core sessions in place of leg day"],
    ),
    "lower_back": Contraindication(
        key="lower_back",
        label="lower back pain",
        triggers=["lower back", "low back", "lumbar", "back pain", "slipped disc", "herniated"],
        direct=["deadlifts", "good mornings", "barbell rows", "back extensions under load"],
        lengthened=["heavy overhead press", "weighted twists", "sit-ups", "leg raises",
                    "loaded carries with poor posture"],
        stretches=["deep forward folds", "aggressive spinal twists"],
        substitutions=["chest-supported rows", "machine or supported pressing",
                       "dead bugs and bird dogs instead of sit-ups",
                       "glute bridges for posterior chain work"],
    ),
    "knee": Contraindication(
        key="knee",
        label="knee injury",
        triggers=["knee", "patella", "acl", "mcl", "meniscus", "runner's knee"],
        direct=["deep squats", "lunges", "leg extensions under load", "pistol squats",
                "jumping", "plyometrics", "running on hard surfaces"],
        lengthened=["step-ups onto high boxes", "sissy squats"],
        stretches=["deep kneeling stretches"],
        substitutions=["box squats to a comfortable depth",
                       "leg press within a shortened range",
                       "swimming or cycling instead of running",
                       "glute bridges and hip thrusts"],
    ),
    "shoulder": Contraindication(
        key="shoulder",
        label="shoulder injury",
        triggers=["shoulder", "rotator cuff", "delt", "impingement", "labrum", "ac joint"],
        direct=["overhead press", "upright rows", "dips", "behind-the-neck work",
                "lateral raises above shoulder height"],
        lengthened=["bench press near end range", "deep chest flyes", "wide-grip pressing"],
        stretches=["aggressive doorway chest stretches", "sleeper stretch under load"],
        substitutions=["neutral-grip and landmine pressing",
                       "cable work within a pain-free arc",
                       "floor press instead of bench press"],
    ),
    "wrist": Contraindication(
        key="wrist",
        label="wrist pain",
        triggers=["wrist", "carpal", "forearm"],
        direct=["push-ups on flat palms", "front squats", "barbell curls", "planks on hands"],
        lengthened=["heavy pressing with bent wrists"],
        stretches=["deep wrist extension stretches"],
        substitutions=["dumbbell or neutral-grip variations",
                       "push-ups on parallettes or dumbbells",
                       "forearm planks instead of hand planks",
                       "straps for pulling movements"],
    ),
    "ankle": Contraindication(
        key="ankle",
        label="ankle injury",
        triggers=["ankle", "achilles", "plantar", "calf strain"],
        direct=["running", "jumping", "skipping", "calf raises under load", "sprinting"],
        lengthened=["deep squats requiring dorsiflexion"],
        stretches=["aggressive calf stretches", "deep lunge stretches"],
        substitutions=["cycling or swimming for cardio",
                       "seated leg work",
                       "upper-body focused sessions"],
    ),
    "hip": Contraindication(
        key="hip",
        label="hip injury",
        triggers=["hip", "groin", "adductor", "hip flexor", "labral"],
        direct=["deep squats", "wide-stance work", "adductor machine", "high knees"],
        lengthened=["deep lunges", "sumo deadlifts", "side splits"],
        stretches=["deep pigeon pose", "butterfly stretch under pressure"],
        substitutions=["narrow-stance movements in a comfortable range",
                       "machine-based leg work",
                       "glute bridges"],
    ),
    "neck": Contraindication(
        key="neck",
        label="neck pain",
        triggers=["neck", "cervical", "trap strain"],
        direct=["shrugs", "overhead press", "neck bridges", "heavy front squats"],
        lengthened=["behind-the-neck pulldowns"],
        stretches=["forced neck stretches"],
        substitutions=["supported and machine-based movements",
                       "keeping load off the upper traps"],
    ),
}

# Phrases that mean "get this looked at", not "work around it".
RED_FLAGS = (
    "sharp pain", "numbness", "tingling", "swelling", "giving way", "gave way",
    "can't put weight", "cannot put weight", "getting worse", "worse", "popped",
    "clicking and pain", "locked",
)


def detect(text: str) -> List[Contraindication]:
    """Find every injury mentioned in a piece of free text."""
    if not text:
        return []
    low = text.lower()
    found = []
    for c in CONTRAINDICATIONS.values():
        if any(t in low for t in c.triggers):
            found.append(c)
    return found


def has_red_flag(text: str) -> bool:
    """True if the wording suggests this needs a clinician rather than a plan."""
    return bool(text) and any(f in text.lower() for f in RED_FLAGS)


def expand_feedback(feedback: str) -> str:
    """
    Turn "my knee hurts" into instructions a generator can actually act on.

    The specialist services do not reason about anatomy, so passing the user's
    words through unchanged is what produced plans that still contained the
    offending exercises. Returns the feedback unchanged when no injury is
    detected.
    """
    found = detect(feedback)
    if not found:
        return feedback

    parts = [feedback.strip()]
    for c in found:
        excluded = ", ".join(c.all_excluded())
        parts.append(
            f"\n\nIMPORTANT - {c.label}. Remove ALL of the following from the plan: "
            f"{excluded}."
        )
        if c.substitutions:
            parts.append("Substitute: " + "; ".join(c.substitutions) + ".")

    parts.append(
        "\nState clearly at the end which exercises were removed and why. "
        "Add one short line noting that an exercise plan is not rehabilitation "
        "and a physiotherapist can advise on what this specific injury tolerates."
    )
    return " ".join(parts)


def summarise(feedback: str) -> Optional[dict]:
    """Machine-readable summary of what was detected, for the UI to display."""
    found = detect(feedback)
    if not found:
        return None
    return {
        "injuries": [
            {
                "label": c.label,
                "excluded": c.all_excluded(),
                "substitutions": c.substitutions,
            }
            for c in found
        ],
        "red_flag": has_red_flag(feedback),
    }
