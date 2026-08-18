#!/usr/bin/env python3
"""
Regression suite for CulinaryExplorer dietary safety and validation.

Every agent response is FAKE - a canned string swapped onto the service's
agent - so no Groq call is ever made and this is safe to run on any quota.

    python scripts/test_culinaryexplorer.py
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GREEN, RED, DIM, BOLD, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[1m", "\033[0m"
passed = failed = 0

# The service logs bounded metadata at INFO; silence it so the test output is
# readable. test_logging_hygiene below re-enables capture deliberately.
logging.disable(logging.CRITICAL)


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
# fake agent
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
        if not self.responses:
            raise AssertionError("FakeAgent called more times than expected")
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return _Response(nxt)

    @property
    def calls(self):
        return len(self.prompts)


class RateLimit(Exception):
    def __str__(self):
        return "rate_limit_exceeded"


def svc():
    from app.services.culinaryexplorer_service import culinaryexplorer_service
    return culinaryexplorer_service


def with_agent(*responses):
    agent = FakeAgent(*responses)
    svc().regional_food_agent = agent
    return agent


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

VEGAN_SAFE = """**Kerala Vegan Day 🌿**

### Breakfast
- Appam with vegetable stew
- Coconut chutney

### Lunch
- Sambar with rice
- Thoran with cabbage and coconut oil

### Dinner
- Kadala curry
- Steamed red rice"""

HAS_MILK = """### Breakfast
- Idli with sambar
- 1 cup whole milk

### Lunch
- Curd rice"""

HAS_CHICKEN = """**Kerala Chicken Stew**

### Ingredients
- 500g chicken, cubed
- Coconut milk
- Curry leaves"""

HAS_PANEER = """### Lunch
- Paneer butter masala
- Naan"""

HAS_WHEAT = """### Breakfast
- Whole wheat roti
- Vegetable curry"""


# ---------------------------------------------------------------------------
# 1. dietary hard failures
# ---------------------------------------------------------------------------

def dietary_hard_failures():
    print(f"\n{BOLD}1. Dietary hard failures{RESET}")

    cases = [
        ("vegan + milk", HAS_MILK, ["vegan"]),
        ("vegan + egg", "### Breakfast\n- Egg curry\n- Rice", ["vegan"]),
        ("vegetarian + chicken", HAS_CHICKEN, ["vegetarian"]),
        ("dairy-free + paneer", HAS_PANEER, ["dairy-free"]),
        ("gluten-free + wheat roti", HAS_WHEAT, ["gluten-free"]),
        ("gluten-free + naan", "### Dinner\n- Butter naan\n- Dal", ["gluten-free"]),
        ("nut-free + cashew", "### Snack\n- Cashew barfi", ["nut-free"]),
        ("nut-free + coconut milk", "### Curry\n- Coconut milk base", ["nut-free"]),
        ("vegan + honey", "### Breakfast\n- Oats with honey", ["vegan"]),
        ("vegan + ghee", "### Lunch\n- Rice, dal, ghee", ["vegan"]),
    ]
    for label, body, restrictions in cases:
        agent = with_agent(body, body)          # retry also bad -> fail closed
        result = run(svc().generate_regional_meal_plan(
            "kerala", dietary_restrictions=restrictions))
        check(f"{label} is rejected", result["success"] is False,
              result.get("error"))
        check(f"{label} reports the conflict deterministically",
              result.get("verification", {}).get("dietary", {}).get("violations"),
              result.get("verification"))


# ---------------------------------------------------------------------------
# 2. false-positive controls
# ---------------------------------------------------------------------------

def false_positive_controls():
    from app.services import dietary_rules as dr
    print(f"\n{BOLD}2. False-positive controls{RESET}")

    controls = [
        ("vegan chicken curry", "vegan"),
        ("plant-based meat bowl", "vegetarian"),
        ("gluten-free bread", "gluten-free"),
        ("coconut milk", "vegan"),
        ("coconut milk", "dairy-free"),
        ("peanut butter", "dairy-free"),
        ("water chestnut", "nut-free"),
        ("Chicken of the Woods", "vegetarian"),
        ("Sarson da Saag", "vegan"),
        ("Appam with vegetable stew", "vegan"),
        ("Baingan bharta", "vegan"),
        ("Aloo gobi", "vegan"),
    ]
    for food, restriction in controls:
        body = f"### Lunch\n- {food}\n- Steamed rice"
        agent = with_agent(body)
        result = run(svc().generate_regional_meal_plan(
            "punjab", dietary_restrictions=[restriction]))
        check(f"{food!r} is allowed under {restriction}", result["success"],
              result.get("error"))
        check(f"...and needed no retry ({food!r})", agent.calls == 1, agent.calls)

    # A culturally legitimate dish name whose words look forbidden.
    check("'Chicken of the Woods' is not a vegetarian conflict",
          dr.forbidden_hit("Chicken of the Woods", dr.VEGETARIAN) is None)


# ---------------------------------------------------------------------------
# 3. every entry point is audited
# ---------------------------------------------------------------------------

def every_entry_point():
    print(f"\n{BOLD}3. Every entry point runs the audit{RESET}")

    # meal plan
    with_agent(HAS_MILK, HAS_MILK)
    r = run(svc().generate_regional_meal_plan("kerala", dietary_restrictions=["vegan"]))
    check("meal plan: vegan + milk rejected", r["success"] is False, r.get("error"))

    # recipe - had NO dietary audit at all before this pass
    with_agent(HAS_CHICKEN, HAS_CHICKEN)
    r = run(svc().generate_regional_recipe("kerala", dietary_restrictions=["vegetarian"]))
    check("recipe: vegetarian + chicken rejected", r["success"] is False, r.get("error"))
    check("recipe: carries verification metadata", "verification" in r, list(r))

    # adaptation - also had none
    with_agent(HAS_PANEER, HAS_PANEER)
    r = run(svc().adapt_regional_plan("- Idli\n- Sambar", "make it creamier",
                                      dietary_restrictions=["vegan"]))
    check("adaptation: vegan + paneer rejected", r["success"] is False, r.get("error"))

    # retry output is audited, not trusted
    with_agent(HAS_MILK, VEGAN_SAFE)
    r = run(svc().generate_regional_meal_plan("kerala", dietary_restrictions=["vegan"]))
    check("retry output is re-audited and accepted when clean", r["success"],
          r.get("error"))
    check("...and the milk plan was not the one returned",
          "whole milk" not in r.get("meal_plan", ""), r.get("meal_plan", "")[:120])

    # a successful path always carries verification
    with_agent(VEGAN_SAFE)
    r = run(svc().generate_regional_meal_plan("kerala", dietary_restrictions=["vegan"]))
    check("successful meal plan carries verification",
          r["verification"]["dietary"]["checked"] == ["vegan"], r["verification"])


# ---------------------------------------------------------------------------
# 4. adaptation preservation
# ---------------------------------------------------------------------------

def adaptation_preservation():
    print(f"\n{BOLD}4. Restrictions survive adaptation{RESET}")

    # Generate vegan; the model omits any claim of its own.
    with_agent(VEGAN_SAFE)
    gen = run(svc().generate_regional_meal_plan(
        "kerala", dietary_restrictions=["vegan"]))
    check("generation records the restriction authoritatively",
          gen["dietary_restrictions"] == ["vegan"], gen["dietary_restrictions"])

    # Adapt with unrelated feedback: vegan still enforced.
    with_agent(HAS_MILK, HAS_MILK)
    ad = run(svc().adapt_regional_plan(
        gen["meal_plan"], "make it creamier",
        dietary_restrictions=gen["dietary_restrictions"]))
    check("adaptation that introduces milk is rejected", ad["success"] is False,
          ad.get("error"))

    # A compliant adaptation succeeds and returns the merged set.
    with_agent(VEGAN_SAFE)
    ad = run(svc().adapt_regional_plan(
        gen["meal_plan"], "more variety",
        dietary_restrictions=gen["dietary_restrictions"]))
    check("compliant adaptation succeeds", ad["success"], ad.get("error"))
    check("...and carries the restriction forward",
          ad["dietary_restrictions"] == ["vegan"], ad["dietary_restrictions"])

    # Repeated adaptation still has it.
    with_agent(HAS_PANEER, HAS_PANEER)
    ad2 = run(svc().adapt_regional_plan(
        ad["adapted_plan"], "richer please",
        dietary_restrictions=ad["dietary_restrictions"]))
    check("a SECOND adaptation still enforces vegan", ad2["success"] is False,
          ad2.get("error"))

    # New restrictions are additive, never a replacement.
    with_agent(VEGAN_SAFE)
    ad3 = run(svc().adapt_regional_plan(
        ad["adapted_plan"], "no wheat please",
        dietary_restrictions=["vegan"], new_dietary_restrictions=["gluten-free"]))
    check("new restrictions are additive",
          ad3["dietary_restrictions"] == ["vegan", "gluten_free"],
          ad3["dietary_restrictions"])

    # And the added one is then enforced.
    with_agent(HAS_WHEAT, HAS_WHEAT)
    ad4 = run(svc().adapt_regional_plan(
        ad["adapted_plan"], "add bread",
        dietary_restrictions=["vegan", "gluten-free"]))
    check("the added gluten-free restriction is enforced",
          ad4["success"] is False, ad4.get("error"))

    # Model prose claiming compliance is never treated as evidence.
    lying = "🌿 Vegan 🌾 Gluten-free\n\n### Lunch\n- Paneer butter masala\n- Naan"
    with_agent(lying, lying)
    ad5 = run(svc().adapt_regional_plan(
        "- Idli", "make it rich", dietary_restrictions=["vegan"]))
    check("a model's own 'Vegan' label does not make it vegan",
          ad5["success"] is False, ad5.get("error"))


# ---------------------------------------------------------------------------
# 5. rate-limit fallback
# ---------------------------------------------------------------------------

def rate_limit_fallback():
    print(f"\n{BOLD}5. Rate-limit fallbacks never bypass the audit{RESET}")

    for restriction in ["vegan", "vegetarian", "dairy-free", "gluten-free",
                        "nut-free"]:
        with_agent(RateLimit())
        r = run(svc().generate_regional_meal_plan(
            "kerala", dietary_restrictions=[restriction]))
        body = (r.get("meal_plan") or "").lower()
        check(f"{restriction}: fallback carries no forbidden food",
              not any(w in body for w in
                      ("yogurt", "curd", "paneer", "ghee", "roti", "naan",
                       "chicken", "milk", "cheese")),
              body[:160])
        check(f"{restriction}: the served fallback was audited clean",
              r["success"] and r["verification"]["dietary"]["violations"] == [],
              r.get("verification"))

    # The clean-fallback branch above only proves the canned text happens to be
    # safe. Force it unsafe to prove the audit is what gates it, and that an
    # unservable fallback is WITHHELD rather than served.
    from app.services import culinaryexplorer_service as mod
    original_generic = mod._generic_plan
    mod._generic_plan = lambda region: "### Sides\n- Yogurt/curd\n- Roti"
    try:
        with_agent(RateLimit())
        r = run(svc().generate_regional_meal_plan(
            "kerala", dietary_restrictions=["vegan"]))
        check("an unsafe fallback is withheld, not served",
              r["success"] is False, r.get("meal_plan"))
        check("...and reported as a rate limit, not a fake success",
              r.get("error_type") == "rate_limit", r)

        # ...while an unrestricted user is still served the same text.
        with_agent(RateLimit())
        r = run(svc().generate_regional_meal_plan("kerala",
                                                  dietary_restrictions=[]))
        check("...and the same text is still fine with no restrictions",
              r["success"], r.get("error"))
    finally:
        mod._generic_plan = original_generic

    # Unrestricted users still get something useful.
    with_agent(RateLimit())
    r = run(svc().generate_regional_meal_plan("kerala", dietary_restrictions=[]))
    check("unrestricted fallback still returns a plan", r["success"], r)
    check("...flagged as a fallback, not a personalised plan",
          r.get("fallback") is True, r)

    # Recipe fallback, same rules.
    with_agent(RateLimit())
    r = run(svc().generate_regional_recipe("kerala", dietary_restrictions=["vegan"]))
    body = (r.get("recipe") or "").lower()
    check("recipe fallback carries no forbidden food",
          not any(w in body for w in ("yogurt", "curd", "paneer", "ghee", "chicken")),
          body[:160])

    # Adaptation refuses outright rather than inventing content.
    with_agent(RateLimit())
    r = run(svc().adapt_regional_plan("- Idli", "more variety",
                                      dietary_restrictions=["vegan"]))
    check("adaptation under rate limit fails honestly", r["success"] is False, r)
    check("...with a rate_limit error_type", r.get("error_type") == "rate_limit", r)


# ---------------------------------------------------------------------------
# 6. retry bounds
# ---------------------------------------------------------------------------

def retry_bounds():
    print(f"\n{BOLD}6. At most one corrective call{RESET}")

    agent = with_agent(VEGAN_SAFE)
    r = run(svc().generate_regional_meal_plan("kerala", dietary_restrictions=["vegan"]))
    check("a good first result costs one call", agent.calls == 1, agent.calls)

    agent = with_agent(HAS_MILK, VEGAN_SAFE)
    r = run(svc().generate_regional_meal_plan("kerala", dietary_restrictions=["vegan"]))
    check("a bad first result costs exactly two", agent.calls == 2, agent.calls)
    check("...and the corrected retry is returned", r["success"], r.get("error"))

    agent = with_agent(HAS_MILK, HAS_MILK)
    r = run(svc().generate_regional_meal_plan("kerala", dietary_restrictions=["vegan"]))
    check("two bad results still stop at two calls", agent.calls == 2, agent.calls)
    check("...and fail closed", r["success"] is False, r.get("error"))

    # A retry that raises must not cost the first result.
    agent = with_agent(HAS_MILK, RuntimeError("boom"))
    r = run(svc().generate_regional_meal_plan("kerala", dietary_restrictions=["vegan"]))
    check("a failed retry does not add calls", agent.calls == 2, agent.calls)
    check("...and the unsafe first result is still rejected",
          r["success"] is False, r.get("error"))

    # No restrictions and no macro target: never any reason to retry.
    agent = with_agent(HAS_MILK)
    r = run(svc().generate_regional_meal_plan("kerala", dietary_restrictions=[]))
    check("an unrestricted user triggers no dietary retry", agent.calls == 1,
          agent.calls)
    check("...and the plan is returned", r["success"], r.get("error"))

    # Recipe and adaptation are bounded identically.
    agent = with_agent(HAS_CHICKEN, HAS_CHICKEN)
    run(svc().generate_regional_recipe("kerala", dietary_restrictions=["vegetarian"]))
    check("recipe path is bounded at two calls", agent.calls == 2, agent.calls)

    agent = with_agent(HAS_PANEER, HAS_PANEER)
    run(svc().adapt_regional_plan("- Idli", "creamier",
                                  dietary_restrictions=["vegan"]))
    check("adaptation path is bounded at two calls", agent.calls == 2, agent.calls)


# ---------------------------------------------------------------------------
# 7. macro behaviour
# ---------------------------------------------------------------------------

def macro_behaviour():
    from app.services import macro_targets as mt
    print(f"\n{BOLD}7. Macro verification{RESET}")

    target = mt.MacroTarget(calories=600, protein=40, carbs=60, fat=20,
                            basis="daily", meal_type="lunch", share=0.35)

    on_target = (VEGAN_SAFE +
                 "\n\nTOTAL: 600 kcal, 42g protein, 60g carbs, 20g fat")
    off_target = (VEGAN_SAFE +
                  "\n\nTOTAL: 300 kcal, 10g protein, 40g carbs, 8g fat")

    agent = with_agent(on_target)
    r = run(svc().generate_regional_meal_plan(
        "kerala", dietary_restrictions=["vegan"], macro_target=target))
    check("on-target macros need no retry", agent.calls == 1, agent.calls)
    check("...and are reported hit", r["verification"]["macros"]["hit"], r["verification"])

    agent = with_agent(off_target, on_target)
    r = run(svc().generate_regional_meal_plan(
        "kerala", dietary_restrictions=["vegan"], macro_target=target))
    check("off-target macros trigger exactly one retry", agent.calls == 2, agent.calls)
    check("an improved retry replaces the original",
          r["verification"]["macros"]["hit"], r["verification"]["macros"])

    agent = with_agent(off_target, off_target)
    r = run(svc().generate_regional_meal_plan(
        "kerala", dietary_restrictions=["vegan"], macro_target=target))
    check("a worse/equal retry does not loop", agent.calls == 2, agent.calls)
    check("...and the macro miss is reported honestly, not hidden",
          r["success"] and r["verification"]["macros"]["hit"] is False,
          r["verification"]["macros"])

    # Unparseable macros must read as unchecked, never as verified.
    agent = with_agent(VEGAN_SAFE)
    r = run(svc().generate_regional_meal_plan(
        "kerala", dietary_restrictions=["vegan"], macro_target=target))
    check("unparseable macros report checked=False",
          r["verification"]["macros"]["checked"] is False, r["verification"]["macros"])
    check("...and are never reported as hit",
          not r["verification"]["macros"].get("hit"), r["verification"]["macros"])
    check("...and do not trigger a retry", agent.calls == 1, agent.calls)

    # No macro target at all.
    agent = with_agent(VEGAN_SAFE)
    r = run(svc().generate_regional_meal_plan("kerala", dietary_restrictions=["vegan"]))
    check("no macro target means no macro block", r["verification"]["macros"] is None,
          r["verification"])

    # Dietary safety outranks a macro improvement.
    macro_good_but_unsafe = HAS_MILK + "\n\nTOTAL: 600 kcal, 42g protein, 60g carbs, 20g fat"
    agent = with_agent(off_target, macro_good_but_unsafe)
    r = run(svc().generate_regional_meal_plan(
        "kerala", dietary_restrictions=["vegan"], macro_target=target))
    check("a macro-better but dietary-unsafe retry never wins",
          r["success"] and "whole milk" not in r["meal_plan"],
          r.get("meal_plan", "")[:150])


# ---------------------------------------------------------------------------
# 8. logging hygiene
# ---------------------------------------------------------------------------

def logging_hygiene():
    print(f"\n{BOLD}8. Logging hygiene{RESET}")

    import logging as _logging

    records = []

    class Capture(_logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    logger = _logging.getLogger("app.services.culinaryexplorer_service")
    handler = Capture()
    logger.addHandler(handler)
    logger.setLevel(_logging.DEBUG)
    _logging.disable(_logging.NOTSET)
    try:
        with_agent(HAS_MILK, VEGAN_SAFE)
        run(svc().generate_regional_meal_plan(
            "kerala", dietary_restrictions=["vegan", "nut-free"],
            available_ingredients=["coconut", "curry leaves"]))
    finally:
        logger.removeHandler(handler)
        _logging.disable(_logging.CRITICAL)

    blob = "\n".join(records)
    check("the prompt is not logged", "I'm interested in" not in blob, blob[:200])
    check("the plan body is not logged", "Appam with vegetable stew" not in blob,
          blob[:200])
    check("the restriction list is not logged", "nut_free" not in blob and
          "nut-free" not in blob, blob[:200])
    check("bounded metadata IS logged", "chars=" in blob and "violations=" in blob,
          blob[:200])
    check("...including the dietary status", "dietary=" in blob, blob[:200])


# ---------------------------------------------------------------------------
# 9. Markdown adversarial shapes
# ---------------------------------------------------------------------------

def markdown_shapes():
    from app.services import dietary_rules as dr
    print(f"\n{BOLD}9. Markdown shapes, negation and optional wording{RESET}")

    must_hit = [
        ("bulleted ingredient", "- 1 cup whole milk"),
        ("numbered ingredient", "1. Paneer cubes, 200g"),
        ("bold dish name", "**Chicken Chettinad**"),
        ("heading dish name", "### Butter Chicken"),
        ("dish and ingredient on one line", "- Dal makhani with cream and butter"),
        ("comma separated", "- Rice, dal, ghee"),
        ("semicolon separated", "- Rice; curd; pickle"),
        ("slash separated", "- Yogurt/curd"),
        ("plus separated", "- Roti + paneer"),
        ("serving suggestion bullet", "- Serve with yogurt"),
        ("topping bullet", "- Top with cheese"),
    ]
    for label, line in must_hit:
        audit = dr.audit_markdown(f"### Lunch\n{line}", ["vegan"])
        check(f"9. {label}: {line!r} is a hard conflict",
              not audit.hard_safe, audit.summary())

    must_not_hit = [
        ("negated", "- Prepared without milk"),
        ("negated 'no'", "- Dal, no ghee"),
        ("substitution", "- Use plant-based milk, not cow milk"),
        ("instead-of", "- Coconut oil instead of butter"),
        ("cultural name", "- Sarson da Saag"),
        ("analogue", "- Vegan chicken curry"),
        ("plant milk", "- Coconut milk stew"),
    ]
    for label, line in must_not_hit:
        audit = dr.audit_markdown(f"### Lunch\n{line}", ["vegan"])
        check(f"9. {label}: {line!r} is NOT a hard conflict",
              audit.hard_safe, audit.summary())

    # Optional and precautionary wording is advisory, never silent.
    optional = dr.audit_markdown("### Lunch\n- Optional chicken for the family",
                                 ["vegetarian"])
    check("9. 'optional chicken' is advisory, not a hard failure",
          optional.hard_safe and optional.advisories, optional.as_dict())

    precaution = dr.audit_markdown("### Snack\n- Granola (may contain nuts)",
                                   ["nut-free"])
    check("9. 'may contain nuts' is advisory, not a hard failure",
          precaution.hard_safe and precaution.advisories, precaution.as_dict())

    # Commentary is advisory only when there is a real structured plan for it
    # to be commentary ON - see the unstructured-document rule below.
    prose = dr.audit_markdown(
        "### Lunch\n- Sambar\n- Rice\n\n### Notes\n"
        "Some families enjoy this with cheese on the side.", ["vegan"])
    check("9. loose prose beside a real plan is advisory, not a hard failure",
          prose.hard_safe and prose.advisories, prose.as_dict())

    # The agent's own emoji legend is not content.
    legend = dr.audit_markdown("🍗 Contains meat/poultry\n🌿 Vegan", ["vegetarian"])
    check("9. the emoji legend is not audited as an ingredient",
          legend.hard_safe, legend.as_dict())

    # Unsupported restrictions are unverifiable, not compliant.
    unsup = dr.audit_markdown(VEGAN_SAFE, ["low-sodium", "diabetic-friendly"])
    check("9. unsupported restrictions are reported unverifiable",
          set(unsup.unverifiable) == {"low_sodium", "diabetic_friendly"},
          unsup.as_dict())
    check("9. ...and are never listed as checked", unsup.checked == [],
          unsup.checked)

    # No restrictions at all stays permissive.
    permissive = dr.audit_markdown(HAS_CHICKEN, [])
    check("9. no restrictions means nothing is flagged",
          permissive.hard_safe and not permissive.violations, permissive.as_dict())

    # --- shapes that were bypasses until self-review found them -------------
    # Each of these was served to a restricted user as a clean success.
    bypasses = [
        ("prose-only plan (no bullets anywhere)",
         "For lunch you will prepare chicken curry with rice. Serve it hot.",
         ["vegetarian"]),
        ("heading + prose body",
         "### Lunch\nYou will prepare chicken curry.", ["vegetarian"]),
        ("markdown table row",
         "| Item | Qty |\n|---|---|\n| Milk | 200ml |\n| Rice | 100g |", ["vegan"]),
        ("'Ingredients:' lead-in", "Ingredients: chicken, salt", ["vegetarian"]),
        ("exclusion before a prescription",
         "- Idli\n- Sambar\n- No ghee, add paneer", ["vegan"]),
    ]
    for label, text, restrictions in bypasses:
        audit = dr.audit_markdown(text, restrictions)
        check(f"9. bypass closed — {label}", not audit.hard_safe, audit.as_dict())
        agent = with_agent(text, text)
        r = run(svc().generate_regional_meal_plan(
            "kerala", dietary_restrictions=restrictions))
        check(f"9. ...and the service rejects it — {label}",
              r["success"] is False, r.get("error"))

    # An exclusion must still silence what it actually excludes.
    for line in ("Cooked without milk or cream", "Dal, no ghee",
                 "Coconut oil instead of butter"):
        audit = dr.audit_markdown(f"- Idli\n- Sambar\n- {line}", ["vegan"])
        check(f"9. exclusion still clears {line!r}", audit.hard_safe,
              audit.as_dict())

    # ...but only up to its own clause.
    audit = dr.audit_markdown("- Idli\n- Sambar\n- Chicken curry, no rice",
                              ["vegetarian"])
    check("9. an exclusion after a food does not clear that food",
          not audit.hard_safe, audit.as_dict())

    # A structured document keeps commentary advisory.
    structured = dr.audit_markdown(
        "- Idli\n- Sambar\n- Rice\nNote: some families add cheese.", ["vegan"])
    check("9. commentary beside real bullets stays advisory",
          structured.hard_safe and structured.advisories, structured.as_dict())

    # --- replacement / exclusion wording ------------------------------------
    # A modification instruction names two foods with OPPOSITE meanings. The
    # excluded one must not violate; the newly prescribed one must.
    swaps = [
        ("Replace tofu with paneer",           ["vegan"],      "paneer"),
        ("Substitute coconut milk with cream", ["vegan"],      "cream"),
        ("Substitute coconut milk with cream", ["dairy-free"], "cream"),
        ("Swap tofu for chicken",              ["vegetarian"], "chicken"),
        ("No ghee and add paneer",             ["vegan"],      "paneer"),
        ("Without milk and serve cheese",      ["vegan"],      "cheese"),
        ("Omit butter then add cheese",        ["vegan"],      "cheese"),
        ("Remove tofu and use paneer",         ["vegan"],      "paneer"),
        ("Drop tofu, add paneer",              ["vegan"],      "paneer"),
        ("Switch tofu with paneer",            ["vegan"],      "paneer"),
    ]
    for line, restrictions, expected in swaps:
        prescribed, excluded = dr.split_prescription(line)
        check(f"9. split — {line!r} prescribes the replacement",
              expected.split()[-1] in prescribed.lower(),
              f"prescribed={prescribed!r} excluded={excluded!r}")
        audit = dr.audit_markdown(f"### Dinner\n- Rice\n- Dal\n- {line}",
                                  restrictions)
        check(f"9. {line!r} violates {restrictions[0]}", not audit.hard_safe,
              audit.as_dict())
        check(f"9. ...naming {expected!r}, the prescribed food",
              audit.violations and audit.violations[0].matched == expected,
              audit.as_dict())

    # The mirror image: the food being REMOVED is not a violation.
    for line, restrictions in [("Remove paneer and use tofu", ["vegan"]),
                               ("Drop ghee, add coconut oil", ["vegan"]),
                               ("Replace paneer with tofu", ["vegan"]),
                               ("Swap chicken for jackfruit", ["vegetarian"])]:
        audit = dr.audit_markdown(f"### Dinner\n- Rice\n- Dal\n- {line}",
                                  restrictions)
        check(f"9. {line!r} is clean — the forbidden food is the one removed",
              audit.hard_safe, audit.as_dict())

    # Ordinary prose must not invent a prescribed ingredient.
    for line in ("No added sugar is needed", "Focus on reducing oil",
                 "Avoid heavy meals", "Cooked without milk or cream"):
        prescribed, _excluded = dr.split_prescription(line)
        check(f"9. {line!r} prescribes no new food",
              dr.forbidden_hit(prescribed, "vegan") is None,
              f"prescribed={prescribed!r}")

    # A bare conjunction must never resume: both foods stay excluded.
    p, e = dr.split_prescription("Cooked without milk or cream")
    check("9. 'without milk or cream' excludes both",
          "cream" in e.lower() and "cream" not in p.lower(), (p, e))

    # audit_plan (structured ingredient lists) has no negation handling by
    # design - a real ingredient list never contains instructions - so swap
    # wording there fails CLOSED on the food it names. Pinned so the two
    # auditors' differing treatment stays deliberate.
    def structured(ingredients):
        return {"plan": {"Monday": [{"meal_label": "dinner", "name": "Swap night",
                                     "ingredients": ingredients}]}}

    for ingredients, restriction, expected in (
        (["Rice", "Replace tofu with paneer"], "vegan", "paneer"),
        (["Rice", "Swap tofu for chicken"], "vegetarian", "chicken"),
    ):
        audit = dr.audit_plan(structured(ingredients), [restriction])
        check(f"9. audit_plan flags {expected!r} in {ingredients[1]!r}",
              not audit.hard_safe
              and audit.violations[0].matched == expected, audit.as_dict())

    clean = dr.audit_plan(structured(["Rice", "Tofu"]), ["vegan"])
    check("9. audit_plan still passes a genuinely vegan list", clean.hard_safe,
          clean.as_dict())

    # End to end, on every entry point.
    swap_plan = "### Dinner\n- Rice\n- No ghee and add paneer"
    for name, call in (
        ("generation", lambda: svc().generate_regional_meal_plan(
            "kerala", dietary_restrictions=["vegan"])),
        ("adaptation", lambda: svc().adapt_regional_plan(
            "- Idli", "make it richer", dietary_restrictions=["vegan"])),
        ("recipe", lambda: svc().generate_regional_recipe(
            "kerala", dietary_restrictions=["vegan"])),
    ):
        with_agent(swap_plan, swap_plan)
        r = run(call())
        check(f"9. {name} rejects 'No ghee and add paneer' for a vegan",
              r["success"] is False, r.get("error"))
        check(f"9. ...and reports it as a dietary violation ({name})",
              (r.get("verification") or {}).get("dietary", {}).get("status")
              == "violation", r.get("verification"))

    # Mutation: without the resume/replacement rules the bypass returns.
    original_resume, original_target = dr._RESUME, dr._REPLACE_TARGET
    never = __import__("re").compile(r"$^")
    dr._RESUME = dr._REPLACE_TARGET = never
    try:
        broken = [dr.audit_markdown(f"- Rice\n- Dal\n- {line}", ["vegan"]).hard_safe
                  for line in ("Replace tofu with paneer", "No ghee and add paneer")]
    finally:
        dr._RESUME, dr._REPLACE_TARGET = original_resume, original_target
    check("9. mutation: dropping the resume rules re-opens the swap bypass",
          all(broken), broken)

    # Mutation: restore the old end-of-line cut and the bypass returns.
    original_clause = dr._CLAUSE_END
    dr._CLAUSE_END = __import__("re").compile(r"$^")   # never matches
    try:
        broken = dr.audit_markdown("- Idli\n- Sambar\n- No ghee, add paneer",
                                   ["vegan"])
    finally:
        dr._CLAUSE_END = original_clause
    check("9. mutation: end-of-line avoidance re-opens the paneer bypass",
          broken.hard_safe, broken.as_dict())

    # Mutation: treat prose as advisory even with no structure.
    original_items = dr.markdown_food_candidates
    dr.markdown_food_candidates = lambda text: [
        (f, "prose" if s == "structural" and not f.startswith("#") else s, h)
        for f, s, h in original_items(text)]
    try:
        broken = dr.audit_markdown(
            "For lunch you will prepare chicken curry.", ["vegetarian"])
    finally:
        dr.markdown_food_candidates = original_items
    check("9. mutation: advisory-only prose re-opens the prose-plan bypass",
          broken.hard_safe, broken.as_dict())


# ---------------------------------------------------------------------------
# 10. router / interface
# ---------------------------------------------------------------------------

def router_interface():
    import inspect
    from app.routers import culinary
    print(f"\n{BOLD}10. Router interface{RESET}")

    for name in ("generate_regional_meal_plan", "generate_regional_recipe",
                 "adapt_regional_plan"):
        params = inspect.signature(getattr(culinary, name)).parameters
        check(f"10. /{name} requires an authenticated user",
              "current_user" in params, list(params))

    fields = culinary.RegionalPlanAdaptationRequest.model_fields
    check("10. the adaptation request accepts the ORIGINAL restrictions",
          "dietary_restrictions" in fields, list(fields))
    check("10. ...separately from additions",
          "new_dietary_restrictions" in fields, list(fields))

    # The response the frontend actually receives carries verification.
    with_agent(VEGAN_SAFE)
    r = run(svc().generate_regional_meal_plan("kerala",
                                              dietary_restrictions=["vegan"]))
    for key in ("dietary", "macros", "hard_safe", "usable"):
        check(f"10. verification exposes {key!r}", key in r["verification"],
              r["verification"])


# ---------------------------------------------------------------------------
# 11. mutations
# ---------------------------------------------------------------------------

def mutations():
    from app.services import dietary_rules as dr
    from app.services import culinaryexplorer_service as mod
    print(f"\n{BOLD}11. Mutations — each guard is load-bearing{RESET}")

    # M1: bypass the dietary audit entirely.
    original_audit = dr.audit_markdown
    dr.audit_markdown = lambda text, restrictions, macro_totals=None: dr.DietaryAudit()
    try:
        with_agent(HAS_MILK)
        r = run(svc().generate_regional_meal_plan(
            "kerala", dietary_restrictions=["vegan"]))
        broken = r["success"] and "whole milk" in r["meal_plan"]
    finally:
        dr.audit_markdown = original_audit
    check("M1 bypassing the audit lets vegan + milk through", broken)

    # M2: drop the original restrictions during adaptation.
    original_set = dr.canonical_set
    dr.canonical_set = lambda values: []
    try:
        with_agent(HAS_PANEER)
        r = run(svc().adapt_regional_plan("- Idli", "creamier",
                                          dietary_restrictions=["vegan"]))
        broken = r["success"] and "Paneer" in r["adapted_plan"]
    finally:
        dr.canonical_set = original_set
    check("M2 dropping existing restrictions allows unsafe adaptation", broken)

    # M3: bypass fallback validation.
    original_fb = mod.CulinaryExplorerService._fallback
    mod.CulinaryExplorerService._fallback = (
        lambda self, text, restrictions, operation:
        {"text": "### Sides\n- Yogurt/curd\n- Traditional bread/roti",
         "verification": {}})
    try:
        with_agent(RateLimit())
        r = run(svc().generate_regional_meal_plan(
            "kerala", dietary_restrictions=["vegan"]))
        body = (r.get("meal_plan") or "").lower()
        broken = r["success"] and ("yogurt" in body or "roti" in body)
    finally:
        mod.CulinaryExplorerService._fallback = original_fb
    check("M3 bypassing fallback validation returns conflicting content", broken)

    # M4: remove the retry bound -> more agent calls.
    original_attempt = mod.CulinaryExplorerService._attempt

    def unbounded(self, prompt, restrictions=None, macro_target=None,
                  operation="generate"):
        result = self._assess(self._run(prompt), restrictions, macro_target)
        for _ in range(3):                      # a per-validator loop
            if not result.needs_retry():
                break
            result = self._assess(self._run(prompt), restrictions, macro_target)
        return result

    mod.CulinaryExplorerService._attempt = unbounded
    try:
        agent = with_agent(HAS_MILK, HAS_MILK, HAS_MILK, HAS_MILK)
        run(svc().generate_regional_meal_plan("kerala",
                                              dietary_restrictions=["vegan"]))
        broken = agent.calls > 2
    finally:
        mod.CulinaryExplorerService._attempt = original_attempt
    check("M4 removing the retry bound causes extra agent calls", broken,
          f"calls={agent.calls}")

    # M5: trust the model's own compliance label.
    lying = "🌿 Vegan\n\n### Lunch\n- Paneer butter masala"
    original_hit = dr.forbidden_hit
    dr.forbidden_hit = lambda text, restriction: None
    try:
        with_agent(lying)
        r = run(svc().generate_regional_meal_plan(
            "kerala", dietary_restrictions=["vegan"]))
        broken = r["success"] and "Paneer" in r["meal_plan"]
    finally:
        dr.forbidden_hit = original_hit
    check("M5 trusting model labels permits a false safe result", broken)

    # Everything restored.
    with_agent(HAS_MILK, HAS_MILK)
    r = run(svc().generate_regional_meal_plan("kerala",
                                              dietary_restrictions=["vegan"]))
    check("all mutations restored: vegan + milk is rejected again",
          r["success"] is False, r.get("error"))


def main():
    print(f"\n{BOLD}CULINARY EXPLORER — dietary safety & validation{RESET}")
    dietary_hard_failures()
    false_positive_controls()
    every_entry_point()
    adaptation_preservation()
    rate_limit_fallback()
    retry_bounds()
    macro_behaviour()
    logging_hygiene()
    markdown_shapes()
    router_interface()
    mutations()
    print(f"\n{BOLD}{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
