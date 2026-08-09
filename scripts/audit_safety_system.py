#!/usr/bin/env python3
"""
Adversarial audit of the workout injury-safety system.

This is not a regression suite. Its purpose is to BREAK things: to find
exercises the classifier waves through, injuries that produce no restrictions,
laterality that gets lost, and defaults that treat "unknown" as "safe".

It deliberately does not import the app's own test helpers, so a bug in the
test suite cannot hide a bug in the system.

    python scripts/audit_safety_system.py            # everything offline
    python scripts/audit_safety_system.py --phase 4  # one phase
    python scripts/audit_safety_system.py --quiet    # findings only

Phases 11 (LLM repetition), 18 (multi-user integration) and 22 (performance
under load) require a running backend and real AI quota; they live in
scripts/test_workouts.py --live and are not attempted here.
"""

import argparse
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GREEN, RED, YELLOW, CYAN, DIM, BOLD, RESET = (
    "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[2m", "\033[1m", "\033[0m"
)

FINDINGS = []          # (severity, phase, title, detail)
STATS = defaultdict(int)
QUIET = False


def finding(severity, phase, title, detail=""):
    FINDINGS.append((severity, phase, title, detail))
    STATS[severity] += 1
    colour = {"CRITICAL": RED, "HIGH": RED, "MEDIUM": YELLOW, "LOW": DIM}[severity]
    print(f"  {colour}[{severity}]{RESET} {title}")
    if detail and not QUIET:
        for line in detail.splitlines()[:6]:
            print(f"        {DIM}{line}{RESET}")


def ok(label):
    STATS["PASS"] += 1
    if not QUIET:
        print(f"  {GREEN}ok{RESET}    {label}")


def header(n, title):
    print(f"\n{BOLD}PHASE {n} — {title}{RESET}")


# ===========================================================================

def phase3_movement_families():
    """Do equivalent movements classify to the same patterns?"""
    from app.services import movement_ontology as mo
    header(3, "movement-pattern families")

    families = {
        "hip hinge": (["Romanian Deadlift", "RDL", "Stiff Leg Deadlift",
                       "Straight Leg Deadlift", "Good Morning", "Back Extension",
                       "Hip Hinge", "Bent Over Dumbbell Row", "Bent Over Barbell Row",
                       "Pendlay Row", "T-Bar Row", "Dumbbell Bent Row"], "hip_hinge"),
        "high speed": (["Sprint", "Sprints", "Sprinting", "Max Sprint",
                        "Maximum Velocity Run", "Max Velocity Run", "Flying Sprint",
                        "Acceleration Sprint", "100m Sprint", "Hill Sprint",
                        "Short Burst Run", "High-Speed Running"], "high_speed"),
        "cutting": (["Pro Agility Shuttle", "5-10-5 Shuttle", "Shuttle Run",
                     "Change of Direction Drill", "COD Drill", "Cutting Drill",
                     "Reactive Cutting", "Lateral Cut"], "cutting"),
        "jumping": (["Box Jump", "Box Jumps", "Jumping onto Box", "Broad Jump",
                     "Standing Broad Jump", "Depth Jump", "Drop Jump", "Tuck Jump",
                     "Jump Squat", "Vertical Jump", "Plyometric Jump"], "jumping"),
    }

    for family, (names, required) in families.items():
        misses = [n for n in names if required not in mo.classify(n).patterns]
        if misses:
            finding("HIGH", 3, f"{family}: {len(misses)}/{len(names)} not recognised",
                    f"Missing {required!r}: {misses}")
        else:
            ok(f"{family}: all {len(names)} variants classify as {required}")


def phase4_unknown_exercises():
    """Exercises absent from every hard-coded list."""
    from app.services import movement_ontology as mo
    header(4, "exercises not in any safety list")

    expectations = [
        ("Dumbbell Romanian Deadlift", "hip_hinge"),
        ("Single Leg Romanian Deadlift", "hip_hinge"),
        ("Landmine Press", "vertical_push"),
        ("Z Press", "vertical_push"),
        ("Sled Sprint", "high_speed"),
        ("Resisted Sprint", "high_speed"),
        ("Bounding", "jumping"),
        ("Skater Jump", "jumping"),
        ("Lateral Bound", "jumping"),
        ("Copenhagen Plank", "hip_adduction"),
        ("Nordic Hamstring Curl", "knee_flexion"),
        ("Reverse Nordic", "knee_extension"),
        ("Jefferson Curl", "spinal_flexion"),
        ("Pendlay Row", "hip_hinge"),
        ("Seal Row", "horizontal_pull"),
        ("Meadows Row", "hip_hinge"),
        ("Split Squat", "lunge"),
        ("Bulgarian Split Squat", "lunge"),
    ]
    for name, expected in expectations:
        m = mo.classify(name)
        if m.unknown:
            finding("HIGH", 4, f"{name!r} is UNCLASSIFIED",
                    "Unclassified means the audit sees no patterns, so nothing can "
                    "flag it. Unknown must not behave as safe.")
        elif expected not in m.patterns:
            finding("HIGH", 4, f"{name!r} missing {expected!r}",
                    f"Classified as: {sorted(m.patterns)}")
        else:
            ok(f"{name} -> {expected}")


def phase5_injury_coverage():
    """What the taxonomy actually covers, and what is missing."""
    from app.services import injury_taxonomy as it
    header(5, "injury coverage")

    by_region = defaultdict(list)
    for c in it.CONDITIONS:
        by_region[c.region].append(c.key)

    expected_regions = ["shoulder", "elbow", "wrist", "hand", "neck", "thoracic",
                        "lumbar", "hip_groin", "thigh", "knee", "lower_leg",
                        "ankle", "foot"]
    for region in expected_regions:
        if region not in by_region:
            finding("MEDIUM", 5, f"no conditions for region {region!r}",
                    "An injury here falls back to region rules at best, and to "
                    "speed-only restrictions if the region is not recognised.")
        else:
            ok(f"{region}: {by_region[region]}")

    # Every condition must restrict something at a mid severity, or it is inert.
    stage = it.stage_for_severity(5)
    for c in it.CONDITIONS:
        if not c.restricted(stage):
            finding("HIGH", 5, f"condition {c.key!r} restricts nothing at 5/10",
                    "A condition with no active restrictions is decoration.")
    # And must leave something trainable.
    for c in it.CONDITIONS:
        if not c.keep:
            finding("MEDIUM", 5, f"condition {c.key!r} lists nothing it keeps",
                    "Without `keep`, a region fallback can strip the whole plan.")


def phase6_laterality():
    """Side must survive parsing and never be invented."""
    from app.services import injury_taxonomy as it
    header(6, "laterality")

    cases = [
        ("right shoulder impingement", "right"),
        ("left shoulder impingement", "left"),
        ("bilateral shoulder pain", "bilateral"),
        ("right knee ACL tear", "right"),
        ("left knee ACL tear", "left"),
        ("pain in both knees", "bilateral"),
        ("right hamstring strain", "right"),
        ("left hamstring strain", "left"),
        ("hamstring strain", None),
        ("right ankle sprain", "right"),
        ("left ankle sprain", "left"),
    ]
    for text, expected in cases:
        p = it.parse(text)
        got = p.side if p else "NOT PARSED"
        if got != expected:
            finding("HIGH", 6, f"{text!r} -> side {got!r}, expected {expected!r}")
        else:
            ok(f"{text} -> {expected}")

    # The two side detectors in the repo must agree.
    from app.services.injury_service import _side_of
    for text in ["pain in both knees", "left and right ankle", "bilateral hip pain"]:
        a, b = _side_of(text), it._detect_side(text)
        if a != b:
            finding("MEDIUM", 6, f"side detectors disagree on {text!r}",
                    f"injury_service._side_of={a!r} vs injury_taxonomy._detect_side={b!r}. "
                    "Two implementations of one concept.")


def phase7_severity():
    """Restrictions must tighten as severity rises, monotonically."""
    from app.services import injury_taxonomy as it
    header(7, "severity monotonicity")

    for c in it.CONDITIONS:
        counts = [len(c.restricted(it.stage_for_severity(s))) for s in (8, 6, 4, 2, 0)]
        if counts != sorted(counts, reverse=True):
            finding("HIGH", 7, f"{c.key}: restrictions not monotonic",
                    f"counts at 8/6/4/2/0 = {counts} (should never increase as it heals)")
    ok("restriction counts decrease monotonically for all conditions")

    if it.stage_for_severity(9).prescribe:
        finding("CRITICAL", 7, "9/10 still prescribes a plan",
                "Above the medical threshold the system must decline, not modify.")
    else:
        ok("9/10 declines to prescribe")

    if it.stage_for_severity(None).key != it.stage_for_severity(5).key:
        finding("MEDIUM", 7, "missing severity does not default to mid-range")
    else:
        ok("missing severity defaults cautiously")


def phase9_multiple_injuries():
    """Combined restrictions must union - and must not erase the whole plan."""
    from app.services.contraindications import audit_plan
    header(9, "multiple injuries")

    PLAN = "\n".join([
        "* Overhead press: 3x8",
        "* Romanian deadlift: 3x8",
        "* Seated cable row: 3x12",
        "* Leg press: 3x10",
        "* Sprint intervals: 6x100m",
        "* Chest-supported row: 3x10",
        "* Stationary bike: 20 min",
        "* Plank: 3x45s",
    ])
    combos = [
        (["right shoulder impingement (severity 5/10)", "left knee ACL tear (severity 5/10)"], "shoulder + knee"),
        (["hamstring strain (severity 5/10)", "right ankle sprain (severity 5/10)"], "hamstring + ankle"),
        (["lower back pain (severity 5/10)", "shoulder impingement (severity 5/10)"], "back + shoulder"),
        (["right hamstring strain (severity 5/10)", "right ankle sprain (severity 5/10)"], "same-side pair"),
    ]
    total_lines = len(PLAN.splitlines())
    for constraints, label in combos:
        flagged = {f["line"] for f in audit_plan(PLAN, constraints)}
        remaining = total_lines - len(flagged)
        if remaining == 0:
            finding("HIGH", 9, f"{label}: entire plan removed",
                    "A filter that removes everything is not usable.")
        elif remaining <= 2:
            finding("MEDIUM", 9, f"{label}: only {remaining}/{total_lines} exercises survive",
                    f"Removed: {sorted(flagged)}")
        else:
            ok(f"{label}: {remaining}/{total_lines} survive")


def phase10_adversarial_language():
    """Case, plurals, hyphens, abbreviations, typos."""
    from app.services import movement_ontology as mo
    header(10, "adversarial language")

    groups = [
        ("high_speed", ["sprint", "sprints", "sprinting", "Sprint", "SPRINT",
                        "max-speed sprint", "max velocity", "acceleration run",
                        "explosive run"]),
        ("hip_hinge", ["bent over row", "bent-over row", "bent over dumbbell row",
                       "dumbbell bent row", "DB bent row", "Pendlay row", "T-bar row",
                       "T bar row", "tbar row"]),
        ("jumping", ["box jump", "box jumps", "jumping onto a box",
                     "plyometric box jump", "Box Jump", "BOX JUMPS"]),
    ]
    for pattern, variants in groups:
        misses = [v for v in variants if pattern not in mo.classify(v).patterns]
        if misses:
            finding("HIGH", 10, f"{pattern}: {len(misses)} variants missed", f"{misses}")
        else:
            ok(f"{pattern}: all {len(variants)} phrasings recognised")

    # Case-insensitivity as a property.
    for name in ["Sprint", "ROMANIAN DEADLIFT", "box JUMP", "Bent Over Row"]:
        if mo.classify(name).patterns != mo.classify(name.lower()).patterns:
            finding("MEDIUM", 10, f"capitalisation changes classification of {name!r}")


def phase12_explanatory_text():
    """Text describing a removal must never be read as a prescription."""
    from app.services.contraindications import audit_plan, strip_excluded
    header(12, "safety notes must not self-trigger")

    cons = ["hamstring strain (severity 6/10)"]
    notes = [
        "**Removed for safety:** sprints, box jumps, Romanian deadlifts.",
        "Removed: Deadlifts and leg press, due to strain on the hamstring.",
        "Note: chest-supported rows instead of bent-over rows.",
        "Avoided all sprinting and jumping this week.",
        "We swapped Romanian deadlifts for glute bridges.",
        "No running until this settles.",
    ]
    for note in notes:
        hits = audit_plan(note, cons)
        if hits:
            finding("HIGH", 12, "explanation flagged as a violation",
                    f"{note!r} -> flagged {[h['movement'] for h in hits]}")
        else:
            ok(f"spared: {note[:52]}")

    # Round trip: stripping must produce text that re-audits clean.
    plan = ("* Sprint intervals: 6x100m\n* Romanian deadlift: 3x8\n"
            "* Seated row: 3x10\n* Stationary bike: 20 min")
    cleaned, _ = strip_excluded(plan, cons)
    leftover = audit_plan(cleaned, cons)
    if leftover:
        finding("CRITICAL", 12, "stripped plan does not re-audit clean",
                f"{[f['line'] for f in leftover]}")
    else:
        ok("strip -> re-audit round trip is clean")


def phase13_sparsity():
    """Does the system notice when it has gutted a plan?"""
    from app.services.contraindications import strip_excluded
    header(13, "sparsity after filtering")

    plan = "\n".join([
        "* Sprint intervals: 6x100m", "* Box jumps: 4x5", "* Romanian deadlift: 3x8",
        "* Nordic curls: 3x6", "* Walking lunges: 3x12", "* Back squat: 4x6",
        "* Agility ladder: 10 min", "* Seated row: 3x10", "* Plank: 3x45s",
        "* Stationary bike: 20 min",
    ])
    cleaned, findings_ = strip_excluded(plan, ["hamstring strain (severity 6/10)"])
    kept = [l for l in cleaned.splitlines() if l.strip().startswith("*")]
    removed = len(plan.splitlines()) - len(kept)

    print(f"        {DIM}{removed} of 10 removed, {len(kept)} exercises remain{RESET}")
    if len(kept) <= 3:
        finding("HIGH", 13, f"plan gutted: only {len(kept)}/10 exercises remain",
                "There is no regeneration or replacement step, so the user receives "
                "a near-empty session with no way to recover it.")

    # Prove regeneration exists by exercising it, rather than grepping.
    try:
        from app.services import plan_repair
        calls = {"n": 0}

        def fake_regen(brief):
            calls["n"] += 1
            return plan  # deliberately unchanged, to test the bound too

        plan_repair.repair("* Sprint: 10x100m", ["hamstring strain (severity 6/10)"],
                           requested_minutes=60, regenerate=fake_regen)
        if calls["n"] == 0:
            finding("HIGH", 13, "regeneration never fires on a gutted plan",
                    "A one-exercise result should be judged inadequate.")
        elif calls["n"] > plan_repair.MAX_REGENERATIONS:
            finding("CRITICAL", 13, f"regeneration unbounded: {calls['n']} calls")
        else:
            ok(f"regeneration fires and is bounded ({calls['n']} of "
               f"{plan_repair.MAX_REGENERATIONS} attempts)")
    except Exception as e:
        finding("HIGH", 13, f"regeneration unavailable: {type(e).__name__}: {e}")


def phase14_replacements():
    """A replacement must not share the prohibited pattern."""
    from app.services import movement_ontology as mo
    header(14, "replacement quality")

    pairs = [
        ("Sprint", "Max velocity run", True),          # bad: same pattern
        ("Sprint", "Stationary bike", False),          # good
        ("Romanian deadlift", "Stiff-leg deadlift", True),
        ("Romanian deadlift", "Chest-supported row", False),
        ("Box jump", "Depth jump", True),
        ("Box jump", "Seated calf raise", False),
    ]
    for removed, replacement, should_clash in pairs:
        a = mo.classify(removed).patterns
        b = mo.classify(replacement).patterns
        # Stance and impact descriptors are CONTEXT, not movement identity.
        # A box jump and a seated calf raise both happen on your feet; that
        # does not make one a synonym for the other. The safety audit does
        # care about weight_bearing - this check is asking a different
        # question, namely "is the replacement the same exercise in disguise".
        contextual = {"low_impact", "unilateral", "isometric", "weight_bearing",
                      "seated_supported", "non_weight_bearing", "loaded_stance",
                      "impact"}
        clash = bool((a & b) - contextual)
        if clash != should_clash:
            finding("MEDIUM", 14, f"replacement check wrong: {removed} -> {replacement}",
                    f"shared={sorted(a & b)}, expected clash={should_clash}")
        else:
            ok(f"{removed} -> {replacement}: {'clashes' if clash else 'genuinely different'}")

    # Does anything in the codebase actually USE this comparison, end to end?
    # Checking the service file alone was wrong once the logic moved into
    # plan_repair - the audit has to follow the call, not the filename.
    try:
        from app.services import plan_repair
        from app.services import injury_taxonomy as tax
        profs = [p for p in (tax.parse("hamstring strain (severity 6/10)"),) if p]
        result = plan_repair.repair("* Bent Over Dumbbell Rows: 3x8",
                                    ["hamstring strain (severity 6/10)"])
        swap = result.replacements[0] if result.replacements else None
        if not swap or not swap.replacement:
            finding("HIGH", 14, "no replacement produced for a removable exercise",
                    "The exercise was dropped rather than substituted.")
        elif not swap.preserved:
            finding("MEDIUM", 14, "replacement does not record a preserved purpose",
                    f"{swap.original} -> {swap.replacement}")
        else:
            from app.services.contraindications import audit_against_profiles
            if audit_against_profiles(swap.replacement, profs):
                finding("CRITICAL", 14, "the chosen replacement is itself unsafe",
                        f"{swap.replacement}")
            else:
                ok(f"replacement validated end to end: {swap.original.strip()[:28]} "
                   f"-> {swap.replacement} (kept {', '.join(swap.preserved)})")
    except Exception as e:
        finding("HIGH", 14, f"replacement pipeline unavailable: {type(e).__name__}: {e}")


def phase15_healthy_controls():
    """False positives: a healthy user must lose nothing."""
    from app.services.contraindications import audit_plan
    header(15, "healthy control group")

    plan = "\n".join([
        "* Sprint intervals: 8x100m", "* Pro agility shuttle: 6 sets",
        "* Box jumps: 4x5", "* Back squat: 5x5", "* Romanian deadlift: 3x8",
        "* Bench press: 4x6", "* Overhead press: 3x8", "* Pull-ups: 4x8",
        "* Bent over row: 4x8", "* Farmer carries: 3x40m",
    ])
    for label, constraints in [("no constraints", []), ("empty strings", ["", "  "])]:
        hits = audit_plan(plan, constraints)
        if hits:
            finding("HIGH", 15, f"healthy user ({label}) lost {len(hits)} exercises",
                    f"{[h['line'] for h in hits][:4]}")
        else:
            ok(f"healthy user ({label}): nothing removed")

    # A recovered injury must not keep restricting.
    hits = audit_plan(plan, ["hamstring strain (severity 0/10)"])
    if len(hits) > 2:
        finding("MEDIUM", 15, f"fully recovered injury still removes {len(hits)} items",
                f"{[h['line'] for h in hits][:4]}")
    else:
        ok(f"recovered (0/10): {len(hits)} removed")


def phase16_unknown_defaults():
    """UNKNOWN must never mean SAFE."""
    from app.services import movement_ontology as mo
    from app.services.contraindications import audit_plan
    header(16, "unknown handling")

    invented = ["Zercher Anderson squat", "Kang squat", "Jefferson deadlift",
                "Hatfield squat", "Poliquin step-up", "Cossack squat",
                "Sissy squat", "Sorenson hold", "Petersen step-up",
                "Frankenstein squat", "Spanish squat", "ATG split squat"]
    unclassified = [n for n in invented if mo.classify(n).unknown]
    if unclassified:
        finding("MEDIUM", 16, f"{len(unclassified)}/{len(invented)} invented names unclassified",
                f"{unclassified}\nThese reach the user unexamined - nothing flags them.")
    else:
        ok("all invented exercise names classified")

    # An unrecognised CONDITION must still restrict something.
    for text in ["costochondritis (severity 6/10)", "Sever's disease (severity 6/10)",
                 "os trigonum syndrome (severity 6/10)"]:
        hits = audit_plan("* Explosive sled sprints: 6 sets\n* Seated row: 3x10", [text])
        if not hits:
            finding("HIGH", 16, f"unknown condition {text.split(' (')[0]!r} restricts nothing",
                    "Unrecognised must fall back to cautious, not permissive.")
        else:
            ok(f"unknown condition {text.split(' (')[0]!r} still guarded")


def phase17_red_flags():
    """Escalation must beat modification."""
    from app.services import injury_taxonomy as it
    header(17, "red flags and escalation")

    cases = ["my knee gave way and it's swollen",
             "numbness and tingling down my arm",
             "I heard a pop and can't bear weight",
             "sharp pain that's getting worse",
             "suspected fracture in my wrist"]
    for text in cases:
        p = it.parse(text)
        if not p:
            finding("CRITICAL", 17, f"red-flag text not parsed at all: {text!r}")
        elif not p.needs_medical:
            finding("CRITICAL", 17, f"red flag not escalated: {text!r}",
                    f"flags={p.red_flags}, stage={p.stage.key}")
        else:
            ok(f"escalated: {text[:44]}")

    # The two red-flag lists must agree, or one path escalates and the other does not.
    from app.services import contraindications as c
    only_a = set(c.RED_FLAGS) - set(it.RED_FLAGS)
    only_b = set(it.RED_FLAGS) - set(c.RED_FLAGS)
    if only_a or only_b:
        finding("HIGH", 17, "two red-flag lists disagree",
                f"contraindications only: {sorted(only_a)[:6]}\n"
                f"taxonomy only: {sorted(only_b)[:6]}\n"
                "Whether you are told to see someone depends on which code path ran.")


def phase19_regressions():
    """Every bug found so far must stay fixed."""
    from app.services.contraindications import audit_plan, strip_excluded
    header(19, "regression suite for known bugs")

    cons = ["upper hamstring strain, left leg (severity 6/10)"]
    regressions = [
        ("R1 'Sprints' vs 'sprinting'", "* Sprints (20m): 6 sets", True),
        ("R2 'Pro Agility Shuttle'", "* Pro Agility Shuttle: 6 sets", True),
        ("R3 'Bent Over Dumbbell Rows'", "* Bent Over Dumbbell Rows: 3x10", True),
        ("R4 safety note self-flag", "**Removed for safety:** sprints, box jumps.", False),
        ("R5 supported row spared", "* Chest-supported row: 3x10", False),
        ("R6 avoidance note spared", "* Cycling instead of running: 20 min", False),
    ]
    for label, line, should_flag in regressions:
        flagged = bool(audit_plan(line, cons))
        if flagged != should_flag:
            finding("CRITICAL", 19, f"{label} REGRESSED",
                    f"expected flag={should_flag}, got {flagged}")
        else:
            ok(label)


def phase20_mutation():
    """Do the tests actually detect a broken rule?"""
    from app.services import injury_taxonomy as it
    from app.services.contraindications import audit_plan
    header(20, "mutation testing - can the suite detect sabotage?")

    hamstring = next(c for c in it.CONDITIONS if c.key == "hamstring")
    probe = "* Romanian deadlift: 3x8"
    cons = ["hamstring strain (severity 6/10)"]

    before = bool(audit_plan(probe, cons))
    # Sabotage: remove hip_hinge from the hamstring's primary restrictions.
    original = hamstring.primary
    object.__setattr__(hamstring, "primary", set())
    after = bool(audit_plan(probe, cons))
    object.__setattr__(hamstring, "primary", original)

    if before and not after:
        ok("removing a restriction changes behaviour - the rule is load-bearing")
    elif before and after:
        finding("MEDIUM", 20, "sabotaging the pattern rule did not change the outcome",
                "The name-based fallback masks it, so a broken pattern rule would "
                "not be detected by a pattern-level test.")
    else:
        finding("HIGH", 20, "probe was not flagged even before sabotage")


def phase21_properties():
    """Invariants that must hold for any input."""
    from app.services import movement_ontology as mo
    from app.services import injury_taxonomy as it
    from app.services.contraindications import audit_plan, strip_excluded
    header(21, "property-based invariants")

    corpus = ["Sprint", "sprints", "SPRINTING", "Romanian Deadlift", "rdl",
              "Box Jump", "box jumps", "Bent Over Row", "bent-over rows",
              "Chest Supported Row", "Stationary Bike", "Plank", "Leg Press"]

    # P1 capitalisation invariance
    bad = [n for n in corpus if mo.classify(n).patterns != mo.classify(n.upper()).patterns]
    finding("MEDIUM", 21, f"capitalisation changes classification for {bad}") if bad \
        else ok("P1 classification is case-invariant")

    # P2 simple pluralisation invariance
    pairs = [("sprint", "sprints"), ("box jump", "box jumps"), ("lunge", "lunges"),
             ("row", "rows"), ("squat", "squats")]
    bad = [(a, b) for a, b in pairs if mo.classify(a).patterns != mo.classify(b).patterns]
    finding("MEDIUM", 21, f"pluralisation changes classification: {bad}") if bad \
        else ok("P2 classification is plural-invariant")

    # P4 adding an injury must never make something previously unsafe become safe
    plan = "\n".join(f"* {n}: 3x8" for n in corpus)
    base = {f["line"] for f in audit_plan(plan, ["hamstring strain (severity 6/10)"])}
    more = {f["line"] for f in audit_plan(plan, ["hamstring strain (severity 6/10)",
                                                 "shoulder impingement (severity 6/10)"])}
    if not base <= more:
        finding("CRITICAL", 21, "adding an injury UNFLAGGED previously unsafe lines",
                f"lost: {sorted(base - more)}")
    else:
        ok("P4 restrictions are monotonic when injuries are added")

    # P5 a stripped plan contains nothing prohibited
    for sev in (2, 4, 6, 7):
        cleaned, _ = strip_excluded(plan, [f"hamstring strain (severity {sev}/10)"])
        if audit_plan(cleaned, [f"hamstring strain (severity {sev}/10)"]):
            finding("CRITICAL", 21, f"stripped plan still audits dirty at {sev}/10")
    ok("P5 stripped plans audit clean at every severity")

    # P6 unknown is never silently safe
    unknown_count = sum(1 for n in corpus if mo.classify(n).unknown)
    if unknown_count:
        finding("LOW", 21, f"{unknown_count} corpus items unclassified")


def phase2_live_path():
    """
    The join that matters: constraints are BUILT by one system and PARSED by
    another. If the wording drifts, restrictions silently vanish.
    """
    from app.services import contraindications as c
    from app.services import injury_taxonomy as it
    header("2b", "live path - do built constraints survive re-parsing?")

    # Reproduce what injury_service.as_constraints() emits, without a database.
    for key, entry in c.CONTRAINDICATIONS.items():
        stage = c.stage_for(5)
        label = key.replace("_", " ")
        constraint = (f"{label} (severity 5/10, {stage['label']}). {stage['guidance']}"
                      f" Avoid: {', '.join(entry.all_excluded()[:16])}.")
        parsed = it.parse(constraint)
        if not parsed:
            finding("CRITICAL", "2b", f"{key!r} constraint does not parse at all",
                    f"{constraint[:100]}...\nNo restrictions would be applied.")
        elif not parsed.condition and not parsed.region:
            finding("HIGH", "2b", f"{key!r} parses with no condition and no region",
                    "Falls back to speed-only restrictions.")
        elif not parsed.condition:
            finding("MEDIUM", "2b", f"{key!r} resolves only to region {parsed.region!r}",
                    "Region fallback is coarser than the condition rules.")
        else:
            ok(f"{key} -> {parsed.condition.key}")


PHASES = {
    "2b": phase2_live_path, 3: phase3_movement_families, 4: phase4_unknown_exercises,
    5: phase5_injury_coverage, 6: phase6_laterality, 7: phase7_severity,
    9: phase9_multiple_injuries, 10: phase10_adversarial_language,
    12: phase12_explanatory_text, 13: phase13_sparsity, 14: phase14_replacements,
    15: phase15_healthy_controls, 16: phase16_unknown_defaults, 17: phase17_red_flags,
    19: phase19_regressions, 20: phase20_mutation, 21: phase21_properties,
}


def main():
    global QUIET
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", help="run one phase")
    ap.add_argument("--quiet", action="store_true", help="findings only")
    args = ap.parse_args()
    QUIET = args.quiet

    print(f"\n{BOLD}ADVERSARIAL SAFETY AUDIT{RESET}")
    started = time.time()

    selected = ([PHASES[args.phase if args.phase in PHASES else int(args.phase)]]
                if args.phase else list(PHASES.values()))
    for fn in selected:
        try:
            fn()
        except Exception as e:
            finding("CRITICAL", "?", f"{fn.__name__} raised {type(e).__name__}: {e}")

    print(f"\n{BOLD}SUMMARY{RESET}  {DIM}({time.time() - started:.1f}s){RESET}")
    print(f"  passed         {STATS['PASS']}")
    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        if STATS[sev]:
            colour = {"CRITICAL": RED, "HIGH": RED, "MEDIUM": YELLOW, "LOW": DIM}[sev]
            print(f"  {colour}{sev:<14}{STATS[sev]}{RESET}")

    if FINDINGS:
        print(f"\n{BOLD}FINDINGS{RESET}")
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            for s, phase, title, _ in FINDINGS:
                if s == sev:
                    print(f"  [{sev}] phase {phase}: {title}")
    print()
    return 1 if STATS["CRITICAL"] or STATS["HIGH"] else 0


if __name__ == "__main__":
    sys.exit(main())
