"""
What an exercise *is*, rather than what it is called.

THE PROBLEM
-----------
Injury safety was matched on exercise names. That fails, repeatedly and in the
same way, because names are unbounded and generated text invents new ones:

    list said "sprinting"              plan said "Sprints (20m)"          missed
    list said "shuttle runs"           plan said "Pro Agility Shuttle"    missed
    list said "bent-over barbell row"  plan said "Bent Over Dumbbell Row" missed

Each time the fix was another string, and each time the next unseen phrasing
got through. The list can only contain what someone already thought of.

THE APPROACH
------------
Classify the movement instead. A hamstring is loaded by the *hip hinge* - the
bent-over position with a long lever - and it does not care whether you are
holding a barbell, a dumbbell, a kettlebell or nothing at all. So:

    "Bent Over Dumbbell Row"  ->  {hip_hinge, horizontal_pull}
    "Chest-Supported Row"     ->  {horizontal_pull}
    "Pro Agility Shuttle"     ->  {running, cutting, high_speed}

and the injury rules restrict *patterns*. An unseen name still classifies,
because the words that describe a movement's shape are far more stable than
the words that name it.

WHAT THIS IS NOT
----------------
Not a complete exercise database, and not a clinical tool. It is a
decision-support layer that errs toward caution: an exercise it cannot
classify is reported as unknown so the caller can be careful with it, rather
than being silently assumed safe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# the vocabulary
# ---------------------------------------------------------------------------

# Movement patterns. Deliberately few - these are the shapes that determine
# which tissue takes load, not a taxonomy of every exercise variation.
PATTERNS = {
    # lower body
    "hip_hinge",         # bending at the hip with a long spine and long lever
    "squat",             # knee-dominant bilateral flexion
    "lunge",             # split stance, loaded front knee
    "knee_flexion",      # bending the knee under load (leg curls, nordics)
    "knee_extension",    # straightening the knee under load
    "calf_raise",
    "hip_abduction",
    "hip_adduction",
    # Bridging and thrusting: hip extension with the back supported and a
    # short lever. NOT a hinge - this is what people are given instead of one,
    # so conflating the two would remove the standard substitution.
    "hip_extension",
    # upper body
    "vertical_push",     # overhead
    "horizontal_push",
    "vertical_pull",
    "horizontal_pull",
    "elbow_flexion",
    "elbow_extension",
    "shoulder_rotation",
    "gripping",
    # trunk
    "spinal_flexion",    # sit-ups, crunches
    "spinal_extension",  # back extensions, hyperextensions
    "spinal_rotation",
    "anti_rotation",     # planks, dead bugs - bracing without moving
    "axial_load",        # weight on the spine
    # locomotion and impact
    "running",
    "high_speed",        # sprinting, accelerations, max velocity
    "jumping",           # take-off and landing
    "cutting",           # change of direction under speed
    "impact",            # repeated ground contact
    # --- ankle and foot -------------------------------------------------
    # Case A: a plan for a 6/10 ankle sprain contained seated calf raises,
    # leg press, deadlifts, RDLs, cycling and a standing Pallof press, and the
    # model called it ankle-safe. "Seated" and "low impact" are not the same
    # as "the ankle is unloaded", and the ontology had no way to say so.
    "plantarflexion",     # pointing the foot - calf raises, cycling, pressing
    "dorsiflexion",       # pulling the foot up - deep squat, lunge, descending
    "repetitive_ankle",   # cyclical ankle motion under load - bike, elliptical
    "weight_bearing",     # standing with bodyweight through the foot
    "loaded_stance",      # standing while carrying EXTERNAL load
    "seated_supported",   # foot force present but body weight taken elsewhere
    "non_weight_bearing", # lying, seated with the leg free, in water

    # qualities
    "overhead",
    "end_range_stretch",
    "maximal_effort",     # heavy load - 1RM, to failure, heavy singles
    "cardio_intensity",   # hard breathing - HIIT, intervals, conditioning
    "isometric",
    "unilateral",
    "low_impact",        # cycling, swimming, machines
}


@dataclass
class Movement:
    """One exercise, resolved into what it demands of the body."""
    raw: str
    patterns: Set[str] = field(default_factory=set)
    # True when nothing matched. The caller should treat this as "unclassified",
    # not as "safe" - which is the entire point of tracking it separately.
    unknown: bool = False

    def has(self, *names: str) -> bool:
        return any(n in self.patterns for n in names)


# ---------------------------------------------------------------------------
# classification rules
#
# Each rule is (regex, patterns it implies). Ordered general -> specific, and
# a phrase may match several rules; the resulting pattern set is their union.
#
# The regexes describe SHAPE words. "bent over", "hinge", "romanian", "good
# morning" and "deadlift" all describe the same hip position, which is why they
# share a rule rather than needing one entry each.
# ---------------------------------------------------------------------------

# Named exercises whose name actively misleads the general rules. Checked
# first and exclusively, because getting these wrong is worse than not
# classifying them at all - a confident wrong answer passes the audit.
#
#   "Reverse Nordic" contains "nordic" (a knee FLEXION exercise) but is knee
#   EXTENSION, so a quad injury was left unprotected while a hamstring injury
#   wrongly blocked it.
#   "Jefferson Curl" contains "curl" (elbow flexion) but is loaded spinal
#   flexion - close to the worst thing you can give a lumbar disc injury.
_EXCEPTIONS: List[tuple] = [
    (r"reverse nordic|reverse hamstring curl",
     {"knee_extension", "end_range_stretch"}),
    (r"jefferson curl|jefferson deadlift",
     {"spinal_flexion", "hip_hinge", "end_range_stretch"}),
    (r"sissy squat",
     {"knee_extension", "end_range_stretch"}),
    (r"copenhagen",
     {"hip_adduction", "isometric"}),
    (r"reverse hyper",
     {"hip_hinge", "spinal_extension"}),
]

_RULES: List[tuple] = [
    # --- hip hinge: the pattern that caused three separate misses ---------
    (r"bent[\s-]?over|bentover|bent\s+\w*\s*row|hip hinge|hinge|romanian|rdl\b|"
     r"stiff[\s-]?leg|straight[\s-]?leg deadlift|good morning|"
     r"meadows row|kroc row|dead row|seal row(?!.*chest)|"
     r"deadlift|dl\b|pendlay|t[\s-]?bar row|barbell row|yates row|"
     r"back extension|hyperextension|reverse hyper|glute[\s-]?ham|ghr\b|"
     r"kettlebell swing|kb swing|clean pull|snatch pull|high pull|"
     r"single[\s-]?leg (?:rdl|deadlift)",
     {"hip_hinge"}),

    # --- squat and knee dominant ------------------------------------------
    (r"\bsquat|hack squat|leg press|sissy squat|wall sit|box squat|"
     r"goblet|front squat|back squat|pistol",
     {"squat", "knee_extension"}),
    (r"\blunge|split squat|step[\s-]?up|bulgarian|walking lunge|reverse lunge",
     {"lunge", "knee_extension", "unilateral"}),
    (r"leg extension|knee extension|terminal knee",
     {"knee_extension"}),
    (r"leg curl|hamstring curl|nordic|glute[\s-]?ham raise|"
     r"knee flexion|slider curl|ball curl",
     {"knee_flexion"}),
    (r"calf raise|heel raise|calf press|donkey calf",
     {"calf_raise"}),
    (r"abduction|clamshell|banded walk|monster walk|side[\s-]?lying raise",
     {"hip_abduction"}),
    (r"adduction|copenhagen|adductor|inner thigh",
     {"hip_adduction"}),
    (r"glute bridge|hip thrust|hip extension|\bbridges?\b|frog pump|"
     r"single[\s-]?leg bridge",
     {"hip_extension"}),

    # --- upper body pushing and pulling ------------------------------------
    (r"overhead press|shoulder press|military press|push press|jerk|"
     r"handstand|pike push|behind[\s-]?the[\s-]?neck|arnold press|"
     r"landmine press|z press",
     {"vertical_push", "overhead"}),
    (r"bench press|chest press|push[\s-]?up|floor press|dip\b|dips\b|"
     r"chest (?:fly|flye)|pec deck|cable crossover|incline press|decline press",
     {"horizontal_push"}),
    (r"pull[\s-]?up|chin[\s-]?up|lat pulldown|pulldown|"
     r"straight[\s-]?arm pulldown",
     {"vertical_pull", "overhead"}),
    (r"\brow\b|\brows\b|seated row|cable row|machine row|face pull|"
     r"chest[\s-]?supported|inverted row|ring row",
     {"horizontal_pull"}),
    (r"lateral raise|side raise|front raise|rear delt|reverse fly",
     {"shoulder_rotation"}),
    (r"external rotation|internal rotation|cuban press|rotator cuff|"
     r"band pull[\s-]?apart",
     {"shoulder_rotation"}),
    (r"upright row",
     {"vertical_pull", "shoulder_rotation"}),
    (r"(?<!leg )(?<!nordic )(?<!hamstring )(?<!ham )(?<!slider )(?<!ball )"
     r"(?:curl\b|curls\b)|bicep|hammer curl|preacher",
     {"elbow_flexion", "gripping"}),
    (r"tricep|skull crusher|pushdown|kickback|overhead extension|"
     r"close[\s-]?grip",
     {"elbow_extension"}),
    (r"farmer|carry|carries|grip|dead hang|hold the bar|deadhang",
     {"gripping"}),

    # --- trunk --------------------------------------------------------------
    (r"sit[\s-]?up|crunch|leg raise|knee raise|toes to bar|v[\s-]?up|"
     r"hollow|jackknife",
     {"spinal_flexion"}),
    (r"russian twist|woodchop|wood chop|cable rotation|twist|"
     r"landmine rotation|medicine ball throw|med ball throw",
     {"spinal_rotation"}),
    (r"plank|dead[\s-]?bug|bird[\s-]?dog|pallof|anti[\s-]?rotation|"
     r"suitcase|side plank",
     {"anti_rotation", "isometric"}),
    (r"back squat|front squat|overhead squat|barbell squat|"
     r"loaded carry|zercher",
     {"axial_load"}),

    # --- locomotion and impact ---------------------------------------------
    # This block is why "Pro Agility Shuttle" and "Sprints (20m)" now resolve.
    (r"sprint|max(?:imum)?[\s-]?velocity|maximal velocity|flying \d+|acceleration|"
     r"high[\s-]?speed|short burst|burst run|explosive run|explosive effort|"
     r"accel\b|top speed|stride[\s-]?out|striding|\d+\s?m dash|"
     r"hill sprint|resisted run|sled sprint",
     {"running", "high_speed", "impact"}),
    (r"\bruns?\b|running|\bjog\b|jogging|treadmill|road work|tempo run|"
     r"fartlek|interval run|shuttle|beep test|yo[\s-]?yo test|"
     r"\d+\s?km|\d+\s?mile",
     {"running", "impact"}),
    (r"agility|ladder drill|cone drill|zig[\s-]?zag|change of direction|"
     r"\bcod\b|lateral cut|\bcuts?\b|side[\s-]?step drill|weave|"
     r"cutting|shuttle|t[\s-]?test|pro agility|5[\s-]?10[\s-]?5",
     {"cutting", "running", "impact", "high_speed"}),
    (r"jump|jumping|hop\b|hops\b|bound|plyo|plyometric|box jump|"
     r"broad jump|depth jump|skip\b|skipping|jump rope|burpee|"
     r"tuck jump|squat jump",
     {"jumping", "impact"}),

    # --- stance and weight bearing -----------------------------------------
    # This block is why a deadlift is no longer "just a hip hinge" for someone
    # with a bad ankle: standing under load puts the whole system through the
    # foot, whatever the exercise is nominally training.
    (r"deadlift|romanian|rdl\b|good morning|clean|snatch|jerk|"
     r"back squat|front squat|overhead squat|barbell squat|zercher|"
     r"standing (?:press|row|curl|raise|calf|cable|pallof|band)|"
     r"farmer|carry|carries|suitcase|yoke|sled push|sled drag|"
     r"kettlebell swing|thruster|lunge|step[\s-]?up|split squat",
     {"weight_bearing", "loaded_stance"}),
    (r"\bsquat|\blunge|step[\s-]?up|calf raise|jump|hops?\b|bound|"
     r"\brun|sprint|walk|stand|balance|agility|shuttle|cutting|"
     r"plyometric|skater|pistol",
     {"weight_bearing"}),
    (r"seated|sitting|lying|prone|supine|bench[\s-]?supported|"
     r"chest[\s-]?supported|machine|kneeling|floor|half[\s-]?kneeling",
     {"seated_supported"}),
    (r"swim|swimming|pool|aqua|upper[\s-]?body ergometer|arm bike|"
     r"lying|supine|seated cable|seated row|lat pulldown|leg extension|"
     r"leg curl|hip thrust|glute bridge|dead[\s-]?bug|bird[\s-]?dog",
     {"non_weight_bearing"}),

    # --- ankle mechanics ----------------------------------------------------
    # Ankle load is not the same as ground impact. A seated calf raise has no
    # impact at all and is the most direct plantarflexion loading there is.
    (r"calf raise|heel raise|calf press|donkey calf|toe raise|"
     r"plantarflex|pointe|tibialis|seated calf|standing calf",
     {"plantarflexion"}),
    (r"deep squat|full squat|ass to grass|atg|dorsiflex|"
     r"knees over toes|deep lunge|weighted squat hold",
     {"dorsiflexion"}),
    # Cycling, elliptical and rowing all cycle the ankle continuously under
    # load. They are LOW IMPACT and NOT low ankle load - the distinction the
    # previous model could not express.
    # Upper-body ergometers and arm bikes are excluded by the lookbehind:
    # they cycle the SHOULDERS, and treating "ergometer" as an ankle movement
    # removed one of the few conditioning options an ankle injury leaves.
    (r"(?<!upper[\s-]body )(?<!arm )(?<!upper body )"
     r"(?:cycl|bike|spin\b|elliptical|cross[\s-]?trainer|stair|"
     r"rowing machine|\berg\b|ergometer|ski erg|arc trainer)",
     {"repetitive_ankle", "plantarflexion"}),

    # --- qualities ----------------------------------------------------------
    (r"hiit|tabata|circuit|for time|emom|metcon|conditioning|intervals?\b",
     {"cardio_intensity"}),
    (r"max effort|maximal|1rm|one rep max|to failure|amrap|all[\s-]?out|"
     r"heavy single|as heavy as possible|pr attempt|test day",
     {"maximal_effort"}),
    (r"isometric|hold\b|holds\b|wall sit|static hold|iso ",
     {"isometric"}),
    (r"stretch|mobility|yoga|forward fold|toe touch|downward dog|"
     r"pigeon|butterfly|splits|pnf|hamstring stretch",
     {"end_range_stretch"}),
    (r"cycle|cycling|bike|elliptical|rowing machine|erg\b|ergometer|"
     r"ski erg|air bike|assault bike|swim|swimming|pool|aqua|stationary|"
     r"\bwalks?\b|walking(?! lunge)|brisk walk|incline walk|ruck|hike",
     {"low_impact"}),
    (r"single[\s-]?arm|single[\s-]?leg|one[\s-]?arm|one[\s-]?leg|unilateral|"
     r"split stance|staggered",
     {"unilateral"}),
]

# Phrases that make a movement supported, removing the hinge or the balance
# demand. "Chest-supported row" and "seated row" are the standard substitutions
# for someone who cannot hinge, so classifying them as hinges would leave
# nothing to train the back with.
_SUPPORTED = re.compile(
    r"chest[\s-]?supported|seated|machine|smith|supported|lying|"
    r"prone(?! row)|incline bench|bench[\s-]?supported|cable(?! rotation)",
    re.I,
)

# Anything that means the exercise is being named in order to exclude it.
_NEGATION = re.compile(
    r"instead of|rather than|avoid|avoided|avoiding|no |not |replaced|"
    r"replacing|swap|swapped|removed|removing|remove|excluded|excluding|"
    r"skip|skipped|in place of|substitut|left out|dropped|for safety",
    re.I,
)


def normalise(text: str) -> str:
    """Lowercase, strip punctuation noise, collapse whitespace."""
    lowered = (text or "").lower()
    lowered = re.sub(r"[（）()\[\]{}*_#:•·–—]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def classify(text: str) -> Movement:
    """
    Resolve an exercise description into movement patterns.

    Works on a whole line, because generated plans write "Bent Over Dumbbell
    Rows: 3 sets of 8-12 reps" rather than a bare exercise name, and the
    set-and-rep noise is harmless to match through.
    """
    cleaned = normalise(text)
    movement = Movement(raw=text.strip())
    if not cleaned:
        movement.unknown = True
        return movement

    # Exceptions win outright. If one matches, the general rules are skipped
    # entirely - their whole purpose is to override a misleading name.
    for pattern, implies in _EXCEPTIONS:
        if re.search(pattern, cleaned):
            movement.patterns |= implies
            movement.unknown = False
            return movement

    for pattern, implies in _RULES:
        if re.search(pattern, cleaned):
            movement.patterns |= implies

    # A supported version of a pull is not a hinge. This has to run after the
    # rules, because "chest-supported row" legitimately matches the row rule
    # and must keep horizontal_pull while losing hip_hinge.
    if _SUPPORTED.search(cleaned):
        movement.patterns.discard("hip_hinge")
        movement.patterns.discard("axial_load")
        # A seated or machine version also removes the balance demand.
        movement.patterns.discard("unilateral")

    movement.unknown = not movement.patterns
    return movement


def classify_prescribed(text: str) -> Movement:
    """
    Classify only the part of a line that is actually being PRESCRIBED.

    Plan lines routinely name two movements with opposite intent:

        "Cycling instead of running: 20 minutes"
        "Chest-supported rows rather than bent-over rows"
        "Removed: sprints and box jumps"

    Classifying the whole line marks all of them as present, so a line whose
    entire purpose is to avoid running gets flagged for containing running.
    Cutting at the negation keeps the prescription and discards the rest -
    and when the negation comes first, nothing is being prescribed at all.
    """
    cleaned = normalise(text)
    negation = _NEGATION.search(cleaned)
    if not negation:
        return classify(text)

    prescribed = cleaned[: negation.start()].strip()
    if not prescribed:
        # The line begins with the negation - "Removed: sprints". Nothing here
        # is being asked for.
        return Movement(raw=text.strip(), patterns=set(), unknown=False)
    return classify(prescribed)


def is_negated(text: str) -> bool:
    """
    Whether the line names a movement only to say it is being avoided.

    Position matters: "cycling instead of running" is an avoidance, but
    "squats (avoid deep squats)" is prescribing squats with a caveat, and
    treating both the same let the second kind straight through.
    """
    cleaned = normalise(text)
    negation = _NEGATION.search(cleaned)
    if not negation:
        return False

    # Find where the first classified movement word appears. If the negation
    # comes first, the movement is being ruled out rather than prescribed.
    earliest_movement = len(cleaned)
    for pattern, _ in _RULES:
        match = re.search(pattern, cleaned)
        if match and match.start() < earliest_movement:
            earliest_movement = match.start()

    return negation.start() < earliest_movement


def describe(patterns: Set[str]) -> str:
    """Human-readable pattern list, for explaining a decision."""
    return ", ".join(sorted(p.replace("_", " ") for p in patterns)) or "unclassified"
