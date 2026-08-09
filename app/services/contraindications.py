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

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


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
    # Whether running, jumping and change-of-direction work are risky for this
    # injury. True for anything load-bearing; False for upper-limb problems,
    # where sprinting is entirely safe and removing it takes away useful
    # training for nothing.
    impact_sensitive: bool = True

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
        # Running and jogging belong here, not just sprinting. The hamstring
        # works hardest in late swing phase at any pace, which is why a plan
        # that avoided deadlifts but opened every session with a jog was still
        # loading the injury five times a week.
        # Sprint variants get their own attention because they are both the
        # most dangerous entry here and the most likely to appear in a plan
        # for an athlete. A generated football plan came back prescribing
        # "Sprints (20m)" and a "Pro Agility Shuttle" for a 6/10 proximal
        # strain - neither matched "sprinting" or "shuttle runs", so both the
        # filter and its test waved them through.
        direct=["leg curls", "nordic curls",
                "sprint", "sprints", "sprinting", "hill sprint", "hill sprints",
                "shuttle", "shuttles", "shuttle run", "shuttle runs",
                "agility", "agility drill", "agility drills", "agility ladder",
                "change of direction", "cutting drills", "acceleration",
                "accelerations", "running", "jogging", "jog", "run",
                "high knees", "butt kicks", "hurdle", "hurdles", "striding",
                "HIIT", "box jumps", "bounding", "plyometric", "plyometrics",
                "jumping", "skipping"],
        # Hip hinges are listed by SHAPE, not by implement. A generated plan
        # came back with "Bent Over Dumbbell Rows" for a 6/10 proximal strain
        # and passed the filter, because the list named the barbell and T-bar
        # versions and nothing else. What loads the hamstring is the bent-over
        # position; the thing in your hands is irrelevant.
        lengthened=["squats", "deadlifts", "Romanian deadlifts", "good mornings", "lunges",
                    "leg press", "kettlebell swings",
                    "bent over", "bent-over", "bentover",
                    "barbell row", "barbell rows", "pendlay row", "pendlay rows",
                    "T-bar row", "T-bar rows", "hip hinge", "hip hinges",
                    "straight-leg raises", "straight leg raises",
                    "hanging leg raises", "back extension", "back extensions",
                    "reverse hyper", "reverse hypers", "glute ham raise",
                    "glute-ham raise", "GHR"],
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
        # Upper limb - running, jumping and agility work are unaffected.
        impact_sensitive=False,
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
        # Upper limb - running, jumping and agility work are unaffected.
        impact_sensitive=False,
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
        # Upper limb - running, jumping and agility work are unaffected.
        impact_sensitive=False,
    ),

    # --- conditions the app already recognised but had no rules for ------
    # mentions_injury() has detected all of these since the audit, and every
    # one of them produced a plan with no exclusions whatsoever - detected,
    # acknowledged in conversation, and then silently ignored by the generator.
    "sciatica": Contraindication(
        key="sciatica",
        label="sciatica",
        triggers=["sciatica", "sciatic", "nerve pain down", "shooting pain down my leg",
                  "radiating leg pain"],
        direct=["deadlifts", "good mornings", "heavy squats", "sit-ups", "leg raises",
                "seated rows with a rounded back"],
        lengthened=["seated hamstring stretches", "forward folds", "toe touches",
                    "slump sitting", "long seated work"],
        stretches=["aggressive piriformis stretching", "deep forward folds"],
        substitutions=["walking within a pain-free distance",
                       "standing rather than seated work where possible",
                       "nerve glides only if a physio has prescribed them",
                       "glute bridges and bird dogs for the posterior chain"],
    ),
    "shin_splints": Contraindication(
        key="shin_splints",
        label="shin splints",
        triggers=["shin splint", "shin splints", "medial tibial", "shin pain"],
        direct=["running", "jogging", "jumping", "skipping", "plyometrics", "sprinting",
                "box jumps", "hill runs", "treadmill running"],
        lengthened=["repeated calf raises under load", "downhill running"],
        stretches=["aggressive calf stretching on a step"],
        substitutions=["cycling, swimming or the elliptical for cardio",
                       "soft surfaces instead of concrete when running resumes",
                       "seated and machine-based leg work"],
    ),
    "plantar_fasciitis": Contraindication(
        key="plantar_fasciitis",
        label="plantar fasciitis",
        triggers=["plantar fasciitis", "plantar", "heel pain", "arch pain"],
        direct=["running", "jogging", "jumping", "skipping", "sprinting", "plyometrics",
                "standing calf raises under load", "barefoot training"],
        lengthened=["deep lunges on the toes", "prolonged standing work"],
        stretches=["aggressive plantar stretching first thing in the morning"],
        substitutions=["cycling or swimming for cardio",
                       "seated leg work",
                       "supportive footwear for anything standing"],
    ),
    "elbow": Contraindication(
        key="elbow",
        label="elbow pain",
        triggers=["tennis elbow", "golfer's elbow", "golfers elbow", "elbow",
                  "lateral epicondyl", "medial epicondyl"],
        direct=["barbell curls", "heavy gripping work", "pull-ups", "chin-ups",
                "reverse curls", "wrist curls", "hammering movements"],
        lengthened=["straight-arm pulldowns", "skull crushers", "deep tricep extensions"],
        stretches=["forced wrist and forearm stretching"],
        substitutions=["neutral-grip and machine work",
                       "straps to reduce grip demand",
                       "keeping the elbow at a fixed comfortable angle"],
        # Upper limb - running, jumping and agility work are unaffected.
        impact_sensitive=False,
    ),
    "it_band": Contraindication(
        key="it_band",
        label="IT band syndrome",
        triggers=["it band", "iliotibial", "itbs", "outside of my knee"],
        direct=["running", "jogging", "downhill running", "cycling with a high saddle",
                "step-ups", "lunges", "deep squats"],
        lengthened=["repeated knee flexion under load"],
        stretches=["aggressive IT band foam rolling directly on the band"],
        substitutions=["swimming or upper-body cardio",
                       "glute medius work - clamshells, side-lying raises, banded walks",
                       "short-range leg work only"],
    ),
    "hernia": Contraindication(
        key="hernia",
        label="hernia",
        triggers=["hernia", "inguinal", "abdominal wall"],
        direct=["heavy deadlifts", "heavy squats", "sit-ups", "crunches", "leg raises",
                "heavy overhead press", "valsalva", "max lifts"],
        lengthened=["loaded twisting", "heavy carries"],
        stretches=["deep abdominal stretching"],
        substitutions=["light machine-based work only",
                       "breathing out through the effort rather than bracing hard",
                       "medical clearance before any loaded training"],
    ),
    # Not an injury, and it excludes no specific movement - but it caps
    # intensity, which is exactly the kind of limit a plan ignores when the
    # only thing it understands is a list of banned exercises.
    "asthma": Contraindication(
        key="asthma",
        label="asthma",
        triggers=["asthma", "asthmatic", "exercise-induced broncho", "inhaler"],
        direct=["HIIT", "sprint intervals", "maximal effort intervals",
                "long continuous high-intensity running", "cold outdoor running"],
        lengthened=[],
        stretches=[],
        substitutions=["longer warm-ups, built up gradually",
                       "intervals with generous rest rather than continuous hard effort",
                       "swimming in a warm pool, which most people tolerate well",
                       "keeping a reliever inhaler to hand during sessions"],
    ),
}

# Phrases that mean "get this looked at", not "work around it".
# Red flags live in injury_taxonomy, which is the single source of truth.
# Two lists existed and had already drifted - whether a user was told to see
# someone depended on which code path happened to run.
try:
    from app.services.injury_taxonomy import RED_FLAGS
except Exception:  # pragma: no cover - import cycle guard
    RED_FLAGS = (
        "sharp pain", "numbness", "tingling", "swelling", "giving way",
        "gave way", "getting worse", "worse", "popped", "locked",
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


# ---------------------------------------------------------------------------
# severity and return to play
# ---------------------------------------------------------------------------

# Rehabilitation reopens movement in a known order: hold it still, then shorten
# it under load, then lengthen it under load, then move it fast. Reintroducing
# everything at once the moment pain drops is the single most common way people
# re-tear something.
#
# Severity here is the user's own 0-10 rating, so these bands are deliberately
# broad. The point is that a 2/10 niggle and an 8/10 tear stop being treated
# identically, which is what happened before.
STAGES = [
    {
        "max_severity": 10, "min_severity": 8,
        "key": "medical",
        "label": "Too painful to program around",
        "guidance": (
            "At this level a modified training plan is the wrong tool. Get it "
            "assessed before loading it at all."
        ),
        "excludes": ("direct", "lengthened", "stretches", "intensity"),
        "prescribe": False,
    },
    {
        "max_severity": 7, "min_severity": 6,
        "key": "isometric",
        "label": "Early - static loading only",
        "guidance": (
            "Hold positions rather than moving through them. Pain-free isometrics "
            "maintain strength without lengthening the tissue."
        ),
        "excludes": ("direct", "lengthened", "stretches", "intensity"),
        "prescribe": True,
    },
    {
        "max_severity": 5, "min_severity": 4,
        "key": "concentric",
        "label": "Rebuilding - shortening movements",
        "guidance": (
            "Controlled movements in a shortened, pain-free range. Nothing "
            "explosive and nothing that stretches it under load."
        ),
        # `direct` stays excluded here. Dropping it at this stage let nordic
        # curls through for a 5/10 hamstring - the hardest eccentric exercise
        # there is - and left every newly-added condition with no exclusions
        # at all, since their key movements all live in `direct`.
        "excludes": ("direct", "lengthened", "intensity"),
        "prescribe": True,
    },
    {
        "max_severity": 3, "min_severity": 2,
        "key": "eccentric",
        "label": "Loading - controlled lengthening",
        "guidance": (
            "Slow lengthening under load, which is what actually rebuilds tolerance. "
            "Still no sprinting, jumping or maximal effort."
        ),
        # Controlled loading is the point of this stage - Romanian deadlifts
        # for a healing hamstring are rehabilitation, not a hazard. Speed and
        # impact are what remain off the table.
        "excludes": ("intensity",),
        "prescribe": True,
    },
    {
        "max_severity": 1, "min_severity": 0,
        "key": "return",
        "label": "Nearly there - reintroducing speed",
        "guidance": (
            "Build speed and impact back gradually. Stop and reassess if anything "
            "returns during or the day after a session."
        ),
        "excludes": (),
        "prescribe": True,
    },
]

# Language that signals high intensity regardless of the specific movement.
# This is the answer to the circularity problem: the exclusion lists can only
# catch what someone thought to write down, whereas a plan for an injured
# person that says "explosive" or "max effort" is worth questioning whatever
# exercise it is attached to.
# Phrases meaning "this movement is named here in order to say we are NOT
# doing it". Defined once and shared: the exclusion scan and the intensity
# scan previously kept separate copies, they drifted, and the shorter one
# flagged the safety note this module itself writes.
AVOIDANCE_PHRASES = (
    "instead of", "rather than", "avoid", "avoided", "avoiding",
    "no ", "not ", "replaced", "replacing", "swap", "swapped",
    "removed", "removing", "remove", "excluded", "excluding", "exclude",
    "skip", "skipped", "in place of", "substitut", "left out", "dropped",
    "for safety",
)


def _earliest_avoidance(line: str) -> int:
    """Where the first avoidance phrase starts, or -1 if there is none."""
    return min((line.find(p) for p in AVOIDANCE_PHRASES if p in line), default=-1)


# Two tiers, because intensity is not one thing.
#
# Maximal effort strains the whole body - bracing, breath-holding, fatigue -
# so it is worth questioning for any injury. Running and jumping only matter
# if the injured part bears load. Treating them the same meant a shoulder
# injury stripped sprint intervals, box jumps and HIIT on a bike, none of
# which involve the shoulder, leaving a plan gutted for no safety gain.
SYSTEMIC_INTENSITY_MARKERS = (
    "maximal", "max effort", "all-out", "all out", "to failure",
    "1rm", "one rep max", "heavy singles", "as heavy as possible",
)

IMPACT_INTENSITY_MARKERS = (
    "sprint", "explosive", "plyometric", "plyo", "hiit", "ballistic",
    "jump", "bound", "agility", "change of direction", "high intensity",
    "as fast as possible", "race pace", "shuttle",
)

# Kept for callers that want the full set.
INTENSITY_MARKERS = SYSTEMIC_INTENSITY_MARKERS + IMPACT_INTENSITY_MARKERS


def stage_for(severity: int) -> dict:
    """Which recovery stage a severity rating falls into."""
    severity = max(0, min(10, int(severity or 0)))
    for stage in STAGES:
        if stage["min_severity"] <= severity <= stage["max_severity"]:
            return stage
    return STAGES[-1]


def graded_exclusions(entry: Contraindication, severity: int) -> List[str]:
    """
    The exclusions that apply at this severity, rather than all of them always.

    Being over-restrictive is not free: someone at 2/10 who is told they still
    cannot do half their programme stops using the feature, and stops telling
    the app about injuries at all.
    """
    stage = stage_for(severity)
    out: List[str] = []
    if "direct" in stage["excludes"]:
        out += entry.direct
    if "lengthened" in stage["excludes"]:
        out += entry.lengthened
    if "stretches" in stage["excludes"]:
        out += entry.stretches

    seen, unique = set(), []
    for item in out:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def audit_plan(plan_text: str, constraints: List[str]) -> List[dict]:
    """
    Find movements a plan should not contain, given the stated injuries.

    Decided by MOVEMENT PATTERN, not exercise name. The name-based lists below
    are kept as a secondary signal for the handful of specific exercises worth
    naming, but the primary judgement comes from classifying what each line
    actually asks the body to do - which is what makes an unseen exercise name
    resolve correctly instead of slipping through.
    """
    if not plan_text or not constraints:
        return []

    try:
        from app.services import injury_taxonomy as taxonomy
    except Exception as e:  # pragma: no cover - import guard
        print(f"Pattern engine unavailable ({e}); falling back to name matching.")
        return _audit_by_name(plan_text, constraints)

    profiles = [p for p in (taxonomy.parse(c) for c in constraints) if p]
    if not profiles:
        return []

    findings = audit_against_profiles(plan_text, profiles)

    # Names still matter for a few specifics the patterns cannot express, so
    # run the old scan too and merge anything it uniquely caught.
    known = {f["line_no"] for f in findings}
    for finding in _audit_by_name(plan_text, constraints):
        if finding["line_no"] not in known:
            findings.append(finding)

    return findings


# Explicit verdicts. The previous model was binary - a line was either in the
# findings or it was not - which quietly conflated "checked and fine" with
# "could not be understood". For an injured user those are not the same thing.
VERDICT_SAFE = "safe"                # classified, and nothing restricted matched
VERDICT_UNSAFE = "unsafe"            # classified, and it hits a restriction
VERDICT_CONDITIONAL = "conditional"  # not confidently classified, injury active
VERDICT_UNKNOWN = "unknown"          # not classified, no injury to worry about

# Words that make an unclassified line worth questioning rather than ignoring.
# A line the ontology cannot read is only a risk if it is prescribing effort.
# Lines that are instructions, not exercises. Without this, "Rest 90 seconds
# between sets" is unclassifiable + prescriptive-looking, so it becomes
# CONDITIONAL and gets swapped for a stationary bike.
_INSTRUCTION = re.compile(
    r"^\s*(?:rest|recover|recovery(?!\s+day)|tempo|rpe|note|tip|progression|"
    r"duration|total|focus|remember|aim|target|cue|breathe|hydrat|"
    r"warm[\s-]?up\s*:?\s*$|cool[\s-]?down\s*:?\s*$)\b",
    re.I,
)

_EFFORT_HINTS = (
    "set", "sets", "rep", "reps", "x8", "x10", "x12", "min", "minute",
    "second", "sec", "round", "circuit", "drill", "exercise", "hold",
    "km", "metre", "meter", "mile", "interval",
)


def classify_line(line: str, profiles: list) -> dict:
    """
    Judge one line, with an explicit verdict rather than a silent pass.

    The important case is CONDITIONAL: the ontology could not classify the
    movement AND the user has an active injury. Treating that as safe is the
    unsafe default this exists to remove - an exercise nobody recognised is
    exactly the one most likely to be a novel name for something restricted.
    """
    from app.services import movement_ontology as ontology

    text = (line or "").strip()
    if not text:
        return {"line": text, "verdict": VERDICT_SAFE, "patterns": [], "reasons": []}

    movement = ontology.classify_prescribed(text)

    if movement.patterns:
        restricted: Set[str] = set()
        reasons = []
        for profile in profiles:
            clash = movement.patterns & profile.restricted_patterns()
            clash -= profile.keep_patterns()
            if clash:
                restricted |= clash
                reasons.append(
                    f"{profile.label} at {profile.severity}/10 cannot tolerate "
                    f"{ontology.describe(clash)}"
                )
        return {
            "line": text,
            "verdict": VERDICT_UNSAFE if restricted else VERDICT_SAFE,
            "patterns": sorted(movement.patterns),
            "clash": sorted(restricted),
            "reasons": reasons,
        }

    # Unclassified from here on.
    stripped = re.sub(r"^\s*(?:[-*•+]|\d+[.)])\s*", "", text)
    if _INSTRUCTION.match(stripped):
        # Programme instructions carry no movement, so there is nothing to
        # judge and nothing to replace.
        return {"line": text, "verdict": VERDICT_UNKNOWN, "patterns": [],
                "clash": [], "reasons": ["instruction, not an exercise"]}

    lowered = text.lower()
    looks_prescriptive = any(hint in lowered for hint in _EFFORT_HINTS)
    if profiles and looks_prescriptive:
        return {
            "line": text,
            "verdict": VERDICT_CONDITIONAL,
            "patterns": [],
            "clash": [],
            "reasons": ["could not be classified while an injury is active - "
                        "treated cautiously rather than assumed safe"],
        }
    return {"line": text, "verdict": VERDICT_UNKNOWN, "patterns": [],
            "clash": [], "reasons": []}


def assess_plan(plan_text: str, profiles: list) -> List[dict]:
    """Per-line verdicts for a whole plan. Structured, for callers and logs."""
    out = []
    for line_no, raw in enumerate(plan_text.splitlines()):
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        verdict = classify_line(text, profiles)
        verdict["line_no"] = line_no
        out.append(verdict)
    return out


def audit_against_profiles(plan_text: str, profiles: list) -> List[dict]:
    """
    Pattern-based audit against ALREADY-PARSED injury profiles.

    Split out so callers that check many candidate exercises against the same
    injuries - replacement validation does exactly this - parse the injuries
    once instead of re-parsing them for every candidate. Same logic, same
    single source of truth; only the entry point differs.
    """
    from app.services import movement_ontology as ontology

    findings: List[dict] = []
    for line_no, raw_line in enumerate(plan_text.splitlines()):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        movement = ontology.classify_prescribed(line)
        if not movement.patterns:
            continue

        for profile in profiles:
            restricted = profile.restricted_patterns()
            clash = movement.patterns & restricted
            # A pattern the condition explicitly keeps overrides a fallback
            # restriction - a shoulder injury must not remove squats.
            clash -= profile.keep_patterns()
            if clash:
                findings.append({
                    "line_no": line_no,
                    "line": line,
                    "injury": profile.label,
                    "movement": ", ".join(sorted(p.replace("_", " ") for p in clash)),
                    "patterns": sorted(movement.patterns),
                    "stage": profile.stage.key,
                    "reason": f"{profile.label} at {profile.severity}/10 cannot tolerate "
                              f"{ontology.describe(clash)}",
                })
                break

    return findings


def _audit_by_name(plan_text: str, constraints: List[str]) -> List[dict]:
    """
    Find excluded movements that made it into a generated plan.

    WHY A FILTER AND NOT JUST A BETTER PROMPT
    -----------------------------------------
    The exclusions are given to the model as hard rules and it still breaks
    them - a plan for a torn hamstring came back with hanging leg raises and
    jogging warm-ups, under a heading that said "hamstring friendly". Prompting
    reduces that; it does not stop it, and "usually safe" is not a standard
    worth shipping for injury advice.

    This is a text scan, so it is deterministic and cannot be argued with.
    Returns one entry per offending line, with the injury and movement that
    triggered it, for the caller to strip or flag.
    """
    if not plan_text or not constraints:
        return []

    joined = " ".join(constraints).lower()
    relevant = [c for c in CONTRAINDICATIONS.values()
                if any(t in joined for t in c.triggers) or c.key in joined]

    # Severity, if the constraint carries one ("severity 6/10"). Without it,
    # assume the middle of the range rather than the most permissive end.
    severity_match = re.search(r"severity\s*(\d+)\s*/\s*10", joined)
    severity = int(severity_match.group(1)) if severity_match else 5
    stage = stage_for(severity)

    if not relevant:
        # No exclusion data for this injury - but an injury was still stated,
        # so intensity language is worth flagging. This is what stops an
        # unrecognised condition producing a completely unguarded plan.
        return _intensity_findings(plan_text, "stated injury", stage) if joined else []

    # A line that names an exercise in order to say it is being AVOIDED is not
    # a violation - it is the plan doing the right thing.
    findings: List[dict] = []
    for line_no, raw_line in enumerate(plan_text.splitlines()):
        line = raw_line.lower()
        if not line.strip():
            continue
        # Position matters. "Cycling instead of running" is an avoidance;
        # "Squats: 3 sets of 8 (avoid deep squats)" is PRESCRIBING squats and
        # merely qualifying them. Skipping any line containing "avoid" let the
        # second kind straight through - the movement is only excused when the
        # avoidance phrase comes BEFORE it.
        earliest_avoidance = _earliest_avoidance(line)
        for entry in relevant:
            for movement in graded_exclusions(entry, severity):
                # Word-boundary match: "row" must not fire on "rowing machine"
                # being mentioned as an alternative, and "run" must not fire
                # inside "running shoes".
                match = re.search(rf"(?<!\w){re.escape(movement.lower())}", line)
                if match:
                    if 0 <= earliest_avoidance < match.start():
                        continue   # named only to say it is being avoided
                    findings.append({
                        "line_no": line_no,
                        "line": raw_line.strip(),
                        "injury": entry.label,
                        "movement": movement,
                        "stage": stage["key"],
                    })
                    break

    # Then the intensity sweep, which catches what no list anticipated.
    known_lines = {f["line_no"] for f in findings}
    # Impact only matters if at least one active injury is load-bearing.
    impact_sensitive = any(getattr(e, "impact_sensitive", True) for e in relevant)
    for finding in _intensity_findings(
        plan_text, relevant[0].label, stage, impact_sensitive
    ):
        if finding["line_no"] not in known_lines:
            findings.append(finding)

    return findings


def _intensity_findings(plan_text: str, injury_label: str, stage: dict,
                        impact_sensitive: bool = True) -> List[dict]:
    """
    Flag high-intensity language while an injury is still healing.

    The exclusion lists can only contain movements somebody thought to write
    down. A plan that says "explosive", "max effort" or "to failure" for an
    injured person is worth removing whatever exercise it is attached to - and
    this is the only check here that can catch something nobody anticipated.

    Skipped in the final stage, where rebuilding speed is the entire point.
    """
    if "intensity" not in stage["excludes"]:
        return []

    # Maximal effort is questionable for any injury. Running and jumping only
    # matter when the injured part carries load.
    markers = SYSTEMIC_INTENSITY_MARKERS
    if impact_sensitive:
        markers = markers + IMPACT_INTENSITY_MARKERS

    out: List[dict] = []
    for line_no, raw_line in enumerate(plan_text.splitlines()):
        line = raw_line.strip().lower()
        if not line or line.startswith("#"):
            continue
        earliest = _earliest_avoidance(line)
        for marker in markers:
            match = re.search(rf"(?<!\w){re.escape(marker)}", line)
            if match:
                if 0 <= earliest < match.start():
                    break
                out.append({
                    "line_no": line_no,
                    "line": raw_line.strip(),
                    "injury": injury_label,
                    "movement": marker,
                    "stage": stage["key"],
                    "reason": "high intensity while healing",
                })
                break
    return out


def strip_excluded(plan_text: str, constraints: List[str]) -> Tuple[str, List[dict]]:
    """
    Remove offending lines from a plan and append a note explaining why.

    Removing a line is safe here because plans are formatted one exercise per
    line. Taking the exercise out leaves the session shorter but correct, which
    is the right trade when the alternative is telling an injured person to do
    the thing that injured them.
    """
    findings = audit_plan(plan_text, constraints)
    if not findings:
        return plan_text, []

    bad_lines = {f["line_no"] for f in findings}
    kept = [
        line for i, line in enumerate(plan_text.splitlines())
        if i not in bad_lines
    ]

    removed = sorted({f["movement"] for f in findings})
    note = (
        "\n\n---\n"
        f"**Removed for safety:** {', '.join(removed)}. "
        "These load or lengthen the injured tissue, so they were taken out of "
        "the plan above. A physio can tell you when they are safe to reintroduce."
    )
    return "\n".join(kept) + note, findings


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
