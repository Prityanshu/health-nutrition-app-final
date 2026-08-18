#!/usr/bin/env python3
"""
Regression suite for AdvancedMealPlanner validation and dietary safety.

Every agent response here is FAKE - a canned string swapped onto the service's
agent. No Groq call is ever made, so this is safe to run on any quota.

    python scripts/test_advanced_meal_planner.py
"""

import inspect
import json
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


# ---------------------------------------------------------------------------
# fake agent
# ---------------------------------------------------------------------------

class _Response:
    def __init__(self, content):
        self.content = content


class FakeAgent:
    """Returns canned text. Records every prompt it was asked to run."""

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


def with_agent(*responses):
    """Swap a FakeAgent onto the singleton service for one call."""
    from app.services import advanced_meal_planner_service as mod
    agent = FakeAgent(*responses)
    mod.advanced_meal_planner_service.advanced_meal_agent = agent
    return agent


def service():
    from app.services.advanced_meal_planner_service import advanced_meal_planner_service
    return advanced_meal_planner_service


# ---------------------------------------------------------------------------
# plan builders
# ---------------------------------------------------------------------------

def _with_qty(ingredients):
    """Fill in a default qty so a test about DIETARY logic is not really a
    test about the qty field. Tests that care about qty set it explicitly."""
    out = []
    for item in ingredients:
        item = dict(item)
        item.setdefault("qty", "100g")
        out.append(item)
    return out


def meal(label="Breakfast", name="Oats Bowl", ingredients=None,
         calories=667, protein=33, carbs=84, fat=22):
    return {
        "meal_label": label,
        "recipe_name": name,
        "ingredients": _with_qty(ingredients) if ingredients
                       else [{"name": "rolled oats", "qty": "80g",
                              "est_cost": 12.0}],
        "macros": {"calories": calories, "protein_g": protein,
                   "carbs_g": carbs, "fat_g": fat},
        "prep_time_min": 10,
    }


def plan(days=7, meals_per_day=3, per_meal=None, ingredients=None,
         day_overrides=None):
    """
    A structurally valid plan. Defaults total ~2000 kcal/day across 3 meals,
    with macros that are energy-consistent (4/4/9).
    """
    per_meal = per_meal or {"calories": 667, "protein": 33, "carbs": 84, "fat": 22}
    body = {}
    for n in range(1, days + 1):
        key = f"day_{n}"
        if day_overrides and key in day_overrides:
            body[key] = day_overrides[key]
            continue
        body[key] = [
            meal(label=f"Meal {i + 1}", name=f"Dish {n}-{i + 1}",
                 ingredients=ingredients,
                 calories=per_meal["calories"], protein=per_meal["protein"],
                 carbs=per_meal["carbs"], fat=per_meal["fat"])
            for i in range(meals_per_day)
        ]
    return {
        "meta": {"assumptions": "none", "total_daily_calories": 2000,
                 "meals_per_day": meals_per_day, "budget_per_day": 200,
                 "food_preferences": [], "dietary_restrictions": []},
        "plan": body,
        "summary": {"avg_daily_cost": 200, "avg_daily_calories": 2000,
                    "weekly_shopping_list": [], "progression_tip": "keep going"},
    }


def as_json(obj):
    return json.dumps(obj)


BASE_PAYLOAD = {"target_calories": 2000, "meals_per_day": 3,
                "dietary_restrictions": [], "food_preferences": []}


def generate(text, payload=None, macro_target=None, extra_responses=()):
    agent = with_agent(text, *extra_responses)
    result = service().generate_meal_plan(
        {**BASE_PAYLOAD, **(payload or {})}, macro_target=macro_target)
    return result, agent


# ---------------------------------------------------------------------------
# 1. structural failures
# ---------------------------------------------------------------------------

def structural_failures():
    print(f"\n{BOLD}1. Structural contract{RESET}")

    good = plan()
    result, _ = generate(as_json(good))
    check("a complete, valid 7-day plan succeeds", result["success"],
          result.get("error"))

    cases = [
        ("a JSON list", "[]"),
        ("null", "null"),
        ("a bare string", '"here is your plan"'),
        ("an empty object", "{}"),
        ("missing 'plan'", as_json({"meta": {}, "summary": {}})),
    ]
    for label, text in cases:
        result, _ = generate(text)
        check(f"{label} is rejected", result["success"] is False, result)

    # Day-shape failures, each built from a valid plan.
    one_day = plan(days=1)
    result, _ = generate(as_json(one_day))
    check("a one-day plan is rejected", result["success"] is False,
          result.get("error"))
    check("...and the error names the missing days",
          "day_2" in result.get("error", ""), result.get("error"))

    missing_four = plan()
    del missing_four["plan"]["day_4"]
    result, _ = generate(as_json(missing_four))
    check("a week missing day_4 is rejected", result["success"] is False,
          result.get("error"))

    extra_day = plan()
    extra_day["plan"]["day_8"] = extra_day["plan"]["day_1"]
    result, _ = generate(as_json(extra_day))
    check("an unexpected day_8 is rejected", result["success"] is False,
          result.get("error"))

    wrong_count = plan()
    wrong_count["plan"]["day_3"] = wrong_count["plan"]["day_3"][:2]
    result, _ = generate(as_json(wrong_count))
    check("a day with 2 meals when 3 were asked for is rejected",
          result["success"] is False, result.get("error"))

    empty_day = plan()
    empty_day["plan"]["day_5"] = []
    result, _ = generate(as_json(empty_day))
    check("a day with no meals is rejected", result["success"] is False,
          result.get("error"))

    non_dict_meal = plan()
    non_dict_meal["plan"]["day_2"][0] = "porridge"
    result, _ = generate(as_json(non_dict_meal))
    check("a meal that is a string is rejected", result["success"] is False,
          result.get("error"))

    # Meal-level field failures.
    field_cases = [
        ("a meal with no recipe_name", lambda m: m.pop("recipe_name")),
        ("a meal with no meal_label", lambda m: m.pop("meal_label")),
        ("a meal with an empty ingredients list",
         lambda m: m.update(ingredients=[])),
        ("an ingredient with an empty name",
         lambda m: m.update(ingredients=[{"name": "  "}])),
        ("a meal with no macros", lambda m: m.pop("macros")),
        ("macros missing fat_g", lambda m: m["macros"].pop("fat_g")),
        ("NaN calories", lambda m: m["macros"].update(calories=float("nan"))),
        ("Infinity protein", lambda m: m["macros"].update(protein_g=float("inf"))),
        ("boolean calories", lambda m: m["macros"].update(calories=True)),
        ("negative calories", lambda m: m["macros"].update(calories=-100)),
        ("negative fat", lambda m: m["macros"].update(fat_g=-1)),
        ("a negative ingredient cost",
         lambda m: m.update(ingredients=[{"name": "oats", "est_cost": -5}])),
        ("a negative prep_time_min", lambda m: m.update(prep_time_min=-10)),
        ("non-numeric calories", lambda m: m["macros"].update(calories="lots")),
    ]
    for label, mutate in field_cases:
        broken = plan()
        mutate(broken["plan"]["day_1"][0])
        result, _ = generate(as_json(broken))
        check(f"{label} is rejected", result["success"] is False,
              result.get("error"))

    # Chosen contract: numeric STRINGS are accepted and coerced, because
    # models emit them constantly and the value is unambiguous.
    numeric_strings = plan()
    numeric_strings["plan"]["day_1"][0]["macros"] = {
        "calories": "667", "protein_g": "33", "carbs_g": "84", "fat_g": "22"}
    result, _ = generate(as_json(numeric_strings))
    check("numeric strings are accepted and coerced (documented contract)",
          result["success"], result.get("error"))

    # Harmless extra fields must not make a plan brittle.
    extra_fields = plan()
    extra_fields["plan"]["day_1"][0]["chef_tip"] = "toast the oats"
    extra_fields["extra_top_level"] = {"anything": 1}
    result, _ = generate(as_json(extra_fields))
    check("unknown extra fields are allowed", result["success"],
          result.get("error"))


# ---------------------------------------------------------------------------
# 2. dietary safety
# ---------------------------------------------------------------------------

def dietary_safety():
    from app.services import dietary_rules as dr
    print(f"\n{BOLD}2. Dietary restrictions are enforced deterministically{RESET}")

    def with_ingredient(name, restriction):
        bad = plan(ingredients=[{"name": name, "qty": "100g", "est_cost": 10}])
        return generate(as_json(bad),
                        payload={"dietary_restrictions": [restriction]})

    hard_cases = [
        ("vegan", ["milk", "butter", "paneer", "egg", "honey", "chicken breast"]),
        ("vegetarian", ["chicken", "fish", "gelatin"]),
        ("dairy-free", ["milk", "yogurt", "paneer", "ghee"]),
        ("gluten-free", ["wheat flour", "barley", "whole wheat bread"]),
        ("nut-free", ["peanut", "almonds", "cashew"]),
    ]
    for restriction, ingredients in hard_cases:
        for name in ingredients:
            result, _ = with_ingredient(name, restriction)
            check(f"{restriction} + {name!r} fails", result["success"] is False,
                  result.get("error"))

    # The finding must be precise enough to act on.
    result, _ = with_ingredient("milk", "vegan")
    violations = result["verification"]["dietary"]["violations"]
    check("the violation names day, meal, ingredient and restriction",
          violations and all(k in violations[0]
                             for k in ("day", "meal", "ingredient", "restriction")),
          violations[:1])

    print(f"\n{BOLD}   false-positive controls{RESET}")
    controls = [
        ("coconut milk", "vegan"), ("coconut milk", "dairy-free"),
        ("almond milk", "dairy-free"), ("eggplant", "vegan"),
        ("eggplant", "egg-free"), ("nutmeg", "nut-free"),
        ("butternut squash", "nut-free"), ("gluten-free bread", "gluten-free"),
        ("vegan cheese", "dairy-free"), ("plant-based cheese", "vegan"),
        ("peanut butter", "dairy-free"), ("rice flour", "gluten-free"),
    ]
    for name, restriction in controls:
        result, _ = with_ingredient(name, restriction)
        check(f"{restriction} + {name!r} is NOT a violation", result["success"],
              result.get("error"))

    # Coconut IS a tree nut for allergen labelling.
    result, _ = with_ingredient("coconut milk", "nut-free")
    check("nut-free + 'coconut milk' does fail (FDA treats coconut as a tree nut)",
          result["success"] is False, result.get("error"))

    # Precautionary labelling is an advisory, never a silent pass or a hard fail.
    advisory = plan(ingredients=[{"name": "granola (may contain nuts)", "qty": "50g"}])
    result, _ = generate(as_json(advisory),
                         payload={"dietary_restrictions": ["nut-free"]})
    check("'may contain nuts' does not hard-fail the plan", result["success"],
          result.get("error"))
    check("...but is surfaced as an advisory",
          any("precautionary" in a for a in result["verification"]["dietary"]["advisories"]),
          result["verification"]["dietary"]["advisories"])

    # Recipe names are ALWAYS a defensive signal, not only when the
    # ingredient list is missing.
    #
    # This assertion used to be the opposite - it called a present
    # ingredient list "authoritative" and expected "Chicken Biryani" with
    # only rice to SUCCEED for a vegetarian. Since structural validation
    # already requires a non-empty ingredient list, that branch fired on
    # every real plan and the recipe name was never checked at all: omitting
    # the chicken from the list while leaving it in the title was a complete
    # bypass. The test encoded the bug.
    hidden = plan()
    for day in hidden["plan"].values():
        day[0]["recipe_name"] = "Chicken Biryani"
        day[0]["ingredients"] = [{"name": "rice", "qty": "150g"},
                                 {"name": "spices", "qty": "1 tsp"}]
    result, _ = generate(as_json(hidden),
                         payload={"dietary_restrictions": ["vegetarian"]},
                         extra_responses=[as_json(hidden)])
    check("a forbidden ingredient hidden in the recipe name is caught",
          result["success"] is False, result.get("error"))
    check("...and the finding cites the recipe name as its source",
          any(v["source"] == "recipe_name"
              for v in result["verification"]["dietary"]["violations"]),
          result["verification"]["dietary"]["violations"][:2])

    # ...while a vegan analogue named after the thing it imitates is fine,
    # which is what stops the recipe-name signal over-firing.
    for name, restriction in [("Vegan Chicken Curry", "vegan"),
                              ("Plant-Based Meat Bowl", "vegetarian"),
                              ("Vegan Cheese Toastie", "dairy-free")]:
        analogue = plan()
        for day in analogue["plan"].values():
            day[0]["recipe_name"] = name
        result, _ = generate(as_json(analogue),
                             payload={"dietary_restrictions": [restriction]})
        check(f"{name!r} is not rejected as {restriction}", result["success"],
              result.get("error"))

    # Unverifiable claims must not be reported as verified.
    result, _ = generate(as_json(plan()),
                         payload={"dietary_restrictions": ["low-sodium",
                                                           "diabetic-friendly"]})
    check("low-sodium/diabetic-friendly succeed structurally", result["success"],
          result.get("error"))
    dietary = result["verification"]["dietary"]
    check("...but are explicitly reported as unverifiable",
          set(dietary["unverifiable"]) == {"low_sodium", "diabetic_friendly"},
          dietary)
    check("...and are never listed as checked",
          "low_sodium" not in dietary["checked"], dietary["checked"])

    # Macro-assessable labels ARE assessed.
    result, _ = generate(as_json(plan()), payload={"dietary_restrictions": ["keto"]})
    check("keto is assessed from macros, not marked unverifiable",
          "keto" in result["verification"]["dietary"]["checked"],
          result["verification"]["dietary"])
    check("...and a 252g-carb day is flagged as breaching it",
          any("ketogenic" in a for a in result["verification"]["dietary"]["advisories"]),
          result["verification"]["dietary"]["advisories"])


# ---------------------------------------------------------------------------
# 3. completeness, retry and candidate comparison
# ---------------------------------------------------------------------------

def completeness_and_retry():
    from app.services import macro_targets as mt
    print(f"\n{BOLD}3. Completeness, retry bound and candidate comparison{RESET}")

    target = mt.MacroTarget(calories=2000, protein=100, carbs=250, fat=67,
                            basis="daily", meal_type="full_day", share=1.0)

    # A one-day plan can never pass, even with perfect macros.
    one_day = plan(days=1)
    result, agent = generate(as_json(one_day), macro_target=target,
                             extra_responses=[as_json(one_day)])
    check("one perfect day never passes as a week", result["success"] is False,
          result.get("error"))

    # A one-day retry never replaces a complete seven-day first attempt.
    off_target = plan(per_meal={"calories": 500, "protein": 20, "carbs": 60, "fat": 17})
    perfect_one_day = plan(days=1)
    result, agent = generate(as_json(off_target), macro_target=target,
                             extra_responses=[as_json(perfect_one_day)])
    check("a 7-day first attempt survives a 1-day retry", result["success"],
          result.get("error"))
    check("...and the returned plan still has 7 days",
          len(result["meal_plan"]["plan"]) == 7,
          list(result["meal_plan"]["plan"]))
    check("...and the retry was attempted exactly once", agent.calls == 2,
          agent.calls)

    # A dietary-unsafe retry never wins, even with better macros.
    off_target_safe = plan(per_meal={"calories": 500, "protein": 20, "carbs": 60,
                                     "fat": 17})
    perfect_but_milk = plan(ingredients=[{"name": "whole milk", "qty": "200ml"}])
    result, _ = generate(as_json(off_target_safe), macro_target=target,
                         payload={"dietary_restrictions": ["vegan"]},
                         extra_responses=[as_json(perfect_but_milk)])
    check("a dietary-unsafe retry never wins on macros", result["success"],
          result.get("error"))
    check("...and the milk plan was not returned",
          "milk" not in json.dumps(result["meal_plan"]).lower(),
          json.dumps(result["meal_plan"])[:200])

    # An incomplete retry never wins.
    incomplete_retry = plan(days=3)
    result, _ = generate(as_json(off_target), macro_target=target,
                         extra_responses=[as_json(incomplete_retry)])
    check("an incomplete retry never replaces a complete week",
          result["success"] and len(result["meal_plan"]["plan"]) == 7,
          result.get("error"))

    # Both candidates invalid -> fail closed, no success with unusable data.
    result, agent = generate("{}", macro_target=target, extra_responses=["{}"])
    check("two invalid candidates return success=False", result["success"] is False,
          result)
    check("...and no meal_plan is returned", "meal_plan" not in result, result)
    check("...with the retry still bounded to one", agent.calls == 2, agent.calls)

    # Retry is called at most once even when the second is also bad.
    result, agent = generate(as_json(off_target), macro_target=target,
                             extra_responses=[as_json(off_target)])
    check("retry happens at most once", agent.calls == 2, agent.calls)

    # A response that never parsed must still spend its one corrective retry -
    # it is the most recoverable failure there is, and an empty retry brief
    # used to skip it entirely.
    result, agent = generate("[]", extra_responses=[as_json(plan())])
    check("a parse failure spends its one retry and can recover",
          result["success"] and agent.calls == 2, (result.get("error"), agent.calls))
    result, agent = generate("[]", extra_responses=["[]"])
    check("...and two parse failures still stop at one retry",
          result["success"] is False and agent.calls == 2, agent.calls)

    # checked=False must never read as verified.
    incomplete_target = mt.MacroTarget(calories=2000, protein=0, carbs=0, fat=0,
                                       basis="daily", meal_type="full_day", share=1.0)
    verification = mt.verify_structured(incomplete_target, plan())
    check("a zero-macro target is refused, not 'hit'",
          verification["checked"] is False and not verification.get("hit"),
          verification)
    check("...and says which fields are missing",
          "protein" in verification["reason"], verification["reason"])
    check("MacroTarget.complete is False for zero macros",
          incomplete_target.complete is False)

    # macro_distance ranks an unchecked candidate worst, never best.
    check("an unchecked verification scores worst, not zero",
          mt.macro_distance({"checked": False}) == float("inf"))

    # The old 'All 1 days inside every range' summary.
    one_day_verification = mt.verify_structured(target, plan(days=1))
    check("a one-day plan does not summarise as a clean week",
          "All 1 days inside every range." not in one_day_verification["summary"],
          one_day_verification["summary"])
    check("...and is not reported as hit", one_day_verification["hit"] is False,
          one_day_verification)


# ---------------------------------------------------------------------------
# 4. calories and macros
# ---------------------------------------------------------------------------

def calories_and_macros():
    from app.services import macro_targets as mt
    print(f"\n{BOLD}4. Calorie and macro verification{RESET}")

    # Standard (calorie-only) mode must still check the calorie target.
    starved = plan(per_meal={"calories": 167, "protein": 8, "carbs": 21, "fat": 5})
    result, agent = generate(as_json(starved),
                             extra_responses=[as_json(starved)])
    check("a 2000 kcal request returning 500 kcal days is caught in standard mode",
          result["verification"]["calories"]["hit"] is False,
          result["verification"]["calories"]["summary"])
    check("...and it triggered the one corrective retry", agent.calls == 2,
          agent.calls)

    good = plan()
    result, agent = generate(as_json(good))
    check("seven correct calorie days pass standard mode",
          result["success"] and result["verification"]["calories"]["hit"],
          result["verification"]["calories"])
    check("...with no retry spent", agent.calls == 1, agent.calls)

    # Stated summary/meta must not override the summed meals.
    liar = plan(per_meal={"calories": 167, "protein": 8, "carbs": 21, "fat": 5})
    liar["meta"]["total_daily_calories"] = 2000
    liar["summary"]["avg_daily_calories"] = 2000
    result, _ = generate(as_json(liar), extra_responses=[as_json(liar)])
    check("a claimed meta/summary calorie total does not override the meals",
          result["verification"]["calories"]["hit"] is False,
          result["verification"]["calories"]["summary"])

    # Strict mode: all four macros on all seven days.
    target = mt.MacroTarget(calories=2000, protein=100, carbs=250, fat=67,
                            basis="daily", meal_type="full_day", share=1.0)
    result, _ = generate(as_json(plan()), macro_target=target)
    macros = result["verification"]["macros"]
    check("strict mode checks all seven days", macros["days_total"] == 7, macros)
    check("...and every day reports all four macros",
          all(set(d["macros"]) == {"calories", "protein", "carbs", "fat"}
              for d in macros["days"]), macros["days"][0])

    # Energy consistency: calories that do not match 4/4/9.
    inconsistent = plan(per_meal={"calories": 667, "protein": 5, "carbs": 10, "fat": 2})
    verification = mt.verify_structured(target, inconsistent)
    check("calories materially inconsistent with macros are caught",
          verification["energy_inconsistent_days"], verification["summary"])
    check("...and the plan is not reported as hit", verification["hit"] is False,
          verification["summary"])

    consistent = mt._energy_consistency({"calories": 2000, "protein": 100,
                                         "carbs": 250, "fat": 67})
    check("a 4/4/9-consistent day passes the energy check",
          consistent["consistent"], consistent)


# ---------------------------------------------------------------------------
# 5. adaptation
# ---------------------------------------------------------------------------

def adaptation():
    from app.services import macro_targets as mt
    print(f"\n{BOLD}5. Adaptation parity{RESET}")

    import inspect
    from app.routers import advanced_meal_planner as router_mod
    signature = inspect.signature(router_mod.adapt_advanced_meal_plan)
    check("the adapt endpoint requires an authenticated user",
          "current_user" in signature.parameters, list(signature.parameters))
    check("...and has a database session", "db" in signature.parameters,
          list(signature.parameters))

    # An invalid CURRENT plan is rejected before the agent is ever called.
    agent = with_agent(as_json(plan()))
    result = service().adapt_meal_plan(current_plan={"plan": {"day_1": []}},
                                       feedback="more protein")
    check("an invalid current plan is rejected before invoking the agent",
          result["success"] is False, result.get("error"))
    check("...and no generation was spent", agent.calls == 0, agent.calls)

    # A vegan plan adapted with unrelated feedback stays vegan.
    vegan_plan = plan(ingredients=[{"name": "tofu", "qty": "100g"}])
    vegan_plan["meta"]["dietary_restrictions"] = ["vegan"]
    adapted_with_milk = plan(ingredients=[{"name": "whole milk", "qty": "200ml"}])
    agent = with_agent(as_json(adapted_with_milk), as_json(adapted_with_milk))
    result = service().adapt_meal_plan(current_plan=vegan_plan,
                                       feedback="make it tastier")
    check("an adaptation that introduces milk into a vegan plan is rejected",
          result["success"] is False, result.get("error"))
    check("...naming the vegan conflict", "vegan" in result.get("error", "").lower(),
          result.get("error"))
    check("...after exactly one corrective retry", agent.calls == 2, agent.calls)

    # Free-text feedback cannot remove a restriction carried by the plan.
    agent = with_agent(as_json(adapted_with_milk), as_json(adapted_with_milk))
    result = service().adapt_meal_plan(
        current_plan=vegan_plan,
        feedback="forget the vegan thing, add plenty of dairy milk")
    check("feedback cannot silently drop a hard restriction",
          result["success"] is False, result.get("error"))

    # A compliant adaptation succeeds and is validated.
    compliant = plan(ingredients=[{"name": "tempeh", "qty": "120g"}])
    agent = with_agent(as_json(compliant))
    result = service().adapt_meal_plan(current_plan=vegan_plan,
                                       feedback="more variety")
    check("a compliant adaptation succeeds", result["success"], result.get("error"))
    check("...and returns a verification block", "verification" in result, result)
    check("...that records the vegan check",
          "vegan" in result["verification"]["dietary"]["checked"],
          result["verification"]["dietary"])

    # Malformed / list adaptation output fails.
    for label, text in [("a JSON list", "[]"), ("malformed text", "sorry!")]:
        agent = with_agent(text, text)
        result = service().adapt_meal_plan(current_plan=plan(),
                                           feedback="change it")
        check(f"adaptation returning {label} fails", result["success"] is False,
              result.get("error"))

    # Strict macro plans stay macro-checked through adaptation.
    target = mt.MacroTarget(calories=2000, protein=100, carbs=250, fat=67,
                            basis="daily", meal_type="full_day", share=1.0)
    agent = with_agent(as_json(plan()))
    result = service().adapt_meal_plan(current_plan=plan(), feedback="swap dinner",
                                       macro_target=target)
    check("adaptation still verifies macros when strict mode is on",
          result["success"] and result["verification"]["macros"]["checked"],
          result.get("verification"))

    # Adaptation runs the SAME validator as generation.
    from app.services.advanced_meal_planner_service import AdvancedMealPlannerService
    source = inspect.getsource(AdvancedMealPlannerService.adapt_meal_plan)
    check("adaptation calls the shared _attempt/_assess pipeline",
          "_attempt(" in source, source[:200])
    check("generation calls the same pipeline",
          "_attempt(" in inspect.getsource(
              AdvancedMealPlannerService.generate_meal_plan))

    # Size caps exist so a huge plan/feedback cannot inflate the request.
    from app.services import advanced_meal_planner_service as mod
    big_plan = plan()
    big_plan["meta"]["assumptions"] = "x" * 100000
    agent = with_agent(as_json(plan()))
    service().adapt_meal_plan(current_plan=big_plan, feedback="y" * 50000)
    prompt = agent.prompts[0]
    check("the adaptation prompt is bounded despite huge inputs",
          len(prompt) < mod.MAX_PLAN_CHARS + mod.MAX_FEEDBACK_CHARS + 8000,
          len(prompt))


# ---------------------------------------------------------------------------
# 6. JSON extraction
# ---------------------------------------------------------------------------

def json_extraction():
    from app.services import meal_plan_contract as mpc
    print(f"\n{BOLD}6. Canonical JSON extraction{RESET}")

    cases = [
        ("fenced JSON", '```json\n{"a": 1}\n```', {"a": 1}, None),
        ("prose around JSON", 'Here you go:\n{"a": 1}\nEnjoy!', {"a": 1}, None),
        ("braces inside a string", '{"notes": "use the {small} pan"}',
         {"notes": "use the {small} pan"}, None),
        ("escaped quotes", '{"notes": "say \\"hi\\""}', {"notes": 'say "hi"'}, None),
        ("a JSON list", "[]", None, mpc.NOT_OBJECT),
        ("a scalar", "42", None, mpc.NOT_OBJECT),
        ("empty text", "   ", None, mpc.EMPTY),
        ("truncated JSON", '{"plan": {"day_1": [{"calories": 3', None, mpc.TRUNCATED),
        ("two competing objects", '{"a": 1}\n{"b": 2}', None, mpc.AMBIGUOUS),
        ("no JSON at all", "I cannot help with that", None, mpc.MALFORMED),
    ]
    for label, text, want_obj, want_code in cases:
        obj, code, _msg = mpc.extract_json_object(text)
        check(f"{label} -> {want_code or 'parsed'}",
              obj == want_obj and code == want_code, f"obj={obj} code={code}")

    check("truncated is distinguished from malformed",
          mpc.extract_json_object('{"a": [1, 2')[1] == mpc.TRUNCATED
          and mpc.extract_json_object('not json')[1] == mpc.MALFORMED)

    # One shared helper: the service must not re-implement extraction.
    import inspect
    from app.services import advanced_meal_planner_service as mod
    source = inspect.getsource(mod)
    check("the service does not count braces manually",
          "brace_count" not in source)
    check("...and uses the shared extractor",
          "extract_json_object" in source)


# ---------------------------------------------------------------------------
# 7. logging hygiene
# ---------------------------------------------------------------------------

def logging_hygiene():
    import inspect
    from app.services import advanced_meal_planner_service as mod
    print(f"\n{BOLD}7. Logging hygiene{RESET}")

    source = inspect.getsource(mod)
    for banned in ["logger.info(f\"AdvancedMealPlanner query",
                   "logger.info(f\"AdvancedMealPlanner raw response",
                   "logger.info(f\"AdvancedMealPlanner extracted text",
                   "logger.info(f\"AdvancedMealPlanner adaptation prompt"]:
        check(f"no longer logs {banned.split('\"')[1][:40]!r}",
              banned not in source)

    check("bounded metadata is logged instead",
          "_describe_candidate" in source)
    check("the metadata line contains no plan text",
          "raw_text[" not in inspect.getsource(mod._describe_candidate)
          or "len(candidate.raw_text)" in inspect.getsource(mod._describe_candidate))


# ---------------------------------------------------------------------------
# 8. mutation tests
# ---------------------------------------------------------------------------

def mutations():
    from app.services import meal_plan_contract as mpc
    from app.services import dietary_rules as dr
    from app.services import macro_targets as mt
    print(f"\n{BOLD}8. Mutations — each guard is load-bearing{RESET}")

    # M1: bypass structural validation -> an incomplete week is accepted.
    original = mpc.validate_structure
    mpc.validate_structure = lambda p, m: mpc.StructureResult(True, [], 7, 21)
    try:
        result, _ = generate(as_json(plan(days=1)))
        broken = result["success"]
    finally:
        mpc.validate_structure = original
    check("M1 bypassing structural validation accepts a one-day plan", broken)

    # M2: bypass the dietary audit -> vegan + milk survives.
    original_audit = dr.audit_plan
    dr.audit_plan = lambda p, r, macro_totals_by_day=None: dr.DietaryAudit()
    try:
        milk = plan(ingredients=[{"name": "whole milk", "qty": "200ml"}])
        result, _ = generate(as_json(milk),
                             payload={"dietary_restrictions": ["vegan"]})
        broken = result["success"]
    finally:
        dr.audit_plan = original_audit
    check("M2 bypassing the dietary audit lets vegan+milk through", broken)

    # M3: the raw days_on_target comparison picks the WRONG candidate.
    #
    # Asserted against the comparison itself rather than end to end, because
    # the structural gate is a second, independent line of defence: with only
    # `better` mutated the one-day plan is still caught by `usable`. Testing
    # end to end would therefore pass for the wrong reason and prove nothing
    # about the comparison. Both layers are checked explicitly below.
    target = mt.MacroTarget(calories=2000, protein=100, carbs=250, fat=67,
                            basis="daily", meal_type="full_day", share=1.0)
    assess = service()._assess
    seven_off = assess(as_json(plan(per_meal={"calories": 500, "protein": 20,
                                              "carbs": 60, "fat": 17})),
                       meals_per_day=3, restrictions=[], target_calories=2000,
                       macro_target=target)
    one_perfect = assess(as_json(plan(days=1)), meals_per_day=3, restrictions=[],
                         target_calories=2000, macro_target=target)

    check("M3 setup: the 1-day plan really does score more days_on_target",
          one_perfect.macro["days_on_target"] > seven_off.macro["days_on_target"],
          (one_perfect.macro["days_on_target"], seven_off.macro["days_on_target"]))

    def days_on_target_better(candidate, incumbent):
        return ((candidate.macro or {}).get("days_on_target", 0)
                > (incumbent.macro or {}).get("days_on_target", 0))

    check("M3 the old raw days_on_target comparison WOULD pick the 1-day plan",
          days_on_target_better(one_perfect, seven_off) is True)
    check("M3 the real comparison refuses it (incomplete week is not usable)",
          mpc.better(one_perfect, seven_off) is False,
          f"one_perfect.usable={one_perfect.usable} "
          f"seven_off.usable={seven_off.usable}")
    check("M3 the complete-but-off-target week is the usable one",
          seven_off.usable and not one_perfect.usable)

    # And with BOTH guards removed the one-day plan really does reach the user,
    # which is what the two guards are jointly preventing.
    original_better = mpc.better
    original_structure = mpc.validate_structure
    mpc.better = days_on_target_better
    mpc.validate_structure = lambda p, m: mpc.StructureResult(True, [], 7, 21)
    try:
        off = plan(per_meal={"calories": 500, "protein": 20, "carbs": 60, "fat": 17})
        result, _ = generate(as_json(off), macro_target=target,
                             extra_responses=[as_json(plan(days=1))])
        broken = result["success"] and len(result["meal_plan"]["plan"]) == 1
    finally:
        mpc.better = original_better
        mpc.validate_structure = original_structure
    check("M3 with both guards removed, the 1-day retry reaches the user", broken,
          result)

    # M4: disable adaptation validation -> restrictions disappear.
    from app.services.advanced_meal_planner_service import AdvancedMealPlannerService
    original_assess = AdvancedMealPlannerService._assess

    def blind_assess(self, text, **kwargs):
        parsed, _code, _msg = mpc.extract_json_object(text)
        return mpc.PlanCandidate(plan=parsed, raw_text=text or "",
                                 structure=mpc.StructureResult(True, [], 7, 21))

    AdvancedMealPlannerService._assess = blind_assess
    try:
        vegan_plan = plan(ingredients=[{"name": "tofu"}])
        vegan_plan["meta"]["dietary_restrictions"] = ["vegan"]
        agent = with_agent(as_json(plan(ingredients=[{"name": "whole milk"}])))
        result = service().adapt_meal_plan(current_plan=vegan_plan,
                                           feedback="make it creamy")
        broken = result["success"] and "milk" in json.dumps(
            result["adapted_plan"]).lower()
    finally:
        AdvancedMealPlannerService._assess = original_assess
    check("M4 disabling adaptation validation lets milk into a vegan plan", broken)

    # M5: remove the calorie check -> 500 kcal days pass unnoticed.
    original_calories = mpc.verify_calories
    mpc.verify_calories = lambda p, t, tolerance=0.10: {"checked": False,
                                                        "reason": "disabled",
                                                        "days": []}
    try:
        starved = plan(per_meal={"calories": 167, "protein": 8, "carbs": 21,
                                 "fat": 5})
        agent = with_agent(as_json(starved))
        result = service().generate_meal_plan({**BASE_PAYLOAD})
        broken = result["success"] and agent.calls == 1
    finally:
        mpc.verify_calories = original_calories
    check("M5 removing the calorie check lets 500 kcal days pass with no retry",
          broken)

    # Everything is genuinely restored.
    result, _ = generate(as_json(plan(days=1)))
    check("all mutations restored: a one-day plan is rejected again",
          result["success"] is False)


# ---------------------------------------------------------------------------
# 9. review findings
# ---------------------------------------------------------------------------

def review_findings():
    """One group per confirmed adversarial finding."""
    from app.services import dietary_rules as dr
    from app.services import meal_plan_contract as mpc
    print(f"\n{BOLD}9. Confirmed review findings{RESET}")

    # --- 1: the corrective calorie retry must actually be selectable -------
    bad = plan(per_meal={"calories": 167, "protein": 8, "carbs": 21, "fat": 5})
    good = plan()
    result, agent = generate(as_json(bad), extra_responses=[as_json(good)])
    day1 = sum(m["macros"]["calories"] for m in result["meal_plan"]["plan"]["day_1"])
    check("1. a corrected calorie retry IS returned in standard mode",
          day1 > 1800, f"day_1={day1} kcal")
    check("1. ...and the retry it spent was not wasted",
          agent.calls == 2 and result["verification"]["calories"]["hit"],
          (agent.calls, result["verification"]["calories"]["summary"]))
    check("1. standard-mode quality is finite, not inf",
          mpc.PlanCandidate(
              plan=good, calories={"checked": True, "days": [
                  {"target": 2000, "delta": 0}]}).quality != float("inf"))

    # A worse retry still must not win.
    result, _ = generate(as_json(good), extra_responses=[as_json(bad)])
    day1 = sum(m["macros"]["calories"] for m in result["meal_plan"]["plan"]["day_1"])
    check("1. a WORSE calorie retry never replaces a good first attempt",
          day1 > 1800, f"day_1={day1}")

    # --- 2: restrictions survive generation -> adaptation ------------------
    compliant = plan(ingredients=[{"name": "tofu", "qty": "100g"}])
    compliant["meta"]["dietary_restrictions"] = []      # model omits them
    with_agent(as_json(compliant))
    gen = service().generate_meal_plan(
        {**BASE_PAYLOAD, "dietary_restrictions": ["vegan"]})
    check("2. the returned plan carries the AUTHORITATIVE restrictions, "
          "not the model's claim",
          gen["meal_plan"]["meta"]["dietary_restrictions"] == ["vegan"],
          gen["meal_plan"]["meta"]["dietary_restrictions"])

    milk = plan(ingredients=[{"name": "whole milk", "qty": "200ml"}])
    agent = with_agent(as_json(milk), as_json(milk))
    ad = service().adapt_meal_plan(current_plan=gen["meal_plan"],
                                   feedback="make it creamier")
    check("2. adapting that plan still enforces vegan",
          ad["success"] is False, ad.get("error"))
    check("2. ...and milk is not returned",
          "milk" not in json.dumps(ad.get("adapted_plan", "")).lower())

    # --- 3: scoped exemptions ---------------------------------------------
    for ingredient, restriction, why in [
        ("vegan cheese with cow milk", dr.VEGAN, "milk"),
        ("gluten-free bread made with wheat flour", dr.GLUTEN_FREE, "wheat"),
        ("coconut milk with whey", dr.DAIRY_FREE, "whey"),
        ("almond milk and paneer", dr.DAIRY_FREE, "paneer"),
    ]:
        check(f"3. {ingredient!r} is caught ({why})",
              dr.forbidden_hit(ingredient, restriction) is not None,
              dr.forbidden_hit(ingredient, restriction))
    for ingredient, restriction in [
        ("vegan cheese", dr.VEGAN), ("coconut milk", dr.DAIRY_FREE),
        ("gluten-free bread", dr.GLUTEN_FREE), ("gluten free pasta", dr.GLUTEN_FREE),
        ("vegan cream cheese", dr.DAIRY_FREE), ("peanut butter", dr.DAIRY_FREE),
        ("plant-based chicken strips", dr.VEGETARIAN),
    ]:
        check(f"3. {ingredient!r} is still exempt",
              dr.forbidden_hit(ingredient, restriction) is None,
              dr.forbidden_hit(ingredient, restriction))

    # --- 5: verification reaches the API in standard mode ------------------
    import inspect
    from app.routers import advanced_meal_planner as router_mod
    source = inspect.getsource(router_mod.generate_advanced_meal_plan)
    attach = source.index('plan["verification"]')
    gated = source.index("if target:")
    check("5. verification is attached BEFORE (outside) the macro-mode gate",
          attach < gated, "verification is still inside `if target:`")

    result, _ = generate(as_json(plan()),
                         payload={"dietary_restrictions": ["low-sodium"]})
    v = result["verification"]
    check("5. standard-mode results carry calorie verification",
          v["calories"]["checked"], v["calories"])
    check("5. ...and dietary advisories/unverifiable notes",
          v["dietary"]["unverifiable"] == ["low_sodium"], v["dietary"])

    # --- 7: meals-per-day can change through adaptation -------------------
    three = plan(meals_per_day=3)
    four = plan(meals_per_day=4)
    agent = with_agent(as_json(four))
    result = service().adapt_meal_plan(
        current_plan=three, feedback="add an afternoon snack",
        new_requirements={"meals_per_day": 4}, meals_per_day=4)
    check("7. changing 3 meals/day to 4 reaches the agent",
          agent.calls >= 1, agent.calls)
    check("7. ...and succeeds", result["success"], result.get("error"))
    check("7. ...returning a 4-meal plan",
          all(len(d) == 4 for d in result["adapted_plan"]["plan"].values()),
          [len(d) for d in result["adapted_plan"]["plan"].values()])

    # The OUTPUT is still held to the new count.
    agent = with_agent(as_json(three), as_json(three))
    result = service().adapt_meal_plan(
        current_plan=three, feedback="add a snack",
        new_requirements={"meals_per_day": 4}, meals_per_day=4)
    check("7. an adaptation that ignores the new meal count is rejected",
          result["success"] is False, result.get("error"))

    # --- 8: qty is required -----------------------------------------------
    no_qty = plan()
    for day in no_qty["plan"].values():
        for m in day:
            m["ingredients"] = [{"name": "oats"}]
    result, _ = generate(as_json(no_qty), extra_responses=[as_json(no_qty)])
    check("8. ingredients without a quantity are rejected",
          result["success"] is False, result.get("error"))
    check("8. ...naming qty in the error", "qty" in result.get("error", ""),
          result.get("error"))
    blank_qty = plan(ingredients=[{"name": "oats", "qty": "  "}])
    result, _ = generate(as_json(blank_qty), extra_responses=[as_json(blank_qty)])
    check("8. a blank quantity is rejected", result["success"] is False,
          result.get("error"))

    # --- 10: chestnut ------------------------------------------------------
    for ingredient, want_hit in [("chestnut", True), ("chestnuts", True),
                                 ("chestnut flour", True),
                                 ("water chestnut", False),
                                 ("water chestnuts", False)]:
        hit = dr.forbidden_hit(ingredient, dr.NUT_FREE)
        check(f"10. nut-free + {ingredient!r} -> "
              f"{'violation' if want_hit else 'exempt'}",
              bool(hit) == want_hit, hit)


def codex_findings():
    """The three issues from the independent Codex verification pass."""
    from app.services import dietary_rules as dr
    from app.services import advanced_meal_planner_service as mod
    print(f"\n{BOLD}11. Codex verification findings{RESET}")

    # --- HIGH 1: authoritative calorie target survives adaptation ----------
    lying = plan()                                   # meals really total ~2001
    lying["meta"]["total_daily_calories"] = 500      # the model's false claim
    with_agent(as_json(lying))
    gen = service().generate_meal_plan({**BASE_PAYLOAD, "target_calories": 2000})
    meta = gen["meal_plan"]["meta"]
    check("H1. generation records the authoritative requested target",
          meta.get("requested_daily_calories") == 2000, meta)
    check("H1. the model's false total_daily_calories is never the target",
          mod._infer_target_calories(gen["meal_plan"]) == 2000,
          mod._infer_target_calories(gen["meal_plan"]))

    # A. adapt with NO new target -> still 2000, not 500.
    agent = with_agent(as_json(plan()))
    ad = service().adapt_meal_plan(current_plan=gen["meal_plan"],
                                   feedback="more variety")
    check("H1-A. adapting with no new target still verifies against 2000",
          ad["verification"]["calories"]["days"][0]["target"] == 2000,
          ad["verification"]["calories"]["days"][0])
    check("H1-A. ...and the adapted plan carries it forward",
          ad["adapted_plan"]["meta"]["requested_daily_calories"] == 2000,
          ad["adapted_plan"]["meta"])
    check("H1-A. ...so the plan is NOT judged a success against 500",
          ad["verification"]["calories"]["hit"] is True,
          ad["verification"]["calories"]["summary"])

    # B. adapt with an EXPLICIT new target -> that becomes authoritative.
    at_2200 = plan(per_meal={"calories": 733, "protein": 36, "carbs": 92, "fat": 24})
    agent = with_agent(as_json(at_2200))
    ad2 = service().adapt_meal_plan(current_plan=gen["meal_plan"],
                                    feedback="bulk a bit",
                                    new_requirements={"target_calories": 2200},
                                    target_calories=2200)
    check("H1-B. an explicitly requested new target becomes authoritative",
          ad2["verification"]["calories"]["days"][0]["target"] == 2200,
          ad2["verification"]["calories"]["days"][0])
    check("H1-B. ...and is stamped onto the adapted plan",
          ad2["adapted_plan"]["meta"]["requested_daily_calories"] == 2200,
          ad2["adapted_plan"]["meta"])

    # Repeated adaptation must not lose it.
    agent = with_agent(as_json(plan()))
    ad3 = service().adapt_meal_plan(current_plan=ad["adapted_plan"],
                                    feedback="swap a dinner")
    check("H1. a SECOND adaptation still knows the authoritative target",
          ad3["adapted_plan"]["meta"]["requested_daily_calories"] == 2000,
          ad3["adapted_plan"]["meta"])

    # A plan with no authoritative target reports unchecked, never invented.
    legacy = plan()
    legacy["meta"].pop("requested_daily_calories", None)
    legacy["meta"]["total_daily_calories"] = 500
    check("H1. a legacy plan yields NO target rather than the model's claim",
          mod._infer_target_calories(legacy) is None,
          mod._infer_target_calories(legacy))

    # C. the frontend reads the authoritative value first.
    #
    # JSX comments are stripped before checking: the explanatory comment in
    # that block legitimately mentions total_daily_calories, and asserting on
    # raw source order would be testing the prose rather than the code.
    import re as _re
    app_js = (Path(__file__).resolve().parent.parent
              / "frontend" / "src" / "App.js").read_text(encoding="utf-8")
    summary = app_js[app_js.index("Plan Summary"):]
    summary = summary[:summary.index("Daily Calories")]
    code = _re.sub(r"\{\s*/\*.*?\*/\s*\}", " ", summary, flags=_re.S)
    check("H1-C. the frontend summary reads requested_daily_calories",
          "requested_daily_calories" in code, code[-300:])
    check("H1-C. ...ahead of the model's total_daily_calories",
          code.index("requested_daily_calories") < code.index("total_daily_calories"),
          code[-300:])
    check("H1-C. ...and falls back to the verified target before the claim",
          code.index("verification?.calories?.target")
          < code.index("total_daily_calories"), code[-300:])

    # --- HIGH 2: clause boundaries ----------------------------------------
    boundary_cases = [
        ("vegan cheese, milk", dr.VEGAN, "milk"),
        ("vegan burger, egg scramble", dr.VEGAN, "egg"),
        ("gluten-free bread, wheat porridge", dr.GLUTEN_FREE, "wheat"),
        ("vegan cheese and milk", dr.VEGAN, "milk"),
        ("vegan cheese; milk", dr.VEGAN, "milk"),
        ("vegan cheese / milk", dr.VEGAN, "milk"),
        ("vegan cheese\nmilk", dr.VEGAN, "milk"),
        ("vegan cheese\n• milk", dr.VEGAN, "milk"),
        ("gluten-free bread with wheat flour", dr.GLUTEN_FREE, "wheat"),
        ("coconut milk, whey", dr.DAIRY_FREE, "whey"),
        ("peanut butter, cheddar", dr.DAIRY_FREE, "cheddar"),
    ]
    for ingredient, restriction, expected in boundary_cases:
        hit = dr.forbidden_hit(ingredient, restriction)
        check(f"H2. {ingredient!r} -> {expected}", hit is not None, hit)

    for ingredient, restriction in [
        ("vegan chicken curry", dr.VEGETARIAN),
        ("plant-based meat bowl", dr.VEGETARIAN),
        ("gluten-free bread", dr.GLUTEN_FREE),
        ("coconut milk", dr.DAIRY_FREE),
        ("peanut butter", dr.DAIRY_FREE),
        ("water chestnut", dr.NUT_FREE),
        ("vegan cream cheese", dr.DAIRY_FREE),
        ("almond milk", dr.DAIRY_FREE),
    ]:
        check(f"H2. {ingredient!r} stays exempt",
              dr.forbidden_hit(ingredient, restriction) is None,
              dr.forbidden_hit(ingredient, restriction))

    # End to end through the audit, as a list of separate ingredients.
    listed = plan(ingredients=[{"name": "vegan cheese, milk", "qty": "50g"}])
    result, _ = generate(as_json(listed),
                         payload={"dietary_restrictions": ["vegan"]},
                         extra_responses=[as_json(listed)])
    check("H2. an ingredient string hiding milk after a comma fails the plan",
          result["success"] is False, result.get("error"))

    # --- MEDIUM 3: animal-named plants ------------------------------------
    for name, restriction, clean in [
        ("Chicken of the Woods", dr.VEGETARIAN, True),
        ("Chicken of the Woods", dr.VEGAN, True),
        ("Hen of the Woods", dr.VEGETARIAN, True),
        ("Oyster mushroom", dr.VEGETARIAN, True),
        ("Beefsteak tomato", dr.VEGETARIAN, True),
        ("Chicken Biryani", dr.VEGETARIAN, False),
        ("Roast chicken", dr.VEGETARIAN, False),
        ("Oyster sauce", dr.VEGETARIAN, False),
        ("Chicken of the Woods with chicken stock", dr.VEGETARIAN, False),
    ]:
        hit = dr.forbidden_hit(name, restriction)
        check(f"M3. {name!r} ({restriction}) -> "
              f"{'allowed' if clean else 'forbidden'}",
              (hit is None) == clean, hit)

    # Through the recipe-name audit, which is where it surfaced.
    fungus = plan()
    for day in fungus["plan"].values():
        day[0]["recipe_name"] = "Chicken of the Woods Stir Fry"
    result, _ = generate(as_json(fungus),
                         payload={"dietary_restrictions": ["vegetarian"]})
    check("M3. a 'Chicken of the Woods' recipe name does not fail a "
          "vegetarian plan", result["success"], result.get("error"))


def separator_boundaries():
    """
    Every inline separator must be a hard boundary the modifier exemption
    cannot cross.

    The bypass this covers: normalisation flattened "+", "-", en dash and em
    dash to whitespace BEFORE exemption masking, so "vegan cheese + milk"
    became "vegan cheese milk" and the two-word scope after "vegan" swallowed
    the milk. Table-driven on purpose - a new separator variant should be one
    row here, not a new special case in the matcher.
    """
    from app.services import dietary_rules as dr
    print(f"\n{BOLD}12. Inline separators are hard boundaries{RESET}")

    # Each row is the LITERAL text, not a suffix glued onto a stem, so a
    # case says exactly what it tests.
    separators = [
        ("plus sign", "vegan cheese + milk"),
        ("hyphen", "vegan cheese - milk"),
        ("en dash", "vegan cheese – milk"),
        ("em dash", "vegan cheese — milk"),
        ("textual plus", "vegan cheese plus milk"),
        ("comma", "vegan cheese, milk"),
        ("semicolon", "vegan cheese; milk"),
        ("slash", "vegan cheese / milk"),
        ("newline", "vegan cheese\nmilk"),
        ("bullet", "vegan cheese\n• milk"),
        ("bullet hyphen", "vegan cheese\n- milk"),
        ("and", "vegan cheese and milk"),
        ("with", "vegan cheese with milk"),
    ]

    # --- direct rule behaviour -------------------------------------------
    for label, text in separators:
        check(f"12. {label}: {text!r} -> milk violation",
              dr.forbidden_hit(text, dr.VEGAN) == "milk",
              f"normalised={dr._normalise_text(text)!r} "
              f"hit={dr.forbidden_hit(text, dr.VEGAN)}")

    # --- through the full audit, hard_safe must be False -------------------
    for label, text in separators:
        audit = dr.audit_plan(
            plan(ingredients=[{"name": text, "qty": "50g"}]), ["vegan"])
        check(f"12. {label}: audit_plan reports hard_safe=False",
              audit.hard_safe is False, audit.summary())

    # --- end to end through the planner, on a valid seven-day plan ---------
    for label, text in separators:
        hidden = plan(ingredients=[{"name": text, "qty": "50g"}])
        result, _ = generate(as_json(hidden),
                             payload={"dietary_restrictions": ["vegan"]},
                             extra_responses=[as_json(hidden)])
        check(f"12. {label}: a 7-day plan hiding milk after it is rejected",
              result["success"] is False, result.get("error"))

    # --- the ASCII hyphen's two jobs, and why the rule is spacing-based ---
    #
    # A hyphen is only a boundary when whitespace sits on BOTH sides. The
    # looser "hyphen followed by whitespace" was measured and rejected: it
    # turns a typo'd modifier into a boundary and invents violations -
    # "gluten- free bread" reports `bread`, "plant- based meat bowl" reports
    # `meat`. Inventing a conflict on a compliant plan is worse than the
    # narrow gap it would close, so the trailing-hyphen shape
    # ("cheese- milk") is deliberately NOT a boundary.
    check("12. a typo'd modifier does not invent a violation "
          "('gluten- free bread')",
          dr.forbidden_hit("gluten- free bread", dr.GLUTEN_FREE) is None,
          dr.forbidden_hit("gluten- free bread", dr.GLUTEN_FREE))
    check("12. ...nor 'plant- based meat bowl'",
          dr.forbidden_hit("plant- based meat bowl", dr.VEGETARIAN) is None,
          dr.forbidden_hit("plant- based meat bowl", dr.VEGETARIAN))

    # --- other restrictions, same boundary semantics ----------------------
    for text, restriction, expected in [
        ("gluten-free bread + wheat porridge", dr.GLUTEN_FREE, "wheat"),
        ("vegan burger + egg scramble", dr.VEGAN, "egg"),
        ("dairy-free dessert – whey", dr.DAIRY_FREE, "whey"),
        ("Chicken of the Woods + chicken stock", dr.VEGETARIAN, "chicken"),
        ("vegan chicken + milk", dr.VEGAN, "milk"),
        ("coconut milk + whey", dr.DAIRY_FREE, "whey"),
    ]:
        check(f"12. {text!r} -> {expected}",
              dr.forbidden_hit(text, restriction) == expected,
              dr.forbidden_hit(text, restriction))

    # --- controls: a tight hyphen is a JOINER, not a separator ------------
    for text, restriction in [
        ("vegan chicken curry", dr.VEGETARIAN),
        ("plant-based meat bowl", dr.VEGETARIAN),
        ("gluten-free bread", dr.GLUTEN_FREE),
        ("gluten free pasta", dr.GLUTEN_FREE),
        ("coconut milk", dr.DAIRY_FREE),
        ("peanut butter", dr.DAIRY_FREE),
        ("water chestnut", dr.NUT_FREE),
        ("Chicken of the Woods", dr.VEGETARIAN),
        ("vegan cream cheese", dr.DAIRY_FREE),
        ("sun-dried tomatoes", dr.VEGAN),
    ]:
        check(f"12. control: {text!r} stays allowed",
              dr.forbidden_hit(text, restriction) is None,
              dr.forbidden_hit(text, restriction))

    # A tight hyphen must still join, or "gluten-free" stops being one word.
    check("12. a tight hyphen is not a boundary (gluten-free stays one term)",
          "|" not in dr._normalise_text("gluten-free bread"),
          dr._normalise_text("gluten-free bread"))
    check("12. a spaced hyphen IS a boundary",
          "|" in dr._normalise_text("vegan cheese - milk"),
          dr._normalise_text("vegan cheese - milk"))

    # A clean vegan plan still succeeds end to end.
    clean = plan(ingredients=[{"name": "vegan cheese + tofu", "qty": "50g"}])
    result, _ = generate(as_json(clean),
                         payload={"dietary_restrictions": ["vegan"]})
    check("12. a compliant plan with a '+' separator still succeeds",
          result["success"], result.get("error"))


def review_mutations():
    """Each fix reverted must reproduce its reported bug."""
    from app.services import dietary_rules as dr
    from app.services import meal_plan_contract as mpc
    print(f"\n{BOLD}10. Mutations for the review findings{RESET}")

    # 1: put macro_distance back into standard-mode quality.
    original = mpc.PlanCandidate.quality
    mpc.PlanCandidate.quality = property(
        lambda self: self.macro_distance + mpc.calorie_distance(self.calories))
    try:
        bad = plan(per_meal={"calories": 167, "protein": 8, "carbs": 21, "fat": 5})
        result, agent = generate(as_json(bad), extra_responses=[as_json(plan())])
        day1 = sum(m["macros"]["calories"]
                   for m in result["meal_plan"]["plan"]["day_1"])
        broken = agent.calls == 2 and day1 < 600
    finally:
        mpc.PlanCandidate.quality = original
    check("MUTATION 1: inf macro distance makes the calorie retry unselectable",
          broken, f"day_1={day1}")

    # 3: whole-string exemption.
    original_mask = dr._mask_cleared
    dr._mask_cleared = lambda normalised, restriction: (
        "" if dr._cleared(normalised, restriction) else normalised)
    try:
        broken = dr.forbidden_hit("vegan cheese with cow milk", dr.VEGAN) is None
    finally:
        dr._mask_cleared = original_mask
    check("MUTATION 3: whole-string exemption lets 'cow milk' through", broken)

    # 4: recipe names only when ingredients are empty.
    hidden = plan()
    for day in hidden["plan"].values():
        day[0]["recipe_name"] = "Chicken Biryani"
        day[0]["ingredients"] = [{"name": "rice", "qty": "150g"}]
    original_texts = dr._meal_ingredient_texts
    original_audit = dr.audit_plan

    def ingredients_only(plan_obj, restrictions, macro_totals_by_day=None):
        stripped = json.loads(json.dumps(plan_obj))
        for day in (stripped.get("plan") or {}).values():
            for m in day:
                m.pop("recipe_name", None)
        return original_audit(stripped, restrictions, macro_totals_by_day)

    dr.audit_plan = ingredients_only
    try:
        audit = dr.audit_plan(hidden, ["vegetarian"])
        broken = audit.hard_safe
    finally:
        dr.audit_plan = original_audit
    check("MUTATION 4: ignoring recipe names lets 'Chicken Biryani' pass "
          "a vegetarian check", broken)

    # Restored.
    check("restored: the hidden chicken is caught again",
          not dr.audit_plan(hidden, ["vegetarian"]).hard_safe)
    check("restored: the compound bypass is caught again",
          dr.forbidden_hit("vegan cheese with cow milk", dr.VEGAN) is not None)


# ---------------------------------------------------------------------------
# 13. top-level extraction: the "19 separate JSON objects" failure
# ---------------------------------------------------------------------------

def _trailing_commas(text):
    """The single most common model JSON error: a comma before a closing brace."""
    return re.sub(r'\]\n(\s*)\}', r'],\n\1}', text)


def top_level_extraction():
    from app.services import meal_plan_contract as mpc
    print(f"\n{BOLD}13. Top-level extraction (the 19-object failure){RESET}")

    good = json.dumps(plan(), indent=1)

    # --- the production scenario -------------------------------------------
    broken = _trailing_commas(good)
    cut = broken[:int(len(broken) * 0.88)]
    obj, code, msg = mpc.extract_json_object(cut)
    check("a malformed+truncated plan is NOT reported as many objects",
          code == mpc.TRUNCATED, f"code={code} msg={msg[:90]}")
    check("...and the message names no object count",
          "separate JSON objects" not in msg
          and "separate top-level" not in msg, msg[:90])

    # It is one plan however far through it was cut.
    codes = {mpc.extract_json_object(good[:n])[1]
             for n in range(40, len(good), 11)}
    check("every truncation point of a valid plan reads as truncated",
          codes == {mpc.TRUNCATED}, codes)
    codes = {mpc.extract_json_object(broken[:n])[1]
             for n in range(40, len(broken), 11)}
    check("...and so does every truncation of a comma-broken plan",
          codes == {mpc.TRUNCATED}, codes)

    # A complete but invalid plan stays MALFORMED - the diagnoses are distinct.
    check("a complete plan with trailing commas is malformed, not truncated",
          mpc.extract_json_object(broken)[1] == mpc.MALFORMED,
          mpc.extract_json_object(broken)[1])

    # --- A/B: one object, with decoration ----------------------------------
    for label, text in (
        ("a deeply nested 7-day plan", good),
        ("a fenced plan", f"```json\n{good}\n```"),
        ("a plan surrounded by prose", f"Here is your plan:\n{good}\nEnjoy!"),
    ):
        obj, code, _ = mpc.extract_json_object(text)
        check(f"{label} -> exactly one object", code is None and obj is not None,
              f"code={code}")

    check("braces inside strings do not split the object",
          mpc.extract_json_object('{"notes":"use the {small} pan","a":1}')[0]
          == {"notes": "use the {small} pan", "a": 1})
    check("escaped quotes and braces inside notes are safe",
          mpc.extract_json_object(r'{"n":"say \"hi\" about {x}","a":1}')[0]
          == {"n": 'say "hi" about {x}', "a": 1})

    # --- C: genuinely independent objects ----------------------------------
    check("two adjacent complete plans stay ambiguous",
          mpc.extract_json_object(f"{good}\n{good}", 3)[1] == mpc.AMBIGUOUS)
    check("two generic objects stay ambiguous",
          mpc.extract_json_object('{"a":1}\n{"b":2}')[1] == mpc.AMBIGUOUS)
    check("JSONL of meal objects is rejected honestly",
          mpc.extract_json_object(
              '{"meal_label":"a"}\n{"meal_label":"b"}\n{"meal_label":"c"}',
              3)[1] == mpc.AMBIGUOUS)

    # --- F: arrays are the wrong top-level shape ---------------------------
    array_of_days = json.dumps([plan()["plan"]["day_1"], plan()["plan"]["day_2"]])
    obj, code, msg = mpc.extract_json_object(array_of_days, 3)
    check("an array of day objects is not_object, not ambiguous",
          code == mpc.NOT_OBJECT, f"code={code} msg={msg}")
    check("...and says which type arrived", "list" in msg, msg)
    check("an array is never accepted as a plan", obj is None)

    # --- G/12/13/14: structural uniqueness ---------------------------------
    obj, code, _ = mpc.extract_json_object(f'{{"note":"example"}}\n{good}', 3)
    check("one complete plan beside metadata is recovered deterministically",
          code is None and obj is not None and "plan" in (obj or {}), f"code={code}")
    obj, code, _ = mpc.extract_json_object(
        f'Thinking: an example is {{"day_1":[]}}\nFinal answer:\n{good}', 3)
    check("a preamble example followed by the real plan is recovered",
          code is None and obj is not None, f"code={code}")
    check("two complete plans plus metadata remain ambiguous",
          mpc.extract_json_object(f'{{"note":"x"}}\n{good}\n{good}', 3)[1]
          == mpc.AMBIGUOUS)
    check("without meals_per_day no selection is attempted",
          mpc.extract_json_object(f'{{"note":"example"}}\n{good}')[1]
          == mpc.AMBIGUOUS)
    check("selection respects meals_per_day, not just shape",
          mpc.extract_json_object(f'{{"note":"example"}}\n{good}', 4)[1]
          == mpc.AMBIGUOUS)

    # --- H: nested fragments are never candidates --------------------------
    starts, _arrays, _unclosed = mpc._top_level_starts(good)
    check("a valid plan exposes exactly one top-level start", len(starts) == 1,
          len(starts))
    starts, _arrays, unclosed = mpc._top_level_starts(cut)
    check("a truncated plan still exposes exactly one top-level start",
          len(starts) == 1, len(starts))
    check("...and is reported unclosed", unclosed is True)
    check("a complete malformed plan is NOT reported unclosed",
          mpc._top_level_starts(broken)[2] is False)

    # --- multiple fences, empty, prose, scalars ----------------------------
    check("two fenced objects stay ambiguous",
          mpc.extract_json_object(
              '```json\n{"a":1}\n```\n```json\n{"b":2}\n```')[1] == mpc.AMBIGUOUS)
    for label, text, want in (("empty output", "   ", mpc.EMPTY),
                              ("plain prose", "I cannot help", mpc.MALFORMED),
                              ("a scalar", "42", mpc.NOT_OBJECT),
                              ("a list", "[]", mpc.NOT_OBJECT)):
        check(f"{label} -> {want}", mpc.extract_json_object(text)[1] == want,
              mpc.extract_json_object(text)[1])

    # --- known trade-offs of depth-based discovery, pinned deliberately ----
    # An UNBALANCED brace in prose swallows the rest of the text, so a plan
    # after it is no longer found. This costs one retry; it never returns a
    # wrong plan. Recovering it would need a heuristic about where a decode
    # error sits, which could misfire on the truncation case this fix exists
    # to diagnose - so the retry is accepted as the cheaper failure.
    check("an unbalanced brace in prose costs a retry, not a wrong plan",
          mpc.extract_json_object(f"Note: use the {{ pan\n{good}", 3)[0] is None)
    # A BALANCED stray brace in prose is fine.
    check("a balanced stray brace in prose is tolerated",
          mpc.extract_json_object(f"Note: use the {{small}} pan\n{good}", 3)[0]
          is not None)
    # A second plan that was cut off is not a competing answer - it never
    # decodes, so the one complete plan is returned.
    obj, code, _ = mpc.extract_json_object(f"{good}\n{good[:len(good)//2]}", 3)
    check("a half-emitted second plan does not create ambiguity",
          code is None and obj is not None, f"code={code}")

    # --- corrective brief targets the real failure -------------------------
    briefs = {}
    for code_name in (mpc.TRUNCATED, mpc.MALFORMED, mpc.AMBIGUOUS,
                      mpc.NOT_OBJECT, mpc.EMPTY):
        candidate = mpc.PlanCandidate(plan=None, raw_text="x",
                                      parse_error="failed", parse_code=code_name)
        briefs[code_name] = candidate.issues_brief()
        check(f"the {code_name} brief demands one root object",
              "exactly ONE JSON object" in briefs[code_name], briefs[code_name][:80])
        for phrase in ("one object per day", "JSON Lines",
                       "example or partial object", "fragments or patches",
                       "day_1 through day_7"):
            check(f"...{code_name} brief covers {phrase!r}",
                  phrase in briefs[code_name], briefs[code_name][:120])

    check("the truncated brief names LENGTH, not multiple objects",
          "LENGTH problem" in briefs[mpc.TRUNCATED], briefs[mpc.TRUNCATED][:90])
    check("the malformed brief names trailing commas",
          "trailing comma" in briefs[mpc.MALFORMED], briefs[mpc.MALFORMED][:90])
    check("the briefs are not all identical",
          len({b[:200] for b in briefs.values()}) == len(briefs))


def top_level_service():
    from app.services import meal_plan_contract as mpc
    print(f"\n{BOLD}13b. Service behaviour after the extraction fix{RESET}")

    good = json.dumps(plan(), indent=1)
    broken = _trailing_commas(good)
    cut = broken[:int(len(broken) * 0.88)]

    result, agent = generate(good)
    check("a valid first response costs one agent call", agent.calls == 1,
          agent.calls)
    check("...and succeeds", result["success"], result.get("error"))

    # Deterministic recovery must not spend a generation.
    result, agent = generate(f'{{"note":"example"}}\n{good}')
    check("a recoverable example+plan response costs one call", agent.calls == 1,
          agent.calls)
    check("...and succeeds", result["success"], result.get("error"))

    # Unrecoverable formatting failure, then a corrected response.
    result, agent = generate(cut, extra_responses=(good,))
    check("truncated then corrected costs exactly two calls", agent.calls == 2,
          agent.calls)
    check("...and succeeds", result["success"], result.get("error"))
    check("the retry brief carried the single-root-object rule",
          "exactly ONE JSON object" in agent.prompts[1], agent.prompts[1][-400:])
    check("...and the length diagnosis, not a multi-object one",
          "LENGTH problem" in agent.prompts[1], agent.prompts[1][-400:])

    # Two ambiguous responses: two calls, then honest failure.
    two = f"{good}\n{good}"
    result, agent = generate(two, extra_responses=(two,))
    check("two ambiguous responses cost exactly two calls", agent.calls == 2,
          agent.calls)
    check("...then fail closed", result["success"] is False, result.get("error"))
    check("...reporting ambiguity, not success", "guess" in result.get("error", ""),
          result.get("error"))

    # The retry output stays subject to the whole pipeline.
    short_week = json.dumps(plan(days=5))
    result, agent = generate(cut, extra_responses=(short_week,))
    check("a corrected-but-incomplete week is still rejected",
          result["success"] is False, result.get("error"))

    wrong_meals = json.dumps(plan(meals_per_day=2))
    result, agent = generate(cut, extra_responses=(wrong_meals,))
    check("a corrected plan with the wrong meal count is rejected",
          result["success"] is False, result.get("error"))

    no_qty = plan()
    no_qty["plan"]["day_1"][0]["ingredients"] = [{"name": "oats"}]
    result, agent = generate(cut, extra_responses=(json.dumps(no_qty),))
    check("a corrected plan missing ingredient quantities is rejected",
          result["success"] is False, result.get("error"))

    beef = plan(ingredients=[{"name": "beef mince", "qty": "100g"}])
    result, agent = generate(cut, extra_responses=(json.dumps(beef),),
                             payload={"dietary_restrictions": ["vegetarian"]})
    check("a corrected plan breaking a dietary restriction is rejected",
          result["success"] is False, result.get("error"))

    hungry = json.dumps(plan(per_meal={"calories": 200, "protein": 10,
                                       "carbs": 25, "fat": 6}))
    result, agent = generate(cut, extra_responses=(hungry,))
    check("a corrected plan far off the calorie target does not pass verified",
          not result.get("verification", {}).get("calories", {}).get("hit", False),
          result.get("verification", {}).get("calories"))

    # A nested fragment can never be returned as a plan.
    fragment = json.dumps(plan()["plan"]["day_1"][0])
    result, agent = generate(fragment, extra_responses=(fragment,))
    check("a single meal object is never a successful plan",
          result["success"] is False, result.get("error"))
    day_only = json.dumps({"day_1": plan()["plan"]["day_1"]})
    result, agent = generate(day_only, extra_responses=(day_only,))
    check("a single day object is never a successful plan",
          result["success"] is False, result.get("error"))

    # No parse-driven regeneration loop.
    result, agent = generate(cut, extra_responses=(cut,))
    check("two unparseable responses stop at two calls", agent.calls == 2,
          agent.calls)
    check("...and fail with the parse diagnosis", result["success"] is False,
          result.get("error"))


def top_level_mutations():
    from app.services import meal_plan_contract as mpc
    print(f"\n{BOLD}13c. Mutations — the extraction guards are load-bearing{RESET}")

    good = json.dumps(plan(), indent=1)
    broken = _trailing_commas(good)
    cut = broken[:int(len(broken) * 0.88)]

    # M1: replay the OLD scanner exactly - every "{" is a candidate, and a
    # successful decode skips only its own interior. On the production
    # fixture it reports the reported 19 objects for what is one broken plan.
    def legacy_scan(cleaned):
        decoder = json.JSONDecoder()
        starts = [i for i, ch in enumerate(cleaned) if ch == "{"]
        found, index = [], 0
        while index < len(starts):
            try:
                value, end = decoder.raw_decode(cleaned, starts[index])
            except json.JSONDecodeError:
                index += 1
                continue
            if isinstance(value, dict):
                found.append(value)
                index = next((k for k in range(index + 1, len(starts))
                              if starts[k] >= end), len(starts))
            else:
                index += 1
        return found

    legacy = legacy_scan(cut)
    check("M1 the old scanner reports 19 objects for one broken plan",
          len(legacy) == 19, len(legacy))
    check("M1 ...every one of them a nested fragment, not a plan",
          all(not mpc.validate_structure(o, 3).ok for o in legacy),
          [list(o)[:3] for o in legacy[:3]])
    check("M1 ...while the fixed extractor calls it truncated",
          mpc.extract_json_object(cut)[1] == mpc.TRUNCATED)

    # M2: selecting the first object accepts the wrong candidate.
    text = f'{{"note":"example"}}\n{good}'
    found, _err = mpc._decode_at(text, mpc._top_level_starts(text)[0])
    check("M2 taking the first object would return the example, not the plan",
          found[0] == {"note": "example"} and "plan" not in found[0], found[0])
    check("M2 ...while structural selection returns the real plan",
          "plan" in mpc.extract_json_object(text, 3)[0])

    # M3: selecting the largest object can accept a structurally invalid one.
    bloated = json.dumps({"note": "x" * (len(good) * 2), "day_1": []})
    text = f"{bloated}\n{good}"
    found, _err = mpc._decode_at(text, mpc._top_level_starts(text)[0])
    largest = max(found, key=lambda o: len(json.dumps(o)))
    check("M3 the largest object is the invalid one",
          not mpc.validate_structure(largest, 3).ok, list(largest))
    check("M3 ...while structural selection returns the valid plan",
          mpc.validate_structure(mpc.extract_json_object(text, 3)[0], 3).ok)

    # M4: removing the two-plan guard accepts competing plans.
    original_validate = mpc.validate_structure
    mpc.validate_structure = lambda obj, meals_per_day: mpc.StructureResult(
        ok=(obj is not None and "plan" in obj))
    try:
        obj, code, _ = mpc.extract_json_object(f"{good}\n{good}", 3)
    finally:
        mpc.validate_structure = original_validate
    check("M4 a weakened uniqueness check still refuses two complete plans",
          code == mpc.AMBIGUOUS and obj is None, f"code={code}")

    # M5: bypassing structural validation lets a nested fragment succeed.
    fragment = json.dumps({"day_1": plan()["plan"]["day_1"]})
    from app.services import advanced_meal_planner_service as mod
    original_structure = mpc.validate_structure
    mpc.validate_structure = lambda obj, meals_per_day: mpc.StructureResult(ok=True)
    try:
        result, _agent = generate(fragment)
        bypassed = result["success"]
    finally:
        mpc.validate_structure = original_structure
    check("M5 bypassing structural validation lets a day fragment through",
          bypassed)
    result, _agent = generate(fragment, extra_responses=(fragment,))
    check("M5 ...and it is rejected once restored", result["success"] is False)

    # M6: an extra application retry would exceed two agent calls.
    original_attempt = mod.AdvancedMealPlannerService._attempt

    def three_attempts(self, prompt, **assess):
        first = self._assess(self._run_agent(prompt), **assess)
        for _ in range(2):
            if not self._needs_retry(first):
                break
            first = self._assess(self._run_agent(prompt), **assess)
        return first

    mod.AdvancedMealPlannerService._attempt = three_attempts
    try:
        _result, agent = generate(cut, extra_responses=(cut, cut, cut))
        extra = agent.calls
    finally:
        mod.AdvancedMealPlannerService._attempt = original_attempt
    check("M6 an extra application retry causes more than two calls", extra > 2,
          extra)
    _result, agent = generate(cut, extra_responses=(cut,))
    check("M6 ...and the real service stays at two", agent.calls == 2, agent.calls)

    # M7: the transport retry bound is set on the planner only.
    from app.models.groq_with_fallback import GroqWithFallback
    bounded = GroqWithFallback(id="x", fallback_id="y", max_retries=1)
    check("M7 the planner's client bounds SDK retries to 1",
          bounded._get_client_params().get("max_retries") == 1)
    check("M7 ...and other agents are untouched",
          GroqWithFallback(id="x")._get_client_params().get("max_retries") is None)
    source = inspect.getsource(mod)
    check("M7 the bound is declared at the planner's model construction",
          "max_retries=1" in source)


def main():
    print(f"\n{BOLD}ADVANCED MEAL PLANNER — validation & dietary safety{RESET}")
    structural_failures()
    dietary_safety()
    completeness_and_retry()
    calories_and_macros()
    adaptation()
    json_extraction()
    logging_hygiene()
    mutations()
    review_findings()
    review_mutations()
    codex_findings()
    separator_boundaries()
    top_level_extraction()
    top_level_service()
    top_level_mutations()
    print(f"\n{BOLD}{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
