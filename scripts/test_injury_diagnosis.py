#!/usr/bin/env python3
"""
Regression suite for injury DIAGNOSIS - the step before any restriction is
chosen.

Three confirmed HIGH bypasses are pinned here:

  1. injury_service.as_constraints() appends generated "Avoid: ..." and
     "Use instead: ..." prose. Diagnosing from that text read the wrong
     injury ("sore elbow" -> wrist, "shoulder pain" -> cervical), applied the
     wrong restriction set, and the final audit reported clean.
  2. One constraint string could only ever produce one injury, so
     "shoulder impingement and knee pain" silently lost the knee.
  3. thoracic had no region hint or fallback, so a mid-back complaint got
     generic speed restrictions only.

No live model call is made anywhere in this file.

    python scripts/test_injury_diagnosis.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import contraindications as ctra          # noqa: E402
from app.services import injury_taxonomy as it              # noqa: E402
from app.services import plan_repair, plan_structure as ps  # noqa: E402

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


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def enriched(label, body_part, severity):
    """Exactly the string injury_service.as_constraints() builds, no DB."""
    stage = ctra.stage_for(severity)
    line = f"{label} (severity {severity}/10, {stage['label']}). {stage['guidance']}"
    entry = ctra.CONTRAINDICATIONS.get(body_part)
    if entry:
        avoid = ctra.graded_exclusions(entry, severity)
        if avoid:
            line += " Avoid: " + ", ".join(avoid[:16]) + "."
        subs = list(getattr(entry, "substitutions", []) or [])
        if subs:
            line += " Use instead: " + ", ".join(subs[:4]) + "."
    return line


def where(profile):
    if profile is None:
        return "None"
    return f"{getattr(profile.condition, 'key', None)}/{profile.region}"


def prescribed_lines(plan_text):
    """
    Only what the plan PRESCRIBES.

    The Adjustment Notes echo every removed exercise by name ("Swapped *Cable
    chest fly*..."), so a naive substring search over the whole plan reports a
    leak for an exercise that was correctly removed.
    """
    body = plan_text.split("**Adjustment Notes**")[0]
    return "\n".join(item.body for item in ps.quality_subjects(ps.parse(body)))


def repaired(constraint, exercise, filler="Seated calf raise: 3x15"):
    plan = f"## Day 1\n- {exercise}\n- {filler}\n"
    result = plan_repair.repair(plan, [constraint])
    name = exercise.split(":")[0]
    return {
        "result": result,
        "leaked": name.lower() in prescribed_lines(result.plan).lower(),
        "residual": ctra.audit_plan(result.plan, [constraint]),
        "audit_clean": result.audit_clean,
    }


def assert_safe(label, constraint, exercise):
    """The full contract: parse -> audit -> repair -> re-audit the exact text."""
    out = repaired(constraint, exercise)
    check(f"{label}: {exercise.split(':')[0]!r} does not survive repair",
          not out["leaked"], prescribed_lines(out["result"].plan))
    check(f"{label}: re-auditing the returned plan is clean",
          not out["residual"], out["residual"])
    check(f"{label}: audit_clean reflects the returned text",
          out["audit_clean"] is True and not out["residual"],
          f"audit_clean={out['audit_clean']} residual={len(out['residual'])}")


# ---------------------------------------------------------------------------
# A. every generated constraint round-trips
# ---------------------------------------------------------------------------

def constraint_round_trip():
    print(f"\n{BOLD}A. Generated constraints keep their meaning{RESET}")

    for body_part in sorted(ctra.CONTRAINDICATIONS):
        label = body_part.replace("_", " ")
        for severity in (3, 6, 8):
            bare = it.parse(label, severity)
            rich = it.parse(enriched(label, body_part, severity))
            check(f"{body_part} @{severity}: guidance does not change the diagnosis",
                  where(bare) == where(rich),
                  f"bare={where(bare)}  enriched={where(rich)}")


# ---------------------------------------------------------------------------
# B. descriptions that collide with the generated avoidance text
# ---------------------------------------------------------------------------

COLLISIONS = [
    # description,     body_part,  severity, region it must NOT become
    ("shoulder pain",  "shoulder", 6, "shoulder", "neck"),
    ("sore shoulder",  "shoulder", 8, "shoulder", "neck"),
    ("hip pain",       "hip",      6, "hip_groin", None),
    ("sciatica",       "sciatica", 6, "lumbar",   "thigh"),
    ("sore elbow",     "elbow",    6, "elbow",    "wrist"),
    ("elbow",          "elbow",    8, "elbow",    "wrist"),
]


def collision_descriptions():
    print(f"\n{BOLD}B. Descriptions that collide with generated Avoid text{RESET}")

    for label, body_part, severity, want_region, wrong_region in COLLISIONS:
        profile = it.parse(enriched(label, body_part, severity))
        check(f"{label!r} keeps region {want_region!r}",
              profile.region == want_region, where(profile))
        if wrong_region:
            check(f"{label!r} is not misread as {wrong_region!r}",
                  profile.region != wrong_region, where(profile))

    # The specific words that caused each corruption are still present in the
    # constraint - the fix is that they are not READ as the diagnosis.
    text = enriched("sore elbow", "elbow", 6)
    check("the generated Avoid text still names 'wrist curls'",
          "wrist curls" in text, text[:120])
    check("...and the subject used for diagnosis excludes it",
          "wrist" not in it.diagnostic_subject(text).lower(),
          it.diagnostic_subject(text))
    check("...while the full text is still kept as raw",
          "wrist curls" in it.parse(text).raw)

    subject = it.diagnostic_subject(enriched("shoulder pain", "shoulder", 6))
    check("the diagnostic subject is just the user's words",
          subject == "shoulder pain", subject)

    # Text a user typed themselves has no severity clause and is untouched.
    check("a user-typed constraint is not truncated",
          it.diagnostic_subject("wrist pain; avoid jumping")
          == "wrist pain; avoid jumping")

    # A severity a USER typed carries no stage label, so only the clause is
    # dropped - everything they wrote after it survives. Stripping to the
    # first "(severity" lost the shoulder here.
    both = {p.region for p in it.parse_many("knee pain (severity 5/10) and shoulder pain")}
    check("a user-typed severity does not swallow the rest of the sentence",
          both == {"knee", "shoulder"}, both)
    check("...and a bare severity clause still sets the severity",
          it.parse("knee pain (severity 5/10)").severity == 5,
          it.parse("knee pain (severity 5/10)").severity)
    patterns = set().union(*(p.restricted_patterns() for p in
                             it.parse_many("knee pain (severity 5/10); avoid jumping")))
    check("...and an explicit restriction after it still applies",
          "jumping" in patterns, sorted(patterns))


# ---------------------------------------------------------------------------
# C. the four exact leaking exercises
# ---------------------------------------------------------------------------

LEAKS = [
    ("shoulder pain", "shoulder", 5, "Cable chest fly: 3x12"),
    ("hip pain",      "hip",      6, "Romanian deadlift: 3x8"),
    ("sciatica",      "sciatica", 6, "Russian twist: 3x12"),
    ("sore elbow",    "elbow",    6, "Cable triceps pushdown: 3x12"),
]


def reported_leaks():
    print(f"\n{BOLD}C. The four reported end-to-end leaks{RESET}")
    for label, body_part, severity, exercise in LEAKS:
        assert_safe(label, enriched(label, body_part, severity), exercise)


# ---------------------------------------------------------------------------
# D. combined injuries and negation controls
# ---------------------------------------------------------------------------

def combined_and_negation():
    print(f"\n{BOLD}D. Several injuries in one constraint{RESET}")

    def areas(text, severity=6):
        return {p.region for p in it.parse_many(text, severity)}

    check("'shoulder impingement and knee pain' keeps both",
          areas("shoulder impingement and knee pain") == {"shoulder", "knee"},
          areas("shoulder impingement and knee pain"))
    check("'left ankle sprain with a hamstring strain' keeps both",
          areas("left ankle sprain with a hamstring strain") == {"ankle", "thigh"},
          areas("left ankle sprain with a hamstring strain"))
    check("'wrist pain; also knee pain' keeps both",
          areas("wrist pain; also knee pain") == {"wrist", "knee"},
          areas("wrist pain; also knee pain"))

    # False splitting controls.
    both = it.parse_many("left and right knee pain", 6)
    check("'left and right knee pain' is ONE knee injury", len(both) == 1,
          [where(p) for p in both])
    check("...marked bilateral", both[0].side == "bilateral", both[0].side)

    context = it.parse_many("knee pain after a shoulder workout", 6)
    check("'knee pain after a shoulder workout' is a knee complaint",
          [p.region for p in context] == ["knee"], [where(p) for p in context])

    negated = it.parse_many("no shoulder pain, only knee pain", 6)
    check("'no shoulder pain, only knee pain' is knee only",
          [p.region for p in negated] == ["knee"], [where(p) for p in negated])

    # An explicit restriction alongside an injury keeps both.
    mixed = it.parse_many("wrist pain; avoid jumping", 6)
    check("'wrist pain; avoid jumping' keeps the wrist injury",
          any(p.region == "wrist" for p in mixed), [where(p) for p in mixed])
    patterns = set().union(*(p.restricted_patterns() for p in mixed))
    check("...and the jumping restriction", "jumping" in patterns,
          sorted(patterns))

    for text, pattern in (("knee pain; no running", "running"),
                          ("wrist pain; avoid jumping", "jumping"),
                          ("no overhead pressing", "overhead")):
        got = set().union(*(p.restricted_patterns()
                            for p in it.parse_many(text, 5)))
        check(f"{text!r} still restricts {pattern!r}", pattern in got,
              sorted(got))

    # Acceptance: the leg press must not survive a combined constraint.
    assert_safe("combined", "shoulder impingement and knee pain (severity 6/10)",
                "Leg press: 3x10")

    # An unrecognisable description still produces an injury, not nothing.
    unknown = it.parse_many("costochondritis 6/10")
    check("an unnamed condition is still treated as an injury",
          len(unknown) == 1, [where(p) for p in unknown])

    # --- each injury keeps its OWN severity ---------------------------------
    mixed = {p.region: p.severity for p in it.parse_many(
        "wrist pain (severity 2/10) and knee pain (severity 7/10)")}
    check("a per-injury severity is not overwritten by the first one",
          mixed == {"wrist": 2, "knee": 7}, mixed)
    check("...so the 7/10 knee still restricts squatting",
          "squat" in next(p for p in it.parse_many(
              "wrist pain (severity 2/10) and knee pain (severity 7/10)")
              if p.region == "knee").restricted_patterns())
    assert_safe("mixed severity",
                "wrist pain (severity 2/10) and knee pain (severity 7/10)",
                "Leg press: 3x10")

    # A clause with no severity of its own falls back to the string's.
    shared = {p.region: p.severity for p in it.parse_many(
        "wrist pain and knee pain (severity 7/10)")}
    check("a clause with no severity inherits the stated one",
          shared == {"wrist": 7, "knee": 7}, shared)

    # --- a user annotation is not a machine stage label ---------------------
    text = "knee pain (severity 5/10, improving) and shoulder pain"
    check("'improving' does not mark the rest as generated prose",
          it.diagnostic_subject(text) == text, it.diagnostic_subject(text))
    both = {p.region for p in it.parse_many(text)}
    check("...so both injuries survive parsing", both == {"knee", "shoulder"},
          both)
    assert_safe("user annotation", text, "Cable chest fly: 3x12")

    for note in ("today", "after training", "getting better"):
        annotated = f"knee pain (severity 5/10, {note}) and shoulder pain"
        regions = {p.region for p in it.parse_many(annotated)}
        check(f"annotation {note!r} keeps both injuries",
              regions == {"knee", "shoulder"}, regions)

    # ...while a real stage label still marks generated prose.
    generated = enriched("shoulder pain", "shoulder", 6)
    check("a real stage label is still recognised as generated",
          it.diagnostic_subject(generated) == "shoulder pain",
          it.diagnostic_subject(generated))

    # --- sides belong to their own injury -----------------------------------
    sides = {p.region: p.side for p in it.parse_many(
        "left wrist pain and right knee pain", 6)}
    check("opposite sides on different injuries stay clause-local",
          sides == {"wrist": "left", "knee": "right"}, sides)
    same = it.parse_many("left and right knee pain", 6)
    check("opposite sides on the SAME injury still become bilateral",
          len(same) == 1 and same[0].side == "bilateral",
          [(p.region, p.side) for p in same])

    # --- negation must not invent the injury it rules out --------------------
    check("'no knee pain' creates no injury", it.parse_many("no knee pain") == [],
          [where(p) for p in it.parse_many("no knee pain")])
    check("'no knee pain but shoulder hurts' keeps the shoulder",
          [p.region for p in it.parse_many("no knee pain but shoulder hurts")]
          == ["shoulder"],
          [where(p) for p in it.parse_many("no knee pain but shoulder hurts")])
    check("'knee pain but no running' keeps the knee",
          [p.region for p in it.parse_many("knee pain but no running")] == ["knee"],
          [where(p) for p in it.parse_many("knee pain but no running")])
    denied = it.parse_many("no knee pain; avoid jumping")
    check("...and an explicit restriction alongside a denial still applies",
          "jumping" in set().union(*(p.restricted_patterns() for p in denied)),
          [where(p) for p in denied])

    # --- malformed input must not cost an injury ----------------------------
    broken = {p.region for p in
              it.parse_many("knee pain (severity 5/10 and shoulder pain")}
    check("an unclosed parenthesis does not swallow the second injury",
          broken == {"knee", "shoulder"}, broken)


# ---------------------------------------------------------------------------
# E. thoracic
# ---------------------------------------------------------------------------

def thoracic_region():
    print(f"\n{BOLD}E. Thoracic coverage and region collisions{RESET}")

    profile = it.parse("thoracic pain", 6)
    check("'thoracic pain' resolves to the thoracic region",
          profile.region == "thoracic", where(profile))
    check("...without inventing a diagnosis", profile.condition is None,
          where(profile))
    check("...and restricts rotation and axial load",
          {"spinal_rotation", "axial_load"} <= profile.restricted_patterns(),
          sorted(profile.restricted_patterns()))

    check("'thoracic spine pain' does not become lumbar",
          it.parse("thoracic spine pain", 6).region == "thoracic",
          where(it.parse("thoracic spine pain", 6)))
    check("'t-spine pain' resolves to thoracic",
          it.parse("t-spine pain", 6).region == "thoracic",
          where(it.parse("t-spine pain", 6)))
    check("'lower back pain' still resolves to lumbar",
          it.parse("lower back pain", 6).region == "lumbar",
          where(it.parse("lower back pain", 6)))
    check("'back pain' still resolves to lumbar",
          it.parse("back pain", 6).region == "lumbar",
          where(it.parse("back pain", 6)))
    check("'neck pain' still resolves to neck",
          it.parse("neck pain", 6).region == "neck",
          where(it.parse("neck pain", 6)))

    # "upper back pain" and "mid back pain" contain the lumbar CONDITION
    # trigger "back pain", which used to win before region hints ran. At the
    # controlled stage lumbar restricts neither spinal_rotation nor overhead,
    # so a mid-back complaint was handed thoracic rotation and called clean.
    for phrase in ("upper back pain", "mid back pain", "midback pain",
                   "upper-back pain"):
        profile = it.parse(phrase, 5)
        check(f"{phrase!r} resolves to thoracic, not lumbar",
              profile.region == "thoracic", where(profile))
        check(f"...and restricts spinal rotation ({phrase})",
              "spinal_rotation" in profile.restricted_patterns(),
              sorted(profile.restricted_patterns()))

    lumbar_at_5 = it.parse("lower back pain", 5).restricted_patterns()
    check("lumbar at 5/10 genuinely does NOT restrict spinal rotation",
          "spinal_rotation" not in lumbar_at_5, sorted(lumbar_at_5))
    check("...which is why thoracic must not fall through to it",
          "spinal_rotation" in it.parse("upper back pain", 5).restricted_patterns())

    assert_safe("thoracic", "thoracic pain (severity 6/10)",
                "Thoracic rotation: 3x10 each side")
    assert_safe("thoracic", "thoracic pain (severity 6/10)",
                "Barbell back squat: 3x5")
    assert_safe("upper back", "upper back pain (severity 5/10)",
                "Thoracic rotation: 3x10 each side")
    assert_safe("mid back", "mid back pain (severity 5/10)",
                "Thoracic rotation: 3x10 each side")


# ---------------------------------------------------------------------------
# preserved invariants
# ---------------------------------------------------------------------------

def preserved_invariants():
    print(f"\n{BOLD}Preserved invariants{RESET}")

    plan = ("## Day 1\n- Barbell back squat: 3x5\n- Bench press: 3x8\n"
            "- Romanian deadlift: 3x8\n- Overhead press: 3x8\n")
    healthy = plan_repair.repair(plan, [])
    check("a healthy user loses nothing", not healthy.removed and
          not healthy.replacements, (healthy.removed, healthy.replacements))
    check("...and every prescribed line survives byte-identically",
          all(line.strip("- ") in healthy.plan
              for line in plan.splitlines() if line.startswith("- ")),
          prescribed_lines(healthy.plan))

    check("MAX_REGENERATIONS is still 2", plan_repair.MAX_REGENERATIONS == 2,
          plan_repair.MAX_REGENERATIONS)

    # Unknown prescription + an active restriction stays fail-closed.
    unknown = repaired("knee pain (severity 7/10)", "Zercher yoke carry: 3x20m")
    check("an unknown exercise is not waved through under a restriction",
          unknown["leaked"] is False or not unknown["residual"],
          prescribed_lines(unknown["result"].plan))

    # One canonical helper, used everywhere.
    import inspect
    for module in (plan_repair, ctra):
        source = inspect.getsource(module)
        check(f"{module.__name__.split('.')[-1]} uses profiles_for()",
              "profiles_for(" in source)
        check(f"...and no longer builds its own parse() comprehension",
              "taxonomy.parse(c) for c" not in source)


# ---------------------------------------------------------------------------
# F. mutations
# ---------------------------------------------------------------------------

def mutations():
    print(f"\n{BOLD}F. Mutations — each guard is load-bearing{RESET}")

    # M1: diagnose from the whole enriched string again.
    # M1 must restore the WHOLE old parsing path: the unsanitised subject AND
    # one profile per constraint string. Disabling only diagnostic_subject
    # leaves parse_many splitting the generated "Avoid: ..." list into many
    # profiles, and those profiles independently remove the very exercises
    # the mutation is supposed to leak - which is what made an earlier version
    # of this test conclude, wrongly, that the four leaks were not real.
    original_subject, original_many = it.diagnostic_subject, it.parse_many
    it.diagnostic_subject = lambda text, keep_severity=False: text or ""
    it.parse_many = lambda text, severity=None: (
        [p] if (p := it.parse(text, severity)) else [])
    try:
        broken = {label: it.parse(enriched(label, bp, sev)).region
                  for label, bp, sev, _ in LEAKS}
        wrong_patterns = it.parse(enriched("sore elbow", "elbow", 6)) \
            .restricted_patterns()
        leaks = {label: repaired(enriched(label, bp, sev), exercise)
                 for label, bp, sev, exercise in LEAKS}
    finally:
        it.diagnostic_subject, it.parse_many = original_subject, original_many

    check("M1 reading generated guidance misdiagnoses the shoulder as neck",
          broken["shoulder pain"] == "neck", broken)
    check("M1 ...the elbow as wrist", broken["sore elbow"] == "wrist", broken)
    check("M1 ...and the sciatica as thigh", broken["sciatica"] == "thigh", broken)

    # All four reported leaks reproduce under the faithful old system.
    for label, _bp, _sev, exercise in LEAKS:
        out = leaks[label]
        check(f"M1 {exercise.split(':')[0]!r} survives repair under the old parser",
              out["leaked"] is True, prescribed_lines(out["result"].plan))
        check(f"M1 ...and the audit calls that plan clean ({label})",
              out["audit_clean"] is True and not out["residual"],
              f"audit_clean={out['audit_clean']} residual={len(out['residual'])}")

    right_patterns = it.parse(enriched("sore elbow", "elbow", 6)) \
        .restricted_patterns()
    check("M1 the misdiagnosis drops elbow_extension from the restrictions",
          "elbow_extension" in right_patterns
          and "elbow_extension" not in wrong_patterns,
          f"correct={sorted(right_patterns)}\nwrong={sorted(wrong_patterns)}")
    check("M1 restored: the elbow is diagnosed correctly",
          it.parse(enriched("sore elbow", "elbow", 6)).region == "elbow")
    for label, bp, sev, exercise in LEAKS:
        out = repaired(enriched(label, bp, sev), exercise)
        check(f"M1 restored: {exercise.split(':')[0]!r} no longer survives",
              out["leaked"] is False, prescribed_lines(out["result"].plan))

    # M2: one profile per constraint string again.
    original_many = it.parse_many
    it.parse_many = lambda text, severity=None: (
        [p] if (p := it.parse(text, severity)) else [])
    try:
        areas = {p.region for p in it.profiles_for(
            ["shoulder impingement and knee pain (severity 6/10)"])}
        leak = repaired("shoulder impingement and knee pain (severity 6/10)",
                        "Leg press: 3x10")
    finally:
        it.parse_many = original_many
    check("M2 one-profile-per-string loses the knee", "knee" not in areas, areas)
    check("M2 ...and the leg press then survives", leak["leaked"] is True,
          prescribed_lines(leak["result"].plan))
    check("M2 restored: both injuries are kept",
          {p.region for p in it.profiles_for(
              ["shoulder impingement and knee pain (severity 6/10)"])}
          == {"shoulder", "knee"})

    # M3: remove the thoracic region fallback.
    original_fallback = it._REGION_FALLBACK.pop("thoracic")
    original_hints = it._REGION_HINTS.pop("thoracic")
    try:
        profile = it.parse("thoracic pain", 6)
        leak = repaired("thoracic pain (severity 6/10)",
                        "Thoracic rotation: 3x10 each side")
    finally:
        it._REGION_FALLBACK["thoracic"] = original_fallback
        it._REGION_HINTS["thoracic"] = original_hints
    check("M3 without the thoracic hint the region is lost",
          profile.region != "thoracic", where(profile))
    check("M3 ...and spinal rotation is no longer restricted",
          "spinal_rotation" not in profile.restricted_patterns(),
          sorted(profile.restricted_patterns()))
    check("M3 ...so thoracic rotation survives", leak["leaked"] is True,
          prescribed_lines(leak["result"].plan))
    check("M3 restored: thoracic is recognised again",
          it.parse("thoracic pain", 6).region == "thoracic")

    # M4: the audit oracle must reject a wrong mapping, not just a null one.
    check("M4 the audit's expected-region table covers every body part",
          _oracle_covers_all(), "audit_safety_system._EXPECTED_REGION")


def _oracle_covers_all():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "audit_safety_system",
        Path(__file__).resolve().parent / "audit_safety_system.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return set(module._EXPECTED_REGION) == set(ctra.CONTRAINDICATIONS)


def main():
    print(f"\n{BOLD}FITMENTOR — injury diagnosis integrity{RESET}")
    constraint_round_trip()
    collision_descriptions()
    reported_leaks()
    combined_and_negation()
    thoracic_region()
    preserved_invariants()
    mutations()
    print(f"\n{BOLD}{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
