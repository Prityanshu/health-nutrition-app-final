#!/usr/bin/env python3
"""
Regression suite for excessive low-severity replacements.

The reported failure: an advanced muscle-gain user with a 2/10 hamstring
tendinopathy got ~30 items replaced with "Stationary bike, steady pace",
including unrelated upper-body work and breathing cues.

Two independent causes, fixed independently:

  1. ONTOLOGY NEAR-MISSES. "Incline dumbbell press" was unknown only because
     the rule required "incline" and "press" to be adjacent. Unknown plus an
     active restriction is CONDITIONAL, so it was replaced. Generalising the
     rule makes it known - and therefore SAFE - at every severity.

  2. AN EMPTY RESTRICTION SET STILL COUNTED AS A RESTRICTION. A 0/10 or 1/10
     injury restricts nothing at all, yet every unclassifiable line was still
     treated cautiously.

What deliberately did NOT change: an unknown prescription is still
CONDITIONAL whenever ANY restriction is active, velocity-only ones included.
A narrower "structural restrictions only" gate was considered and rejected -
see the mutation test at the end for the bypass it would open.

    python scripts/test_low_severity_replacements.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GREEN, RED, DIM, BOLD, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[1m", "\033[0m"
passed = failed = 0


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  {GREEN}pass{RESET}  {label}")
    else:
        failed += 1
        print(f"  {RED}FAIL{RESET}  {label}")
        for line in str(detail).splitlines()[:6]:
            print(f"        {DIM}{line}{RESET}")


def profiles(constraints):
    from app.services import injury_taxonomy as tax
    return [p for p in (tax.parse(c) for c in constraints) if p]


def verdict(line, constraints):
    from app.services import contraindications as c
    return c.classify_line(f"- {line}", profiles(constraints))["verdict"]


# ---------------------------------------------------------------------------
# 1. the conditional gate
# ---------------------------------------------------------------------------

def conditional_gate():
    from app.services import contraindications as c
    from app.services import injury_taxonomy as tax
    print(f"\n{BOLD}1. Unknown prescriptions stay fail-closed whenever anything "
          f"is restricted{RESET}")

    UNKNOWN_NAME = "Blurgle flurbing"

    # Healthy: unchanged.
    check("healthy user + unknown -> UNKNOWN",
          verdict(UNKNOWN_NAME, []) == c.VERDICT_UNKNOWN, verdict(UNKNOWN_NAME, []))

    # Severity 0/1 restrict nothing at all, so there is nothing to be
    # cautious about. This is the only behaviour the gate change alters.
    for sev in (0, 1):
        constraint = f"hamstring strain (severity {sev}/10)"
        p = profiles([constraint])[0]
        check(f"severity {sev} restricts nothing at all",
              p.restricted_patterns() == set(), sorted(p.restricted_patterns()))
        check(f"severity {sev} + unknown -> UNKNOWN (no restriction to guard)",
              verdict(UNKNOWN_NAME, [constraint]) == c.VERDICT_UNKNOWN,
              verdict(UNKNOWN_NAME, [constraint]))

    # Severity 2+ restricts velocity/impact, so unknown stays CONDITIONAL.
    for sev in (2, 3, 4, 5, 6, 7):
        constraint = f"hamstring strain (severity {sev}/10)"
        check(f"severity {sev} + unknown -> CONDITIONAL",
              verdict(UNKNOWN_NAME, [constraint]) == c.VERDICT_CONDITIONAL,
              verdict(UNKNOWN_NAME, [constraint]))

    # The counterexamples that killed the "structural restrictions only" idea:
    # these names are unrecognised AND may well be jumping work.
    for name in ("Ankle pogo", "A-skips"):
        for constraint in ("hamstring strain (severity 2/10)",
                           "hamstring strain (severity 3/10)",
                           "no jumping"):
            check(f"{constraint!r} + {name!r} -> CONDITIONAL",
                  verdict(name, [constraint]) == c.VERDICT_CONDITIONAL,
                  verdict(name, [constraint]))

    # Explicit restrictions participate identically, structural or not.
    for constraint in ("no jumping", "no squats", "avoid running",
                       "avoid overhead pressing"):
        check(f"explicit {constraint!r} + unknown -> CONDITIONAL",
              verdict(UNKNOWN_NAME, [constraint]) == c.VERDICT_CONDITIONAL,
              verdict(UNKNOWN_NAME, [constraint]))

    # Other regions, unchanged.
    check("severity 6 lumbar + 'Power Pull' -> CONDITIONAL",
          verdict("Power Pull", ["lower back pain, severity 6/10"])
          == c.VERDICT_CONDITIONAL)
    check("severity 6 ankle + 'Ankle pogo' -> CONDITIONAL",
          verdict("Ankle pogo", ["ankle sprain (severity 6/10)"])
          == c.VERDICT_CONDITIONAL)

    # Known movements are unaffected by the gate in either direction.
    check("severity 2 hamstring + known 'Sprint intervals' -> UNSAFE",
          verdict("Sprint intervals: 6x100m",
                  ["hamstring strain (severity 2/10)"]) == c.VERDICT_UNSAFE)
    for name in ("Bench press: 4x8", "Lat pulldown: 3x10", "Face pull: 3x15",
                 "Seated cable row: 4x10", "Dead bug: 3x10"):
        check(f"severity 2 hamstring + known {name.split(':')[0]!r} -> SAFE",
              verdict(name, ["hamstring strain (severity 2/10)"]) == c.VERDICT_SAFE,
              verdict(name, ["hamstring strain (severity 2/10)"]))


# ---------------------------------------------------------------------------
# 2. ontology generalisations
# ---------------------------------------------------------------------------

def ontology_generalisations():
    from app.services import movement_ontology as mo
    print(f"\n{BOLD}2. Ontology near-misses now classify{RESET}")

    wanted = [
        ("Incline dumbbell press", "horizontal_push"),
        ("Incline barbell press", "horizontal_push"),
        ("Incline machine press", "horizontal_push"),
        ("Decline dumbbell press", "horizontal_push"),
        ("Incline press", "horizontal_push"),
        ("Overhead band press", "vertical_push"),
        ("Overhead dumbbell press", "vertical_push"),
        ("Overhead resistance band press", "vertical_push"),
        ("Overhead press", "vertical_push"),
        ("Cat-cow", "end_range_stretch"),
        ("Cat cow", "end_range_stretch"),
        ("Thoracic rotation", "spinal_rotation"),
        ("Thoracic rotations", "spinal_rotation"),
        ("Thoracic spine rotation", "spinal_rotation"),
        ("Banded pull-apart", "shoulder_rotation"),
        ("Band pull apart", "shoulder_rotation"),
        ("Pull-apart", "shoulder_rotation"),
    ]
    for name, pattern in wanted:
        got = mo.classify_prescribed(name).patterns
        check(f"{name!r} -> {pattern}", pattern in got, sorted(got))

    print(f"\n{BOLD}   collision controls - a leg press is never an upper-body "
          f"push{RESET}")
    for name in ("incline leg press", "decline leg press", "leg press",
                 "seated leg press", "leg press machine", "calf press",
                 "overhead squat", "overhead carry", "farmer carry overhead"):
        got = mo.classify_prescribed(name).patterns
        bad = {"horizontal_push", "vertical_push"} & got
        check(f"{name!r} gains no upper-body push", not bad, sorted(got))

    # The generalisations must not have broken the exceptions table.
    check("'Jefferson curl' is still spinal flexion, not an arm curl",
          "spinal_flexion" in mo.classify("Jefferson curl").patterns)
    check("'Reverse Nordic' is still knee extension",
          "knee_extension" in mo.classify("Reverse Nordic").patterns)


# ---------------------------------------------------------------------------
# 3. breathing / relaxation
# ---------------------------------------------------------------------------

def breathing_and_relaxation():
    from app.services import plan_structure as ps
    print(f"\n{BOLD}3. Breathing and relaxation: cues vs dosed drills{RESET}")

    for name in ("Breathing/relaxation", "Relax your shoulders", "Relaxation",
                 "Breathe normally between sets",
                 "Focus on slow breathing during recovery"):
        role = ps.classify_single_line(f"- {name}")
        check(f"{name!r} -> instruction",
              role == ps.DEFINITE_INSTRUCTION, role)

    for name in ("Breathing drill: 3 sets of 5 breaths",
                 "Diaphragmatic breathing: 2 minutes",
                 "Breathing ladder: 4 rounds",
                 "Box breathing: 5 minutes"):
        role = ps.classify_single_line(f"- {name}")
        check(f"{name!r} stays a prescription (it is dosed)",
              role == ps.PRESCRIPTION_LIKE, role)

    # plan_structure must remain the sole structural authority.
    import inspect
    import re as _re
    source = inspect.getsource(ps)
    check("plan_structure still imports no movement_ontology",
          not _re.search(r"^\s*(?:from\s+\S*movement_ontology|import\s+\S*"
                         r"movement_ontology)", source, _re.M))


# ---------------------------------------------------------------------------
# 4. end to end
# ---------------------------------------------------------------------------

REPORTED_PLAN = """### Day 1 - Upper (push)
- Incline dumbbell press: 4x8
- Overhead band press: 3x12
- Lateral raise: 3x15
- Scapular push-ups: 2x12
### Day 2 - Upper (pull)
- Pull-up: 4x6
- Face pull: 3x15
- Banded pull-apart: 3x20
### Day 3 - Core & mobility
- Dead bug: 3x10
- Cat-cow: 2x10
- Thoracic rotations: 2x10
- Breathing/relaxation
### Day 4 - Lower
- Back squat: 4x6
- Leg press: 3x12
- Seated calf raise: 4x15
### Day 5 - Unknown work
- Blurgle flurbing: 3x10"""


def end_to_end():
    from app.services import plan_repair
    from app.services.contraindications import (
        audit_against_profiles, assess_plan, VERDICT_CONDITIONAL)
    print(f"\n{BOLD}4. End to end - hamstring 2/10, advanced, muscle gain{RESET}")

    constraint = "right hamstring tendinopathy (severity 2/10)"
    profs = profiles([constraint])
    result = plan_repair.repair(REPORTED_PLAN, [constraint],
                                equipment="gym", requested_minutes=60,
                                goal="muscle_gain", level="advanced")
    live = result.plan.split("\n\n---")[0]

    keep = ["Incline dumbbell press", "Overhead band press", "Lateral raise",
            "Scapular push-ups", "Pull-up", "Face pull", "Banded pull-apart",
            "Dead bug", "Cat-cow", "Thoracic rotations", "Breathing/relaxation",
            "Back squat", "Leg press", "Seated calf raise"]
    for name in keep:
        check(f"{name!r} survives a 2/10 hamstring", name in live, live[:400])

    # The genuinely unknown prescription must still be handled.
    check("the truly unknown 'Blurgle flurbing' is NOT kept unresolved",
          "Blurgle flurbing" not in live, live)

    # Replacement volume collapses - but the assertion is not "exactly zero",
    # because one real unknown prescription remains in the fixture.
    check("at most one replacement remains (was ~30)",
          len(result.replacements) + len(result.removed) <= 1,
          [r.original for r in result.replacements] + list(result.removed))

    # Safety invariants unchanged.
    check("exact returned plan re-audits with no unsafe movement",
          audit_against_profiles(result.plan, profs) == [], result.plan[:300])
    check("no unresolved CONDITIONAL in the exact returned plan",
          not any(v["verdict"] == VERDICT_CONDITIONAL
                  for v in assess_plan(result.plan, profs)), result.plan[:300])
    check("audit_clean is True", result.audit_clean is True, result.as_dict())

    # Healthy user: byte-identical.
    healthy = plan_repair.repair(REPORTED_PLAN, [])
    check("healthy user gets the plan back byte-identical",
          healthy.plan == REPORTED_PLAN, healthy.plan[:200])

    # Block ownership on a conditional removal/replacement is preserved.
    block_plan = ("- Blurgle flurbing\n"
                  "  - 3 sets x 8 reps\n"
                  "- Bench press: 4x6")
    blocked = plan_repair.repair(block_plan, [constraint])
    block_live = blocked.plan.split("\n\n---")[0].splitlines()
    check("a replaced/removed conditional block keeps its dosage with it",
          "  - 3 sets x 8 reps" in block_live and "- Bench press: 4x6" in block_live
          and not any(l.strip() == "- Blurgle flurbing" for l in block_live),
          block_live)

    # Regeneration bounds untouched.
    check("MAX_REGENERATIONS is still 2", plan_repair.MAX_REGENERATIONS == 2)
    calls = {"n": 0}

    def counting_regenerate(_brief):
        calls["n"] += 1
        return REPORTED_PLAN

    plan_repair.repair("- Sprint intervals: 6x100m",
                       ["hamstring strain (severity 6/10)"],
                       requested_minutes=60, regenerate=counting_regenerate)
    check("regeneration stays bounded at MAX_REGENERATIONS",
          calls["n"] <= plan_repair.MAX_REGENERATIONS, calls["n"])


# ---------------------------------------------------------------------------
# 5. mutation
# ---------------------------------------------------------------------------

def mutation_structural_only_gate():
    """
    The rejected design, demonstrated.

    Gating CONDITIONAL on "restricts a STRUCTURAL pattern" exempts every
    velocity-only restriction. Since the ontology's blind spots include
    plyometric names, that exempts exactly the wrong things.
    """
    from app.services import contraindications as c
    from app.services import plan_repair
    print(f"\n{BOLD}5. MUTATION - the rejected 'structural restrictions only' "
          f"gate{RESET}")

    VELOCITY = {"high_speed", "running", "jumping", "cutting", "impact",
                "maximal_effort", "cardio_intensity"}
    original = c.classify_line

    def structural_only(line, profs):
        from app.services import movement_ontology as ontology
        from app.services import plan_structure as structure
        text = (line or "").strip()
        role = structure.classify_single_line(text)
        movement = ontology.classify_prescribed(text)
        if role not in (structure.PRESCRIPTION_CANDIDATE, structure.AMBIGUOUS):
            if not (profs and movement.patterns):
                return {"line": text, "verdict": c.VERDICT_UNKNOWN,
                        "patterns": [], "clash": [], "reasons": []}
        if movement.patterns:
            return original(line, profs)
        structural = any(p.restricted_patterns() - VELOCITY for p in profs)
        return {"line": text,
                "verdict": c.VERDICT_CONDITIONAL if structural else c.VERDICT_UNKNOWN,
                "patterns": [], "clash": [], "reasons": []}

    c.classify_line = structural_only
    try:
        pogo_jump = structural_only("- Ankle pogo", profiles(["no jumping"]))["verdict"]
        pogo_ham = structural_only(
            "- Ankle pogo", profiles(["hamstring strain (severity 2/10)"]))["verdict"]
        skips = structural_only("- A-skips", profiles(["no jumping"]))["verdict"]
        result = plan_repair.repair("- Ankle pogo\n- Bench press: 4x6", ["no jumping"])
        survives = "Ankle pogo" in result.plan.split("\n\n---")[0]
        clean = result.audit_clean
    finally:
        c.classify_line = original

    check("MUTATION: 'no jumping' + 'Ankle pogo' becomes UNKNOWN, not CONDITIONAL",
          pogo_jump == c.VERDICT_UNKNOWN, pogo_jump)
    check("MUTATION: hamstring 2/10 + 'Ankle pogo' becomes UNKNOWN",
          pogo_ham == c.VERDICT_UNKNOWN, pogo_ham)
    check("MUTATION: 'no jumping' + 'A-skips' becomes UNKNOWN",
          skips == c.VERDICT_UNKNOWN, skips)
    check("MUTATION: the plan then ships 'Ankle pogo' with audit_clean=True - "
          "the bypass this gate would open",
          survives and clean, f"survives={survives} audit_clean={clean}")

    # Restored.
    check("restored: 'no jumping' + 'Ankle pogo' is CONDITIONAL again",
          verdict("Ankle pogo", ["no jumping"]) == c.VERDICT_CONDITIONAL)
    restored = plan_repair.repair("- Ankle pogo\n- Bench press: 4x6", ["no jumping"])
    check("restored: 'Ankle pogo' no longer survives",
          "Ankle pogo" not in restored.plan.split("\n\n---")[0],
          restored.plan)


def main():
    print(f"\n{BOLD}LOW-SEVERITY REPLACEMENT REGRESSION SUITE{RESET}")
    conditional_gate()
    ontology_generalisations()
    breathing_and_relaxation()
    end_to_end()
    mutation_structural_only_gate()
    print(f"\n{BOLD}{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
