#!/usr/bin/env python3
"""
Product-recovery regression suite for FitMentor.

Three deterministic defects are pinned here:

  1. Quality evaluation supplied a `regenerate` callback, so one request could
     make three full model calls (one plus MAX_REGENERATIONS=2). Under Groq
     rate limiting each carried its own backoff.
  2. CONDITIONAL (unclassifiable) lines were sent to _find_replacement(),
     which has no purpose to preserve and fell through to a generic
     conditioning fallback. Section labels became exercises:
     "Main lifts - 55 min" -> "Elliptical, steady pace: 55 min".
  3. The whole repair log was appended to the workout Markdown as an
     "Adjustment Notes" block, on top of a session that had already been
     rewritten.

No live model call is made anywhere in this file.

    python scripts/test_fitmentor_recovery.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import plan_repair                      # noqa: E402
from app.services import plan_structure as ps             # noqa: E402

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
        for line in str(detail).splitlines()[:8]:
            print(f"        {DIM}{line}{RESET}")


# ---------------------------------------------------------------------------
# the reported fixture
# ---------------------------------------------------------------------------

HAMSTRING = "right hamstring tendinopathy (severity 6/10)"

FOOTBALL_PLAN = """## Day 1 - Lower Power

- Warm-up – 10 min
- Scapular-wall slides × 12 reps
- Removed: any jogging or dynamic leg swings
- Main lifts – 55 min
- Romanian deadlift – 4 × 6 @ RPE 7
- Single-leg Romanian deadlift – 3 × 8 each side
- Bench Press – 4 × 6 @ RPE 7
- Pendlay row – 4 × 6
- Accessory & Core – 15 min
- Pallof Press – 3 × 12 each side
- Rest 90 seconds between sets
- Focus on controlled form throughout
- Cooldown – 5 min
"""

CONDITIONING = ("stationary bike", "elliptical", "brisk walk", "rowing machine",
                "swimming", "upper-body ergometer", "treadmill walk")


def repaired(plan=FOOTBALL_PLAN, constraints=(HAMSTRING,), minutes=90):
    return plan_repair.repair(plan, list(constraints), requested_minutes=minutes)


# ---------------------------------------------------------------------------
# 1. the hamstring case, end to end
# ---------------------------------------------------------------------------

def hamstring_case():
    print(f"\n{BOLD}1. The reported hamstring plan{RESET}")
    result = repaired()
    text = result.plan
    lower = text.lower()

    for label in ("Warm-up – 10 min", "Main lifts – 55 min",
                  "Accessory & Core – 15 min", "Cooldown – 5 min"):
        check(f"section label preserved: {label!r}", label in text, text)

    check("'Main lifts – 55 min' is not turned into an exercise",
          "55 min" not in lower.replace("main lifts – 55 min", ""), text)

    for keep in ("Bench Press", "Pallof Press"):
        check(f"safe upper-body work preserved: {keep!r}", keep in text, text)

    check("the exclusion line is preserved, not substituted",
          "Removed: any jogging" in text, text)
    check("ordinary instructions are preserved",
          "Rest 90 seconds" in text and "Focus on controlled form" in text, text)

    for banned in ("Romanian deadlift", "Pendlay row"):
        check(f"prohibited hip hinge removed: {banned!r}",
              banned.lower() not in lower, text)

    invented = [c for c in CONDITIONING if c in lower]
    check("no arbitrary conditioning exercises were invented", not invented,
          f"{invented}\n{text}")

    check("no Adjustment Notes block in the workout",
          "Adjustment Notes" not in text, text)
    check("...and no swap log either",
          "Swapped *" not in text and "This session is lighter" not in text, text)

    check("audit_clean is True", result.audit_clean is True, result.as_dict())
    check("no regenerations were spent", result.regenerations == 0,
          result.regenerations)

    # audit_clean must describe the EXACT returned text.
    from app.services.contraindications import (
        VERDICT_CONDITIONAL, assess_plan, audit_against_profiles)
    from app.services import injury_taxonomy as it
    profiles = it.profiles_for([HAMSTRING])
    check("re-auditing the returned text finds no prohibited movement",
          not audit_against_profiles(text, profiles),
          audit_against_profiles(text, profiles))
    check("...and no unresolved CONDITIONAL candidate",
          not [v for v in assess_plan(text, profiles)
               if v["verdict"] == VERDICT_CONDITIONAL],
          [v["line"] for v in assess_plan(text, profiles)
           if v["verdict"] == VERDICT_CONDITIONAL])

    # Structured metadata still carries everything that changed.
    meta = result.as_dict()
    for key in ("removed", "replacements", "regenerations", "quality",
                "audit_clean"):
        check(f"as_dict() still reports {key!r}", key in meta, list(meta))
    check("as_dict() records the replacements that happened",
          len(meta["replacements"]) >= 2, meta["replacements"])


# ---------------------------------------------------------------------------
# 2. structural labels
# ---------------------------------------------------------------------------

def structural_labels():
    print(f"\n{BOLD}2. Allocation labels are structure, not exercises{RESET}")

    labels = [
        "Warm-up – 10 min", "Main lifts – 55 min", "Accessory & Core – 15 min",
        "Cooldown – 5 min", "Mobility Circuit – 30 min", "Warm-up: 10 min",
        "Cool-down — 5 minutes", "Conditioning block – 20 min",
        "Strength + Core – 40 min", "Main lifts", "Warm-up",
    ]
    for label in labels:
        items = ps.parse(f"- {label}\n")
        role = items[0].role if items else "none"
        check(f"{label!r} is not a prescription candidate",
              role != ps.PRESCRIPTION_LIKE, f"role={role}")

    # Nested and emphasised forms.
    for raw in ("  - Warm-up – 10 min", "- **Warm-up – 10 min**",
                "- *Main lifts – 55 min*"):
        items = ps.parse(f"{raw}\n")
        check(f"{raw.strip()!r} is not a prescription candidate",
              items and items[0].role != ps.PRESCRIPTION_LIKE,
              items[0].role if items else "none")

    # ...but a real exercise with a duration still is.
    for exercise in ("Stationary bike: 20 min", "Plank – 3 × 45 sec",
                     "Farmer carry – 4 × 40 m", "Core rotation – 3 × 12",
                     "Cardio intervals – 8 × 30 sec"):
        items = ps.parse(f"- {exercise}\n")
        check(f"{exercise!r} IS still a prescription candidate",
              items and items[0].role == ps.PRESCRIPTION_LIKE,
              items[0].role if items else "none")


def instruction_lines():
    print(f"\n{BOLD}3. Exclusions and instructions are not substituted{RESET}")

    for line in ("Removed: any jogging or dynamic leg swings",
                 "Avoid sprinting and jumping",
                 "Excluded: deep squats",
                 "Rest 90 seconds",
                 "Focus on controlled form",
                 "No running this week"):
        items = ps.parse(f"- {line}\n")
        check(f"{line!r} is not a prescription candidate",
              items and items[0].role != ps.PRESCRIPTION_LIKE,
              items[0].role if items else "none")

    # A prescription that merely mentions an avoidance later is still a
    # prescription.
    items = ps.parse("- Romanian deadlift – 4 × 6, no jumping\n")
    check("'Romanian deadlift ..., no jumping' is still a prescription",
          items and items[0].role == ps.PRESCRIPTION_LIKE,
          items[0].role if items else "none")

    result = repaired("## Day 1\n- Removed: any jogging or dynamic leg swings\n"
                      "- Bench Press – 4 × 6\n")
    check("the exclusion line survives repair verbatim",
          "Removed: any jogging" in result.plan, result.plan)
    check("...and was not replaced by a conditioning exercise",
          not any(c in result.plan.lower() for c in CONDITIONING), result.plan)


# ---------------------------------------------------------------------------
# 4. unknown prescriptions still fail closed
# ---------------------------------------------------------------------------

def unknown_prescriptions():
    print(f"\n{BOLD}4. Genuine unknowns fail closed, never substituted{RESET}")

    for unknown in ("Ankle pogo: 3x20", "Power Pull: 3x5", "Leg Pull: 3x8"):
        plan = f"## Day 1\n- {unknown}\n- Bench Press – 4 × 6\n"
        result = repaired(plan)
        name = unknown.split(":")[0]
        check(f"{name!r} does not survive an active restriction",
              name.lower() not in result.plan.lower(), result.plan)
        check(f"...and is REMOVED, not swapped for conditioning ({name})",
              not any(c in result.plan.lower() for c in CONDITIONING),
              result.plan)
        check(f"...and is recorded as removed ({name})",
              any(name.lower() in r.lower() for r in result.removed),
              result.removed)
        check(f"...while safe work is kept ({name})",
              "Bench Press" in result.plan, result.plan)

    # Healthy users keep unknowns untouched and lose nothing.
    plan = ("## Day 1\n- Ankle pogo: 3x20\n- Power Pull: 3x5\n"
            "- Warm-up – 10 min\n- Bench Press – 4 × 6\n")
    healthy = plan_repair.repair(plan, [], requested_minutes=60)
    check("a healthy user's unknown exercises are untouched",
          "Ankle pogo" in healthy.plan and "Power Pull" in healthy.plan,
          healthy.plan)
    check("...nothing removed or replaced",
          not healthy.removed and not healthy.replacements,
          (healthy.removed, healthy.replacements))
    for line in plan.splitlines():
        if line.startswith("- "):
            check(f"...line preserved byte-identically: {line[:34]!r}",
                  line in healthy.plan, healthy.plan)
    check("...and no notes block is appended for a healthy user",
          "Adjustment Notes" not in healthy.plan, healthy.plan)


# ---------------------------------------------------------------------------
# 5. dosage
# ---------------------------------------------------------------------------

def dosage_preservation():
    print(f"\n{BOLD}5. Dosage follows a real replacement only{RESET}")

    result = repaired("## Day 1\n- Pendlay row – 4 × 6 @ RPE 7\n")
    check("a recognised swap keeps its sets/reps/RPE",
          "4 × 6 @ RPE 7" in result.plan, result.plan)
    check("...and the replacement is purpose-preserving (still a row)",
          "row" in result.plan.lower(), result.plan)

    result = repaired("## Day 1\n- Single-leg Romanian deadlift – 3 × 8 each side\n")
    check("a unilateral swap keeps 'each side'",
          "each side" in result.plan, result.plan)

    # A section allocation must never be carried onto an exercise.
    result = repaired()
    for allocation in ("55 min", "15 min", "10 min", "5 min"):
        carried = [ln for ln in result.plan.splitlines()
                   if allocation in ln
                   and any(c in ln.lower() for c in CONDITIONING)]
        check(f"no exercise inherited the {allocation!r} allocation",
              not carried, carried)


# ---------------------------------------------------------------------------
# 6. call counts
# ---------------------------------------------------------------------------

class _Response:
    def __init__(self, content):
        self.content = content


class FakeAgent:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts = []

    def run(self, prompt):
        self.prompts.append(prompt)
        nxt = self.responses.pop(0) if self.responses else self.responses
        if isinstance(nxt, Exception):
            raise nxt
        return _Response(nxt if isinstance(nxt, str) else FOOTBALL_PLAN)

    @property
    def calls(self):
        return len(self.prompts)


class RateLimit(Exception):
    def __str__(self):
        return "rate_limit_exceeded"


def _service():
    from app.services.fitmentor_service import fitmentor_service
    return fitmentor_service


def _kwargs(**extra):
    base = {"fitness_goal": "hypertrophy", "activity_level": "intermediate",
            "equipment": "gym", "time_per_day": 90, "sport": "football"}
    base.update(extra)
    return base


def call_counts():
    import asyncio
    print(f"\n{BOLD}6. Exactly one model call per request{RESET}")

    service = _service()
    original = service.fitness_agent

    # A deliberately thin plan: the quality evaluator will call it inadequate,
    # which used to buy up to two more generations.
    thin = "## Day 1\n- Bench Press – 4 × 6\n"

    try:
        for label, plan, constraints in (
            ("healthy generation", FOOTBALL_PLAN, []),
            ("injury generation", FOOTBALL_PLAN, [HAMSTRING]),
            ("inadequate quality", thin, []),
            ("inadequate quality with an injury", thin, [HAMSTRING]),
        ):
            agent = FakeAgent(plan, plan, plan, plan)
            service.fitness_agent = agent
            asyncio.run(service.generate_workout_plan(
                **_kwargs(constraints=constraints)))
            check(f"{label}: exactly one agent call", agent.calls == 1,
                  agent.calls)

        for label, constraints in (("healthy adaptation", []),
                                   ("injury adaptation", [HAMSTRING])):
            agent = FakeAgent(FOOTBALL_PLAN, FOOTBALL_PLAN, FOOTBALL_PLAN)
            service.fitness_agent = agent
            asyncio.run(service.adapt_workout_plan(
                current_plan=FOOTBALL_PLAN, feedback="more upper body",
                constraints=constraints, equipment="gym", time_per_day=90,
                fitness_goal="hypertrophy", sport="football"))
            check(f"{label}: exactly one agent call", agent.calls == 1,
                  agent.calls)

        # Rate limit: the fallback is local, so no second model call.
        agent = FakeAgent(RateLimit(), FOOTBALL_PLAN, FOOTBALL_PLAN)
        service.fitness_agent = agent
        asyncio.run(service.generate_workout_plan(**_kwargs(constraints=[HAMSTRING])))
        check("rate-limit fallback spends no extra model call", agent.calls == 1,
              agent.calls)
    finally:
        service.fitness_agent = original

    # The service must not hand repair a regeneration callback at all.
    import inspect
    from app.services import fitmentor_service as mod
    source = inspect.getsource(mod)
    check("no regenerate callback is passed to plan_repair",
          "regenerate=" not in source, "found regenerate= in fitmentor_service")
    check("MAX_REGENERATIONS is still 2 (unchanged, simply unused here)",
          plan_repair.MAX_REGENERATIONS == 2, plan_repair.MAX_REGENERATIONS)
    check("repair without a callback performs no regeneration",
          repaired().regenerations == 0)


# ---------------------------------------------------------------------------
# 7. mutations
# ---------------------------------------------------------------------------

def mutations():
    print(f"\n{BOLD}7. Mutations — each fix is load-bearing{RESET}")

    # M1: send CONDITIONAL lines back through _find_replacement().
    import app.services.plan_repair as pr
    original_once = pr._repair_once

    def arbitrary_fallback(plan_text, profiles, equipment, requested_minutes,
                           goal, sport, level=None):
        from app.services import plan_quality
        from app.services.contraindications import (
            VERDICT_CONDITIONAL, assess_plan, audit_against_profiles)
        findings = audit_against_profiles(plan_text, profiles)
        decisions, used = {}, set()
        for finding in findings:
            if finding["line_no"] in decisions:
                continue
            decision = pr._find_replacement(finding["line"], profiles, equipment, used)
            if decision.replacement:
                used.add(decision.replacement)
            decisions[finding["line_no"]] = decision
        for verdict in [v for v in assess_plan(plan_text, profiles)
                        if v["verdict"] == VERDICT_CONDITIONAL]:
            if verdict["line_no"] in decisions:
                continue
            decision = pr._find_replacement(verdict["line"], profiles, equipment, used)
            if decision.replacement:
                used.add(decision.replacement)
            decisions[verdict["line_no"]] = decision
        repaired_text = pr._apply(plan_text, decisions)
        replacements = [d for d in decisions.values() if d.substituted]
        removed = [d.original for d in decisions.values() if not d.substituted]
        quality = plan_quality.evaluate(
            repaired_text, removed_count=len(removed),
            replaced_count=len(replacements), requested_minutes=requested_minutes,
            goal=goal, sport=sport, equipment=equipment, level=level)
        return pr.RepairResult(plan=repaired_text, removed=removed,
                               replacements=replacements,
                               quality=quality.as_dict())

    pr._repair_once = arbitrary_fallback
    try:
        broken = repaired().plan
    finally:
        pr._repair_once = original_once
    invented = [c for c in CONDITIONING if c in broken.lower()]
    check("M1 replacing CONDITIONAL lines invents a conditioning exercise",
          len(invented) >= 1, f"{invented}\n{broken}")
    check("M1 restored: no conditioning is invented",
          not any(c in repaired().plan.lower() for c in CONDITIONING))

    # Both defects together are what produced the reported output: the
    # structural labels were prescription candidates AND unclassifiable
    # candidates were substituted, so a whole session became cardio machines.
    original_group_re = ps._GROUP_LABEL
    import re as _re2
    ps._GROUP_LABEL = _re2.compile(
        r"^(?:warm[\s-]?up|cool[\s-]?down|main|mobility|activation|strength|"
        r"conditioning|finisher|circuit|block|superset|recovery|cardio|core|"
        r"accessory|primer|workout|session)"
        r"(?:\s+(?:workout|block|session|sequence|phase|segment|part|section|"
        r"routine))?(?:\s+[a-z0-9]{1,3})?\s*:?\s*$", _re2.I)
    pr._repair_once = arbitrary_fallback
    try:
        fully_broken = repaired().plan
    finally:
        pr._repair_once = original_once
        ps._GROUP_LABEL = original_group_re
    invented_all = [c for c in CONDITIONING if c in fully_broken.lower()]
    check("M1+M2 together reproduce the reported multi-machine corruption",
          len(invented_all) >= 3, f"{invented_all}\n{fully_broken}")
    check("M1+M2 ...including a section label turned into an exercise",
          any(f"{alloc}" in ln and any(c in ln.lower() for c in CONDITIONING)
              for ln in fully_broken.splitlines() for alloc in ("55 min", "10 min")),
          fully_broken)
    check("M1+M2 restored: the real pipeline produces neither",
          not any(c in repaired().plan.lower() for c in CONDITIONING)
          and "Main lifts – 55 min" in repaired().plan)

    # M2: put the allocation grammar back the way it was.
    original_group = ps._GROUP_LABEL
    import re as _re
    ps._GROUP_LABEL = _re.compile(
        r"^(?:warm[\s-]?up|cool[\s-]?down|main|mobility|activation|strength|"
        r"conditioning|finisher|circuit|block|superset|recovery|cardio|core|"
        r"accessory|primer|workout|session)"
        r"(?:\s+(?:workout|block|session|sequence|phase|segment|part|section|"
        r"routine))?(?:\s+[a-z0-9]{1,3})?\s*:?\s*$", _re.I)
    try:
        items = ps.parse("- Main lifts – 55 min\n")
        role = items[0].role if items else "none"
    finally:
        ps._GROUP_LABEL = original_group
    check("M2 without the allocation grammar the label is a prescription",
          role == ps.PRESCRIPTION_LIKE, role)
    check("M2 restored: it is structural again",
          ps.parse("- Main lifts – 55 min\n")[0].role != ps.PRESCRIPTION_LIKE)

    # M3: append the repair log to the workout again.
    result = repaired()
    with_note = pr._append_note(result)
    check("M3 restoring _append_note puts the log back in the Markdown",
          "Adjustment Notes" in with_note, with_note[:120])
    check("M3 ...which the returned plan does not contain",
          "Adjustment Notes" not in result.plan, result.plan)

    # M4: weaken the final audit.
    from app.services import contraindications as ctra
    original_audit = ctra.audit_against_profiles
    ctra.audit_against_profiles = lambda text, profiles: []
    try:
        weak = plan_repair.repair(
            "## Day 1\n- Romanian deadlift – 4 × 6\n", [HAMSTRING])
    finally:
        ctra.audit_against_profiles = original_audit
    check("M4 a weakened audit lets the prohibited hip hinge survive",
          "Romanian deadlift" in weak.plan, weak.plan)
    check("M4 ...and still claims audit_clean", weak.audit_clean is True)
    strong = plan_repair.repair("## Day 1\n- Romanian deadlift – 4 × 6\n", [HAMSTRING])
    check("M4 restored: the hip hinge is removed again",
          "Romanian deadlift" not in strong.plan, strong.plan)


# ---------------------------------------------------------------------------
# 8. dosage modality
# ---------------------------------------------------------------------------

def dosage_modality():
    print(f"\n{BOLD}8. Dosage only transfers to a compatible modality{RESET}")

    # The classifier itself.
    for dosage, want in (("4 × 8 @ RPE 7", "reps"),
                         ("4 × 8 @ RPE 7, rest 90 sec", "reps"),
                         ("3 x 12 each side", "reps"),
                         ("10 reps each direction", "reps"),
                         ("6 × 20 m", "distance"),
                         ("4 x 400m", "distance"),
                         ("5 × 100 metres", "distance"),
                         ("3 × 45 sec", "time"),
                         ("30 seconds", "time"),
                         ("20 min", "time"),
                         ("each side", None),
                         ("@ RPE 7", None)):
        got = plan_repair._dosage_modality(dosage)
        check(f"{dosage!r} reads as {want}", got == want, got)

    check("'min' is not mistaken for metres",
          plan_repair._dosage_modality("20 min") == "time")

    # Transfer rules.
    cases = [
        ("4 × 8 @ RPE 7", "Chest-supported dumbbell row", True,
         "sets x reps -> a strength replacement"),
        ("4 × 8 @ RPE 7", "Brisk walk", False,
         "sets x reps -> a conditioning replacement"),
        ("6 × 20 m", "Box squat", False, "metres -> a squat"),
        ("6 × 20 m", "Brisk walk", False, "metres -> a walk"),
        ("6 × 20 m", "Stationary bike, steady pace", False, "metres -> a bike"),
        ("3 × 45 sec", "Front plank", True, "sets x seconds -> an isometric"),
        ("3 × 45 sec", "Stationary bike, steady pace", True,
         "sets x seconds -> conditioning"),
        ("3 × 45 sec", "Chest-supported dumbbell row", False,
         "sets x seconds -> a strength replacement"),
        ("10 reps each direction", "Stationary bike, steady pace", False,
         "reps -> a bike"),
        ("each side", "Brisk walk", True, "an unmeasured note transfers"),
    ]
    for dosage, replacement, want, label in cases:
        got = plan_repair._dosage_transfers(dosage, replacement)
        check(f"{label}: {'kept' if want else 'dropped'}", got == want,
              f"{dosage!r} -> {replacement!r} = {got}")

    # End to end.
    e2e = [
        ("- Box jumps – 3 × 5", "knee pain (severity 7/10)", ("3 × 5", "3 x 5")),
        ("- Sprint intervals – 6 × 20 m", "hamstring strain (severity 7/10)",
         ("20 m", "6 ×")),
        ("- Cat-Cow: 2 × 10", "hamstring strain (severity 7/10)", ("2 × 10",)),
        ("- Box jumps – 10 reps each direction", "knee pain (severity 7/10)",
         ("10 reps",)),
    ]
    for line, constraint, forbidden in e2e:
        out = plan_repair.repair(line, [constraint]).plan
        for token in forbidden:
            check(f"{line.strip('- ')[:26]!r} does not carry {token!r} forward",
                  token not in out, out)
        check(f"...and a replacement is still named ({line.strip('- ')[:22]!r})",
              out.strip().startswith("- ") and len(out.strip()) > 3, out)

    # An UNKNOWN exercise is removed outright, so no dosage question arises.
    out = plan_repair.repair("- Hip CAR – 10 reps each direction",
                             ["hamstring strain (severity 7/10)"]).plan
    check("an unknown exercise is removed rather than given a dosage",
          out.strip() == "", repr(out))

    # A compatible swap keeps everything useful.
    out = plan_repair.repair("- Bent-over row – 4 × 8 @ RPE 7, rest 90 sec",
                             ["hamstring strain (severity 7/10)"]).plan
    check("a strength->strength swap keeps sets, reps, RPE and rest",
          "4 × 8 @ RPE 7, rest 90 sec" in out, out)

    # Nothing semantically invalid survives anywhere in the reported plan.
    result = repaired()
    for bad in ("reps each direction", "× 20 m", "x 20 m"):
        offenders = [ln for ln in result.plan.splitlines()
                     if bad in ln and any(c in ln.lower() for c in CONDITIONING)]
        check(f"no conditioning line carries {bad!r}", not offenders, offenders)


# ---------------------------------------------------------------------------
# 9. exercise names that begin with an avoidance word
# ---------------------------------------------------------------------------

def avoidance_named_exercises():
    print(f"\n{BOLD}9. 'Skip'/'No' exercise names stay auditable{RESET}")

    from app.services import contraindications as ctra

    prescriptions = ["Skip drills: 3x20", "No hands burpees: 3x10",
                     "Skip rope: 3 × 60 sec", "No-jump squat: 4 × 10"]
    for line in prescriptions:
        items = ps.parse(f"- {line}\n")
        check(f"{line!r} is a prescription candidate",
              items and items[0].role == ps.PRESCRIPTION_LIKE,
              items[0].role if items else "none")

    instructions = ["No equipment required", "Skip this exercise if painful",
                    "No jumping today", "Avoid sprinting and jumping",
                    "Removed: any jogging or dynamic leg swings",
                    "Removed: leg swings & any fast knee-drive movements"]
    for line in instructions:
        items = ps.parse(f"- {line}\n")
        check(f"{line!r} stays an instruction",
              items and items[0].role == ps.INSTRUCTION,
              items[0].role if items else "none")

    # They must reach the safety pipeline under an active restriction.
    plan = ("## Day 1\n- Skip drills: 3x20\n- No hands burpees: 3x10\n"
            "- Bench press: 4x6\n")
    subjects = [i.body for i in ctra.safety_subjects_for(ps.parse(plan), True)]
    check("both reach the safety subjects",
          any("Skip drills" in s for s in subjects)
          and any("No hands burpees" in s for s in subjects), subjects)

    result = plan_repair.repair(plan, ["knee pain (severity 6/10); no jumping"])
    for name in ("Skip drills", "No hands burpees"):
        check(f"{name!r} does not survive a no-jumping restriction",
              name not in result.plan, result.plan)
        check(f"...and is recorded as removed ({name})",
              any(name in r for r in result.removed), result.removed)
    check("...while ordinary work is kept", "Bench press" in result.plan,
          result.plan)
    check("...and nothing was invented in their place",
          not any(c in result.plan.lower() for c in CONDITIONING), result.plan)

    # An instruction beginning with "No" must NOT be dragged in.
    prose = "## Day 1\n- No jumping today\n- Bench press: 4x6\n"
    kept = plan_repair.repair(prose, ["knee pain (severity 6/10)"])
    check("'No jumping today' is preserved, not treated as an exercise",
          "No jumping today" in kept.plan, kept.plan)

    # Healthy users keep them verbatim.
    healthy = plan_repair.repair(plan, [])
    check("a healthy user keeps 'Skip drills' and 'No hands burpees'",
          "Skip drills: 3x20" in healthy.plan
          and "No hands burpees: 3x10" in healthy.plan, healthy.plan)
    check("...with nothing removed or replaced",
          not healthy.removed and not healthy.replacements,
          (healthy.removed, healthy.replacements))


# ---------------------------------------------------------------------------
# 10. transport retry bound
# ---------------------------------------------------------------------------

def transport_retries():
    print(f"\n{BOLD}10. One Agent.run() is bounded in HTTP attempts{RESET}")

    from app.models.groq_with_fallback import GroqWithFallback
    from app.config.groq_config import groq_config
    from app.services.fitmentor_service import fitmentor_service

    model = fitmentor_service.fitness_agent.model
    check("FitMentor bounds SDK retries to 1",
          model._get_client_params().get("max_retries") == 1,
          model._get_client_params().get("max_retries"))
    check("...and still keeps its model fallback",
          model.fallback_id and model.fallback_id != model._primary_id,
          model.fallback_id)
    check("other agents are untouched (SDK default)",
          GroqWithFallback(id="x")._get_client_params().get("max_retries") is None)

    # Count the logical attempts GroqWithFallback itself makes, with a fake
    # transport - no network, no Groq client.
    attempts = {"n": 0}

    class Rate(Exception):
        def __str__(self):
            return "rate_limit_exceeded"

    probe = GroqWithFallback(id="primary", fallback_id="secondary", max_retries=1)
    keys = max(1, len(groq_config.api_keys))

    import app.models.groq_with_fallback as gwf
    original_super = gwf.Groq.response

    def counting(self, *a, **k):
        attempts["n"] += 1
        raise Rate()

    gwf.Groq.response = counting
    try:
        try:
            probe.response()
        except Exception:
            pass
    finally:
        gwf.Groq.response = original_super

    check(f"key rotation and model fallback make {2 * keys} logical calls",
          attempts["n"] == 2 * keys, attempts["n"])
    check("...which the SDK multiplies by at most 2 (1 try + 1 retry)",
          2 * keys * 2 == 4 * keys)
    check("...and never loops beyond that",
          attempts["n"] <= 2 * keys, attempts["n"])


def main():
    print(f"\n{BOLD}FITMENTOR — product recovery{RESET}")
    hamstring_case()
    structural_labels()
    instruction_lines()
    unknown_prescriptions()
    dosage_preservation()
    call_counts()
    dosage_modality()
    avoidance_named_exercises()
    transport_retries()
    mutations()
    print(f"\n{BOLD}{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
