#!/usr/bin/env python3
"""
Regression tests for the 7 fixes from the Codex-flagged FitMentor review.

Entirely offline: rate-limit and model-output scenarios use a stub agent
rather than a real Groq call, per the review's own instruction to prefer
mocks over live generation. No network access, no quota spent.

    python scripts/test_codex_fixes.py
"""

import asyncio
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
        print(f"  {RED}FAIL{RESET}  {label}{f' - {detail}' if detail else ''}")


class _RaisingAgent:
    """Stands in for fitness_agent when the model call must fail."""
    def __init__(self, message):
        self._message = message

    def run(self, prompt):
        raise Exception(self._message)


class _FixedAgent:
    """Stands in for fitness_agent when the model must return known text."""
    def __init__(self, text):
        self._text = text

    def run(self, prompt):
        class _Response:
            pass
        r = _Response()
        r.content = self._text
        return r


def _swap_agent(service, agent):
    """Context-manager-free swap/restore, since these are plain functions."""
    original = service.fitness_agent
    service.fitness_agent = agent
    return original


def _live_plan(text):
    """
    The actual prescribed plan, excluding the "Adjusted for your injury"
    transparency note plan_repair appends - that note deliberately QUOTES
    the removed/replaced exercise name ("Swapped *X* for **Y**") so the user
    can see what changed, so checking for the name's absence across the
    whole text is the wrong test: the name is SUPPOSED to appear there.
    """
    return text.split("\n\n---", 1)[0]


async def test_1_rate_limit_fallback_safety():
    """
    FIX 1: the hardcoded rate-limit fallback must not reach a user with an
    active injury unaudited. The fallback text itself contains squats,
    lunges, jumping jacks and burpees - all restricted for an active
    hamstring injury - so this is a real, not synthetic, safety scenario.
    """
    from app.services.fitmentor_service import fitmentor_service
    from app.services import injury_taxonomy as taxonomy
    from app.services.contraindications import audit_against_profiles

    print(f"\n{BOLD}Fix 1: rate-limit fallback safety{RESET}")

    original = _swap_agent(
        fitmentor_service,
        _RaisingAgent("Rate limit reached for model `x` on tokens per day (TPD)"),
    )
    try:
        result = await fitmentor_service.generate_workout_plan(
            activity_level="beginner", fitness_goal="general_fitness",
            time_per_day=30, equipment="none",
            constraints=["hamstring strain (severity 6/10)"],
        )
    finally:
        fitmentor_service.fitness_agent = original

    if not result.get("success"):
        # Failing safely is an explicitly acceptable outcome per the fix.
        check("rate-limited + injury: failed safely rather than returning unaudited content",
              result.get("error_type") in ("rate_limit", "safety_unavailable"),
              f"got {result}")
        return

    profiles = taxonomy.parse_all(["hamstring strain (severity 6/10)"])
    findings = audit_against_profiles(result["workout_plan"], profiles)
    check("rate-limit fallback plan audits clean for an active injury",
          not findings, f"prohibited lines survived: {findings}")
    check("fallback response carries removed_for_safety",
          "removed_for_safety" in result, f"keys={list(result.keys())}")


async def test_2_adapted_plan_safety():
    """
    FIX 2: adapt_workout_plan must run the same deterministic audit/repair
    as generate_workout_plan. Mocked model output deliberately contains a
    hip-hinge movement prohibited for an active hamstring injury.
    """
    from app.services.fitmentor_service import fitmentor_service
    from app.services import injury_taxonomy as taxonomy
    from app.services.contraindications import audit_against_profiles

    print(f"\n{BOLD}Fix 2: adapted-plan safety{RESET}")

    original = _swap_agent(
        fitmentor_service,
        _FixedAgent("* Romanian deadlift: 4x8 @ RPE 7, rest 90 sec\n* Push-up: 3x10"),
    )
    try:
        result = await fitmentor_service.adapt_workout_plan(
            current_plan="* Push-up: 3x10",
            feedback="add another exercise for variety",
            constraints=["hamstring strain (severity 6/10)"],
            equipment="gym",
        )
    finally:
        fitmentor_service.fitness_agent = original

    check("adaptation with injury reports success", result.get("success"), f"{result}")
    if not result.get("success"):
        return

    profiles = taxonomy.parse_all(["hamstring strain (severity 6/10)"])
    findings = audit_against_profiles(result["adapted_plan"], profiles)
    check("adapted plan has no prohibited movement remaining",
          not findings, f"prohibited lines survived: {findings}")
    check("prohibited exercise is gone from the LIVE plan (the note may still name it)",
          "Romanian deadlift" not in _live_plan(result["adapted_plan"]),
          f"live plan={_live_plan(result['adapted_plan'])!r}")


def test_3_unclassifiable_fails_closed():
    """
    FIX 3: a movement the ontology cannot classify, with an active injury
    and no validated safe substitute, must be REMOVED - not silently kept
    while the plan is reported audit-clean.
    """
    from app.services import plan_repair as pr
    from app.services import movement_ontology as ontology

    print(f"\n{BOLD}Fix 3: unclassifiable movement fails closed{RESET}")

    probe = "Ankle pogo drill: 4 rounds"
    check("sanity: this probe is genuinely unclassifiable",
          not ontology.classify_prescribed(probe).patterns)

    plan = f"* {probe}\n* Calf raise: 3x15"
    result = pr.repair(plan, ["ankle sprain (severity 6/10)"], equipment="gym")
    check("unclassifiable line does not survive verbatim in the LIVE plan",
          probe not in _live_plan(result.plan), f"live plan={_live_plan(result.plan)!r}")
    check("removal is recorded (not silently dropped from the report)",
          any(probe in r for r in result.removed) or
          any(probe in rep.original for rep in result.replacements),
          f"removed={result.removed} replacements={result.replacements}")


def test_4_explicit_restriction_deterministic():
    """
    FIX 4: "no jumping" / "avoid overhead" / "no running" must have
    deterministic authority - not depend on the model choosing to honour
    prompt text.
    """
    from app.services import plan_repair as pr
    from app.services import injury_taxonomy as taxonomy

    print(f"\n{BOLD}Fix 4: explicit restrictions{RESET}")

    cases = [
        ("no jumping", "Box jump: 4x5", "jumping"),
        ("avoid overhead exercise", "Overhead press: 3x8", "overhead"),
        ("no running", "Sprint intervals: 6x200m", "running/high_speed"),
    ]
    for constraint, exercise, label in cases:
        parsed = taxonomy.parse(constraint)
        check(f"{constraint!r} parses to a restriction with patterns",
              parsed is not None and bool(parsed.restricted_patterns()),
              f"parsed={parsed}")

        plan = f"* {exercise}\n* Plank: 3x45s"
        result = pr.repair(plan, [constraint], equipment="gym")
        check(f"{constraint!r} -> {exercise!r} removed or replaced deterministically",
              exercise not in _live_plan(result.plan),
              f"live plan={_live_plan(result.plan)!r}")


def test_5_context_aware_duplicate_patterns():
    """
    FIX 5: a legitimate endurance/running week must not be judged
    "repetitive" or "too narrow" merely because running is the whole point
    of the week, and must not trigger a wasted regeneration call.
    """
    from app.services import plan_quality as pq
    from app.services import plan_repair as pr

    print(f"\n{BOLD}Fix 5: context-aware duplicate-pattern detection{RESET}")

    plan = "\n".join([
        "### Monday", "* Easy run: 30 min",
        "### Tuesday", "* Interval run: 6x400m",
        "### Wednesday", "* Easy run: 30 min",
        "### Thursday", "* Tempo run: 20 min",
        "### Friday", "* Easy run: 30 min",
        "### Saturday", "* Long run: 60 min",
        "### Sunday", "* Rest day",
    ])
    q = pq.evaluate(plan, requested_minutes=45, goal="endurance", sport="running",
                     equipment="none", level="intermediate")
    check("running is not flagged as repetitive for a running-goal week",
          "running" not in " ".join(q.duplicate_patterns), f"duplicate_patterns={q.duplicate_patterns}")
    check("plan is adequate (would not trigger regeneration)",
          q.adequate, f"issues={q.issues}")

    calls = {"n": 0}
    pr.repair(plan, [], requested_minutes=45, goal="endurance", sport="running",
              equipment="none", level="intermediate",
              regenerate=lambda b: (calls.__setitem__("n", calls["n"] + 1), plan)[1])
    check("no regeneration call was made for the legitimate running week",
          calls["n"] == 0, f"regenerate called {calls['n']} time(s)")

    # Control: genuine repetition with no goal/sport justification must
    # still be caught - the fix narrows the rule, it does not disable it.
    bad = "\n".join(["* Bicep curl: 3x10"] * 6)
    q2 = pq.evaluate(bad, equipment="gym")
    check("unjustified repetition is still flagged (control)",
          bool(q2.duplicate_patterns), f"duplicate_patterns={q2.duplicate_patterns}")


def test_6_equipment_false_positives():
    """FIX 6: negation, optional language, home equipment, substring false positives."""
    from app.services import plan_quality as pq

    print(f"\n{BOLD}Fix 6: equipment validation false positives{RESET}")

    cases = [
        ("home", "* Dumbbell row: 3x10\n* Kettlebell swing: 3x12",
         "home equipment (dumbbells/kettlebell) is not a violation for equipment=home"),
        ("none", "* Push-up: 3x10\n* No dumbbells required, bodyweight only.",
         "negated equipment mention is not a violation"),
        ("none", "* Push-up: 3x10\n* Optional: use a resistance band if available.",
         "optional equipment language is not a violation"),
        ("gym", "* Sprint drills to improve your on-field performance.",
         "'on-field performance' does not trigger a field-equipment violation"),
    ]
    for equipment, plan, label in cases:
        violations = pq._equipment_issues(plan, equipment)
        check(label, not violations, f"violations={violations}")

    # Controls: real violations must still be caught.
    for equipment, plan, label in [
        ("none", "* Barbell back squat: 4x6", "real gym-only equipment still flagged for equipment=none (control)"),
        ("home", "* Barbell back squat: 4x6", "real gym-only equipment still flagged for equipment=home (control)"),
    ]:
        violations = pq._equipment_issues(plan, equipment)
        check(label, bool(violations), f"violations={violations}")


def test_7_replacement_dosage_preserved():
    """
    FIX 7: substituting an exercise must keep the original prescription
    (sets/reps/RPE/rest) rather than reducing the line to a bare name.
    """
    from app.services import plan_repair as pr

    print(f"\n{BOLD}Fix 7: replacement dosage preservation{RESET}")

    plan = "* Romanian deadlift: 4x8 @ RPE 7, rest 90 sec"
    result = pr.repair(plan, ["hamstring strain (severity 6/10)"], equipment="gym")
    check("a replacement happened", bool(result.replacements), f"{result.replacements}")
    if result.replacements:
        replaced_line = next(
            (line for line in result.plan.splitlines()
             if result.replacements[0].replacement in line),
            None,
        )
        check("original dosage (sets/reps/RPE/rest) carried onto the replacement",
              replaced_line is not None and "4x8" in replaced_line and "RPE 7" in replaced_line
              and "90 sec" in replaced_line,
              f"replaced_line={replaced_line!r}")
        check("replacement is not reduced to a bare exercise name",
              replaced_line is not None and ":" in replaced_line,
              f"replaced_line={replaced_line!r}")


def main():
    print(f"\n{BOLD}CODEX REVIEW FIXES - REGRESSION SUITE{RESET}")
    asyncio.run(test_1_rate_limit_fallback_safety())
    asyncio.run(test_2_adapted_plan_safety())
    test_3_unclassifiable_fails_closed()
    test_4_explicit_restriction_deterministic()
    test_5_context_aware_duplicate_patterns()
    test_6_equipment_false_positives()
    test_7_replacement_dosage_preserved()
    print(f"\n{BOLD}{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
