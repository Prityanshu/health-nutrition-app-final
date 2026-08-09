#!/usr/bin/env python3
"""
Regression tests for the four real-world failures (Cases A-D), generalised.

These are not name checks. Each case identifies a CLASS of failure, and the
tests probe that class across body regions rather than only the exercises that
happened to appear in the original plan.

    python scripts/test_cases_abcd.py
    python scripts/test_cases_abcd.py --mutation
"""

import argparse
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
        for line in str(detail).splitlines()[:5]:
            print(f"        {DIM}{line}{RESET}")


def profiles(constraints):
    from app.services import injury_taxonomy as tax
    return [p for p in (tax.parse(c) for c in constraints) if p]


def case_a():
    """
    CASE A - "seated" and "low impact" were treated as "joint safe".

    The class of failure: the ontology had no way to express weight bearing,
    stance or ankle mechanics, so anything without ground impact looked safe
    for an ankle. Generalised here across every load-bearing region.
    """
    from app.services.contraindications import audit_against_profiles
    print(f"\n{BOLD}CASE A - ankle: seated/low-impact is not joint-safe{RESET}")

    ankle = profiles(["right ankle sprain (severity 6/10)"])
    must_flag = [
        ("* Seated calf raise: 3x12", "direct plantarflexion, no impact at all"),
        ("* Stationary bike: 20 min", "continuous ankle motion under load"),
        ("* Seated leg press: 3x10", "foot force against a platform"),
        ("* Deadlift: 3x5", "standing under external load"),
        ("* Romanian deadlift: 3x8", "standing under external load"),
        ("* Standing Pallof press: 3x12", "standing, ankle stabilising"),
        ("* Elliptical: 25 min", "same ankle cycle as a bike"),
        ("* Rowing machine: 20 min", "foot plate drive"),
    ]
    for line, why in must_flag:
        check(f"flags {line.strip('* ').split(':')[0]}",
              bool(audit_against_profiles(line, ankle)), why)

    must_allow = [
        "* Swimming, easy pace: 20 min",
        "* Lat pulldown: 3x10",
        "* Bench press: 4x6",
        "* Seated cable row: 3x12",
        "* Glute bridge: 3x12",
        "* Upper-body ergometer: 15 min",
    ]
    for line in must_allow:
        check(f"allows {line.strip('* ').split(':')[0]}",
              not audit_against_profiles(line, ankle),
              "The ankle is not loaded here - over-restricting makes the plan useless.")

    # The class generalises: same logic for Achilles, plantar fascia, bone stress.
    for constraint, probe in [
        ("achilles tendinopathy (severity 6/10)", "* Stationary bike: 20 min"),
        ("plantar fasciitis (severity 6/10)", "* Standing calf raise: 3x15"),
        ("shin splints (severity 6/10)", "* Elliptical: 20 min"),
    ]:
        check(f"{constraint.split(' (')[0]} also catches {probe.strip('* ').split(':')[0]}",
              bool(audit_against_profiles(probe, profiles([constraint]))))


def case_b():
    """CASE B - an exercise must clear EVERY active injury, not the first."""
    from app.services.contraindications import audit_against_profiles
    print(f"\n{BOLD}CASE B - left ankle + upper hamstring{RESET}")

    both = profiles(["left ankle sprain (severity 5/10)",
                     "upper hamstring strain (severity 5/10)"])
    only_ankle = profiles(["left ankle sprain (severity 5/10)"])
    only_ham = profiles(["upper hamstring strain (severity 5/10)"])

    # Romanian deadlift is unsafe for BOTH, for different reasons.
    check("RDL flagged by the hamstring alone",
          bool(audit_against_profiles("* Romanian deadlift: 3x8", only_ham)))
    check("RDL flagged by the ankle alone (loaded stance)",
          bool(audit_against_profiles("* Romanian deadlift: 3x8", only_ankle)))
    check("RDL flagged with both present",
          bool(audit_against_profiles("* Romanian deadlift: 3x8", both)))

    # The union must be at least as strict as either injury alone.
    plan = "\n".join([
        "* Stationary bike: 20 min", "* Glute bridges: 3x12",
        "* Seated calf raises: 3x12", "* Seated leg press: 3x10",
        "* Romanian deadlift: 3x8", "* Single-arm dumbbell row: 3x10",
        "* Hanging knee raises: 3x12", "* Seated cable row: 3x12",
    ])
    a = {f["line"] for f in audit_against_profiles(plan, only_ankle)}
    h = {f["line"] for f in audit_against_profiles(plan, only_ham)}
    u = {f["line"] for f in audit_against_profiles(plan, both)}
    check("combined restrictions are a superset of each injury alone",
          a <= u and h <= u, f"ankle-only {a - u}, hamstring-only {h - u}")

    # And an exercise safe for one must not sneak through on that basis.
    check("bike is caught by the ankle even though the hamstring allows it",
          "* Stationary bike: 20 min" in u)


def case_c():
    """CASE C - names must never be the mechanism. Movement class must be."""
    from app.services import movement_ontology as mo
    print(f"\n{BOLD}CASE C - phrasing must not defeat classification{RESET}")

    families = {
        "high_speed": ["sprint", "sprints", "sprinting", "SPRINT", "Max Sprint",
                       "Maximum Velocity Run", "max velocity", "high-speed running",
                       "short burst run", "explosive run", "acceleration run",
                       "flying sprint", "100m sprint", "hill sprint", "sled sprint"],
        "hip_hinge": ["bent-over row", "bent over row", "bent row", "DB bent row",
                      "dumbbell bent row", "Meadows row", "Pendlay row", "T-bar row",
                      "barbell row", "Romanian deadlift", "RDL", "stiff leg deadlift",
                      "good morning", "Jefferson curl"],
        "cutting": ["COD drill", "change of direction", "lateral cut", "cutting drill",
                    "pro agility shuttle", "5-10-5 shuttle", "shuttle run"],
        "jumping": ["box jump", "box jumps", "jumping onto a box", "plyometric box jump",
                    "depth jump", "broad jump", "tuck jump", "skater jump",
                    "lateral bound", "bounding"],
    }
    for pattern, names in families.items():
        misses = [n for n in names if pattern not in mo.classify(n).patterns]
        check(f"{pattern}: all {len(names)} phrasings recognised", not misses, f"{misses}")

    # The misleading-name class: a word that means the opposite of the movement.
    for name, must_have, must_not in [
        ("Jefferson curl", "spinal_flexion", "elbow_flexion"),
        ("Nordic curl", "knee_flexion", "elbow_flexion"),
        ("Nordic curls", "knee_flexion", "elbow_flexion"),
        ("Reverse Nordic", "knee_extension", "knee_flexion"),
        ("seated leg curl", "knee_flexion", "elbow_flexion"),
        ("biceps curl", "elbow_flexion", "knee_flexion"),
        ("incline dumbbell curl", "elbow_flexion", "knee_flexion"),
    ]:
        p = mo.classify(name).patterns
        check(f"{name!r}: {must_have} and NOT {must_not}",
              must_have in p and must_not not in p, f"got {sorted(p)}")


def case_d():
    """CASE D - a plan can be perfectly safe and still a poor workout."""
    from app.services import plan_quality as pq
    print(f"\n{BOLD}CASE D - quality failures on a healthy user{RESET}")

    plan = """### Monday
* Squats: 4 sets of 8
* Lunges: 3 sets of 12
* Calf raises: 3 sets of 15
* Agility ladder drills: 10 min
### Tuesday
* Push-ups: 3 sets of 15
* Incline DB press: 3 sets of 10
* Rows: 3 sets of 10
* Plank: 3x45s
### Progression
Increase weight if too easy. Reduce rest time."""

    q = pq.evaluate(plan, requested_minutes=120, goal="endurance",
                    equipment="gym", level="advanced", sport="football")
    joined = " ".join(q.issues)
    check("under-programming detected against 120 minutes",
          "under-programmed" in joined, f"{q.estimated_minutes} min, issues={q.issues}")
    check("field equipment flagged in a gym-only plan",
          any("field" in v for v in q.equipment_violations), f"{q.equipment_violations}")
    check("vague progression flagged",
          q.progression_measurable is False, f"measurable={q.progression_measurable}")
    check("score reflects the problems", q.score < 80, f"score={q.score}")

    # And the control: a well-built session must NOT be penalised.
    good = """* Warm-up: 8 min bike
* Back squat: 4 sets of 6 @ RPE 7
* Romanian deadlift: 3 sets of 8 @ RPE 7
* Bench press: 4 sets of 6
* Chest-supported row: 4 sets of 10
* Plank: 3x45s
* Cool-down: 5 min stretch
### Progression
Week 1: 3x8 @ RPE 7. Week 2: 3x9. Week 3: 3x10 @ RPE 8. Week 4: deload."""
    q = pq.evaluate(good, requested_minutes=60, goal="strength",
                    equipment="gym", level="intermediate")
    check("a good session scores well", q.score >= 90, f"score={q.score} {q.issues}")
    check("realistic duration is close to the request",
          abs(q.estimated_minutes - 60) <= 20, f"{q.estimated_minutes} min")

    # Equipment: a home user must not be handed a cable stack.
    q = pq.evaluate("* Cable row: 3x10\n* Barbell squat: 4x6\n* Push-up: 3x15",
                    requested_minutes=45, equipment="home")
    check("home plan flags gym equipment", bool(q.equipment_violations),
          f"{q.equipment_violations}")


def unknown_handling():
    """UNKNOWN must never behave as SAFE while an injury is active."""
    from app.services import contraindications as c
    print(f"\n{BOLD}UNKNOWN is not SAFE{RESET}")

    injured = profiles(["hamstring strain (severity 6/10)"])
    invented = "* Blurgle flurbing: 4 sets of 12"
    check("unclassifiable + injury -> conditional",
          c.classify_line(invented, injured)["verdict"] == c.VERDICT_CONDITIONAL)
    check("unclassifiable + healthy -> unknown, not conditional",
          c.classify_line(invented, [])["verdict"] == c.VERDICT_UNKNOWN)

    # Instructions are not exercises and must not be replaced.
    for line in ["* Rest 90 seconds between sets", "* Tempo: 3-1-1",
                 "* RPE 7-8", "* Progression: add 2.5kg weekly"]:
        check(f"instruction not treated as an exercise: {line.strip('* ')[:26]}",
              c.classify_line(line, injured)["verdict"] == c.VERDICT_UNKNOWN)

    # And a conditional line is replaced rather than trusted.
    from app.services import plan_repair
    r = plan_repair.repair(invented + "\n* Bench press: 4x6",
                           ["hamstring strain (severity 6/10)"])
    check("conditional line is swapped for something known",
          any(x.original.strip() == invented.strip() for x in r.replacements),
          f"replacements={[(x.original, x.replacement) for x in r.replacements]}")


def healthy_controls():
    """The safety work must not degrade healthy users."""
    from app.services.contraindications import audit_against_profiles
    from app.services import plan_repair
    print(f"\n{BOLD}Healthy users are untouched{RESET}")

    plan = "\n".join([
        "* Sprint intervals: 8x100m", "* Pro agility shuttle: 6 sets",
        "* Box jumps: 4x5", "* Back squat: 5x5", "* Romanian deadlift: 3x8",
        "* Bench press: 4x6", "* Overhead press: 3x8", "* Bent over row: 4x8",
    ])
    check("nothing flagged with no injuries", not audit_against_profiles(plan, []))
    r = plan_repair.repair(plan, [], requested_minutes=60, equipment="gym")
    check("plan returned byte-identical", r.plan == plan)
    check("no replacements or removals", not r.replacements and not r.removed)

    calls = {"n": 0}
    plan_repair.repair(plan, [], requested_minutes=60,
                       regenerate=lambda b: (calls.__setitem__("n", calls["n"] + 1), plan)[1])
    check("no LLM regeneration for a healthy user", calls["n"] == 0)


def mutation():
    """Sabotage the new patterns; the Case A tests must fail."""
    from app.services import injury_taxonomy as tax
    from app.services.contraindications import audit_against_profiles
    print(f"\n{BOLD}MUTATION - are the new patterns load-bearing?{RESET}")

    ankle = next(c for c in tax.CONDITIONS if c.key == "ankle")
    probes = {
        "loaded_stance": "* Deadlift: 3x5",
        "repetitive_ankle": "* Stationary bike: 20 min",
        "plantarflexion": "* Seated calf raise: 3x12",
    }
    for pattern, probe in probes.items():
        profs = profiles(["ankle sprain (severity 6/10)"])

        # Assert on the CLASH SET, not on a boolean. Several patterns can
        # legitimately catch the same movement - a deadlift is both a loaded
        # stance and weight bearing - so "is it still flagged?" cannot tell
        # whether this particular rule contributed. Two earlier versions of
        # this test failed for exactly that reason and were measuring the
        # wrong thing, not finding a bug.
        before = audit_against_profiles(probe, profs)
        contributed = any(pattern.replace("_", " ") in f["movement"] for f in before)
        check(f"{pattern!r} contributes to flagging "
              f"{probe.strip('* ').split(':')[0]}",
              contributed,
              f"clash was {[f['movement'] for f in before]}")

        saved = (ankle.primary, ankle.secondary, ankle.speed)
        for tier in ("primary", "secondary", "speed"):
            object.__setattr__(ankle, tier, getattr(ankle, tier) - {pattern})
        after = audit_against_profiles(probe, profs)
        still = any(pattern.replace("_", " ") in f["movement"] for f in after)
        for tier, value in zip(("primary", "secondary", "speed"), saved):
            object.__setattr__(ankle, tier, value)
        check(f"removing {pattern!r} removes it from the reason",
              not still,
              f"still cited after removal: {[f['movement'] for f in after]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutation", action="store_true", help="mutation tests only")
    args = ap.parse_args()

    print(f"\n{BOLD}CASES A-D REGRESSION SUITE{RESET}")
    if args.mutation:
        mutation()
    else:
        case_a(); case_b(); case_c(); case_d()
        unknown_handling(); healthy_controls(); mutation()
    print(f"\n{BOLD}{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
