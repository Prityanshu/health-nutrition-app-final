#!/usr/bin/env python3
"""
Safety and relevance audit for generated workout plans.

Two questions, asked across a matrix of real situations:

  SAFETY     does the plan contain anything the stated injury rules out?
             This is checked against the same contraindication data the app
             uses, so a pass here means genuinely nothing excluded got through.

  RELEVANCE  when a sport is given, does the plan actually train for it, or
             does it fall back to a generic gym split?

Offline mode audits the filter against saved sample plans and costs nothing.
Live mode generates real plans, which is slow and spends AI quota, so it is
opt-in and the matrix can be narrowed.

    python scripts/test_workouts.py                      # filter logic only
    python scripts/test_workouts.py --live               # generate everything
    python scripts/test_workouts.py --live --case hamstring_footballer
    python scripts/test_workouts.py --live --show        # print each plan
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GREEN, RED, YELLOW, CYAN, DIM, BOLD, RESET = (
    "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[2m", "\033[1m", "\033[0m"
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
        for line in (detail or "").splitlines():
            print(f"        {DIM}{line}{RESET}")


# Each case is a real situation somebody could be in, not a synthetic input.
CASES = [
    {
        "name": "hamstring_footballer",
        "why": "the case that started this - sport plus a serious injury",
        "request": {
            "activity_level": "intermediate", "fitness_goal": "endurance",
            "time_per_day": 60, "equipment": "gym",
            "constraints": ["upper hamstring strain, left leg (severity 6/10)"],
            "sport": "football",
        },
        # Words that survive the exclusions. Asking for "sprint" or "agility"
        # here would mark the plan down for correctly removing them - the
        # assertion has to test sport AWARENESS, not sport intensity.
        "expect_sport": ["football", "match", "pitch", "play", "season", "training day"],
        "min_sport_hits": 1,
    },
    {
        "name": "knee_runner",
        "why": "an injury that rules out the sport's main activity",
        "request": {
            "activity_level": "intermediate", "fitness_goal": "endurance",
            "time_per_day": 45, "equipment": "home",
            "constraints": ["runner's knee, right side (severity 5/10)"],
            "sport": "running",
        },
        "expect_sport": ["running", "cycling", "swimming", "cross-train", "aerobic", "run"],
        "min_sport_hits": 2,
    },
    {
        "name": "shoulder_cricketer",
        "why": "an overhead sport with an overhead injury",
        "request": {
            "activity_level": "advanced", "fitness_goal": "muscle_gain",
            "time_per_day": 60, "equipment": "gym",
            "constraints": ["rotator cuff injury, bowling arm (severity 4/10)"],
            "sport": "cricket",
        },
        "expect_sport": ["cricket", "bowl", "bat", "rotation", "throw", "field"],
        "min_sport_hits": 1,
    },
    {
        "name": "lower_back_beginner",
        "why": "the most common injury, with the least experienced user",
        "request": {
            "activity_level": "beginner", "fitness_goal": "weight_loss",
            "time_per_day": 30, "equipment": "none",
            "constraints": ["lower back pain (severity 5/10)"],
        },
        "expect_sport": [],
    },
    {
        "name": "asthma_swimmer",
        "why": "a condition rather than an injury - no exercise exclusions, but real limits",
        "request": {
            "activity_level": "beginner", "fitness_goal": "general_fitness",
            "time_per_day": 45, "equipment": "none",
            "constraints": ["asthma - gets breathless with sustained high intensity"],
            "sport": "swimming",
        },
        "expect_sport": ["swim", "pool", "stroke", "breath"],
        "min_sport_hits": 2,
    },
    {
        "name": "multiple_injuries",
        "why": "two injuries at once, which is where exclusion lists usually break down",
        "request": {
            "activity_level": "intermediate", "fitness_goal": "general_fitness",
            "time_per_day": 45, "equipment": "gym",
            "constraints": [
                "hamstring strain (severity 5/10)",
                "left shoulder impingement (severity 4/10)",
            ],
        },
        "expect_sport": [],
    },
    {
        "name": "shoulder_footballer",
        "why": "upper-limb injury in a running sport - the legs must stay in the plan",
        "request": {
            "activity_level": "intermediate", "fitness_goal": "endurance",
            "time_per_day": 60, "equipment": "gym",
            "constraints": ["right shoulder impingement (severity 6/10)"],
            "sport": "football",
        },
        "expect_sport": ["football", "match", "sprint", "agility", "pitch", "run"],
        "min_sport_hits": 2,
    },
    {
        "name": "healthy_footballer",
        "why": "control - no injury, so the sport should drive everything",
        "request": {
            "activity_level": "advanced", "fitness_goal": "general_fitness",
            "time_per_day": 60, "equipment": "gym",
            "constraints": [], "sport": "football",
            "preferences": "matches on Sundays, no gym access at weekends",
        },
        # No injury here, so the sport-specific qualities SHOULD appear.
        "expect_sport": ["football", "match", "sprint", "agility", "sunday"],
        "min_sport_hits": 2,
    },
]


# --------------------------------------------------------------------------
# offline: does the filter work?
# --------------------------------------------------------------------------

SAMPLES = {
    "hamstring": (
        ["upper hamstring strain (severity 6/10)"],
        """Day 1: Upper Body
* Warm-up: 5-minute jog on the treadmill
* Chest-supported row: 3 sets of 10
Day 2: Lower Body (Hamstring Friendly)
* Romanian deadlifts: 3 sets of 8
* Hanging leg raises: 3 sets of 10
* Seated calf raise: 3 sets of 12
Day 3: Active Recovery
* 20 minutes light jogging
Note: we used chest-supported rows instead of bent-over rows.""",
        # These must be caught.
        ["jog", "Romanian deadlifts", "hanging leg raises", "jogging"],
        # This line explains an avoidance and must NOT be caught.
        ["instead of bent-over rows"],
    ),
    "knee": (
        ["knee pain (severity 5/10)"],
        """* Deep squats: 4 sets of 8
* Box squats to a comfortable depth: 3 sets of 10
* Cycling in place of running: 20 minutes
* Jumping lunges: 3 sets of 12""",
        ["deep squats", "lunges"],
        ["in place of running"],
    ),
}


def offline_severity():
    """Exclusions must scale with how bad the injury is."""
    from app.services.contraindications import (
        CONTRAINDICATIONS, audit_plan, graded_exclusions, stage_for,
    )

    print(f"\n{BOLD}Severity grading{RESET}")

    check("8/10 is flagged as needing assessment, not a plan",
          stage_for(9)["prescribe"] is False,
          "Above ~7/10 a modified plan dresses up an unsafe answer as a careful one.")
    check("1/10 allows normal training", stage_for(1)["excludes"] == ())

    counts = [len(graded_exclusions(CONTRAINDICATIONS["hamstring"], s)) for s in (7, 5, 3, 1)]
    check("restrictions ease as it heals",
          counts == sorted(counts, reverse=True) and counts[0] > counts[-1],
          f"Exclusion counts at 7/5/3/1 were {counts} - should decrease.")

    PLAN = "* Nordic curls: 3 sets\n* Romanian deadlifts: 3x8\n* Isometric wall sit: 3x30s"
    early = audit_plan(PLAN, ["hamstring strain (severity 6/10)"])
    late = audit_plan(PLAN, ["hamstring strain (severity 2/10)"])
    nordic_line = "* Nordic curls: 3 sets"
    blocked_early = any(f["line"] == nordic_line for f in early)
    blocked_late = any(f["line"] == nordic_line for f in late)
    check("nordic curls blocked early, allowed late",
          blocked_early and not blocked_late,
          f"early={blocked_early} late={blocked_late}")


def offline_coverage():
    """Conditions the app detects must actually have exclusions."""
    from app.services.contraindications import CONTRAINDICATIONS, audit_plan

    print(f"\n{BOLD}Condition coverage{RESET}")

    cases = [
        ("sciatica (severity 5/10)", "* Deadlifts: 3x5\n* Walking: 20 min", "deadlifts"),
        ("shin splints (severity 5/10)", "* Running: 30 min\n* Cycling: 20 min", "running"),
        ("tennis elbow (severity 4/10)", "* Barbell curls: 3x10", "barbell curls"),
        ("plantar fasciitis (severity 5/10)", "* Jump rope: 10 min", "jump"),
        ("IT band syndrome (severity 5/10)", "* Lunges: 3x10", "lunges"),
        ("asthma (severity 5/10)", "* HIIT intervals: 20 min", "hiit"),
        ("hernia (severity 5/10)", "* Heavy deadlifts: 5x3", "deadlifts"),
    ]
    for constraint, plan, expected in cases:
        # Assert on BEHAVIOUR - was the offending line flagged - rather than on
        # the wording of the finding. The engine reports movement patterns
        # ("hip hinge") not exercise names ("deadlifts"), and a test that
        # checks the wording breaks every time the explanation improves.
        offending = plan.splitlines()[0]
        flagged = [f for f in audit_plan(plan, [constraint])
                   if f["line"].strip() == offending.strip()]
        name = constraint.split(" (")[0]
        check(f"{name}: flags {expected!r}", bool(flagged),
              f"{offending!r} was allowed. "
              f"Whole-plan findings: {[f['movement'] for f in audit_plan(plan, [constraint])]}")


def offline_edges():
    """The awkward cases."""
    from app.services.contraindications import audit_plan

    print(f"\n{BOLD}Edge cases{RESET}")

    # An unrecognised condition must still get the intensity sweep, or it
    # produces a completely unguarded plan.
    unknown = audit_plan("* Explosive sled sprints: 6 sets\n* Seated row: 3x10",
                         ["costochondritis (severity 6/10)"])
    check("unknown condition still guarded by intensity language", bool(unknown),
          "No exclusion data and no intensity check means no protection at all.")

    # Two injuries at once - both sets must apply.
    both = audit_plan("* Overhead press: 3x8\n* Romanian deadlifts: 3x8\n* Seated row: 3x10",
                      ["hamstring strain (severity 5/10)", "shoulder impingement (severity 5/10)"])
    lines = {f["line"] for f in both}
    check("multiple injuries apply together",
          "* Overhead press: 3x8" in lines and "* Romanian deadlifts: 3x8" in lines,
          f"Caught only: {lines}")
    check("the unaffected movement survives both injuries",
          "* Seated row: 3x10" not in lines,
          "A supported row is safe for a hamstring and a shoulder alike.")

    # No severity stated - must not default to the most permissive reading.
    vague = audit_plan("* Sprints: 6x20m", ["hamstring strain"])
    check("missing severity defaults to cautious", bool(vague),
          "With no severity given, assuming 'nearly healed' would be the unsafe guess.")

    # An empty plan should not explode.
    check("empty plan handled", audit_plan("", ["hamstring strain"]) == [])
    check("no constraints handled", audit_plan("* Sprints: 6x20m", []) == [])

    # Hinges must be excluded by SHAPE, not by implement. Every one of these
    # loads the hamstring identically; naming only the barbell version let
    # "Bent Over Dumbbell Rows" into a plan for a 6/10 proximal strain.
    hamstring = ["upper hamstring strain (severity 6/10)"]
    for line in ["- Bent Over Dumbbell Rows: 3x10", "- Pendlay rows: 3x5",
                 "- T-Bar Row: 3x10", "- Back extensions: 3x12",
                 "- Glute ham raise: 3x8"]:
        check(f"hinge caught: {line.split(':')[0].strip('- ')}",
              bool(audit_plan(line, hamstring)),
              "A loaded hip hinge under another name.")

    # Supported rows train the same muscles without the hinge, and are the
    # substitution the app recommends - flagging them would leave nothing.
    for line in ["- Chest-supported row: 3x10", "- Seated cable row: 3x12",
                 "- Machine row: 3x10"]:
        check(f"supported row allowed: {line.split(':')[0].strip('- ')}",
              not audit_plan(line, hamstring),
              "This is the recommended replacement, not a violation.")

    # An upper-limb injury must not strip lower-body conditioning. Treating
    # all intensity the same meant a shoulder problem removed sprints, box
    # jumps, HIIT on a bike and agility work - none of which involve the
    # shoulder - and left the plan gutted for no safety gain.
    CONDITIONING = ("* Sprint intervals: 8 x 100m\n* Box jumps: 3 sets of 8\n"
                    "* HIIT bike intervals: 20 min\n* Agility ladder: 10 min")
    check("shoulder injury keeps lower-body conditioning",
          not audit_plan(CONDITIONING, ["right shoulder impingement (severity 6/10)"]),
          "Running and jumping are unaffected by a shoulder injury.")
    check("hamstring injury still removes it",
          len(audit_plan(CONDITIONING, ["hamstring strain (severity 6/10)"])) >= 3,
          "These are exactly what a healing hamstring must not do.")

    # Maximal effort strains the whole body, so it is questioned for any injury.
    check("max effort flagged even for an upper-limb injury",
          bool(audit_plan("* Max effort deadlift singles: 5x1",
                          ["right shoulder impingement (severity 6/10)"])),
          "Bracing under a maximal load is a whole-body event.")

    # Sided injuries leave a working limb.
    from app.services.injury_service import _side_of
    check("reads the injured side", _side_of("upper hamstring strain, left leg") == "left")
    check("no side stated is not guessed", _side_of("hamstring strain") is None)
    # This previously asserted None, which encoded a bug: "both knees" is
    # bilateral, and returning None silently discarded the laterality. The
    # assertion was wrong, not the behaviour.
    check("both sides resolves to bilateral", _side_of("pain in both knees") == "bilateral")
    check("the word 'bilateral' is detected", _side_of("bilateral shoulder pain") == "bilateral")


def offline():
    from app.services.contraindications import audit_plan, strip_excluded

    print(f"\n{BOLD}Exclusion filter{RESET}")
    for name, (constraints, plan, must_catch, must_not_catch) in SAMPLES.items():
        findings = audit_plan(plan, constraints)
        caught = " ".join(f["movement"].lower() + " " + f["line"].lower() for f in findings)

        for movement in must_catch:
            check(f"{name}: catches {movement!r}",
                  movement.lower() in caught,
                  f"Not flagged. Found instead: {[f['movement'] for f in findings]}")

        for phrase in must_not_catch:
            offending = [f for f in findings if phrase.lower() in f["line"].lower()]
            check(f"{name}: does not flag the avoidance note",
                  not offending,
                  f"Flagged a line that was explaining an avoidance: {offending}")

        cleaned, _ = strip_excluded(plan, constraints)
        check(f"{name}: stripped plan is clean on re-audit",
              not audit_plan(cleaned, constraints),
              "Filtering once should leave nothing behind.")


# --------------------------------------------------------------------------
# live: generate real plans
# --------------------------------------------------------------------------

def live(base, token, only, show):
    import requests
    from app.services.contraindications import audit_plan

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print(f"\n{BOLD}Generated plans{RESET} {DIM}(each costs AI quota and takes 20-40s){RESET}")

    for case in CASES:
        if only and case["name"] != only:
            continue

        print(f"\n{BOLD}{case['name']}{RESET}  {DIM}{case['why']}{RESET}")
        t0 = time.time()
        try:
            r = requests.post(f"{base}/fitness/generate-workout-plan",
                              headers=headers, json=case["request"], timeout=180)
        except Exception as e:
            check(f"{case['name']}: request", False, f"{type(e).__name__}: {e}")
            continue

        elapsed = time.time() - t0
        if not r.ok:
            check(f"{case['name']}: HTTP 201", False, f"HTTP {r.status_code}: {r.text[:200]}")
            continue

        body = r.json()
        data = body.get("data", body)
        plan = data.get("workout_plan", "")
        removed = data.get("removed_for_safety", [])

        print(f"  {DIM}{elapsed:.0f}s · {len(plan):,} chars{RESET}")
        if removed:
            print(f"  {YELLOW}filter stripped: {', '.join(removed)}{RESET}"
                  f"  {DIM}(the model broke the rules; the filter caught it){RESET}")

        # SAFETY - the plan the user actually receives must be clean.
        leaks = audit_plan(plan, case["request"]["constraints"])
        check(f"{case['name']}: no excluded movements reach the user",
              not leaks,
              "\n".join(f"{f['movement']!r} in: {f['line'][:70]}" for f in leaks[:5]))

        # RELEVANCE - a named sport should be visible in the plan.
        sport = case["request"].get("sport")
        if sport and case["expect_sport"]:
            lowered = plan.lower()
            hits = [w for w in case["expect_sport"] if w in lowered]
            # Injured cases need a lower bar: the sport's hard qualities are
            # exactly what gets stripped, so demanding them would score a safe
            # plan as a failure.
            needed = case.get("min_sport_hits", 2)
            check(f"{case['name']}: plan reflects {sport}",
                  len(hits) >= needed,
                  f"Matched {hits or 'nothing'}, needed {needed} of "
                  f"{case['expect_sport']}. Likely fell back to a generic split.")

        # A plan that says nothing about the injury has not explained itself.
        if case["request"]["constraints"]:
            mentioned = any(
                word in plan.lower()
                for word in ("injur", "avoid", "instead", "removed", "modif", "pain-free")
            )
            check(f"{case['name']}: acknowledges the limitation", mentioned,
                  "The plan never mentions working around the injury.")

        if show:
            print(f"\n{DIM}{'-' * 70}{RESET}")
            for line in plan.splitlines()[:45]:
                print(f"  {DIM}{line}{RESET}")
            print(f"{DIM}{'-' * 70}{RESET}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--base", default=None)
    ap.add_argument("--user", default=os.getenv("TEST_USER"))
    ap.add_argument("--password", default=os.getenv("TEST_PASSWORD"))
    ap.add_argument("--case", help="run one case by name")
    ap.add_argument("--show", action="store_true", help="print each generated plan")
    args = ap.parse_args()

    print(f"\n{BOLD}Workout safety audit{RESET}")
    offline()
    offline_severity()
    offline_coverage()
    offline_edges()

    if args.live:
        if not (args.user and args.password):
            print(f"\n{YELLOW}--live needs TEST_USER and TEST_PASSWORD.{RESET}")
        else:
            from test_chatbot_scenarios import login, resolve_base
            base = resolve_base(args.base)
            if not base:
                print(f"{RED}No backend found.{RESET}")
                return 1
            token = login(base, args.user, args.password)
            if token:
                live(base, token, args.case, args.show)
    else:
        names = ", ".join(c["name"] for c in CASES)
        print(f"\n{DIM}Add --live to generate real plans for: {names}{RESET}")

    print(f"\n{BOLD}{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
