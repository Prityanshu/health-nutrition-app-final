#!/usr/bin/env python3
"""
Regression suite for the plan_structure parser and its downstream wiring
(plan_quality.exercise_lines, contraindications.classify_line/assess_plan,
plan_repair's block-aware replace/remove).

Offline only - no LLM calls. Minimum matrix as specified:
  1. bare unknown exercises
  2. numbered items
  3. bold/italic exercise lines
  4. dosage on the next line
  5. warm-up/cooldown exercises
  6. progression/nutrition/safety sections
  7. instruction lines
  8. exercise names containing progression/run/press/rest
  9. active injury: unknown prescription -> CONDITIONAL/repaired/removed
  10. healthy user: unknown prescription -> unchanged
  11. multi-line replacement/removal must not orphan dosage
  12. existing known-unsafe-exercise tests still pass (full suite, separately)
  13. existing healthy-user byte-identical tests still pass (full suite, separately)

    python scripts/test_plan_structure.py
"""

import re
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


def bare_unknown_exercises():
    from app.services import plan_structure as ps
    print(f"\n{BOLD}1. Bare unknown exercises are prescription candidates{RESET}")

    for name in ["Ankle pogo", "Peterson step-down", "Cable pull-through",
                 "Heel-toe rocks", "Cossack flow"]:
        items = ps.parse(f"- {name}")
        check(f"{name!r} is a bare bullet prescription candidate",
              len(items) == 1 and items[0].role == ps.PRESCRIPTION_CANDIDATE
              and items[0].body == name,
              f"{items}")


def numbered_exercises():
    from app.services import plan_structure as ps
    print(f"\n{BOLD}2. Numbered exercises{RESET}")

    plan = "1. Peterson step-down\n2) Cable pull-through"
    items = ps.parse(plan)
    check("two numbered items recognised", len(items) == 2, f"{items}")
    check("both are prescription candidates",
          all(i.role == ps.PRESCRIPTION_CANDIDATE for i in items), f"{items}")
    check("markers captured", [i.marker for i in items] == ["1.", "2)"],
          f"{[i.marker for i in items]}")


def bold_italic_lines():
    from app.services import plan_structure as ps
    print(f"\n{BOLD}3. Bold/italic exercise lines{RESET}")

    items = ps.parse("- **Ankle pogo**\n* *Cossack flow*")
    check("two emphasis-wrapped bullets recognised", len(items) == 2, f"{items}")
    check("bold marker stripped from body", items[0].body == "Ankle pogo",
          f"{items[0].body!r}")
    check("italic marker stripped from body", items[1].body == "Cossack flow",
          f"{items[1].body!r}")
    check("both are prescription candidates",
          all(i.role == ps.PRESCRIPTION_CANDIDATE for i in items), f"{items}")


def dosage_next_line():
    from app.services import plan_structure as ps
    print(f"\n{BOLD}4. Dosage on the next line, and nested dosage{RESET}")

    items = ps.parse("- Ankle pogo\n  3x20 seconds")
    check("one item, dosage folded in", len(items) == 1, f"{items}")
    check("dosage line captured", items[0].dosage_lines == ["3x20 seconds"],
          f"{items[0].dosage_lines}")
    check("both raw lines belong to the block", items[0].line_numbers == [0, 1],
          f"{items[0].line_numbers}")

    # PROBLEM 2 (later review): indentation alone is NOT sufficient to mean
    # dosage. A nested BULLET is always its own independent structural item -
    # never folded - because that is the only way a real unknown exercise
    # nested under a group label ("- Warm-up\n  - Ankle pogo") stays
    # independently auditable. What used to fold "- 3 sets"/"- 20 seconds"
    # into "Ankle pogo"'s dosage_lines now correctly parses them as their own
    # items - and they still never look like unknown exercises, because
    # they are dosage-SHAPED (pure numbers + dosage vocabulary), which routes
    # them to role=INSTRUCTION rather than PRESCRIPTION_CANDIDATE.
    nested = ps.parse("- Ankle pogo\n  - 3 sets\n  - 20 seconds")
    check("a nested bullet is its own item, never folded as dosage",
          len(nested) == 3, f"{nested}")
    check("the parent has no dosage_lines from nested bullets",
          nested[0].dosage_lines == [], f"{nested[0].dosage_lines}")
    check("nested dosage-shaped bullets are classified as instructions, "
          "not unknown exercises",
          nested[1].role == ps.INSTRUCTION and nested[2].role == ps.INSTRUCTION,
          f"{nested}")

    # A sibling bullet at the SAME indent is a new item, not dosage.
    siblings = ps.parse("- Ankle pogo\n- Cossack flow")
    check("same-indent sibling is a separate item, not dosage",
          len(siblings) == 2 and not siblings[0].dosage_lines, f"{siblings}")


def warm_up_cool_down():
    from app.services import plan_structure as ps
    print(f"\n{BOLD}5. Warm-up/cooldown sections are exercise-capable{RESET}")

    plan = "### Warm-up\n- Arm circles\n### Cooldown\n- Heel-toe rocks"
    items = ps.parse(plan)
    check("both items present", len(items) == 2, f"{items}")
    check("warm-up item is a prescription candidate, section tagged",
          items[0].role == ps.PRESCRIPTION_CANDIDATE and items[0].section == "warm_up",
          f"{items[0]}")
    check("cooldown item is a prescription candidate, section tagged",
          items[1].role == ps.PRESCRIPTION_CANDIDATE and items[1].section == "cool_down",
          f"{items[1]}")


def suppressed_sections():
    from app.services import plan_structure as ps
    print(f"\n{BOLD}6. Progression/nutrition/safety sections are suppressed{RESET}")

    plan = (
        "### Progression\n- Add two reps next week\n"
        "### Nutrition\n- Eat sufficient protein\n"
        "### Safety\n- Stop if sharp pain occurs\n"
    )
    items = ps.parse(plan)
    check("all three bullets present but non-exercise", len(items) == 3
          and all(i.role == ps.NON_EXERCISE for i in items), f"{items}")

    # Substring, not structural heading, must NOT suppress - a bullet whose
    # own text happens to mention one of these words is not inside a section.
    not_a_heading = ps.parse("- Progression run: 20 min easy")
    check("a bullet merely mentioning a suppressed word is still a candidate",
          not_a_heading[0].role == ps.PRESCRIPTION_CANDIDATE, f"{not_a_heading}")


def instruction_lines():
    from app.services import plan_structure as ps
    print(f"\n{BOLD}7. Instruction lines are not prescription candidates{RESET}")

    for line in ["Rest 90 seconds", "Tempo: 3-1-1", "RPE: 7", "Duration: 45 minutes",
                 "Focus on controlled form"]:
        items = ps.parse(f"- {line}")
        check(f"{line!r} classified as instruction",
              items[0].role == ps.INSTRUCTION, f"{items}")


def confusing_substrings():
    from app.services import plan_structure as ps
    print(f"\n{BOLD}8. Exercise names containing progression/run/press/rest{RESET}")

    for name in ["Progression run", "Tempo run", "Pallof press", "Rest-pause squat"]:
        items = ps.parse(f"- {name}")
        check(f"{name!r} is a prescription candidate, not an instruction",
              items[0].role == ps.PRESCRIPTION_CANDIDATE, f"{items}")


def active_injury_unknown_prescription():
    from app.services import contraindications as c
    print(f"\n{BOLD}9. Active injury: unknown prescription is CONDITIONAL{RESET}")

    hamstring = profiles(["hamstring strain (severity 6/10)"])
    bare = c.classify_line("- Ankle pogo", hamstring)
    dosed = c.classify_line("- Ankle pogo: 4 rounds", hamstring)
    check("bare unknown exercise -> CONDITIONAL while injured",
          bare["verdict"] == c.VERDICT_CONDITIONAL, f"{bare}")
    check("the SAME exercise with dosage attached -> CONDITIONAL too "
          "(the bug: this used to only trigger with dosage present)",
          dosed["verdict"] == c.VERDICT_CONDITIONAL, f"{dosed}")

    # And it actually gets repaired end to end.
    from app.services import plan_repair
    r = plan_repair.repair("- Ankle pogo\n- Bench press: 4x6",
                           ["hamstring strain (severity 6/10)"])
    check("unresolved unknown prescription is swapped or removed by repair",
          any(x.original.strip() == "- Ankle pogo" for x in r.replacements)
          or any(x.strip() == "- Ankle pogo" for x in r.removed),
          f"replacements={r.replacements} removed={r.removed}")
    check("final plan carries no unresolved conditional item",
          not any(v["verdict"] == c.VERDICT_CONDITIONAL
                  for v in c.assess_plan(r.plan.split("\n\n---")[0], profiles(
                      ["hamstring strain (severity 6/10)"]))),
          f"plan={r.plan!r}")


def healthy_user_unchanged():
    from app.services import contraindications as c
    print(f"\n{BOLD}10. Healthy user: unknown prescription stays UNKNOWN{RESET}")

    bare = c.classify_line("- Ankle pogo", [])
    dosed = c.classify_line("- Ankle pogo: 4 rounds", [])
    check("bare unknown exercise -> UNKNOWN with no injury",
          bare["verdict"] == c.VERDICT_UNKNOWN, f"{bare}")
    check("dosed unknown exercise -> UNKNOWN with no injury",
          dosed["verdict"] == c.VERDICT_UNKNOWN, f"{dosed}")

    from app.services import plan_repair
    plan = "- Ankle pogo\n- Bench press: 4x6"
    r = plan_repair.repair(plan, [])
    check("a healthy user's plan is returned byte-identical",
          r.plan == plan, f"{r.plan!r}")
    check("nothing removed or replaced for a healthy user",
          not r.replacements and not r.removed, f"{r}")


def no_orphaned_dosage():
    from app.services import plan_repair
    from app.services.contraindications import audit_against_profiles
    print(f"\n{BOLD}11. Multi-line replace/remove must not orphan dosage{RESET}")

    hamstring = ["hamstring strain (severity 6/10)"]

    # A genuinely unsafe hinge, with dosage split across two lines, must be
    # replaced (or removed) as a WHOLE block - the dosage line must not
    # survive on its own once the exercise above it is gone.
    plan = "- Romanian deadlift\n  3x8 @ RPE 7\n- Bench press: 4x6"
    r = plan_repair.repair(plan, hamstring)
    lines = r.plan.split("\n\n---")[0].splitlines()
    check("no bare dosage line survives without its exercise",
          not any(l.strip() in ("3x8 @ RPE 7",) for l in lines)
          or any("Romanian deadlift" not in prev for prev in lines),
          f"{lines}")
    orphan_dosage = [
        l for i, l in enumerate(lines)
        if l.strip() == "3x8 @ RPE 7"
        and (i == 0 or not lines[i - 1].strip().startswith(("-", "*")))
    ]
    check("dosage line is never left with no bullet above it", not orphan_dosage,
          f"{lines}")
    check("plan is still clean against the hamstring profile",
          not audit_against_profiles(r.plan, profiles(hamstring)), f"{r.plan!r}")

    # Nested BULLETED lines under a hinge are never that hinge's dosage at
    # all (PROBLEM 2, later review) - "- 3 sets"/"- 8 reps" are independent,
    # dosage-shaped INSTRUCTION items, never handed a repair decision, so
    # they are simply untouched either way; only "Romanian deadlift" itself
    # is repaired, and the unrelated sibling exercise must be unaffected.
    nested_plan = "- Romanian deadlift\n  - 3 sets\n  - 8 reps\n- Bench press: 4x6"
    r2 = plan_repair.repair(nested_plan, hamstring)
    lines2 = r2.plan.split("\n\n---")[0].splitlines()
    check("the hinge line itself no longer names the original exercise",
          not any(l.strip() == "- Romanian deadlift" for l in lines2), f"{lines2}")
    check("the nested dosage-shaped lines are untouched, not turned into a "
          "fabricated exercise",
          "  - 3 sets" in lines2 and "  - 8 reps" in lines2, f"{lines2}")
    check("the unrelated sibling exercise is unaffected",
          "- Bench press: 4x6" in lines2, f"{lines2}")


def control_known_unsafe_still_caught():
    """12. A sanity check that the structural change did not blunt real
    detection - a KNOWN, classifiable unsafe exercise must still be caught,
    with or without a dosage line attached."""
    from app.services.contraindications import audit_against_profiles
    print(f"\n{BOLD}12. Control - known unsafe exercises are still caught{RESET}")

    hamstring = profiles(["hamstring strain (severity 6/10)"])
    check("bent-over row still flagged (no dosage)",
          bool(audit_against_profiles("- Bent over row", hamstring)))
    check("bent-over row still flagged (same-line dosage)",
          bool(audit_against_profiles("- Bent over row: 3x8", hamstring)))
    check("bent-over row still flagged (dosage on next line)",
          bool(audit_against_profiles("- Bent over row\n  3x8 reps", hamstring)))


def control_healthy_byte_identical():
    """13. A sanity check against the existing byte-identical-for-healthy-users
    guarantee, now routed through the structural parser."""
    from app.services import plan_repair
    print(f"\n{BOLD}13. Control - healthy users remain byte-identical{RESET}")

    plan = "\n".join([
        "* Sprint intervals: 8x100m", "* Back squat: 5x5",
        "* Romanian deadlift: 3x8", "* Bench press: 4x6",
        "* Overhead press: 3x8", "* Bent over row: 4x8",
    ])
    r = plan_repair.repair(plan, [], requested_minutes=60, equipment="gym")
    check("plan returned byte-identical for a healthy user", r.plan == plan,
          f"{r.plan!r}")


def exercise_lines_canonical():
    from app.services import plan_quality as pq
    print(f"\n{BOLD}exercise_lines() now derives from plan_structure{RESET}")

    plan = (
        "### Warm-up\n- Arm circles\n"
        "### Main\n- Ankle pogo\n- Bent over row: 3x8\n"
        "### Cooldown\n- Heel-toe rocks\n"
        "### Progression\n- Add 2 reps next week\n"
        "### Nutrition\n- Eat sufficient protein\n"
    )
    lines = pq.exercise_lines(plan)
    check("warm-up/main/cooldown counted, progression/nutrition excluded",
          lines == ["Arm circles", "Ankle pogo", "Bent over row: 3x8", "Heel-toe rocks"],
          f"{lines}")


# ---------------------------------------------------------------------------
# Second review pass - PROBLEMS 1-6
# ---------------------------------------------------------------------------

def heading_substring_safety():
    """PROBLEM 1 - tests 1, 2, 3: non-exercise headings are a normalized
    whole-heading category match, never a substring search."""
    from app.services import plan_structure as ps
    print(f"\n{BOLD}P1.1-3 — normalized heading categories, not substrings{RESET}")

    plan = "### Day 3 - Progression Run\n- Ankle pogo\n- Bench press: 3x8"
    items = ps.parse(plan)
    check("1. 'Day 3 - Progression Run' does not suppress exercise parsing",
          len(items) == 2 and all(i.role == ps.PRESCRIPTION_CANDIDATE for i in items),
          f"{items}")

    items2 = ps.parse("### Progression Notes\n- Increase volume gradually next week")
    check("2. dedicated 'Progression Notes' remains non-exercise",
          len(items2) == 1 and items2[0].role == ps.NON_EXERCISE, f"{items2}")

    for heading, exercise in [
        ("### Day 3 - Progression Run", "Ankle pogo"),
        ("### Running Progression Session", "High knees drill"),
        ("### Push Press Development", "Push press: 3x5"),
        ("### Run Technique", "Stride drill"),
    ]:
        items3 = ps.parse(f"{heading}\n- {exercise}")
        check(f"3. {heading!r} does not trip substring-based suppression",
              len(items3) == 1 and items3[0].role == ps.PRESCRIPTION_CANDIDATE,
              f"{items3}")

    for heading in ["### Progression", "### Progression Notes", "### Nutrition",
                    "### Nutrition Guidance", "### Safety", "### Safety Notes",
                    "### General Notes"]:
        items4 = ps.parse(f"{heading}\n- Some commentary line here")
        check(f"3. {heading!r} remains a dedicated non-exercise heading",
              items4[0].role == ps.NON_EXERCISE, f"{items4}")


def nested_exercises_independently_classified():
    """PROBLEM 2 - tests 4, 5: nested bullets under a group label are
    independent structural items, and get audited independently."""
    from app.services import plan_structure as ps
    from app.services.contraindications import classify_line, audit_against_profiles
    print(f"\n{BOLD}P2.4-5 — nested exercises are independently classified{RESET}")

    items = ps.parse("- Warm-up\n  - Ankle pogo\n  - Heel-toe rocks")
    check("label bullet + 2 nested exercises = 3 structural items",
          len(items) == 3, f"{items}")
    check("the group label itself is a container, never an unknown exercise",
          items[0].role == ps.CONTAINER, f"{items[0]}")
    check("both nested items are independent prescription candidates",
          items[1].role == ps.PRESCRIPTION_CANDIDATE
          and items[2].role == ps.PRESCRIPTION_CANDIDATE, f"{items}")

    ankle = profiles(["ankle sprain (severity 6/10)"])
    verdict = classify_line(items[1].raw_lines[0], ankle)
    check("4. nested UNKNOWN 'Ankle pogo' under a group label is CONDITIONAL "
          "for an active injury",
          verdict["verdict"] == "conditional", f"{verdict}")

    plan2 = "- Main\n  - Bent over row: 3x8\n  - Bench press: 4x6"
    hamstring = profiles(["hamstring strain (severity 6/10)"])
    findings = audit_against_profiles(plan2, hamstring)
    flagged = {f["line"].strip() for f in findings}
    check("5. nested RECOGNISED unsafe 'Bent over row' is caught under a "
          "group label", "- Bent over row: 3x8" in flagged, f"{flagged}")
    check("5. the safe sibling nested exercise is NOT caught",
          "- Bench press: 4x6" not in flagged, f"{flagged}")


def dosage_continuations_attach_exactly():
    """PROBLEM 2 - tests 6, 7: dosage-only continuations remain attached,
    for both bulleted and numbered parent items."""
    from app.services import plan_structure as ps
    print(f"\n{BOLD}P2.6-7 — dosage-only continuations remain attached{RESET}")

    items = ps.parse("- Ankle pogo\n  3 sets x 20 contacts\n  Rest 45 seconds")
    check("6. one item, both plain continuation lines attached in order",
          len(items) == 1
          and items[0].dosage_lines == ["3 sets x 20 contacts", "Rest 45 seconds"],
          f"{items}")

    items2 = ps.parse("1. Peterson step-down\n   3 sets x 8 each side")
    check("7. numbered item keeps its dosage continuation attached",
          len(items2) == 1 and items2[0].dosage_lines == ["3 sets x 8 each side"],
          f"{items2}")


def block_level_remove_and_replace_exact():
    """PROBLEM 2 REPAIR - tests 8, 9: exact structural block membership on
    removal and replacement, not weak "or" assertions."""
    from app.services import plan_repair
    print(f"\n{BOLD}P2 REPAIR.8-9 — exact block removal/replacement{RESET}")

    plan = (
        "- Sprint intervals\n"
        "  8 x 100m\n"
        "  Rest 90 seconds\n"
        "- Bench press: 4x6\n"
        "- Seated row: 3x8"
    )
    decisions = {0: plan_repair.Replacement(
        original="- Sprint intervals", replacement=None, reason="test removal",
    )}
    removed_plan = plan_repair._apply(plan, decisions)
    lines = removed_plan.splitlines()
    check("8. removing an exercise leaves exactly its two neighbors, nothing else",
          lines == ["- Bench press: 4x6", "- Seated row: 3x8"], f"{lines}")

    decisions2 = {0: plan_repair.Replacement(
        original="- Sprint intervals", replacement="Stationary bike",
        reason="test replace",
    )}
    replaced_plan = plan_repair._apply(plan, decisions2)
    lines2 = replaced_plan.splitlines()
    check("9. replacement carries the exercise's original dosage/context "
          "lines, exactly, right after the new name, then the neighbors "
          "unchanged",
          lines2 == ["- Stationary bike", "  8 x 100m", "  Rest 90 seconds",
                     "- Bench press: 4x6", "- Seated row: 3x8"],
          f"{lines2}")


def repaired_plan_audit_clean_matches_reality():
    """PROBLEM 3 - test 10: audit_clean=True must mean the EXACT returned
    plan re-assesses with no unresolved CONDITIONAL prescription candidate
    and no recognised unsafe movement."""
    from app.services import plan_repair
    from app.services.contraindications import (
        assess_plan, audit_against_profiles, VERDICT_CONDITIONAL,
    )
    print(f"\n{BOLD}P3.10 — audit_clean matches the exact returned plan{RESET}")

    hamstring = ["hamstring strain (severity 6/10)"]
    plan = "- Romanian deadlift: 3x8\n- Bench press: 4x6\n- Ankle pogo"
    r = plan_repair.repair(plan, hamstring)
    check("repair reports audit_clean=True", r.audit_clean is True, f"{r.as_dict()}")

    profs = profiles(hamstring)
    reassessed = assess_plan(r.plan, profs)
    check("re-assessing the EXACT returned string finds no unresolved "
          "CONDITIONAL candidate",
          not any(v["verdict"] == VERDICT_CONDITIONAL for v in reassessed),
          f"plan={r.plan!r} reassessed={reassessed}")
    check("re-auditing the EXACT returned string finds no unsafe movement",
          not audit_against_profiles(r.plan, profs), f"{r.plan!r}")


def adjustment_note_is_not_a_prescription():
    """PROBLEM 3 - test 11: the repair log stays OUT of the workout.

    This used to assert that the appended "Adjustment Notes" block parsed as
    non-exercise. The block is no longer appended at all - it buried the
    session under internal bookkeeping, and every swap is already in
    RepairResult.as_dict(). What matters now is that the returned Markdown is
    only the workout, and that the note builder (still used by callers that
    want the prose) remains structurally non-exercise."""
    from app.services import plan_repair
    from app.services import plan_structure as ps
    print(f"\n{BOLD}P3.11 — the adjustment note stays out of the workout{RESET}")

    hamstring = ["hamstring strain (severity 6/10)"]
    r = plan_repair.repair("- Romanian deadlift: 3x8\n- Bench press: 4x6", hamstring)
    check("no note is appended to the returned plan",
          "\n\n---" not in r.plan and "Adjustment Notes" not in r.plan,
          f"{r.plan!r}")
    check("the swap is still reported in the structured result",
          bool(r.as_dict()["replacements"]), r.as_dict())

    # The builder itself must stay safe for any caller that renders it.
    note = plan_repair._append_note(r)
    note_only = note.split("\n\n---", 1)[1]
    items = ps.parse(note_only)
    check("every structural item inside the note is NON_EXERCISE",
          bool(items) and all(i.role == ps.NON_EXERCISE for i in items), f"{items}")


def instructions_are_never_replaced():
    """PROBLEM 4 - tests 12, 13: standalone safety instructions and a
    rest-day instruction are never treated as exercises during repair."""
    from app.services import plan_repair
    print(f"\n{BOLD}P4.12-13 — instructions are never replaced as exercises{RESET}")

    hamstring = ["hamstring strain (severity 6/10)"]
    plan = (
        "- Bench press: 4x6\n"
        "- Take a well-deserved rest day\n"
        "- Stop if sharp pain occurs\n"
        "- Keep movements controlled"
    )
    r = plan_repair.repair(plan, hamstring)
    live_lines = r.plan.split("\n\n---")[0].splitlines()
    check("12/13. all three instruction lines survive byte-identical",
          "- Take a well-deserved rest day" in live_lines
          and "- Stop if sharp pain occurs" in live_lines
          and "- Keep movements controlled" in live_lines,
          f"{live_lines}")
    check("none of the instruction lines were replaced with an exercise",
          not any(rp.original.strip().lstrip("-* ").lower().startswith(
              ("take a", "stop if", "keep movements")) for rp in r.replacements),
          f"{r.replacements}")
    check("none of the instruction lines were removed",
          not any(txt.strip().lstrip("-* ").lower().startswith(
              ("take a", "stop if", "keep movements")) for txt in r.removed),
          f"{r.removed}")


def nutrition_and_safety_prose_not_audited():
    """PROBLEM 5 - tests 14, 15, 16: audit_against_profiles consumes
    canonical prescription candidates only - prose mentioning a movement
    word is not audited, but a real prescription still is."""
    from app.services.contraindications import audit_against_profiles
    print(f"\n{BOLD}P5.14-16 — the final audit does not re-discover raw lines{RESET}")

    hamstring = profiles(["hamstring strain (severity 6/10)"])
    plan = (
        "### Nutrition\n- Refuel after running with carbohydrates\n"
        "### Safety\n- Squats may aggravate knee pain\n"
        "### Main Workout\n- Back squat: 3x8\n"
    )
    findings = audit_against_profiles(plan, hamstring)
    flagged = {f["line"] for f in findings}
    check("14. nutrition prose mentioning running is not audited as a "
          "running prescription", "- Refuel after running with carbohydrates"
          not in flagged, f"{flagged}")
    check("15. safety prose mentioning squats is not audited as a squat "
          "prescription", "- Squats may aggravate knee pain" not in flagged,
          f"{flagged}")
    check("16. a real squat prescription under a real heading is still "
          "audited", "- Back squat: 3x8" in flagged, f"{flagged}")


def combined_explicit_restriction_preserved():
    """PROBLEM 6 - test 19: a recognised condition does not erase a
    combined, explicitly-stated movement restriction in the same text."""
    from app.services import injury_taxonomy as tax
    from app.services import plan_repair
    print(f"\n{BOLD}P6.19 — combined injury + explicit restriction both reach repair{RESET}")

    constraint = "wrist pain (severity 0/10); avoid jumping"
    p = tax.parse(constraint)
    check("the wrist condition is still recognised",
          p is not None and p.region == "wrist", f"{p}")
    check("the explicit 'avoid jumping' restriction survives alongside it, "
          "even though the wrist complaint alone carries no restriction at "
          "severity 0",
          p is not None and "jumping" in p.restricted_patterns(),
          f"{p.restricted_patterns() if p else None}")

    plan = (
        "- Jumping jacks: 3x30 seconds\n"
        "- Burpees: 3x10\n"
        "- Seated row: 3x8"
    )
    r = plan_repair.repair(plan, [constraint])
    live = r.plan.split("\n\n---")[0]
    check("jumping jacks do not survive the exact final safety audit",
          "Jumping jacks" not in live, f"{live!r}")
    check("burpees do not survive the exact final safety audit",
          "Burpees" not in live, f"{live!r}")
    check("the unrelated safe exercise remains untouched",
          "- Seated row: 3x8" in live, f"{live!r}")
    check("the returned plan is reported audit_clean",
          r.audit_clean is True, f"{r.as_dict()}")


def bounded_regeneration_unchanged():
    """Validation item 8/22: MAX_REGENERATIONS is unchanged and bounded."""
    from app.services import plan_repair
    print(f"\n{BOLD}Validation — MAX_REGENERATIONS remains bounded{RESET}")

    check("MAX_REGENERATIONS is a small positive integer, unchanged at 2",
          plan_repair.MAX_REGENERATIONS == 2, f"{plan_repair.MAX_REGENERATIONS}")


def mutation_checks():
    """Test 20 (this review's own fixes): revert each core fix in
    isolation and confirm the specific bug it fixed reproduces - proof the
    fixes are load-bearing, not just incidentally passing."""
    from app.services import plan_structure as ps
    from app.services import injury_taxonomy as tax
    print(f"\n{BOLD}MUTATION — each of the 6 fixes is load-bearing{RESET}")

    # P1: naive substring heading match reproduces the "Progression Run" bypass.
    original_heading = ps._is_non_exercise_heading
    ps._is_non_exercise_heading = lambda text: "progression" in text.lower()
    try:
        items = ps.parse("### Day 3 - Progression Run\n- Ankle pogo")
        broken = items[0].role == ps.NON_EXERCISE
    finally:
        ps._is_non_exercise_heading = original_heading
    check("MUTATION P1: naive substring heading match reproduces the bypass",
          broken)

    # P2: treating every indented bare line as proven dosage/context
    # regardless of content - "indentation alone is sufficient" again -
    # swallows a nested title-like line as fake dosage of the exercise above
    # it.
    original_cont = ps._is_dosage_or_context
    ps._is_dosage_or_context = lambda body: True
    try:
        items2 = ps.parse("- Ankle pogo\n  Heel-toe rocks")
        broken2 = len(items2) == 1
    finally:
        ps._is_dosage_or_context = original_cont
    check("MUTATION P2: treating every indented line as proven dosage/"
          "context (ignoring content) swallows a nested exercise again",
          broken2)

    # P6: dropping the merged explicit restriction loses "avoid jumping".
    original_parse = tax.parse

    def broken_parse(text, severity=None):
        p = original_parse(text, severity)
        if p is not None:
            p.extra_restricted = set()
        return p

    tax.parse = broken_parse
    try:
        p3 = tax.parse("wrist pain (severity 0/10); avoid jumping")
        broken3 = not p3 or "jumping" not in p3.restricted_patterns()
    finally:
        tax.parse = original_parse
    check("MUTATION P6: dropping the merge loses the combined explicit "
          "restriction", broken3)


# ---------------------------------------------------------------------------
# Third review pass - DEFECTS 1-6 (substring phrases, bare-indented
# swallowing, bare ^stop\b, multi-line bare fallback, raw-line public audit,
# negation-proximity false positives)
# ---------------------------------------------------------------------------

def defect1_phrase_pairs():
    """DEFECT 1 - category PHRASES (not just single-word roots) must be a
    complete normalized heading match, never a substring search."""
    from app.services import plan_structure as ps
    print(f"\n{BOLD}D1 — category phrases are whole-heading matches, not substrings{RESET}")

    non_exercise = [
        "Before You Start", "Before You Begin", "About This Plan",
        "Progression Notes", "General Safety Notes", "How to Use This Plan",
    ]
    for heading in non_exercise:
        items = ps.parse(f"### {heading}\n- Some commentary line here")
        check(f"{heading!r} -> non-exercise",
              len(items) == 1 and items[0].role == ps.NON_EXERCISE, f"{items}")

    exercise_bearing = [
        ("Before You Start Workout", "Ankle pogo"),
        ("Before You Start Running", "Ankle pogo"),
        ("About This Plan Workout", "Ankle pogo"),
        ("Day 3 - Progression Run", "Ankle pogo"),
        ("Running Progression Session", "Ankle pogo"),
    ]
    for heading, exercise in exercise_bearing:
        items = ps.parse(f"### {heading}\n- {exercise}")
        check(f"{heading!r} -> exercise-bearing",
              len(items) == 1 and items[0].role == ps.PRESCRIPTION_CANDIDATE,
              f"{items}")

    # End-to-end: the confirmed failing case from the review.
    from app.services import plan_repair
    plan = "### Before You Start Workout\n- Ankle pogo\n- Bench press: 3x8"
    r = plan_repair.repair(plan, ["ankle sprain, severity 6/10"])
    live = r.plan.split("\n\n---")[0]
    check("end-to-end: bare 'Ankle pogo' under 'Before You Start Workout' "
          "does not survive with audit_clean=True",
          not (r.audit_clean and "- Ankle pogo" in live.splitlines()),
          f"audit_clean={r.audit_clean} live={live!r}")
    check("end-to-end: the neighboring safe exercise is untouched",
          "- Bench press: 3x8" in live, f"{live!r}")


def defect2_bare_indented_adversarial():
    """DEFECT 2 - the 4 required numbered adversarial cases, plus the two
    end-to-end audit_clean cases, plus normalized group-label semantics."""
    from app.services import plan_structure as ps
    from app.services import plan_repair
    print(f"\n{BOLD}D2 — bare indented exercises are never silently swallowed{RESET}")

    # 1. One prescription block with two continuations.
    items1 = ps.parse("- Ankle pogo\n  3 sets x 20 contacts\n  Rest 45 seconds")
    check("1. exactly one item; both continuations attached in order",
          len(items1) == 1
          and items1[0].dosage_lines == ["3 sets x 20 contacts", "Rest 45 seconds"],
          f"{items1}")

    # 2. The parent is a container; both movements are independent candidates.
    items2 = ps.parse("- Warm-up sequence\n  Ankle pogo\n  Heel-toe rocks")
    check("2. label is a container, both nested lines are independent "
          "candidates",
          len(items2) == 3 and items2[0].role == ps.CONTAINER
          and items2[1].role == ps.PRESCRIPTION_CANDIDATE
          and items2[2].role == ps.PRESCRIPTION_CANDIDATE,
          f"{items2}")

    # 3. "Peterson step-down" is a candidate; the coaching cue attaches to it.
    items3 = ps.parse("- Mobility\n  Peterson step-down\n  Keep the knee aligned")
    check("3. 'Peterson step-down' is an independent candidate owning the "
          "coaching cue",
          len(items3) == 2 and items3[0].role == ps.CONTAINER
          and items3[1].role == ps.PRESCRIPTION_CANDIDATE
          and items3[1].body == "Peterson step-down"
          and items3[1].dosage_lines == ["Keep the knee aligned"],
          f"{items3}")

    # 4. "Sprint intervals" is independently audited and owns the dosage.
    items4 = ps.parse("- Main\n  Sprint intervals\n  8 x 100m\n  Rest 90 seconds")
    check("4. 'Sprint intervals' owns its dosage/rest context",
          len(items4) == 2 and items4[1].body == "Sprint intervals"
          and items4[1].dosage_lines == ["8 x 100m", "Rest 90 seconds"],
          f"{items4}")

    # 5. Active ankle injury, indented bare "Ankle pogo" - audit_clean=True
    # must not coexist with the movement surviving unresolved.
    ankle = ["ankle sprain, severity 6/10"]
    r5 = plan_repair.repair("- Warm-up sequence\n  Ankle pogo\n- Bench press: 3x8", ankle)
    live5 = r5.plan.split("\n\n---")[0]
    check("5. active ankle injury: indented bare 'Ankle pogo' cannot return "
          "with audit_clean=True",
          not (r5.audit_clean and "  Ankle pogo" in live5.splitlines()),
          f"audit_clean={r5.audit_clean} live={live5!r}")

    # 6. Active hamstring injury, indented bare "Sprint intervals" - same
    # invariant.
    hamstring = ["hamstring strain, severity 6/10"]
    r6 = plan_repair.repair("- Main\n  Sprint intervals\n  8 x 100m\n- Bench press: 4x6",
                            hamstring)
    live6 = r6.plan.split("\n\n---")[0]
    check("6. active hamstring injury: indented bare 'Sprint intervals' "
          "cannot return with audit_clean=True",
          not (r6.audit_clean and "  Sprint intervals" in live6.splitlines()),
          f"audit_clean={r6.audit_clean} live={live6!r}")

    # Normalized group-label semantics - not a long list of exact strings.
    for label in ["Warm-up", "Warm-up sequence", "Main", "Main workout",
                  "Mobility", "Mobility block", "Activation", "Strength",
                  "Conditioning", "Finisher", "Circuit 1", "Block A",
                  "Cooldown", "Recovery block"]:
        items = ps.parse(f"- {label}\n  Ankle pogo")
        check(f"group label {label!r} recognised, nested exercise independent",
              len(items) == 2 and items[0].role == ps.CONTAINER
              and items[1].role == ps.PRESCRIPTION_CANDIDATE, f"{items}")

    # Requirement 6: removing/replacing a parent label never carries an
    # unaudited movement line forward as context - the container is never
    # itself a repair target, so nothing it "carries" is ever unaudited.
    r7 = plan_repair.repair("- Warm-up sequence\n  Ankle pogo\n  Heel-toe rocks",
                            ankle)
    live7 = r7.plan.split("\n\n---")[0].splitlines()
    check("container line itself is never treated as an exercise needing "
          "replacement", "- Warm-up sequence" in live7, f"{live7}")
    check("both nested unknown movements were independently resolved",
          "  Ankle pogo" not in live7 and "  Heel-toe rocks" not in live7,
          f"{live7}")


def defect3_keyword_collision_pairs():
    """DEFECT 3 - narrowed ^stop\\b, plus paired exercise-name checks for
    every broad instruction keyword the review named."""
    from app.services import plan_structure as ps
    from app.services import plan_repair
    print(f"\n{BOLD}D3 — instruction keywords never blindly swallow exercise names{RESET}")

    stop_instructions = [
        "Stop if sharp pain occurs", "Stop when symptoms increase",
        "Stop immediately if you feel pain",
        "Stop the exercise if discomfort worsens",
    ]
    for line in stop_instructions:
        check(f"{line!r} -> instruction",
              ps.classify_single_line(line) == ps.INSTRUCTION,
              ps.classify_single_line(line))

    stop_prescriptions = [
        "Stop-and-go runs: 6x20m", "Stop-start sprint drill",
        "Stop and go shuttle runs", "Start-stop acceleration drill",
    ]
    for line in stop_prescriptions:
        check(f"{line!r} -> prescription candidate",
              ps.classify_single_line(line) == ps.PRESCRIPTION_CANDIDATE,
              ps.classify_single_line(line))

    # Paired keyword collision tests - one instruction, one exercise, per
    # keyword the review explicitly named.
    keyword_pairs = [
        ("Rest 90 seconds", ps.INSTRUCTION, "Rest-pause squat", ps.PRESCRIPTION_CANDIDATE),
        ("Recovery: 60 seconds", ps.INSTRUCTION, "Recovery run: 20 minutes", ps.PRESCRIPTION_CANDIDATE),
        ("Progression: add one set", ps.INSTRUCTION, "Progression run", ps.PRESCRIPTION_CANDIDATE),
        ("Tempo: controlled", ps.INSTRUCTION, "Tempo run: 20 minutes", ps.PRESCRIPTION_CANDIDATE),
        ("Focus on controlled form", ps.INSTRUCTION, "Push press: 3x5", ps.PRESCRIPTION_CANDIDATE),
        ("Focus on controlled form", ps.INSTRUCTION, "Overhead press: 3x8", ps.PRESCRIPTION_CANDIDATE),
    ]
    for instr_line, instr_expected, ex_line, ex_expected in keyword_pairs:
        check(f"{instr_line!r} -> instruction", ps.classify_single_line(instr_line) == instr_expected,
              ps.classify_single_line(instr_line))
        check(f"{ex_line!r} -> prescription candidate", ps.classify_single_line(ex_line) == ex_expected,
              ps.classify_single_line(ex_line))

    # End-to-end: a severe hamstring injury must not receive stop/start
    # running drills with audit_clean=True.
    plan = "### Main Workout\n- Stop-and-go runs: 6x20m\n- Bench press: 3x8"
    r = plan_repair.repair(plan, ["hamstring strain, severity 6/10"])
    live = r.plan.split("\n\n---")[0]
    check("end-to-end: stop/start running drill does not survive an active "
          "hamstring injury with audit_clean=True",
          not (r.audit_clean and "Stop-and-go runs" in live),
          f"audit_clean={r.audit_clean} live={live!r}")
    check("end-to-end: the neighboring safe exercise is untouched",
          "- Bench press: 3x8" in live, f"{live!r}")


def defect4_bare_fallback_scope():
    """DEFECT 4 - the bare-candidate fallback only ever applies to a single,
    unstructured, exercise-shaped line - never a multi-line document."""
    from app.services.contraindications import audit_against_profiles
    print(f"\n{BOLD}D4 — bare-candidate fallback is scoped to true single-line probes{RESET}")

    hamstring = profiles(["hamstring strain, severity 6/10"])

    # 1 & 2. Bare replacement candidate and a single bullet both remain
    # auditable - the fallback must not have been thrown out entirely.
    check("1. bare replacement candidate 'Bent over row' remains auditable",
          bool(audit_against_profiles("Bent over row", hamstring)))
    check("2. single bullet '- Bent over row' remains auditable",
          bool(audit_against_profiles("- Bent over row", hamstring)))

    # 3. A Nutrition-only document mentioning running produces no finding.
    nutrition_only = "### Nutrition\n- Refuel after running with carbohydrates"
    check("3. Nutrition-only document mentioning running: no finding",
          not audit_against_profiles(nutrition_only, hamstring),
          f"{audit_against_profiles(nutrition_only, hamstring)}")

    # 4. A Safety-only document mentioning squats/sprinting produces no
    # finding.
    safety_only = "### Safety\n- Squats may aggravate the injury\n- Sprinting may aggravate it too"
    check("4. Safety-only document mentioning squats/sprinting: no finding",
          not audit_against_profiles(safety_only, hamstring),
          f"{audit_against_profiles(safety_only, hamstring)}")

    # 5. A multi-line non-exercise document is never a synthetic line-zero
    # exercise - two genuinely bare, unstructured, non-blank lines with no
    # markers at all (never parsed into any structural item either way).
    multiline_prose = "Refuel with carbohydrates after training.\nStay hydrated throughout the day."
    check("5. multi-line non-exercise prose: no synthetic line-zero finding",
          not audit_against_profiles(multiline_prose, hamstring),
          f"{audit_against_profiles(multiline_prose, hamstring)}")

    # 6. Existing replacement validation still rejects unsafe catalogue
    # candidates - a bare, definitely-restricted name is still caught.
    check("6. replacement validation still rejects an unsafe bare candidate",
          bool(audit_against_profiles("Romanian deadlift", hamstring)))


def defect5_audit_entry_point_consistency():
    """DEFECT 5 - audit_plan() and audit_against_profiles() must agree on
    which structural line is the prescription; neither may treat
    NON_EXERCISE/INSTRUCTION/CONTAINER content as a prescription."""
    from app.services import contraindications as c
    print(f"\n{BOLD}D5 — public audit entry points agree on canonical structure{RESET}")

    constraint = ["hamstring strain, severity 6/10"]
    hamstring = profiles(constraint)
    plan = (
        "### Nutrition\n- Refuel after running with carbohydrates\n\n"
        "### Safety\n- Sprinting may aggravate the injury\n\n"
        "### Main Workout\n- Sprint intervals: 6x20m"
    )
    f_pattern = c.audit_against_profiles(plan, hamstring)
    f_public = c.audit_plan(plan, constraint)

    check("Nutrition bullet not flagged by audit_against_profiles",
          not any("Refuel after running" in f["line"] for f in f_pattern), f"{f_pattern}")
    check("Nutrition bullet not flagged by audit_plan",
          not any("Refuel after running" in f["line"] for f in f_public), f"{f_public}")
    check("Safety bullet not flagged by audit_against_profiles",
          not any("Sprinting may aggravate" in f["line"] for f in f_pattern), f"{f_pattern}")
    check("Safety bullet not flagged by audit_plan",
          not any("Sprinting may aggravate" in f["line"] for f in f_public), f"{f_public}")
    check("Sprint prescription IS flagged by audit_against_profiles",
          any("Sprint intervals" in f["line"] for f in f_pattern), f"{f_pattern}")
    check("Sprint prescription IS flagged by audit_plan",
          any("Sprint intervals" in f["line"] for f in f_public), f"{f_public}")
    check("both entry points agree on the flagged structural line number",
          {f["line_no"] for f in f_pattern if "Sprint intervals" in f["line"]}
          <= {f["line_no"] for f in f_public if "Sprint intervals" in f["line"]},
          f"pattern={f_pattern} public={f_public}")

    # A plan containing ONLY Nutrition/Safety sections.
    only_commentary = (
        "### Nutrition\n- Refuel after running with carbohydrates\n\n"
        "### Safety\n- Sprinting may aggravate the injury"
    )
    check("Nutrition+Safety-only plan: audit_against_profiles finds nothing",
          not c.audit_against_profiles(only_commentary, hamstring))
    check("Nutrition+Safety-only plan: audit_plan finds nothing",
          not c.audit_plan(only_commentary, constraint))


def defect6_negation_grammar_pairs():
    """DEFECT 6 - a restriction verb must directly govern the movement, not
    merely appear somewhere before it in the same clause."""
    from app.services import injury_taxonomy as tax
    from app.services import plan_repair
    print(f"\n{BOLD}D6 — negation grammar, not negation proximity{RESET}")

    positive = [
        "no jumping", "avoid jumping", "do not jump", "don't jump",
        "cannot jump", "can't jump", "skip jumping", "without jumping",
        "avoid high-impact jumping", "avoid overhead pressing",
        "no running or sprinting",
    ]
    for text in positive:
        r = tax.parse_explicit_restriction(text)
        check(f"{text!r} -> explicit restriction", r is not None, r)

    negative = [
        "no pain when jumping", "no discomfort during running",
        "not avoiding jumping", "I do not have pain when running",
        "jumping does not hurt", "running is not a problem",
        "no restriction on jumping", "no issue with overhead pressing",
    ]
    for text in negative:
        r = tax.parse_explicit_restriction(text)
        check(f"{text!r} -> NOT a restriction", r is None, r)

    # A. wrist pain severity 0/10; avoid jumping -> jumping exercises removed.
    plan = "- Jumping jacks: 3x30 seconds\n- Burpees: 3x10\n- Seated row: 3x8"
    rA = plan_repair.repair(plan, ["wrist pain severity 0/10; avoid jumping"])
    liveA = rA.plan.split("\n\n---")[0]
    check("A. jumping jacks removed/replaced", "Jumping jacks" not in liveA, f"{liveA!r}")
    check("A. burpees removed/replaced", "Burpees" not in liveA, f"{liveA!r}")
    check("A. unrelated safe exercise remains", "- Seated row: 3x8" in liveA, f"{liveA!r}")
    check("A. audit_clean is True", rA.audit_clean is True, f"{rA.as_dict()}")

    # B. wrist pain severity 0/10; no pain when jumping -> wrist profile may
    # remain, but "jumping" must not appear in extra_restricted from that
    # phrase alone.
    pB = tax.parse("wrist pain severity 0/10; no pain when jumping")
    check("B. wrist condition still recognised", pB is not None and pB.region == "wrist", pB)
    check("B. 'jumping' is NOT in extra_restricted",
          pB is not None and "jumping" not in pB.extra_restricted,
          pB.extra_restricted if pB else None)

    # C. "no pain when jumping" alone must not create an ExplicitRestriction.
    pC = tax.parse_explicit_restriction("no pain when jumping")
    check("C. standalone 'no pain when jumping' creates no ExplicitRestriction",
          pC is None, pC)


ADVERSARIAL_PAIRS = [
    ("heading", "Progression Notes", "non-exercise",
     "Progression Run", "exercise-bearing"),
    ("heading", "Before You Start", "non-exercise",
     "Before You Start Workout", "exercise-bearing"),
    ("instruction/exercise", "Stop if pain occurs", "instruction",
     "Stop-and-go runs", "prescription"),
    ("instruction/exercise", "Rest 90 seconds", "instruction",
     "Rest-pause squat", "prescription"),
    ("instruction/exercise", "Progression: add one set", "instruction",
     "Progression run", "prescription"),
    ("instruction/exercise", "Recovery: 60 seconds", "instruction",
     "Recovery run: 20 minutes", "prescription"),
    ("continuation/candidate", "3 sets x 8 reps", "dosage continuation",
     "Peterson step-down", "prescription candidate"),
    ("continuation/candidate", "Keep the spine neutral", "coaching continuation",
     "Heel-toe rocks", "prescription candidate"),
]


def adversarial_pair_matrix():
    """The compact table-driven matrix required by the review: each row is
    two nearby forms that MUST resolve to different structural outcomes."""
    from app.services import plan_structure as ps
    print(f"\n{BOLD}Adversarial pair matrix{RESET}")

    _NON_EX_ROLES = {ps.NON_EXERCISE, ps.HEADING}
    _EX_ROLES = {ps.PRESCRIPTION_CANDIDATE, ps.CONTAINER}

    for category, a_text, a_kind, b_text, b_kind in ADVERSARIAL_PAIRS:
        if category == "heading":
            a_role = ps.parse(f"### {a_text}\n- Ankle pogo")[0].role
            b_items = ps.parse(f"### {b_text}\n- Ankle pogo")
            b_role = b_items[0].role
            check(f"[{category}] {a_text!r} ({a_kind}) suppresses its bullet",
                  a_role == ps.NON_EXERCISE, a_role)
            check(f"[{category}] {b_text!r} ({b_kind}) does not suppress its bullet",
                  b_role == ps.PRESCRIPTION_CANDIDATE, b_role)
        elif category == "instruction/exercise":
            a_role = ps.classify_single_line(a_text)
            b_role = ps.classify_single_line(b_text)
            check(f"[{category}] {a_text!r} -> {a_kind}",
                  a_role == ps.INSTRUCTION, a_role)
            check(f"[{category}] {b_text!r} -> {b_kind}",
                  b_role == ps.PRESCRIPTION_CANDIDATE, b_role)
        elif category == "continuation/candidate":
            plan = f"- Ankle pogo\n  {a_text}\n  {b_text}"
            items = ps.parse(plan)
            check(f"[{category}] {a_text!r} attaches as {a_kind}",
                  len(items) == 2 and a_text in items[0].dosage_lines, f"{items}")
            check(f"[{category}] {b_text!r} becomes its own {b_kind}",
                  len(items) == 2 and items[1].body == b_text
                  and items[1].role == ps.PRESCRIPTION_CANDIDATE, f"{items}")


def mutation_checks_round_two():
    """Mutations 3-6 for this review's own fixes - each must make its
    corresponding regression test fail when the fix is reverted."""
    from app.services import plan_structure as ps
    from app.services import contraindications as c
    from app.services import injury_taxonomy as tax
    print(f"\n{BOLD}MUTATION — round two (D3-D6){RESET}")

    # D3: reintroduce bare ^stop\b.
    original_cue = ps._SAFETY_CUE
    ps._SAFETY_CUE = re.compile(r"^\s*stop\b", re.I)
    try:
        broken = ps.classify_single_line("Stop-and-go runs: 6x20m") == ps.INSTRUCTION
    finally:
        ps._SAFETY_CUE = original_cue
    check("MUTATION D3: bare ^stop\\b reclassifies 'Stop-and-go runs' as an "
          "instruction again", broken)

    # D4: allow the multi-line bare fallback unconditionally - the ORIGINAL
    # defect was gating on `not items` alone, ignoring `all_items` entirely.
    original_probe = c._should_use_bare_fallback
    c._should_use_bare_fallback = lambda plan_text, all_items, items: not items
    try:
        findings = c.audit_against_profiles(
            "### Nutrition\n- Refuel after running with carbohydrates",
            profiles(["hamstring strain, severity 6/10"]),
        )
        broken2 = bool(findings)
    finally:
        c._should_use_bare_fallback = original_probe
    check("MUTATION D4: unconditional bare fallback flags the Nutrition-only "
          "document again", broken2)

    # D5: reintroduce a raw-line scan for the name/intensity checks.
    original_candidates = c._prescription_candidates
    c._prescription_candidates = lambda plan_text: [
        (i, raw) for i, raw in enumerate((plan_text or "").splitlines())
        if raw.strip()
    ]
    try:
        broken3 = bool(c.audit_plan(
            "### Safety\n- Sprinting may aggravate the injury",
            ["hamstring strain, severity 6/10"],
        ))
    finally:
        c._prescription_candidates = original_candidates
    check("MUTATION D5: raw-line scanning flags Safety-section prose again",
          broken3)

    # D6: reintroduce plain negation-proximity (no blocking-word check).
    original_negates = tax._negates
    tax._negates = lambda lowered, word: re.search(
        rf"\b{tax._NEGATION}\b[^.?!;]{{0,20}}?\b{re.escape(word)}\b", lowered
    ) is not None
    try:
        r = tax.parse_explicit_restriction("no pain when jumping")
        broken4 = r is not None and "jumping" in r.explicit_patterns
    finally:
        tax._negates = original_negates
    check("MUTATION D6: negation-proximity treats 'no pain when jumping' as "
          "a jumping restriction again", broken4)


# ---------------------------------------------------------------------------
# Fourth review pass - live-observed regression: decorated bold group
# labels ("- **Warm-up (10 min)** - 🏋️‍♂️") were unrecognised and treated
# as unknown prescription candidates.
# ---------------------------------------------------------------------------

def decorated_group_labels_recognised():
    """
    Every observed live-output format must resolve to a container WHEN there
    is structural evidence for it - reserved grammar, or independently-
    parsed nested children - and never merely from vocabulary overlap. A
    decorated label tested in total isolation, with no reserved grammar and
    no children, is honestly AMBIGUOUS, not confidently CONTAINER - that is
    the entire point of this architecture: "Vertical Push (25 min)" alone
    proves nothing more than "Power Pull (2 min)" alone does.
    """
    from app.services import plan_structure as ps
    print(f"\n{BOLD}Decorated bold group labels (duration + emoji + en dash){RESET}")

    # Reserved-grammar heads resolve to a definite container even standing
    # alone - "warm-up"/"cool-down" are recognised by name, not by having
    # children.
    for line in ["- **Warm-up (10 min)** – 🏋️‍♂️", "- **Cool-down (5 min)** – 🧘‍♂️"]:
        items = ps.parse(line)
        check(f"{line!r} -> definite container (reserved grammar, no "
              f"children needed)",
              len(items) == 1 and items[0].role == ps.DEFINITE_CONTAINER, f"{items}")

    # Non-reserved decorated labels - "Strength - Push", "Core - Stability",
    # "Vertical Push", "Low-Impact Cardio" - are AMBIGUOUS in isolation...
    non_reserved = [
        "- **Strength – Push (15 min)** – 🏋️‍♂️",
        "- **Core – Stability (15 min)** – 🧘‍♂️",
        "- **Vertical Push (25 min)** – 🏋️‍♂️",
        "- **Low-Impact Cardio (20 min)** – 🏃‍♂️",
        "- **Push (20 min)**", "- **Pull (20 min)**",
        "- **Core – Push (15 min)**",
    ]
    for line in non_reserved:
        items = ps.parse(line)
        check(f"{line!r} alone (no children) -> ambiguous, not assumed "
              f"container", len(items) == 1 and items[0].role == ps.AMBIGUOUS,
              f"{items}")

    # ...and become definite containers the instant they gain independently-
    # parsed children, exactly as they do in real generated plans.
    for label in ["Strength – Push (15 min)", "Core – Stability (15 min)",
                  "Vertical Push (25 min)", "Low-Impact Cardio (20 min)",
                  "Push (20 min)", "Core – Push (15 min)"]:
        plan = f"- **{label}** – 🏋️‍♂️\n  - Some Nested Drill"
        items = ps.parse(plan)
        # Asserts the BEHAVIOUR (promoted, and the child really is linked to
        # it) rather than the exact wording of the `evidence` debug string,
        # which is diagnostic output and free to be reworded.
        check(f"{label!r} + a nested PRESCRIPTION child -> promoted to "
              f"definite container",
              len(items) == 2 and items[0].role == ps.DEFINITE_CONTAINER
              and items[1].role == ps.PRESCRIPTION_LIKE
              and items[1].parent_id == items[0].line_numbers[0],
              f"{items}")

    # Reserved-grammar heads not in the earlier list: Core, Cardio, Mobility
    # ARE recognised by name alone (word-for-word in _GROUP_LABEL).
    for line in ["- **Core (15 min)**", "- **Cardio (20 min)**", "- **Mobility (10 min)**"]:
        items = ps.parse(line)
        check(f"{line!r} -> definite container (reserved grammar)",
              items[0].role == ps.DEFINITE_CONTAINER, items)

    # Warm-up/cooldown specifically, decorated, must remain exercise-CAPABLE
    # sections - i.e. the label itself is a definite container, but what is
    # nested beneath it is still independently auditable.
    warm_plan = "- **Warm-up (10 min)** – 🏋️‍♂️\n  - Arm circles → 2 × 30 s each direction"
    warm_items = ps.parse(warm_plan)
    check("decorated Warm-up label is a definite container",
          warm_items[0].role == ps.DEFINITE_CONTAINER, warm_items)
    check("the nested exercise under it is an independent prescription-like "
          "item", warm_items[1].role == ps.PRESCRIPTION_LIKE
          and warm_items[1].body == "Arm circles → 2 × 30 s each direction"
          and warm_items[1].parent_id == warm_items[0].line_numbers[0],
          warm_items)

    cool_plan = "- **Cool-down (5 min)** – 🧘‍♂️\n  - Chest stretch, triceps stretch"
    cool_items = ps.parse(cool_plan)
    check("decorated Cool-down label is a definite container",
          cool_items[0].role == ps.DEFINITE_CONTAINER, cool_items)
    check("the nested exercise under it is an independent prescription-like "
          "item", cool_items[1].role == ps.PRESCRIPTION_LIKE, cool_items)

    # Dosage continuation handling remains intact underneath a decorated
    # label - a nested exercise's OWN plain-text dosage still attaches to it,
    # not to the label, and multiple siblings under one label all get the
    # SAME parent (the stack-based ancestor tracking, not just the first).
    dosage_plan = (
        "- **Strength – Push (15 min)** – 🏋️‍♂️\n"
        "  - Dumbbell Shoulder Press\n"
        "    3 sets x 12 reps\n"
        "    Rest 90 seconds\n"
        "  - Incline Bench Press\n"
        "    3 sets x 10 reps"
    )
    dosage_items = ps.parse(dosage_plan)
    check("the label is a definite container (has 2 children)",
          len(dosage_items) == 3 and dosage_items[0].role == ps.DEFINITE_CONTAINER,
          f"{dosage_items}")
    check("dosage continuation attaches to the FIRST nested exercise, not "
          "the decorated label",
          dosage_items[1].role == ps.PRESCRIPTION_LIKE
          and dosage_items[1].dosage_lines == ["3 sets x 12 reps", "Rest 90 seconds"],
          f"{dosage_items}")
    check("dosage continuation attaches to the SECOND nested exercise too",
          dosage_items[2].role == ps.PRESCRIPTION_LIKE
          and dosage_items[2].dosage_lines == ["3 sets x 10 reps"],
          f"{dosage_items}")
    check("both nested exercises share the SAME parent (the label)",
          dosage_items[1].parent_id == dosage_items[0].line_numbers[0]
          and dosage_items[2].parent_id == dosage_items[0].line_numbers[0],
          f"{dosage_items}")

    # --- negative controls: real exercises with similar bold/wording must
    # NOT become containers or ambiguous, with or without decoration nearby,
    # because they carry no duration/decoration signal at all. ---
    negative = [
        "- **Dumbbell Shoulder Press** 3 × 12",
        "- **Progression Run** 6 × 200m",
        "- **Pallof Press** 3 × 12",
        "- **Rest-pause Squat** 3 × 8",
        "- Progression run",
        "- Tempo run",
        "- Pallof press",
        "- Rest-pause squat",
        "- Strength-endurance deadlifts: 3x12",
    ]
    for line in negative:
        items = ps.parse(line)
        check(f"{line!r} remains prescription-like (negative control)",
              len(items) == 1 and items[0].role == ps.PRESCRIPTION_LIKE,
              f"{items}")

    # A bold exercise immediately followed by a SEPARATE decorated label
    # bullet - the exercise must not leak into the label's classification
    # or vice versa.
    mixed_plan = (
        "- **Push Press** 3 × 5\n"
        "- **Cool-down (5 min)** – 🧘‍♂️"
    )
    mixed_items = ps.parse(mixed_plan)
    check("a real bold exercise next to a decorated label: both classified "
          "independently and correctly",
          mixed_items[0].role == ps.PRESCRIPTION_LIKE
          and mixed_items[1].role == ps.DEFINITE_CONTAINER, f"{mixed_items}")


def decorated_group_label_end_to_end():
    """The exact live-observed shape, through the full repair pipeline: the
    label bullets must never be treated as unknown exercises requiring
    replacement, and real nested exercises must still be safety-audited."""
    from app.services import plan_repair
    from app.services.contraindications import audit_against_profiles, assess_plan, VERDICT_CONDITIONAL
    print(f"\n{BOLD}Decorated group labels - end-to-end repair{RESET}")

    hamstring = ["upper hamstring strain, left leg, severity 6/10"]
    plan = (
        "### Day 1\n"
        "- **Warm-up (10 min)** – 🏋️‍♂️\n"
        "  - Arm circles → 2 × 30 s each direction\n\n"
        "- **Strength – Push (15 min)** – 🏋️‍♂️\n"
        "  - Dumbbell Shoulder Press 3 × 12\n"
        "  - Incline Dumbbell Bench Press 3 × 10\n\n"
        "- **Cool-down (5 min)** – 🧘‍♂️\n"
        "  - Chest stretch, triceps stretch\n\n"
        "### Day 2\n"
        "- **Core – Stability (15 min)** – 🧘‍♂️\n"
        "  - Pallof Press (cable) 3 × 12 each side\n"
        "  - Side Plank 3 × 30 s each side\n\n"
        "- **Vertical Push (25 min)** – 🏋️‍♂️\n"
        "  - Seated Dumbbell Shoulder Press 4 × 10\n\n"
        "- **Low-Impact Cardio (20 min)** – 🏃‍♂️\n"
        "  - Stationary bike, steady pace"
    )
    r = plan_repair.repair(plan, hamstring)
    live = r.plan.split("\n\n---")[0]

    for label in ["- **Warm-up (10 min)** – 🏋️‍♂️", "- **Strength – Push (15 min)** – 🏋️‍♂️",
                  "- **Cool-down (5 min)** – 🧘‍♂️", "- **Core – Stability (15 min)** – 🧘‍♂️",
                  "- **Vertical Push (25 min)** – 🏋️‍♂️", "- **Low-Impact Cardio (20 min)** – 🏃‍♂️"]:
        check(f"group label survives untouched: {label!r}", label in live, live)

    check("safe nested exercises (Dumbbell Shoulder Press, Pallof Press, "
          "Side Plank, Seated Dumbbell Shoulder Press, Stationary bike) "
          "are untouched",
          "Dumbbell Shoulder Press 3 × 12" in live
          and "Pallof Press (cable) 3 × 12 each side" in live
          and "Side Plank 3 × 30 s each side" in live
          and "Seated Dumbbell Shoulder Press 4 × 10" in live
          and "Stationary bike, steady pace" in live, live)

    check("far fewer replacements than the live-observed flood (2, not 40+)",
          len(r.replacements) <= 4, f"{[x.original for x in r.replacements]}")

    profs = profiles(hamstring)
    check("exact-final-plan re-audit: no unsafe movement",
          not audit_against_profiles(r.plan, profs), r.plan)
    check("exact-final-plan re-audit: no unresolved CONDITIONAL candidate",
          not any(v["verdict"] == VERDICT_CONDITIONAL for v in assess_plan(r.plan, profs)),
          r.plan)
    check("audit_clean is True", r.audit_clean is True, r.as_dict())

    # Healthy user: byte-identical, decorated labels and all.
    healthy = plan_repair.repair(plan, [])
    check("healthy user: plan with decorated labels is returned byte-identical",
          healthy.plan == plan, healthy.plan)

    # An actual unsafe nested exercise under a decorated label must still be
    # caught (safety invariant unchanged: active injury + genuinely unsafe
    # movement => flagged/removed, never silently kept because it happened
    # to sit under a container).
    unsafe_plan = (
        "- **Strength – Pull (15 min)** – 🏋️‍♂️\n"
        "  - Bent over row: 3 × 8"
    )
    r2 = plan_repair.repair(unsafe_plan, hamstring)
    live2 = r2.plan.split("\n\n---")[0]
    check("a genuinely unsafe exercise nested under a decorated label is "
          "still caught and repaired",
          "Bent over row" not in live2, live2)
    check("the decorated label itself survives",
          "- **Strength – Pull (15 min)** – 🏋️‍♂️" in live2, live2)


# ---------------------------------------------------------------------------
# Sixth review pass - architecture rework: AMBIGUOUS is a first-class
# structural result. plan_structure no longer asks movement_ontology
# anything; it only ever says "definite" or "ambiguous", and resolves
# ambiguity purely from structural evidence (reserved grammar, or
# independently-parsed children). Safety and quality resolve the remaining
# ambiguity differently, through safety_subjects()/quality_subjects().
# ---------------------------------------------------------------------------

def plan_structure_has_no_movement_ontology_dependency():
    """The parser must not import movement_ontology at all - not even
    lazily - and must not recognise a name it has never seen through any
    ontology lookup. "Power Pull"/"Leg Pull" are deliberately absent from
    movement_ontology's own vocabulary; if plan_structure still resolved
    them definitely, it would be consulting the ontology somewhere."""
    import inspect
    import re as _re
    from app.services import plan_structure as ps
    print(f"\n{BOLD}plan_structure has no movement-ontology dependency{RESET}")

    source = inspect.getsource(ps)
    # An actual import (top-level or lazy, inside a function) - not the
    # word appearing in a comment/docstring explaining that it is NOT used,
    # which this module's own docstring does at length.
    import_pattern = _re.compile(
        r"^\s*(?:from\s+\S*movement_ontology\S*\s+import|import\s+\S*movement_ontology\S*)",
        _re.M,
    )
    check("no import of movement_ontology anywhere in plan_structure.py",
          not import_pattern.search(source), "found an import statement")

    for name in ["Power Pull", "Leg Pull", "Completely New Drill"]:
        items = ps.parse(f"- **{name} (2 min)** – 🏋️‍♂️")
        check(f"{name!r} (never seen by movement_ontology) is structurally "
              f"AMBIGUOUS, not silently resolved either way",
              items[0].role == ps.AMBIGUOUS, items)


def strong_container_and_ambiguous_leaf_invariants():
    """Section 9's required cases: strong containers resolve definitely by
    structure; ambiguous leaves stay ambiguous and are resolved differently
    per consumer, never guessed at parse time."""
    from app.services import plan_structure as ps
    print(f"\n{BOLD}Strong containers vs. ambiguous leaves{RESET}")

    # Strong containers: parent definite container, child prescription-like.
    strong = ps.parse("- **Warm-up (10 min)** – 🏋️\n  - Arm circles\n  - March in place")
    check("parent is a definite container",
          strong[0].role == ps.DEFINITE_CONTAINER, strong)
    check("both children are prescription-like, both parented to the label",
          strong[1].role == ps.PRESCRIPTION_LIKE
          and strong[2].role == ps.PRESCRIPTION_LIKE
          and strong[1].parent_id == strong[0].line_numbers[0]
          and strong[2].parent_id == strong[0].line_numbers[0],
          strong)

    # Ambiguous leaves: structurally ambiguous, standing alone.
    for name in ["Power Pull", "Leg Pull", "Completely New Drill"]:
        items = ps.parse(f"- **{name} (2 min)** – 🏋️")
        check(f"{name!r} is structurally ambiguous",
              items[0].role == ps.AMBIGUOUS, items)

    # Known exercises must enter safety subjects regardless of decoration -
    # decorated or plain, all of these are real, ontology-recognised moves.
    known = ["Push-up", "Pull-up", "High Pull", "Push Press", "Side Plank",
             "Jump Squat"]
    for name in known:
        decorated = ps.parse(f"- **{name} (2 min)** – 🏋️")
        plain = ps.parse(f"- {name}")
        subjects_decorated = ps.safety_subjects(decorated, constraints_active=True)
        subjects_plain = ps.safety_subjects(plain, constraints_active=True)
        check(f"{name!r} (decorated) is a safety subject under an active "
              f"constraint", len(subjects_decorated) == 1, decorated)
        check(f"{name!r} (plain) is a safety subject under an active "
              f"constraint", len(subjects_plain) == 1, plain)

    # Non-exercise content stays definite non-exercise/instruction and
    # never enters the safety projection, active constraint or not.
    non_exercise_plan = (
        "### Nutrition\n- Eat sufficient protein\n\n"
        "### Progression\n- Add two reps next week\n\n"
        "### Safety\n- Stop if sharp pain occurs\n\n"
        "- Rest 90 seconds"
    )
    ne_items = ps.parse(non_exercise_plan)
    ne_subjects = ps.safety_subjects(ne_items, constraints_active=True)
    check("nutrition/progression/safety/instruction content produces zero "
          "safety subjects even with a constraint active",
          not ne_subjects, f"items={ne_items} subjects={ne_subjects}")


def projection_invariant_and_exact_final_plan_invariant():
    """Section 9's two closing invariants, tested directly against
    assess_plan()/audit_against_profiles() rather than only helper output."""
    from app.services import plan_structure as ps
    from app.services import plan_repair
    from app.services.contraindications import (
        assess_plan, audit_against_profiles, VERDICT_CONDITIONAL,
    )
    print(f"\n{BOLD}Projection invariant and exact-final-plan invariant{RESET}")

    plan = (
        "- **Power Pull (2 min)** – 🏋️\n"
        "- **Warm-up (10 min)** – 🏋️\n"
        "  - Arm circles\n"
        "- Bench press: 4x6\n"
        "### Nutrition\n- Eat sufficient protein"
    )
    constraint = ["lower back pain, severity 6/10"]
    profs = profiles(constraint)
    items = ps.parse(plan)
    verdicts = assess_plan(plan, profs)
    verdict_lines = {v["line_no"] for v in verdicts}

    # Projection invariant: every PRESCRIPTION_LIKE/AMBIGUOUS item under an
    # active profile must appear in assess_plan()'s output.
    missing = [it for it in items
               if it.role in (ps.PRESCRIPTION_LIKE, ps.AMBIGUOUS)
               and it.line_numbers[0] not in verdict_lines]
    check("every prescription-like/ambiguous item appears in assess_plan() "
          "under an active profile", not missing, f"missing={missing}")

    # Exact-final-plan invariant, exercised through the real pipeline: a
    # plan that ends up audit_clean=True must re-audit clean and carry no
    # unresolved CONDITIONAL candidate for the EXACT returned text.
    r = plan_repair.repair(plan, constraint)
    if r.audit_clean:
        check("audit_clean=True implies audit_against_profiles(result.plan) == []",
              audit_against_profiles(r.plan, profs) == [], r.plan)
        check("audit_clean=True implies no CONDITIONAL verdict on the exact "
              "returned plan",
              not any(v["verdict"] == VERDICT_CONDITIONAL
                      for v in assess_plan(r.plan, profs)),
              r.plan)
    else:
        check("audit_clean was False - invariant vacuously satisfied "
              "(nothing to check)", True)


def decorated_label_exercise_disambiguation():
    """The four decorated genuine exercises from the bug report are
    structurally AMBIGUOUS (never guessed as an exercise OR a container by
    plan_structure), and negative controls with no duration/decoration
    signal remain definitely prescription-like as before."""
    from app.services import plan_structure as ps
    print(f"\n{BOLD}Decorated-label vs. genuine-exercise disambiguation{RESET}")

    # 2. The four decorated genuine exercises from the bug report are
    # structurally ambiguous - resolved to "audited and repaired" only by
    # safety_subjects()/movement_ontology downstream, never guessed here.
    exercises = [
        "- **Push-up (2 min)** – 🏋️‍♂️",
        "- **Pull-up (2 min)** – 🏋️‍♂️",
        "- **High Pull (5 min)** – 🏋️‍♂️",
        "- **Strength Push-up (5 min)** – 🏋️‍♂️",
    ]
    for line in exercises:
        items = ps.parse(line)
        check(f"2. {line!r} -> structurally ambiguous (bug fixed - "
              f"resolved by safety_subjects, not guessed at parse time)",
              len(items) == 1 and items[0].role == ps.AMBIGUOUS, f"{items}")

    # 6. Existing negative controls, still definite prescriptions - none of
    # these carry a duration/decoration signal, so they never enter the
    # ambiguous path at all.
    for line in ["- Progression run", "- Tempo run", "- Pallof press",
                 "- Rest-pause squat", "- Strength-endurance deadlifts: 3x12"]:
        items = ps.parse(line)
        check(f"6. {line!r} still prescription-like (no regression)",
              len(items) == 1 and items[0].role == ps.PRESCRIPTION_LIKE,
              f"{items}")

    # 5. A nested exercise under a decorated group still behaves correctly -
    # including when the nested exercise itself has a push/pull-shaped name,
    # and the label gains a child so it resolves to a definite container.
    nested = ps.parse("- **Strength – Push (15 min)** – 🏋️‍♂️\n  Push-up")
    check("5. the decorated label, now with a child, is a definite container",
          nested[0].role == ps.DEFINITE_CONTAINER, f"{nested}")
    check("5. the nested 'Push-up' is an independent prescription-like item, "
          "not swallowed as the container's continuation",
          len(nested) == 2 and nested[1].role == ps.PRESCRIPTION_LIKE
          and nested[1].body == "Push-up"
          and nested[1].parent_id == nested[0].line_numbers[0], f"{nested}")


def decorated_label_safety_end_to_end():
    """3/4 - active-injury safety and healthy-user byte-identical behavior
    for each of the three exercises named in the bug report, PLUS a genuinely
    unknown decorated leaf ("Power Pull") the ontology has never seen."""
    from app.services import plan_repair
    from app.services.contraindications import audit_against_profiles, assess_plan, VERDICT_CONDITIONAL
    print(f"\n{BOLD}Decorated push-up/pull-up/high-pull/power-pull - end-to-end safety{RESET}")

    cases = [
        ("- **Push-up (2 min)** – 🏋️‍♂️", "wrist injury, severity 6/10", "Push-up"),
        ("- **Pull-up (2 min)** – 🏋️‍♂️", "shoulder injury, severity 6/10", "Pull-up"),
        ("- **High Pull (5 min)** – 🏋️‍♂️", "lower back pain, severity 6/10", "High Pull"),
        ("- **Power Pull (2 min)** – 🏋️‍♂️", "lower back pain, severity 6/10", "Power Pull"),
        ("- **Leg Pull (2 min)** – 🏋️‍♂️", "hamstring strain, severity 6/10", "Leg Pull"),
    ]
    for plan, constraint, name in cases:
        profs = profiles([constraint])
        r = plan_repair.repair(plan, [constraint])
        live = r.plan.split("\n\n---")[0]
        check(f"3. active injury ({constraint.split(',')[0]}): decorated "
              f"{name!r} does not survive unresolved",
              name not in live, f"live={live!r}")
        check(f"3. re-audit of the exact returned plan finds no unsafe "
              f"movement ({name})",
              not audit_against_profiles(r.plan, profs), r.plan)
        check(f"3. re-audit finds no unresolved CONDITIONAL candidate ({name})",
              not any(v["verdict"] == VERDICT_CONDITIONAL for v in assess_plan(r.plan, profs)),
              r.plan)
        check(f"3. audit_clean is True ({name})", r.audit_clean is True, r.as_dict())

        # 4. Healthy control - byte-identical.
        healthy = plan_repair.repair(plan, [])
        check(f"4. healthy user: decorated {name!r} plan is byte-identical",
              healthy.plan == plan, healthy.plan)

    # 8. Extra healthy-user byte-identical coverage: unknown decorated leaf,
    # decorated true container WITH children, and mixed known/unknown.
    for plan in [
        "- **Power Pull (2 min)** – 🏋️‍♂️",
        "- **Leg Pull (2 min)** – 🏋️‍♂️",
        "- **Warm-up (10 min)** – 🏋️‍♂️\n  - Arm circles\n  - March in place",
        "- **Push-up (2 min)** – 🏋️‍♂️\n- **Power Pull (2 min)** – 🏋️‍♂️\n- Bench press: 4x6",
    ]:
        healthy = plan_repair.repair(plan, [])
        check(f"8. healthy user byte-identical for: {plan[:40]!r}...",
              healthy.plan == plan, healthy.plan)


def mutation_check_ambiguity_bypass():
    """Section 10's required mutation: exclude AMBIGUOUS from
    safety_subjects() entirely. This proves fail-closed AMBIGUITY handling -
    not any particular ontology entry or vocabulary word - is the
    load-bearing safety mechanism."""
    from app.services import plan_structure as ps
    from app.services import plan_repair
    print(f"\n{BOLD}MUTATION — excluding AMBIGUOUS from safety_subjects(){RESET}")

    original = ps.safety_subjects

    def broken_safety_subjects(items, constraints_active=True):
        return [it for it in items if it.role == ps.PRESCRIPTION_LIKE]

    ps.safety_subjects = broken_safety_subjects
    try:
        r = plan_repair.repair("- **Power Pull (2 min)** – 🏋️‍♂️",
                               ["lower back pain, severity 6/10"])
        live = r.plan.split("\n\n---")[0]
        broken = "Power Pull" in live and r.audit_clean
    finally:
        ps.safety_subjects = original
    check("MUTATION: excluding AMBIGUOUS from safety_subjects() reproduces "
          "the 'Power Pull' bypass (audit_clean=True with the unknown "
          "exercise untouched)", broken,
          f"live={live!r} audit_clean={r.audit_clean}")

    # Confirm the fix is restored after the mutation (no leaked monkeypatch).
    r2 = plan_repair.repair("- **Power Pull (2 min)** – 🏋️‍♂️",
                            ["lower back pain, severity 6/10"])
    live2 = r2.plan.split("\n\n---")[0]
    check("after restoring safety_subjects(), 'Power Pull' is repaired again",
          "Power Pull" not in live2, live2)


# ---------------------------------------------------------------------------
# Seventh review pass - TWO verified defects:
#   P1 (HIGH)   pass 2 promoted an AMBIGUOUS item to CONTAINER on
#               bool(child_ids), so a decorated unknown exercise whose only
#               child was its own dosage bullet dropped out of
#               safety_subjects() entirely.
#   P2 (MEDIUM) _role_for_body defaulted whole instructional sentences
#               ("Choose a comfortable range of motion") to PRESCRIPTION_LIKE,
#               so an active injury "repaired" them into exercises.
# The cross-product these missed: AMBIGUOUS decorated exercise + nested
# DEFINITE_INSTRUCTION child + active injury.
# ---------------------------------------------------------------------------

_NESTED_CONTEXT_BYPASS_CASES = [
    # (label, plan, constraint, exercise name)
    ("nested dosage bullet",
     "- **Power Pull (2 min)** – 🏋️‍♂️\n  - 3 sets x 8 reps",
     "lower back pain, severity 6/10", "Power Pull"),
    ("nested RPE + rest",
     "- **Leg Pull (2 min)** – 🏋️‍♂️\n  - RPE 7\n  - Rest 60 seconds",
     "hamstring strain, severity 6/10", "Leg Pull"),
    ("nested coaching context",
     "- **Power Pull (2 min)** – 🏋️‍♂️\n  - Keep the spine neutral",
     "lower back pain, severity 6/10", "Power Pull"),
    ("numbered, nested dosage",
     "1. **Power Pull (2 min)** – 🏋️‍♂️\n   1. 3 sets x 8 reps",
     "lower back pain, severity 6/10", "Power Pull"),
    ("numbered, nested coaching",
     "1. **Leg Pull (2 min)** – 🏋️‍♂️\n   1. Keep the spine neutral",
     "hamstring strain, severity 6/10", "Leg Pull"),
]


def nested_context_does_not_create_a_container():
    """1/2/3/4 - a decorated unknown exercise whose only children are
    dosage/coaching context must NOT be promoted to a container, and must
    stay a safety subject under an active injury."""
    from app.services import plan_structure as ps
    from app.services.contraindications import (
        assess_plan, audit_against_profiles, VERDICT_CONDITIONAL,
    )
    from app.services import plan_repair
    print(f"\n{BOLD}P1 — nested dosage/context is not container evidence{RESET}")

    for label, plan, constraint, name in _NESTED_CONTEXT_BYPASS_CASES:
        items = ps.parse(plan)
        profs = profiles([constraint])

        check(f"[{label}] the parent stays AMBIGUOUS, not promoted to a "
              f"container", items[0].role == ps.AMBIGUOUS, f"{items}")
        check(f"[{label}] every child is definite instruction/context",
              all(it.role == ps.DEFINITE_INSTRUCTION for it in items[1:]),
              f"{items}")
        subjects = ps.safety_subjects(items, constraints_active=True)
        check(f"[{label}] {name!r} IS a safety subject under an active injury",
              [s.line_numbers[0] for s in subjects] == [items[0].line_numbers[0]],
              f"{subjects}")

        # It reaches the ontology and gets a real verdict (CONDITIONAL for a
        # name the ontology cannot classify).
        verdicts = assess_plan(plan, profs)
        check(f"[{label}] assess_plan returns a verdict for {name!r}",
              any(v["line_no"] == items[0].line_numbers[0] for v in verdicts),
              f"{verdicts}")
        check(f"[{label}] that verdict is CONDITIONAL (ontology cannot "
              f"classify {name!r})",
              any(v["line_no"] == items[0].line_numbers[0]
                  and v["verdict"] == VERDICT_CONDITIONAL for v in verdicts),
              f"{verdicts}")

        # End to end: repaired, and the exact returned text is clean.
        r = plan_repair.repair(plan, [constraint])
        live = r.plan.split("\n\n---")[0]
        check(f"[{label}] {name!r} does not survive the repaired plan",
              name not in live, f"live={live!r}")
        check(f"[{label}] exact returned plan: no unsafe movement",
              audit_against_profiles(r.plan, profs) == [], r.plan)
        check(f"[{label}] exact returned plan: no unresolved CONDITIONAL",
              not any(v["verdict"] == VERDICT_CONDITIONAL
                      for v in assess_plan(r.plan, profs)), r.plan)
        check(f"[{label}] audit_clean is True and reflects that exact text",
              r.audit_clean is True, r.as_dict())


def owned_block_removal_and_replacement():
    """5/6 - block ownership: replacing keeps the owned dosage/context with
    the replacement; removing takes it away, leaving no orphan."""
    from app.services import plan_structure as ps
    from app.services import plan_repair
    from app.services import exercise_catalogue as catalogue
    print(f"\n{BOLD}P1 — owned-block removal / replacement{RESET}")

    plan = ("- **Power Pull (2 min)** – 🏋️‍♂️\n"
            "  - 3 sets x 8 reps\n"
            "  - Keep the spine neutral\n"
            "- Bench press: 4x6")
    items = ps.parse(plan)

    check("owned_block_lines() claims the exercise plus BOTH context lines",
          ps.owned_block_lines(items[0], items) == [0, 1, 2],
          ps.owned_block_lines(items[0], items))
    check("the independent sibling exercise is NOT owned by it",
          3 not in ps.owned_block_lines(items[0], items),
          ps.owned_block_lines(items[0], items))

    # 5. Replacement keeps the owned context, in document order.
    replaced = plan_repair._apply(plan, {
        0: plan_repair.Replacement(original="- **Power Pull (2 min)**",
                                   replacement="Seated cable row", reason="t"),
    })
    check("5. replacement retains sets/reps and coaching context, in order, "
          "with the sibling untouched",
          replaced.splitlines()[1:] == ["  - 3 sets x 8 reps",
                                        "  - Keep the spine neutral",
                                        "- Bench press: 4x6"],
          f"{replaced!r}")
    check("5. the replacement name is on the primary line",
          "Seated cable row" in replaced.splitlines()[0], f"{replaced!r}")

    # 6. Removal takes the whole owned block, leaving no orphaned dosage.
    removed = plan_repair._apply(plan, {
        0: plan_repair.Replacement(original="- **Power Pull (2 min)**",
                                   replacement=None, reason="t"),
    })
    check("6. removal leaves EXACTLY the untouched sibling - no orphaned "
          "dosage or coaching line",
          removed.splitlines() == ["- Bench press: 4x6"], f"{removed!r}")

    # 6 (end to end): force "no validated replacement" by emptying the
    # catalogue offline - no Groq, no regeneration callback.
    saved = list(catalogue.CATALOGUE)
    catalogue.CATALOGUE[:] = []
    try:
        r = plan_repair.repair(plan, ["lower back pain, severity 6/10"])
        live = r.plan.split("\n\n---")[0]
    finally:
        catalogue.CATALOGUE[:] = saved
    check("6. end-to-end forced removal: exercise and owned context both gone",
          live.splitlines() == ["- Bench press: 4x6"], f"{live!r}")
    check("6. end-to-end forced removal: no orphaned '3 sets x 8 reps'",
          "3 sets x 8 reps" not in live, f"{live!r}")


def true_container_controls():
    """7/8/9/10 - genuine containers still resolve, keep independently
    auditable children, share one parent across siblings, nest correctly,
    and tolerate an instruction sitting among their exercises."""
    from app.services import plan_structure as ps
    print(f"\n{BOLD}P1 — true-container controls{RESET}")

    # 7. True decorated container with two real exercises.
    plan7 = ("- **Strength – Pull (15 min)** – 🏋️‍♂️\n"
             "  - Seated cable row: 3x10\n"
             "  - Lat pulldown: 3x10")
    items7 = ps.parse(plan7)
    check("7. the parent is a definite container",
          items7[0].role == ps.DEFINITE_CONTAINER, f"{items7}")
    check("7. both exercises remain independently auditable",
          [s.body for s in ps.safety_subjects(items7, True)]
          == ["Seated cable row: 3x10", "Lat pulldown: 3x10"],
          f"{ps.safety_subjects(items7, True)}")

    # 8. Multiple siblings share the SAME parent.
    check("8. both sibling exercises are parented to the same container",
          items7[1].parent_id == items7[0].line_numbers[0]
          and items7[2].parent_id == items7[0].line_numbers[0], f"{items7}")

    # 9. Nested container hierarchy: BOTH outer labels must resolve, which
    # only works because promotion is recursive/order-independent.
    plan9 = ("- **Power Segment (20 min)** – 🏋️‍♂️\n"
             "  - **Pull Focus (15 min)** – 🏋️‍♂️\n"
             "    - Seated cable row: 3x10")
    items9 = ps.parse(plan9)
    check("9. the outer label is a definite container",
          items9[0].role == ps.DEFINITE_CONTAINER, f"{items9}")
    check("9. the intermediate label is a definite container",
          items9[1].role == ps.DEFINITE_CONTAINER, f"{items9}")
    check("9. only the innermost exercise is a safety subject",
          [s.body for s in ps.safety_subjects(items9, True)]
          == ["Seated cable row: 3x10"], f"{ps.safety_subjects(items9, True)}")
    check("9. the hierarchy is linked outer -> intermediate -> exercise",
          items9[1].parent_id == items9[0].line_numbers[0]
          and items9[2].parent_id == items9[1].line_numbers[0], f"{items9}")

    # 10. A container whose children are one instruction + one exercise.
    plan10 = ("- **Strength – Pull (15 min)** – 🏋️‍♂️\n"
              "  - Work with controlled form\n"
              "  - Seated cable row: 3x10")
    items10 = ps.parse(plan10)
    check("10. the parent is still a definite container (a real exercise "
          "child qualifies even alongside an instruction)",
          items10[0].role == ps.DEFINITE_CONTAINER, f"{items10}")
    check("10. the instruction child stays an instruction, not an exercise",
          items10[1].role == ps.DEFINITE_INSTRUCTION, f"{items10}")
    check("10. only the real exercise is a safety subject",
          [s.body for s in ps.safety_subjects(items10, True)]
          == ["Seated cable row: 3x10"], f"{ps.safety_subjects(items10, True)}")


def general_instruction_controls():
    """12/13 - common instructional sentences survive an active injury
    byte-identically; every named collision control still enters the
    safety pipeline."""
    from app.services import plan_structure as ps
    from app.services import plan_repair
    print(f"\n{BOLD}P2 — general instructions vs. exercise collisions{RESET}")

    instructions = [
        "Choose a comfortable range of motion",
        "Perform each exercise with controlled form",
        "Work at a conversational pace",
    ]
    for text in instructions:
        check(f"12. {text!r} -> definite instruction",
              ps.classify_single_line(f"- {text}") == ps.DEFINITE_INSTRUCTION,
              ps.classify_single_line(f"- {text}"))

    # 12. They survive an active-injury repair byte-identically.
    plan = "\n".join(f"- {t}" for t in instructions) + "\n- Bench press: 4x6"
    r = plan_repair.repair(plan, ["ankle sprain, severity 6/10"])
    live = r.plan.split("\n\n---")[0]
    for text in instructions:
        check(f"12. {text!r} survives an active ankle injury untouched",
              f"- {text}" in live.splitlines(), f"{live!r}")
    check("12. no instruction was replaced or removed",
          not any(t.lower() in (x.original or "").lower()
                  for x in r.replacements for t in instructions)
          and not any(t.lower() in (rem or "").lower()
                      for rem in r.removed for t in instructions),
          f"replacements={r.replacements} removed={r.removed}")

    # 12. Instructions never enter either projection.
    items = ps.parse(plan)
    instruction_lines = {i for i, it in enumerate(items)
                         if it.role == ps.DEFINITE_INSTRUCTION}
    check("12. instructions are excluded from safety_subjects()",
          not (instruction_lines
               & {items.index(s) for s in ps.safety_subjects(items, True)}),
          f"{ps.safety_subjects(items, True)}")
    check("12. instructions are excluded from quality_subjects()",
          not (instruction_lines
               & {items.index(s) for s in ps.quality_subjects(items)}),
          f"{ps.quality_subjects(items)}")

    # 13. Collision controls remain prescriptions and enter the pipeline.
    collisions = [
        "Run 5 km", "Press overhead: 3x8", "Perform Romanian deadlifts: 3x8",
        "Work capacity shuttle: 5 rounds", "Choose-your-pace run: 20 minutes",
        "Progression run", "Rest-pause squat", "Stop-and-go runs",
    ]
    for text in collisions:
        role = ps.classify_single_line(f"- {text}")
        check(f"13. {text!r} remains prescription-like/ambiguous, not an "
              f"instruction", role in (ps.PRESCRIPTION_LIKE, ps.AMBIGUOUS), role)
        one = ps.parse(f"- {text}")
        check(f"13. {text!r} enters safety_subjects() under an active injury",
              len(ps.safety_subjects(one, constraints_active=True)) == 1, one)


def quality_projection_and_healthy_identity():
    """11/15 - healthy users get byte-identical text for every nested-context
    shape; the quality projection counts ambiguous leaves but not container
    labels or nested dosage."""
    from app.services import plan_structure as ps
    from app.services import plan_quality
    from app.services import plan_repair
    print(f"\n{BOLD}P1/P2 — quality projection and healthy-user identity{RESET}")

    # 11. Healthy-user byte identity for every bypass shape.
    for label, plan, _constraint, _name in _NESTED_CONTEXT_BYPASS_CASES:
        healthy = plan_repair.repair(plan, [])
        check(f"11. healthy user: [{label}] returned byte-identical",
              healthy.plan == plan, f"{healthy.plan!r}")

    # 15. Quality: an ambiguous leaf that OWNS nested dosage still counts as
    # exactly one exercise - fixing the parser must not report zero.
    plan_a = "- **Power Pull (2 min)** – 🏋️‍♂️\n  - 3 sets x 8 reps"
    check("15. an ambiguous leaf with nested dosage counts as ONE exercise",
          len(plan_quality.exercise_lines(plan_a)) == 1,
          plan_quality.exercise_lines(plan_a))
    check("15. its nested dosage bullet is NOT counted as an exercise",
          not any("3 sets" in line for line in plan_quality.exercise_lines(plan_a)),
          plan_quality.exercise_lines(plan_a))

    # 15. A true container label is not counted; its children are.
    plan_b = ("- **Strength – Pull (15 min)** – 🏋️‍♂️\n"
              "  - Seated cable row: 3x10\n"
              "  - Lat pulldown: 3x10")
    lines_b = plan_quality.exercise_lines(plan_b)
    check("15. the container label is not counted as an exercise",
          lines_b == ["Seated cable row: 3x10", "Lat pulldown: 3x10"], lines_b)

    # 15. Instructions are not counted either.
    plan_c = ("- **Strength – Pull (15 min)** – 🏋️‍♂️\n"
              "  - Work with controlled form\n"
              "  - Seated cable row: 3x10")
    check("15. a nested instruction is not counted as an exercise",
          plan_quality.exercise_lines(plan_c) == ["Seated cable row: 3x10"],
          plan_quality.exercise_lines(plan_c))


def mutation_check_untyped_child_promotion():
    """16 - restore the broken `if item.child_ids` promotion and prove the
    nested-dosage Power Pull bypass reappears. The mutation must fail on the
    newly added invariant (the exercise surviving with audit_clean=True),
    not on some unrelated assertion."""
    from app.services import plan_structure as ps
    from app.services import plan_repair
    print(f"\n{BOLD}MUTATION — untyped bool(child_ids) container promotion{RESET}")

    plan = "- **Power Pull (2 min)** – 🏋️‍♂️\n  - 3 sets x 8 reps"
    original = ps._contains_prescription_work
    # The exact pre-fix behaviour: ANY child is container evidence.
    ps._contains_prescription_work = lambda item, by_id, seen=None: bool(item.child_ids)
    try:
        items = ps.parse(plan)
        promoted = items[0].role == ps.DEFINITE_CONTAINER
        subjects = ps.safety_subjects(items, constraints_active=True)
        r = plan_repair.repair(plan, ["lower back pain, severity 6/10"])
        live = r.plan.split("\n\n---")[0]
        bypassed = "Power Pull" in live and r.audit_clean
    finally:
        ps._contains_prescription_work = original

    check("MUTATION: untyped promotion turns the unknown exercise into a "
          "container", promoted)
    check("MUTATION: it then vanishes from safety_subjects()",
          not subjects, f"{subjects}")
    check("MUTATION: the exact bypass reappears - 'Power Pull' survives with "
          "audit_clean=True", bypassed,
          f"live={live!r} audit_clean={r.audit_clean}")

    # And the fix is genuinely restored afterwards.
    r2 = plan_repair.repair(plan, ["lower back pain, severity 6/10"])
    live2 = r2.plan.split("\n\n---")[0]
    check("MUTATION restored: 'Power Pull' is repaired again",
          "Power Pull" not in live2, f"{live2!r}")


# ---------------------------------------------------------------------------
# Eighth review pass - an instructional WRAPPER must never hide a real
# movement from an active injury. The movement ontology, not more English
# grammar, is the authority on whether a line contains a movement.
# ---------------------------------------------------------------------------

_WRAPPED_MOVEMENTS = [
    ("- Perform push-ups with controlled form", "wrist injury, severity 6/10", "push-up"),
    ("- Use a controlled tempo for pull-ups", "shoulder injury, severity 6/10", "pull-up"),
    ("- Maintain strict form on overhead press", "shoulder injury, severity 6/10", "overhead press"),
    ("- Work at a conversational pace: easy run", "hamstring strain, severity 6/10", "run"),
]

_PLAIN_INSTRUCTIONS = [
    "Rest 90 seconds between sets",
    "Focus on controlled form",
    "Stop if pain increases",
    "Breathe normally",
    "Choose a comfortable range of motion",
    "Work at a conversational pace",
]


def instruction_wrapper_cannot_hide_a_movement():
    """A line the parser calls an instruction, but which the ontology finds
    a real movement in, must still be audited and repaired."""
    from app.services import plan_structure as ps
    from app.services import plan_repair
    from app.services.contraindications import (
        safety_subjects_for, assess_plan, audit_against_profiles,
        VERDICT_CONDITIONAL,
    )
    print(f"\n{BOLD}Instruction wrappers cannot hide a real movement{RESET}")

    for line, constraint, name in _WRAPPED_MOVEMENTS:
        profs = profiles([constraint])
        items = ps.parse(line)

        # The structural layer is still allowed to call it an instruction -
        # that is fine, and is exactly why the safety layer must not rely
        # on it alone.
        subjects = safety_subjects_for(items, constraints_active=True)
        check(f"{name!r}: recovered into the safety projection despite the "
              f"instructional wrapper",
              [s.line_numbers[0] for s in subjects] == [0], f"{items} -> {subjects}")

        verdicts = assess_plan(line, profs)
        check(f"{name!r}: assess_plan returns a real verdict, not silence",
              len(verdicts) == 1 and verdicts[0]["verdict"] != VERDICT_CONDITIONAL,
              f"{verdicts}")

        r = plan_repair.repair(line, [constraint])
        live = r.plan.split("\n\n---")[0]
        check(f"{name!r}: does not survive the repaired plan",
              name not in live.lower(), f"live={live!r}")
        check(f"{name!r}: exact returned plan re-audits with no unsafe movement",
              audit_against_profiles(r.plan, profs) == [], r.plan)
        check(f"{name!r}: no unresolved CONDITIONAL on the exact returned plan",
              not any(v["verdict"] == VERDICT_CONDITIONAL
                      for v in assess_plan(r.plan, profs)), r.plan)
        check(f"{name!r}: audit_clean is True", r.audit_clean is True, r.as_dict())

        # Healthy user: unchanged, byte for byte.
        check(f"{name!r}: healthy user gets byte-identical text",
              plan_repair.repair(line, []).plan == line, line)


def plain_instructions_stay_instructions():
    """The ontology finds no movement in these, so nothing pulls them into
    the safety pipeline and they survive an active injury untouched."""
    from app.services import plan_structure as ps
    from app.services import plan_repair
    from app.services.contraindications import safety_subjects_for
    print(f"\n{BOLD}Ordinary instructions are still never repaired{RESET}")

    plan = "\n".join(f"- {t}" for t in _PLAIN_INSTRUCTIONS)
    items = ps.parse(plan)
    check("no plain instruction enters the safety projection, even with an "
          "active constraint",
          safety_subjects_for(items, constraints_active=True) == [],
          f"{safety_subjects_for(items, True)}")

    r = plan_repair.repair(plan, ["ankle sprain, severity 6/10"])
    check("all plain instructions survive an active injury byte-identically",
          r.plan.split("\n\n---")[0] == plan, f"{r.plan!r}")
    check("nothing was replaced or removed", not r.replacements and not r.removed,
          f"replacements={r.replacements} removed={r.removed}")

    # And each one individually stays a definite instruction.
    for text in _PLAIN_INSTRUCTIONS:
        check(f"{text!r} -> definite instruction",
              ps.classify_single_line(f"- {text}") == ps.DEFINITE_INSTRUCTION,
              ps.classify_single_line(f"- {text}"))


def decoration_is_not_dosage():
    """A decorated label's trailing emoji must not be carried onto a
    replacement as if it were a prescription."""
    from app.services import plan_repair
    print(f"\n{BOLD}Decoration is not dosage{RESET}")

    check("a pure-emoji suffix yields no dosage",
          plan_repair._dosage_suffix("- **Power Pull (2 min)** – 🏋️‍♂️") == "",
          plan_repair._dosage_suffix("- **Power Pull (2 min)** – 🏋️‍♂️"))
    for line, expected in [("- Bench press: 4x8 @ RPE 7", "4x8 @ RPE 7"),
                           ("- Row – 3x10 each side", "3x10 each side"),
                           ("- Squat: 5x5", "5x5")]:
        check(f"real dosage still preserved: {expected!r}",
              plan_repair._dosage_suffix(line) == expected,
              plan_repair._dosage_suffix(line))

    # "Power Pull" is a genuine unknown prescription. Under an active injury
    # it is now REMOVED fail-closed rather than swapped for a guess, and its
    # owned block - the nested dosage - goes with it. The emoji-as-dosage
    # assertions above already prove the parsing point directly.
    r = plan_repair.repair("- **Power Pull (2 min)** – 🏋️‍♂️\n  - 3 sets x 8 reps",
                           ["lower back pain, severity 6/10"])
    live = r.plan.split("\n\n---")[0]
    check("the unknown prescription does not survive an active injury",
          "Power Pull" not in live, f"{live!r}")
    check("its owned dosage line is removed with it",
          "3 sets x 8 reps" not in live, f"{live!r}")
    check("no emoji is carried into whatever remains", "🏋" not in live, f"{live!r}")
    check("nothing was invented in its place",
          not any(w in live.lower() for w in
                  ("stationary bike", "elliptical", "brisk walk", "rowing machine")),
          f"{live!r}")


def mutation_check_instruction_wrapper_recovery():
    """Disable the ontology-backed recovery; every wrapped movement must
    bypass safety again."""
    from app.services import contraindications as c
    from app.services import plan_structure as ps
    from app.services import plan_repair
    print(f"\n{BOLD}MUTATION — removing the instruction-wrapper recovery{RESET}")

    original = c.safety_subjects_for
    c.safety_subjects_for = (
        lambda items, constraints_active: ps.safety_subjects(
            items, constraints_active=constraints_active)
    )
    try:
        line, constraint, name = _WRAPPED_MOVEMENTS[0]
        r = plan_repair.repair(line, [constraint])
        live = r.plan.split("\n\n---")[0]
        broken = name in live.lower() and r.audit_clean
    finally:
        c.safety_subjects_for = original
    check("MUTATION: without the recovery, 'Perform push-ups with controlled "
          "form' survives a wrist injury with audit_clean=True", broken,
          f"live={live!r} audit_clean={r.audit_clean}")

    r2 = plan_repair.repair(_WRAPPED_MOVEMENTS[0][0], [_WRAPPED_MOVEMENTS[0][1]])
    check("MUTATION restored: it is repaired again",
          "push-up" not in r2.plan.split("\n\n---")[0].lower(), r2.plan)


def main():
    print(f"\n{BOLD}PLAN STRUCTURE — canonical parser regression suite{RESET}")
    bare_unknown_exercises()
    numbered_exercises()
    bold_italic_lines()
    dosage_next_line()
    warm_up_cool_down()
    suppressed_sections()
    instruction_lines()
    confusing_substrings()
    active_injury_unknown_prescription()
    healthy_user_unchanged()
    no_orphaned_dosage()
    control_known_unsafe_still_caught()
    control_healthy_byte_identical()
    exercise_lines_canonical()
    heading_substring_safety()
    nested_exercises_independently_classified()
    dosage_continuations_attach_exactly()
    block_level_remove_and_replace_exact()
    repaired_plan_audit_clean_matches_reality()
    adjustment_note_is_not_a_prescription()
    instructions_are_never_replaced()
    nutrition_and_safety_prose_not_audited()
    combined_explicit_restriction_preserved()
    defect1_phrase_pairs()
    defect2_bare_indented_adversarial()
    defect3_keyword_collision_pairs()
    defect4_bare_fallback_scope()
    defect5_audit_entry_point_consistency()
    defect6_negation_grammar_pairs()
    adversarial_pair_matrix()
    mutation_checks_round_two()
    decorated_group_labels_recognised()
    decorated_group_label_end_to_end()
    plan_structure_has_no_movement_ontology_dependency()
    strong_container_and_ambiguous_leaf_invariants()
    projection_invariant_and_exact_final_plan_invariant()
    decorated_label_exercise_disambiguation()
    decorated_label_safety_end_to_end()
    mutation_check_ambiguity_bypass()
    nested_context_does_not_create_a_container()
    owned_block_removal_and_replacement()
    true_container_controls()
    general_instruction_controls()
    quality_projection_and_healthy_identity()
    mutation_check_untyped_child_promotion()
    instruction_wrapper_cannot_hide_a_movement()
    plain_instructions_stay_instructions()
    decoration_is_not_dosage()
    mutation_check_instruction_wrapper_recovery()
    bounded_regeneration_unchanged()
    mutation_checks()
    print(f"\n{BOLD}{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
