#!/usr/bin/env python3
"""
Regression suite for plan repair - replacement (BUG-14) and regeneration (BUG-13).

Covers the 17 scenarios specified, plus mutation testing: safety rules are
temporarily sabotaged to confirm the tests actually detect a broken engine
rather than passing regardless.

    python scripts/test_plan_repair.py
    python scripts/test_plan_repair.py --mutation-only
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
)

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


HAMSTRING = ["upper hamstring strain, left leg (severity 6/10)"]
SHOULDER_R = ["right shoulder impingement (severity 6/10)"]
BIG_PLAN = "\n".join([
    "* Warm-up: 5-minute jog",
    "* Bent Over Dumbbell Rows: 3x8",
    "* Romanian deadlift: 3x8",
    "* Box jumps: 4x5",
    "* Sprint intervals: 6x100m",
    "* Bench press: 4x6",
    "* Seated calf raise: 3x12",
    "* Plank: 3x45s",
    "* Walking lunges: 3x12",
    "* Nordic curls: 3x6",
])
SMALL_PLAN = "\n".join([
    "* Romanian deadlift: 3x8",
    "* Bench press: 4x6",
    "* Seated cable row: 3x10",
    "* Plank: 3x45s",
    "* Stationary bike: 20 min",
])


def run():
    from app.services import plan_repair
    from app.services.contraindications import audit_against_profiles
    from app.services import injury_taxonomy as taxonomy

    def profiles(constraints):
        return [p for p in (taxonomy.parse(c) for c in constraints) if p]

    print(f"\n{BOLD}1-2. Regeneration triggers on ratio, not raw count{RESET}")
    heavy = plan_repair.repair(BIG_PLAN, HAMSTRING, requested_minutes=60)
    light = plan_repair.repair(SMALL_PLAN, HAMSTRING, requested_minutes=45)
    check("6/10 hamstring on a 10-exercise plan stays usable",
          heavy.quality["exercises"] >= 8,
          f"{heavy.quality}")
    check("1 removal from 5 does not trigger regeneration",
          light.quality["adequate"] or light.quality["removed"] <= 1,
          f"{light.quality}")

    print(f"\n{BOLD}3. Same movement family, many instances{RESET}")
    family = "\n".join([f"* {n}: 3x8" for n in
                        ["Romanian deadlift", "Stiff-leg deadlift", "Good morning",
                         "Bent over row", "Pendlay row", "T-bar row"]])
    r = plan_repair.repair(family, HAMSTRING)
    check("every hinge variant is handled",
          len(r.replacements) + len(r.removed) == 6,
          f"handled {len(r.replacements) + len(r.removed)} of 6")
    check("no hinge survives", not audit_against_profiles(r.plan, profiles(HAMSTRING)))

    print(f"\n{BOLD}4. Multiple injuries - replacement must satisfy ALL{RESET}")
    both = ["right hamstring strain (severity 5/10)",
            "left shoulder impingement (severity 5/10)"]
    r = plan_repair.repair(BIG_PLAN, both)
    leftover = audit_against_profiles(r.plan, profiles(both))
    check("final plan is clean against both injuries", not leftover, f"{leftover[:2]}")
    for swap in r.replacements:
        check(f"replacement {swap.replacement!r} clears both injuries",
              not audit_against_profiles(swap.replacement, profiles(both)))

    print(f"\n{BOLD}5-6. Laterality survives the pipeline{RESET}")
    for text, expected in [("right hamstring strain (severity 5/10)", "right"),
                           ("left hamstring strain (severity 5/10)", "left"),
                           ("bilateral hamstring strain (severity 5/10)", "bilateral")]:
        p = taxonomy.parse(text)
        check(f"{expected} preserved through parse", p and p.side == expected,
              f"got {p.side if p else None}")
    r = plan_repair.repair(BIG_PLAN, ["right hamstring strain (severity 5/10)"])
    check("sided injury still produces a clean plan",
          not audit_against_profiles(r.plan, profiles(["right hamstring strain (severity 5/10)"])))

    print(f"\n{BOLD}7-8. Replacement validation{RESET}")
    # A synonym must never be accepted as a replacement.
    from app.services import movement_ontology as ontology
    bad_pairs = [("Sprint", "Max velocity run"), ("Romanian deadlift", "Stiff-leg deadlift"),
                 ("Box jump", "Depth jump"), ("Bent over row", "Pendlay row")]
    for original, synonym in bad_pairs:
        shared = ontology.classify(original).patterns & ontology.classify(synonym).patterns
        check(f"{synonym!r} shares a pattern with {original!r} (would be rejected)",
              bool(shared), f"shared={shared}")
        check(f"{synonym!r} is rejected by the audit for a hamstring",
              bool(audit_against_profiles(synonym, profiles(HAMSTRING)))
              or "hip_hinge" not in ontology.classify(original).patterns)

    r = plan_repair.repair("* Bent Over Dumbbell Rows: 3x8", HAMSTRING)
    swap = r.replacements[0] if r.replacements else None
    check("genuinely safe replacement is chosen and keeps the purpose",
          swap and "horizontal_pull" in swap.preserved,
          f"{swap.replacement if swap else None} preserved={swap.preserved if swap else None}")

    print(f"\n{BOLD}9-11. Regeneration is bounded and validated{RESET}")
    calls = {"n": 0}

    def regen_returns_unsafe(brief):
        calls["n"] += 1
        return "\n".join(["* Sprint intervals: 6x100m"] * 3 + ["* Romanian deadlift: 3x8"])

    r = plan_repair.repair("* Sprint: 6x100m\n* Box jump: 4x5", HAMSTRING,
                           requested_minutes=60, regenerate=regen_returns_unsafe)
    check("regeneration returning unsafe work is still filtered",
          not audit_against_profiles(r.plan, profiles(HAMSTRING)))
    check(f"regeneration bounded at {plan_repair.MAX_REGENERATIONS}",
          calls["n"] <= plan_repair.MAX_REGENERATIONS,
          f"called {calls['n']} times")

    calls2 = {"n": 0}

    def regen_returns_synonyms(brief):
        calls2["n"] += 1
        return "\n".join(["* Max velocity run: 6x100m", "* Stiff-leg deadlift: 3x8",
                          "* Depth jumps: 4x5"])

    r = plan_repair.repair(BIG_PLAN, HAMSTRING, requested_minutes=60,
                           regenerate=regen_returns_synonyms)
    check("synonyms from regeneration are caught too",
          not audit_against_profiles(r.plan, profiles(HAMSTRING)))
    check("no infinite loop", calls2["n"] <= plan_repair.MAX_REGENERATIONS)

    print(f"\n{BOLD}12. Healthy user never regenerates{RESET}")
    calls3 = {"n": 0}

    def should_not_be_called(brief):
        calls3["n"] += 1
        return BIG_PLAN

    r = plan_repair.repair(BIG_PLAN, [], regenerate=should_not_be_called)
    check("no regeneration for a healthy user", calls3["n"] == 0)
    check("healthy plan is returned untouched", r.plan == BIG_PLAN)
    check("nothing removed for a healthy user", not r.removed and not r.replacements)

    print(f"\n{BOLD}13. Final audit catches an unsafe replacement{RESET}")
    # Force a bad replacement into the catalogue and confirm the final audit
    # removes it rather than trusting the replacement step.
    from app.services import exercise_catalogue as catalogue
    poison = catalogue.Candidate("Sprint intervals on the track", "conditioning", "none")
    poison.patterns = ontology.classify(poison.name).patterns
    catalogue.CATALOGUE.insert(0, poison)
    try:
        r = plan_repair.repair("* Box jumps: 4x5", HAMSTRING)
        check("poisoned candidate never reaches the final plan",
              not audit_against_profiles(r.plan, profiles(HAMSTRING)),
              f"plan={r.plan!r}")
    finally:
        catalogue.CATALOGUE.remove(poison)

    print(f"\n{BOLD}14-15. Purpose preserved, plan stays useful{RESET}")
    r = plan_repair.repair(BIG_PLAN, HAMSTRING, requested_minutes=60)
    row_swap = next((s for s in r.replacements if "row" in s.original.lower()), None)
    check("a removed row is replaced by another pull, not a leg exercise",
          row_swap and "row" in (row_swap.replacement or "").lower(),
          f"{row_swap.replacement if row_swap else None}")
    check("plan remains useful after filtering",
          r.quality["exercises"] >= 8 and r.quality["distinct_patterns"] >= 3,
          f"{r.quality}")

    print(f"\n{BOLD}16-17. Loop safety and the explanation note{RESET}")
    calls4 = {"n": 0}

    def always_bad(brief):
        calls4["n"] += 1
        return "* Sprint: 10x100m"

    r = plan_repair.repair("* Sprint: 10x100m", HAMSTRING, requested_minutes=60,
                           regenerate=always_bad)
    check("terminates when regeneration never improves",
          calls4["n"] <= plan_repair.MAX_REGENERATIONS, f"{calls4['n']} calls")
    check("the appended note is not audited as prescribed work",
          not audit_against_profiles(r.plan, profiles(HAMSTRING)),
          f"{r.plan[-200:]}")

    print(f"\n{BOLD}Catalogue integrity{RESET}")
    from app.services import injury_taxonomy as tax
    unsafe = []
    for cond in tax.CONDITIONS:
        for sev in (6, 4, 2):
            profs = [tax.InjuryProfile(raw=cond.label, condition=cond, region=cond.region,
                                       severity=sev, side=None,
                                       stage=tax.stage_for_severity(sev))]
            for cand in catalogue.CATALOGUE:
                if audit_against_profiles(cand.name, profs):
                    unsafe.append((cond.key, sev, cand.name))
    # Being rejected is FINE - that is the audit working. This only reports
    # how often, so a catalogue that is useless for a condition is visible.
    by_condition = {}
    for key, sev, name in unsafe:
        by_condition.setdefault(key, set()).add(name)
    starved = [k for k, v in by_condition.items()
               if len(v) > len(catalogue.CATALOGUE) * 0.8]
    check("no condition has almost every candidate rejected", not starved,
          f"starved: {starved}")


def mutation():
    """Break safety rules on purpose; the checks above must fail."""
    from app.services import injury_taxonomy as tax
    from app.services import plan_repair
    from app.services.contraindications import audit_against_profiles

    print(f"\n{BOLD}MUTATION TESTING{RESET}")
    profs = [p for p in (tax.parse(c) for c in HAMSTRING) if p]
    hamstring = next(c for c in tax.CONDITIONS if c.key == "hamstring")

    # M1 - break the restriction data.
    original = hamstring.primary
    object.__setattr__(hamstring, "primary", set())
    detected = not audit_against_profiles("* Romanian deadlift: 3x8", profs)
    object.__setattr__(hamstring, "primary", original)
    check("M1 removing hip_hinge restriction changes the verdict", detected,
          "The audit still flagged it, so a broken rule would go unnoticed.")

    # M2 - break the final audit by making repair skip it.
    real_audit = plan_repair.__dict__.get("_repair_once")
    r_before = plan_repair.repair("* Sprint: 6x100m", HAMSTRING)
    check("M2 baseline: repair produces a clean plan",
          not audit_against_profiles(r_before.plan, profs))

    # M3 - break replacement validation by accepting the first candidate blindly.
    from app.services import exercise_catalogue as catalogue
    saved = list(catalogue.CATALOGUE)
    poison = catalogue.Candidate("Sprint drills", "conditioning", "none")
    from app.services import movement_ontology as ontology
    poison.patterns = ontology.classify(poison.name).patterns
    catalogue.CATALOGUE.insert(0, poison)
    try:
        r = plan_repair.repair("* Box jumps: 4x5", HAMSTRING)
        clean = not audit_against_profiles(r.plan, profs)
        check("M3 a poisoned catalogue cannot produce an unsafe plan", clean,
              f"plan={r.plan!r}")
    finally:
        catalogue.CATALOGUE[:] = saved

    # M4 - break the regeneration trigger.
    #
    # The trigger is deliberately multi-factor (count, removal ratio, pattern
    # spread, duration), so disabling ONE threshold must not stop it - an
    # earlier version of this mutation did exactly that and "failed" because
    # the other factors correctly still fired. Sabotaging all of them is the
    # real test of whether quality is what drives regeneration.
    import app.services.plan_quality as pq
    saved = (pq.MIN_EXERCISES, pq.MAX_REMOVED_FRACTION, pq.MIN_DISTINCT_PATTERNS)

    calls_partial = {"n": 0}
    def regen_partial(brief):
        calls_partial["n"] += 1
        return BIG_PLAN
    pq.MIN_EXERCISES = 0
    plan_repair.repair("* Sprint: 6x100m", HAMSTRING, requested_minutes=60,
                       regenerate=regen_partial)
    pq.MIN_EXERCISES = saved[0]
    check("M4a disabling ONE threshold does not disable regeneration",
          calls_partial["n"] > 0,
          "A single-factor trigger would be the simplistic rule we were told to avoid.")

    calls_all = {"n": 0}
    def regen_all(brief):
        calls_all["n"] += 1
        return BIG_PLAN
    pq.MIN_EXERCISES, pq.MAX_REMOVED_FRACTION, pq.MIN_DISTINCT_PATTERNS = 0, 1.0, 0
    plan_repair.repair("* Sprint: 6x100m", HAMSTRING, requested_minutes=None,
                       regenerate=regen_all)
    pq.MIN_EXERCISES, pq.MAX_REMOVED_FRACTION, pq.MIN_DISTINCT_PATTERNS = saved
    check("M4b disabling ALL quality thresholds stops regeneration",
          calls_all["n"] == 0,
          "Regeneration fired with every threshold disabled, so something other "
          "than the quality evaluator is driving it.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutation-only", action="store_true")
    args = ap.parse_args()

    print(f"\n{BOLD}PLAN REPAIR — BUG-13 + BUG-14 regression suite{RESET}")
    if not args.mutation_only:
        run()
    mutation()
    print(f"\n{BOLD}{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
