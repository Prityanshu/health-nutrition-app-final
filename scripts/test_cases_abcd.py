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
    # Duration is advisory, not a gating issue - see the `advisory` field's
    # own comment. It is reported here, not in `issues`, specifically so a
    # measurement it gets wrong can never force a wasted regeneration.
    joined = " ".join(q.advisory)
    check("under-programming detected against 120 minutes (advisory, not gating)",
          "under-programmed" in joined, f"{q.estimated_minutes} min, advisory={q.advisory}")
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

    # And a conditional line is REMOVED rather than trusted.
    #
    # It used to be swapped for "something known", but nothing is known about
    # it: an unclassifiable line has no movement purpose to preserve, so the
    # substitute was drawn from a generic conditioning list. That is how
    # "Main lifts - 55 min" came back as "Elliptical, steady pace: 55 min".
    # Removing it fails closed without inventing a prescription.
    from app.services import plan_repair
    r = plan_repair.repair(invented + "\n* Bench press: 4x6",
                           ["hamstring strain (severity 6/10)"])
    check("conditional line does not survive an active injury",
          invented.strip("* ").strip() not in r.plan, r.plan)
    check("conditional line is removed, not swapped for a guess",
          not any(x.original.strip() == invented.strip() for x in r.replacements),
          f"replacements={[(x.original, x.replacement) for x in r.replacements]}")
    check("...and the removal is recorded",
          any(invented.strip("* ").strip() in x for x in r.removed), r.removed)
    check("...while known-safe work is kept", "Bench press" in r.plan, r.plan)


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


def duration_and_parsing():
    """
    Regression suite for the duration/exercise-count estimator.

    Added after live FitMentor testing surfaced real plans - well-formed,
    realistic 7-day plans, not malformed ones - being judged as needing
    hundreds of minutes for a 20-90 minute request. Traced to concrete,
    fixable bugs in exercise_lines()/estimate_minutes()/split_days(), not to
    the model producing bad content. Each case below is a minimal, offline,
    hand-built fixture reproducing one of those bugs - no LLM call involved,
    matching what was actually seen rather than a synthetic worst case.
    """
    from app.services import plan_quality as pq
    print(f"\n{BOLD}Duration/exercise-count estimation{RESET}")

    # A real 7-day beginner plan (this exact text was generated and reviewed
    # earlier in the session that added this test) - 5 exercises/day, proper
    # warm-up/main/cool-down structure, requested at 30 min/day. This must
    # NOT be flagged as needing hundreds of minutes, and must not be
    # gate-blocked (advisory only) even if the estimate is imperfect.
    real_plan = """**Your 7-Day Beginner General-Fitness Plan**
*30 minutes per day - no equipment needed*

### Day 1 - Full-Body Strength
**Warm-up (5 min)**
- March in place - 1 min
- Arm circles (forward & backward) - 30 s each

**Main (20 min)**
- **Squat to Chair** - **12 reps x 2 sets**
- **Incline Push-Ups** - **10 reps x 2 sets**
- **Glute Bridge** - **15 reps x 2 sets**
- **Bird-Dog** - **8 reps per side x 2 sets**
- **Wall Sit** - **30 s x 2 sets**

**Cool-down (5 min)**
- Standing hamstring stretch - 30 s each leg
- Child's pose - 1 min

**Progression tip:** Add 2 reps to each movement every week.

### Day 2 - Cardio + Core
**Warm-up (5 min)**
- Light jogging in place - 2 min

**Main (20 min) - Perform the circuit 3 times, 30 s work / 30 s rest**
- **High Knees**
- **Standing Bicycle Crunches**
- **Plank (knees if needed)** - **30 s**

**Cool-down (5 min)**
- Seated forward fold - 1 min

**Progression tip:** Increase work interval to 35 s after week 2.

### Day 7 - Rest & Light Mobility
- Take a leisurely walk or gentle stretching for 20-30 min.

**Progression tip:** Use this day to note any sore spots.

### General Nutrition Tips (optional)
- Aim for balanced meals with protein, complex carbs, and healthy fats.
- Stay hydrated - roughly 2 L water daily.
- For recovery, include a source of vitamin C and magnesium.

### Safety & Warnings
- Keep movements controlled; avoid bouncing on squats or push-ups.
- If any exercise causes sharp pain, stop immediately.
- Warm-up and cool-down are mandatory for injury prevention."""

    q = pq.evaluate(real_plan, requested_minutes=30, goal="general_fitness",
                    equipment="none", level="beginner")
    check("real 30-min plan is not gate-blocked by duration/count",
          q.adequate or not any(("will not fit" in i or "under-programmed" in i
                                  or "exercises in one day" in i) for i in q.issues),
          f"issues={q.issues}")
    check("estimate is in a plausible range, not hundreds of minutes",
          q.estimated_minutes < 90, f"estimated {q.estimated_minutes} min")
    check("nutrition-tip bullets are not counted as exercises",
          not any("balanced meals" in l or "hydrated" in l for l in pq.exercise_lines(real_plan)))
    check("safety-warning bullets are not counted as exercises",
          not any("sharp pain" in l or "mandatory" in l for l in pq.exercise_lines(real_plan)))

    # Distance-based intervals must not be read as sets x reps.
    sprint_plan = "* Sprint intervals: 8x100m\n* Cool-down walk: 5 min"
    lines = pq.exercise_lines(sprint_plan)
    mins = pq.estimate_minutes(lines)
    check("8x100m is not read as 800 reps", mins < 30, f"estimated {mins} min for: {lines}")

    # Weekday headings are a real day-heading style and must split, exactly
    # like "Day N". They used to be unrecognised, which silently disabled
    # every per-week check for that whole output format - see
    # weekly_resistance_volume() below for the gate it was bypassing.
    monday_style = "### Monday\n* Push-ups: 3x10\n### Tuesday\n* Squats: 3x10"
    days = pq.split_days(monday_style)
    check("weekday headings split into days", len(days) == 2, f"{days!r}")
    check("all seven weekday names are recognised",
          len(pq.split_days("\n".join(
              f"### {d}\n* Push-ups: 3x10" for d in
              ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
               "Saturday", "Sunday")))) == 7)
    check("'Day N' headings still split", len(pq.split_days(
        "### Day 1\n* Push-ups: 3x10\n### Day 2\n* Squats: 3x10")) == 2)

    # Not every line mentioning a weekday is a day boundary.
    check("'Sun Salutations' does not split the plan on 'Sun'",
          len(pq.split_days("### Sun Salutations\n* Flow x5\n"
                            "### Sun Salutations B\n* Flow x5")) == 1)
    check("a bulleted '- Monday: rest' is a list item, not a heading",
          len(pq.split_days("- Monday: rest\n- Tuesday: rest")) == 1)
    check("a weekday mid-sentence does not split the plan",
          len(pq.split_days("Train on Monday and Tuesday if you can.")) == 1)


def weekly_resistance_volume():
    """
    The weekly resistance-volume gate must apply to every multi-day format.

    It is deliberately skipped for a SINGLE session, because a weekly floor
    cannot judge one day - five resistance exercises is both a complete
    strength session and a gutted week, and nothing here can tell which was
    asked for. That exemption is only safe if "is this multi-day?" is
    answered correctly for every heading style the generator produces.
    """
    from app.services import plan_quality as pq
    print(f"\n{BOLD}Weekly resistance volume across day-heading styles{RESET}")

    single = ("* Back squat: 4 sets of 6\n* Romanian deadlift: 3 sets of 8\n"
              "* Bench press: 4 sets of 6\n* Chest-supported row: 4 sets of 10\n"
              "* Plank: 3x45s")
    weekday = ("### Monday\n- Bench press: 3x8\n- Row: 3x8\n\n"
               "### Tuesday\n- Squat: 3x8\n- Deadlift: 3x8")
    day_n = weekday.replace("Monday", "Day 1").replace("Tuesday", "Day 2")

    q = pq.evaluate(single, goal="muscle_gain", level="advanced", equipment="gym")
    check("a single session is not judged against a WEEKLY floor",
          q.resistance_exercises is None, q.resistance_exercises)
    check("...and is not gated by a resistance issue",
          not any("resistance" in i for i in q.issues), q.issues)

    for label, plan in (("'Day N'", day_n), ("weekday", weekday)):
        q = pq.evaluate(plan, goal="muscle_gain", level="advanced", equipment="gym")
        check(f"an under-programmed {label} week IS counted",
              q.resistance_exercises == 4, q.resistance_exercises)
        check(f"...and IS gated by the resistance issue ({label})",
              any("resistance" in i for i in q.issues), q.issues)

    # Both formats must reach the identical verdict - the bypass was that
    # they did not.
    a = pq.evaluate(day_n, goal="muscle_gain", level="advanced", equipment="gym")
    b = pq.evaluate(weekday, goal="muscle_gain", level="advanced", equipment="gym")
    check("both day-heading styles produce the same resistance verdict",
          a.resistance_exercises == b.resistance_exercises
          and a.adequate == b.adequate,
          f"day_n={a.resistance_exercises}/{a.adequate} "
          f"weekday={b.resistance_exercises}/{b.adequate}")

    # A properly programmed weekday week is not flagged.
    good = "\n".join(
        f"### {d}\n- Back squat: 4x6\n- Bench press: 4x8\n- Seated cable row: 4x10"
        for d in ("Monday", "Tuesday", "Wednesday", "Thursday"))
    q = pq.evaluate(good, goal="muscle_gain", level="advanced", equipment="gym")
    check("a well-programmed weekday week is not flagged",
          not any("resistance" in i for i in q.issues),
          (q.resistance_exercises, q.issues))

    # Progression section text must never be counted as a prescribed exercise.
    prog_plan = "* Bench press: 3x8\n### Progression\n* Add 2.5kg when all sets hit 8 reps."
    lines = pq.exercise_lines(prog_plan)
    check("a bulleted progression-section line is not counted as an exercise",
          len(lines) == 1, f"{lines!r}")

    # Warm-up/cool-down are detected, and duration scales sanely 20 -> 90 min.
    for minutes in (20, 30, 60, 90):
        plan = (
            "* Warm-up: 5 min easy cardio\n"
            "* Squat: 3 sets of 10\n* Push-up: 3 sets of 10\n* Row: 3 sets of 10\n"
            "* Cool-down: 5 min stretch"
        )
        q = pq.evaluate(plan, requested_minutes=minutes, equipment="none")
        check(f"{minutes}-min request: short realistic plan is not gate-blocked",
              q.adequate, f"issues={q.issues}")
    check("warm-up detected", q.has_warm_up)
    check("cool-down detected", q.has_cool_down)


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
        unknown_handling(); healthy_controls(); duration_and_parsing()
        weekly_resistance_volume(); mutation()
    print(f"\n{BOLD}{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
