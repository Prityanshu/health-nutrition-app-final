#!/usr/bin/env python3
"""
Severity is now an input, not a label. These tests hold that claim up.

The point of the FitMentor severity slider is that the SAME injury at 3/10 and
7/10 must produce different plans - and produce them at generation time, not by
deleting things afterwards. That is only true if:

  * severity survives the round trip through the wire format
  * a higher rating restricts strictly more than a lower one
  * the brief handed to the model actually changes with it
  * 8+ still refuses rather than quietly producing a "gentle" plan
  * the JS severity table and the Python one agree

    python scripts/test_severity.py
"""


import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GREEN, RED, DIM, BOLD, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[1m", "\033[0m"
passed = failed = skipped = 0


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

def test_round_trip():
    """The wire format has to survive both directions, including odd input."""
    from app.services import injury_taxonomy as tax
    print(f"\n{BOLD}1. Severity survives the wire format{RESET}")

    for text, severity in [
        ("upper hamstring injury", 0), ("upper hamstring injury", 3),
        ("left ankle sprain", 6), ("knee pain", 7),
        ("rotator cuff strain", 10),
    ]:
        encoded = f"{text} (severity {severity}/10)"
        profile = tax.parse(encoded)
        check(f"{text!r} at {severity}/10 parses back to {severity}",
              profile is not None and profile.severity == severity,
              f"got {profile.severity if profile else None}")

    # An injury with no rating must not silently become 0/10 - that would read
    # as "fully recovered" and lift every restriction.
    unrated = tax.parse("upper hamstring injury")
    check("an unrated injury defaults to cautious, not to zero",
          unrated is not None and unrated.severity == 5,
          f"got {unrated.severity if unrated else None}")


def test_monotonic():
    """
    Higher severity must restrict a SUPERSET of lower severity.

    This is the property that makes the slider trustworthy. If raising a rating
    could ever unlock a movement, the whole control is worse than not having it.
    """
    from app.services import injury_taxonomy as tax
    print(f"\n{BOLD}2. Restrictions only ever grow with severity{RESET}")

    for injury in ["upper hamstring strain", "right ankle sprain", "knee pain",
                   "shoulder impingement", "lower back pain", "achilles tendinopathy"]:
        sets = {}
        for sev in range(0, 11):
            p = tax.parse(f"{injury} (severity {sev}/10)")
            sets[sev] = p.restricted_patterns()

        breaks = [
            (lo, hi) for lo in range(0, 10) for hi in [lo + 1]
            if not sets[lo] <= sets[hi]
        ]
        check(f"{injury}: never unlocks anything as it gets worse",
              not breaks,
              "\n".join(f"{lo}->{hi} lost {sorted(sets[lo] - sets[hi])}" for lo, hi in breaks))

        check(f"{injury}: 7/10 restricts strictly more than 2/10",
              sets[2] < sets[7],
              f"2/10={len(sets[2])} patterns, 7/10={len(sets[7])}")


def test_brief_changes():
    """The model must be told something different at each stage."""
    from app.services import injury_taxonomy as tax
    print(f"\n{BOLD}3. The generation brief actually changes with severity{RESET}")

    briefs = {}
    for sev in (1, 3, 5, 7):
        briefs[sev] = tax.brief(tax.parse_all([f"left hamstring strain (severity {sev}/10)"]))

    check("every stage produces a distinct brief",
          len(set(briefs.values())) == 4,
          {k: v[:60] for k, v in briefs.items()})

    for sev, expected in [(1, "Returning to sport"), (3, "Building strength"),
                          (5, "Controlled loading"), (7, "Acute")]:
        check(f"{sev}/10 is described as {expected!r}", expected in briefs[sev],
              briefs[sev][:120])

    # Plain language, not internal identifiers - the model cannot act on
    # "hip_hinge" but can act on the words.
    check("the brief contains no raw pattern identifiers",
          not any("_" in w for w in re.findall(r"\b\w+_\w+\b", briefs[7])),
          briefs[7])

    # Laterality has to reach the model, or it programmes both legs the same.
    sided = tax.brief(tax.parse_all(["right ankle sprain (severity 5/10)"]))
    check("the side reaches the brief", "right" in sided.lower(), sided[:120])

    both = tax.brief(tax.parse_all(["bilateral knee pain (severity 5/10)"]))
    check("bilateral is stated as both sides", "both sides" in both.lower(), both[:120])

    # And it must say what IS still trainable. A brief that only forbids things
    # produces a week that avoids the injury by avoiding training.
    check("the brief also names what is still safe to train hard",
          "safe to train hard" in briefs[5], briefs[5][:200])


def test_refusal():
    """8+ refuses. Below 8 does not."""
    from app.services import injury_taxonomy as tax
    print(f"\n{BOLD}4. The 8+ refusal threshold{RESET}")

    for sev in range(0, 8):
        p = tax.parse(f"knee pain (severity {sev}/10)")
        check(f"{sev}/10 still gets a plan", p.stage.prescribe,
              f"stage={p.stage.key}")
    for sev in (8, 9, 10):
        p = tax.parse(f"knee pain (severity {sev}/10)")
        check(f"{sev}/10 is refused", not p.stage.prescribe, f"stage={p.stage.key}")

    # Red flags warn, they do not block - somebody with a sore knee can still
    # train their upper body, and refusing everything is over-restriction.
    flagged = tax.parse("sharp pain and numbness in my knee (severity 4/10)")
    check("a red flag at 4/10 warns but still produces a plan",
          flagged.stage.prescribe and flagged.red_flags,
          f"prescribe={flagged.stage.prescribe} flags={flagged.red_flags}")

    # The worst injury decides. A 9/10 hidden behind a 2/10 must still refuse.
    profiles = tax.parse_all(["wrist pain (severity 2/10)",
                              "hamstring tear (severity 9/10)"])
    check("the worst of several injuries decides the refusal",
          any(not p.stage.prescribe for p in profiles),
          [(p.label, p.severity) for p in profiles])


def test_multi_injury():
    """Two injuries at different severities are not one injury at the mean."""
    from app.services import injury_taxonomy as tax
    print(f"\n{BOLD}5. Per-injury severity, not one global rating{RESET}")

    profiles = tax.parse_all(["wrist pain (severity 2/10)",
                              "right knee pain (severity 7/10)"])
    check("both injuries parse", len(profiles) == 2, [p.label for p in profiles])
    severities = sorted(p.severity for p in profiles)
    check("each keeps its own severity", severities == [2, 7], severities)
    check("each gets its own stage",
          len({p.stage.key for p in profiles}) == 2,
          [(p.label, p.stage.key) for p in profiles])

    # The severe one must not be softened by the mild one.
    knee_alone = tax.parse("right knee pain (severity 7/10)")
    combined_knee = next(p for p in profiles if "knee" in p.label)
    check("the 7/10 knee is not relaxed by the 2/10 wrist",
          combined_knee.restricted_patterns() == knee_alone.restricted_patterns())


def test_js_python_agree():
    """
    The UI duplicates the severity->stage table so it can show the consequence
    before calling the API. Duplication is a drift risk, so it is checked.
    """
    print(f"\n{BOLD}6. The JS severity table matches the Python one{RESET}")

    from app.services.injury_taxonomy import _STAGE_BY_SEVERITY, stage_for_severity

    js = (ROOT / "frontend/src/components/severity.js").read_text()

    labels = re.search(r"SEVERITY_LABELS\s*=\s*\[(.*?)\]", js, re.S)
    js_labels = re.findall(r"'([^']*)'", labels.group(1)) if labels else []
    check("SEVERITY_LABELS covers 0-10", len(js_labels) == 11, f"got {len(js_labels)}")

    block = re.search(r"export const STAGES\s*=\s*\{(.*?)\n\};", js, re.S)
    js_stages = dict(
        (int(k), v) for k, v in
        re.findall(r"(\d+):\s*\['([a-z]+)'", block.group(1) if block else "")
    )
    check("JS STAGES covers 0-10", sorted(js_stages) == list(range(11)),
          sorted(js_stages))

    mismatches = [
        (sev, js_stages.get(sev), _STAGE_BY_SEVERITY[sev])
        for sev in range(11)
        if js_stages.get(sev) != _STAGE_BY_SEVERITY[sev]
    ]
    check("every severity maps to the same stage in both languages",
          not mismatches,
          "\n".join(f"{s}: js={j!r} python={p!r}" for s, j, p in mismatches))

    blocking = re.search(r"BLOCKING_SEVERITY\s*=\s*(\d+)", js)
    js_block = int(blocking.group(1)) if blocking else None
    py_block = min(s for s in range(11) if not stage_for_severity(s).prescribe)
    check(f"the blocking threshold agrees ({py_block})", js_block == py_block,
          f"js={js_block} python={py_block}")


def test_encoding_matches_tracker():
    """
    FitMentor's encoding and injury_service's must be readable by one parser.

    Tracked injuries arrive as "label (severity 6/10, Acute - protect it)" and
    typed ones as "label (severity 6/10)". Both have to parse identically or
    importing from the dashboard would silently change the plan.
    """
    from app.services import injury_taxonomy as tax
    print(f"\n{BOLD}7. Typed and imported injuries parse the same{RESET}")

    for sev in (2, 5, 7):
        typed = tax.parse(f"left hamstring injury (severity {sev}/10)")
        tracked = tax.parse(
            f"left hamstring injury (severity {sev}/10, {tax.stage_for_severity(sev).label})")
        check(f"{sev}/10: typed and tracked agree on severity",
              typed.severity == tracked.severity == sev)
        check(f"{sev}/10: typed and tracked agree on restrictions",
              typed.restricted_patterns() == tracked.restricted_patterns(),
              f"typed-only {typed.restricted_patterns() ^ tracked.restricted_patterns()}")
        check(f"{sev}/10: typed and tracked agree on side",
              typed.side == tracked.side == "left")


def test_service_refusal_shape():
    """The service must refuse at 8+ without ever calling the model."""
    print(f"\n{BOLD}8. FitMentor refuses 8+ before spending a generation{RESET}")

    from app.services import injury_taxonomy as tax

    class Boom:
        """Any call to this is a test failure."""
        def run(self, *a, **k):
            raise AssertionError("the model was called for a severity-8+ injury")

    try:
        import app.services.fitmentor_service as fm
    except ImportError as e:
        # agno is not installed everywhere. Say so loudly - a skipped safety
        # test that prints nothing is indistinguishable from a passing one.
        global skipped
        skipped += 5
        print(f"  {DIM}SKIP  fitmentor_service unavailable ({e}). "
              f"Run this on the backend venv to cover the refusal path.{RESET}")
        return

    service = fm.FitMentorService.__new__(fm.FitMentorService)
    service.fitness_agent = Boom()

    # generate_workout_plan is a coroutine - calling it without awaiting
    # returns a coroutine object whose .get() would fail, so this has to run
    # through the event loop or the whole test is vacuous.
    result = asyncio.run(service.generate_workout_plan(
        activity_level="beginner", fitness_goal="general_fitness",
        time_per_day=45, equipment="gym",
        constraints=["hamstring tear (severity 9/10)"],
    ))
    check("refuses rather than generating", result.get("success") is False, result)
    check("names the reason as needing assessment",
          result.get("error_type") == "needs_assessment", result.get("error_type"))
    check("reports the severity that caused it", result.get("severity") == 9,
          result.get("severity"))
    check("no plan text is returned", "workout_plan" not in result, list(result))

    # And the mirror image: 7/10 must NOT be refused.
    p = tax.parse("hamstring tear (severity 7/10)")
    check("7/10 is not refused", p.stage.prescribe, p.stage.key)


def main():
    test_round_trip()
    test_monotonic()
    test_brief_changes()
    test_refusal()
    test_multi_injury()
    test_js_python_agree()
    test_encoding_matches_tracker()
    test_service_refusal_shape()

    tail = f", {skipped} skipped" if skipped else ""
    print(f"\n{BOLD}{GREEN if not failed else RED}"
          f"{passed} passed, {failed} failed{tail}{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
