#!/usr/bin/env python3
"""
Explorer's personalised mode: does the food actually get built to the numbers?

The claim is that a Kerala full-day plan can be held to a 150g protein target
instead of being nutritionally arbitrary. That is only true if:

  * the target is derived from the real goal, not invented
  * "what's left today" is genuinely what's left, and never negative
  * standard mode is byte-for-byte what it was
  * the numbers reach the prompt, because a target the model never sees is
    a target that does nothing

    python scripts/test_macro_targets.py
"""

import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_DB = Path(tempfile.mkdtemp()) / "macro_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

GREEN, RED, DIM, BOLD, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[1m", "\033[0m"
passed = failed = 0

TZ = "Asia/Kolkata"


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


def fresh_db():
    from app.database import Base, SessionLocal, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def make_user(db, with_goal=True, username="tester"):
    from app.database import Goal, User
    user = User(email=f"{username}@t", username=username, hashed_password="x",
                full_name="T", age=25, height=180, weight=75, timezone=TZ)
    db.add(user); db.commit(); db.refresh(user)
    if with_goal:
        db.add(Goal(user_id=user.id, goal_type="muscle_gain", target_calories=2000,
                    target_protein=150, target_carbs=200, target_fat=60,
                    is_active=True, created_at=datetime.utcnow()))
        db.commit()
    return user


def log_today(db, user, calories, protein, carbs, fat):
    from zoneinfo import ZoneInfo

    from app.database import MealLog
    from app.services import daytime
    tz = ZoneInfo(TZ)
    today = daytime.local_date(tz=tz)
    local = datetime(today.year, today.month, today.day, 12, 0, tzinfo=tz)
    db.add(MealLog(user_id=user.id, meal_type="lunch", calories=calories,
                   protein=protein, carbs=carbs, fat=fat,
                   logged_at=local.astimezone(timezone.utc).replace(tzinfo=None)))
    db.commit()


# ---------------------------------------------------------------------------

def test_daily_split():
    from app.services import macro_targets as mt
    print(f"\n{BOLD}1. The day's targets, split by meal{RESET}")

    db = fresh_db()
    user = make_user(db)

    full = mt.resolve(db, user, "full_day", "daily")
    check("a full day is the whole goal",
          (full.calories, full.protein) == (2000, 150), full.describe())

    shares = {}
    for meal in ("breakfast", "lunch", "dinner", "snack"):
        target = mt.resolve(db, user, meal, "daily")
        shares[meal] = target.calories
        check(f"{meal} is a fraction of the day",
              0 < target.calories < full.calories, target.describe())

    # Meals are not equal thirds - splitting evenly gives a 700 kcal breakfast
    # nobody will cook.
    check("breakfast is smaller than lunch", shares["breakfast"] < shares["lunch"], shares)
    check("a snack is the smallest", shares["snack"] == min(shares.values()), shares)

    # Macros must scale together, or the ratio the goal encodes is destroyed.
    dinner = mt.resolve(db, user, "dinner", "daily")
    check("every macro scales by the same share",
          abs(dinner.protein / 150 - dinner.calories / 2000) < 0.001,
          f"protein share {dinner.protein/150:.3f} vs cal share {dinner.calories/2000:.3f}")
    db.close()


def test_remaining():
    from app.services import macro_targets as mt
    print(f"\n{BOLD}2. What's left today{RESET}")

    db = fresh_db()
    user = make_user(db)

    # Nothing used up yet, so remaining == the day, which then splits by meal
    # exactly like `daily`. Asserting 2000 here was wrong: that would mean
    # serving an entire day's calories as one dinner.
    empty = mt.resolve(db, user, "dinner", "remaining")
    daily_dinner = mt.resolve(db, user, "dinner", "daily")
    check("with nothing logged, remaining matches the daily split",
          empty.calories == daily_dinner.calories,
          f"{empty.describe()} vs {daily_dinner.describe()}")
    check("...and is flagged so the UI can explain why", empty.fell_back)
    check("...and reports basis as daily, not remaining", empty.basis == "daily")

    log_today(db, user, 1200, 60, 140, 35)
    left = mt.resolve(db, user, "dinner", "remaining")
    check("after logging, remaining is goal minus eaten",
          (round(left.calories), round(left.protein)) == (800, 90), left.describe())
    check("...and is not split by meal type - what's left is what's left",
          left.share == 1.0, left.share)
    check("...and is flagged as remaining", left.basis == "remaining" and not left.fell_back)

    # Over target: a negative target is not a smaller meal, it is nonsense.
    db2 = fresh_db()
    over = make_user(db2)
    log_today(db2, over, 2600, 200, 300, 90)
    blown = mt.resolve(db2, over, "dinner", "remaining")
    check("going over never produces a negative target",
          all(getattr(blown, m) >= 0 for m in ("calories", "protein", "carbs", "fat")),
          blown.describe())
    check("...and is reported as unusable rather than a 0 kcal recipe",
          not blown.usable, blown.describe())
    db.close(); db2.close()


def test_no_goal():
    """No goal means no target. Inventing one would look personalised."""
    from app.services import macro_targets as mt
    print(f"\n{BOLD}3. Without a goal{RESET}")

    db = fresh_db()
    user = make_user(db, with_goal=False)
    check("resolve returns None", mt.resolve(db, user, "dinner", "daily") is None)
    check("the preview says there is no goal",
          mt.preview(db, user) == {"has_goal": False})
    db.close()


def test_prompt_block():
    from app.services import macro_targets as mt
    print(f"\n{BOLD}4. The instruction handed to the generator{RESET}")

    db = fresh_db()
    user = make_user(db)
    target = mt.resolve(db, user, "dinner", "daily")
    block = target.prompt_block()
    bounds = target.bounds()

    # Derived from the target, never hardcoded. Pasting figures from a
    # different fixture broke this test twice; a literal here is a literal
    # that will be wrong the next time a share or tolerance changes.
    for macro in ("calories", "protein", "carbs", "fat"):
        aim = f"{getattr(target, macro):.0f}"
        check(f"the block states the {macro} target ({aim})",
              aim in block, block[:300])

    check("it is stated as a requirement, not a preference",
          "not a preference" in block.lower(), block[:150])

    # All four must be binding. An earlier version called protein "the one
    # that matters most" and gave the rest a soft percentage - a plan that
    # nails protein and lands 700 kcal over has not hit the target.
    check("all four macros are named as required",
          "ALL FOUR" in block, block[:200])
    for macro in ("Calories", "Protein", "Carbs", "Fat"):
        check(f"{macro} has its own line", f"{macro}:" in block, block[:400])
    check("no macro is described as mattering most",
          "matters most" not in block.lower(), block)

    # Explicit ranges rather than percentages: a percentage gets rounded,
    # ignored, or applied to the wrong base.
    check("ranges are given in absolute numbers, not percentages",
          "%" not in block, [l for l in block.splitlines() if "%" in l])
    for macro in ("calories", "carbs", "fat"):
        low, high = bounds[macro]
        check(f"{macro} has an explicit low-high range",
              f"{low:.0f}-{high:.0f}" in block, block[:400])
    # Protein is a floor, not a window - over is never a failure.
    check("protein is stated as a floor, not a range",
          f"at least {bounds['protein'][0]:.0f}" in block, block[:400])

    check("it asks for per-dish numbers so the total can be checked",
          "EVERY dish" in block)
    check("...and for a machine-readable total line",
          "TOTAL:" in block, block[-400:])
    check("...and tells it to check its own arithmetic first",
          "recompute" in block.lower())
    # Without this the model reaches the protein number with a shake, which is
    # not Kerala food and not what was asked for.
    check("it forbids solving the maths with supplements",
          "protein shake" in block.lower() or "protein powder" in block.lower(), block)
    check("...and forbids inventing dishes outside the cuisine",
          "do not invent dishes" in block.lower())

    remaining_block = mt.resolve(db, user, "dinner", "remaining").prompt_block()
    log_today(db, user, 1000, 50, 100, 30)
    remaining_block = mt.resolve(db, user, "dinner", "remaining").prompt_block()
    check("the remaining variant says it completes the day",
          "completes the day" in remaining_block, remaining_block[-200:])
    db.close()


def test_endpoint():
    """Standard must be untouched; personalised must carry the numbers."""
    import asyncio
    import types
    print(f"\n{BOLD}5. Through the endpoint{RESET}")

    for name in ["agno", "agno.agent", "agno.models", "agno.models.groq"]:
        sys.modules.setdefault(name, types.ModuleType(name))

    class Fake:
        def __init__(self, *a, **k): pass
    sys.modules["agno.agent"].Agent = Fake
    sys.modules["agno.models.groq"].Groq = Fake

    from fastapi import HTTPException

    from app.routers.culinary import (CuisineRegion, MealType,
                                      RegionalMealPlanRequest,
                                      generate_regional_meal_plan)
    from app.services import culinaryexplorer_service as ces

    class Spy:
        prompt = None

        def run(self, prompt):
            Spy.prompt = prompt
            raise RuntimeError("captured after the prompt was built")

    ces.culinaryexplorer_service.regional_food_agent = Spy()

    db = fresh_db()
    user = make_user(db)

    def run(**kwargs):
        Spy.prompt = None
        request = RegionalMealPlanRequest(cuisine_region=CuisineRegion.KERALA, **kwargs)
        error = None
        try:
            asyncio.run(generate_regional_meal_plan(request, current_user=user, db=db))
        except HTTPException as e:
            error = e
        except Exception:
            pass
        return Spy.prompt, error

    prompt, _ = run(meal_type=MealType.DINNER)
    check("standard mode sends no target",
          prompt and "NUTRITIONAL TARGET" not in prompt, (prompt or "")[:120])
    check("...and still asks for the cuisine", "kerala" in (prompt or "").lower())

    prompt, _ = run(meal_type=MealType.DINNER, personalised=True, basis="daily")
    check("personalised mode sends a target", "NUTRITIONAL TARGET" in (prompt or ""))
    # 150g protein at the 0.3 dinner share.
    check("...with the dinner protein figure", "45" in (prompt or ""),
          (prompt or "")[-400:])
    check("...and all four macros named",
          all(m in (prompt or "") for m in ("Calories", "Protein", "Carbs", "Fat")),
          (prompt or "")[-500:])
    check("the target goes LAST, where models weight hardest",
          (prompt or "").rindex("NUTRITIONAL TARGET") > (prompt or "").rindex("authenticity"),
          "target appears before the authenticity instruction")

    prompt, _ = run(meal_type=MealType.FULL_DAY, personalised=True, basis="daily")
    check("a full day asks for the whole goal",
          "aim for 150 g" in (prompt or ""), (prompt or "")[-400:])

    # No goal: refuse rather than generate something falsely labelled.
    db2 = fresh_db()
    goalless = make_user(db2, with_goal=False)

    Spy.prompt = None
    request = RegionalMealPlanRequest(cuisine_region=CuisineRegion.KERALA,
                                      meal_type=MealType.DINNER, personalised=True)
    raised = None
    try:
        asyncio.run(generate_regional_meal_plan(request, current_user=goalless, db=db2))
    except HTTPException as e:
        raised = e
    except Exception:
        pass
    check("without a goal, personalised refuses", raised is not None and raised.status_code == 400,
          raised.detail if raised else "no error raised")
    check("...and never calls the model", Spy.prompt is None)
    check("...and says what to do about it",
          raised and "goal" in raised.detail.lower(), raised.detail if raised else "")

    # Already over target: refuse rather than ask for a 0 kcal dinner.
    db3 = fresh_db()
    stuffed = make_user(db3, username="stuffed")
    log_today(db3, stuffed, 2600, 200, 300, 90)
    Spy.prompt = None
    request = RegionalMealPlanRequest(cuisine_region=CuisineRegion.KERALA,
                                      meal_type=MealType.DINNER,
                                      personalised=True, basis="remaining")
    raised = None
    try:
        asyncio.run(generate_regional_meal_plan(request, current_user=stuffed, db=db3))
    except HTTPException as e:
        raised = e
    except Exception:
        pass
    check("already over target refuses rather than generating nothing",
          raised is not None and raised.status_code == 400,
          raised.detail if raised else "no error")
    check("...and never calls the model", Spy.prompt is None)

    db.close(); db2.close(); db3.close()


def test_parsing_totals():
    """
    The output has to be readable back, or verification is theatre.

    Models reformat the requested TOTAL line into tables, bold text and
    reversed labels constantly, so insisting on one shape would report
    "unverifiable" on most real generations.
    """
    from app.services.macro_targets import parse_totals
    print(f"\n{BOLD}7. Reading the totals back out{RESET}")

    for label, text, expected in [
        ("the exact requested line",
         "TOTAL: 660 kcal, 46g protein, 78g carbs, 18g fat",
         (660, 46, 78, 18)),
        ("thousands separators",
         "TOTAL: 1,240 kcal, 92g protein, 140g carbs, 38g fat",
         (1240, 92, 140, 38)),
        ("markdown bold with pipes",
         "**Total for the day:** 700 kcal | 40 g protein | 85 g carbs | 20 g fat",
         (700, 40, 85, 20)),
        ("a table row",
         "| **Total** | 655 kcal | 47 g protein | 80 g carbs | 17 g fat |",
         (655, 47, 80, 17)),
        ("labels before numbers",
         "Grand total - calories: 690, protein: 44 g, carbs: 82 g, fat: 19 g",
         (690, 44, 82, 19)),
        ("'energy' instead of calories",
         "Daily total: Energy 705, Protein 46 g, Carbohydrate 81 g, Fat 19 g",
         (705, 46, 81, 19)),
    ]:
        got = parse_totals(text)
        check(f"parses {label}",
              got is not None and (got["calories"], got["protein"],
                                   got["carbs"], got["fat"]) == expected,
              got)

    # Not finding totals must be distinguishable from finding zeros: one is a
    # parser problem, the other is a food problem.
    check("returns None when there are no totals",
          parse_totals("A lovely Kerala dinner with rice and sambar.") is None)
    check("a per-dish line is not mistaken for a total",
          parse_totals("Sambar: 180 kcal, 9g protein, 22g carbs, 5g fat") is None)
    check("empty text is handled", parse_totals("") is None)

    # The summary is at the END. An early per-dish line must not win.
    multi = ("Sambar: 180 kcal, 9g protein, 22g carbs, 5g fat\n"
             "Rice: 300 kcal, 6g protein, 65g carbs, 1g fat\n"
             "TOTAL: 480 kcal, 15g protein, 87g carbs, 6g fat")
    got = parse_totals(multi)
    check("the final total wins over per-dish lines",
          got and got["calories"] == 480, got)


def test_verification():
    """Every macro is judged, and the verdict names which one slipped."""
    from app.services.macro_targets import MacroTarget, retry_brief, verify
    print(f"\n{BOLD}8. Checking the plan against all four{RESET}")

    target = MacroTarget(calories=600, protein=45, carbs=60, fat=18,
                         basis="daily", meal_type="dinner", share=0.3)

    perfect = verify(target, "TOTAL: 600 kcal, 45g protein, 60g carbs, 18g fat")
    check("an exact plan passes", perfect["hit"], perfect.get("summary"))
    check("...and reports every macro on target",
          all(m["status"] == "on_target" for m in perfect["macros"].values()))

    # The case that motivated this: protein nailed, calories blown. Under the
    # old prompt this looked like a success.
    protein_only = verify(target, "TOTAL: 1100 kcal, 46g protein, 160g carbs, 40g fat")
    check("hitting protein alone is NOT a pass", not protein_only["hit"])
    check("...and calories is named as a miss",
          "calories" in protein_only["missed"], protein_only["missed"])
    check("...along with carbs and fat",
          {"carbs", "fat"} <= set(protein_only["missed"]), protein_only["missed"])
    check("...and the summary says by how much",
          "over" in protein_only["summary"], protein_only["summary"])

    # Protein is asymmetric: plenty over is fine, under is the failure.
    over_protein = verify(target, "TOTAL: 620 kcal, 80g protein, 60g carbs, 18g fat")
    check("well over on protein is still on target",
          over_protein["macros"]["protein"]["status"] == "on_target",
          over_protein["macros"]["protein"])
    under_protein = verify(target, "TOTAL: 600 kcal, 30g protein, 60g carbs, 18g fat")
    check("under on protein is a miss",
          under_protein["macros"]["protein"]["status"] == "under")

    # Each macro individually.
    for macro, bad in [("calories", "TOTAL: 900 kcal, 45g protein, 60g carbs, 18g fat"),
                       ("carbs", "TOTAL: 600 kcal, 45g protein, 110g carbs, 18g fat"),
                       ("fat", "TOTAL: 600 kcal, 45g protein, 60g carbs, 40g fat")]:
        result = verify(target, bad)
        check(f"{macro} alone out of range fails the plan",
              macro in result["missed"], result["missed"])

    unreadable = verify(target, "Just some lovely food, no numbers at all.")
    check("unparseable output is reported as unchecked, not as a failure",
          unreadable["checked"] is False and "hit" not in unreadable, unreadable)

    brief = retry_brief(protein_only, target)
    check("the retry brief names each miss", "calories" in brief and "carbs" in brief)
    check("...with the direction", "too high" in brief, brief[:200])
    check("...and the range to hit", "must be between" in brief)
    check("...and says to keep what already worked",
          "already inside its range" in brief.lower(), brief[-200:])


def test_retry_only_when_better():
    """A retry that makes things worse must not replace the first attempt."""
    import types
    for name in ["agno", "agno.agent", "agno.models", "agno.models.groq"]:
        sys.modules.setdefault(name, types.ModuleType(name))

    class Fake:
        def __init__(self, *a, **k): pass
    sys.modules["agno.agent"].Agent = Fake
    sys.modules["agno.models.groq"].Groq = Fake

    from app.services.culinaryexplorer_service import _closer
    print(f"\n{BOLD}9. Regeneration must be an improvement{RESET}")

    def v(checked=True, hit=False, missed=(), deltas=None):
        macros = {m: {"delta": (deltas or {}).get(m, 0), "target": 100}
                  for m in ("calories", "protein", "carbs", "fat")}
        return {"checked": checked, "hit": hit, "missed": list(missed), "macros": macros}

    worse = v(missed=["calories", "carbs", "fat"], deltas={"calories": 400})
    better = v(missed=["carbs"], deltas={"carbs": 10})

    check("fewer misses wins", _closer(better, worse))
    check("more misses loses", not _closer(worse, better))
    check("a clean retry always wins", _closer(v(hit=True), better))
    check("an unparseable retry never replaces a checked one",
          not _closer(v(checked=False), worse))
    check("a checked retry replaces an unparseable first attempt",
          _closer(better, v(checked=False)))

    # Same number of misses: the smaller total deviation wins.
    near = v(missed=["carbs"], deltas={"carbs": 5})
    far = v(missed=["carbs"], deltas={"carbs": 50})
    check("with equal misses, the closer one wins", _closer(near, far))
    check("...and the further one does not", not _closer(far, near))


def _fake_plan(days=7, per_day=None, meals=3):
    """A 7-day plan shaped like the planner's real JSON output."""
    per_day = per_day or {"calories": 2000, "protein": 150, "carbs": 200, "fat": 60}
    plan = {"plan": {}}
    for d in range(1, days + 1):
        plan["plan"][f"day_{d}"] = [
            {"meal_label": f"Meal {i+1}",
             "macros": {"calories": per_day["calories"] / meals,
                        "protein_g": per_day["protein"] / meals,
                        "carbs_g": per_day["carbs"] / meals,
                        "fat_g": per_day["fat"] / meals}}
            for i in range(meals)
        ]
    return plan


def test_planner_prompt():
    """The 7-day planner knew calories and nothing else."""
    import types
    for name in ["agno", "agno.agent", "agno.models", "agno.models.groq"]:
        sys.modules.setdefault(name, types.ModuleType(name))

    class Fake:
        def __init__(self, *a, **k): pass
    sys.modules["agno.agent"].Agent = Fake
    sys.modules["agno.models.groq"].Groq = Fake

    from app.services.advanced_meal_planner_service import advanced_meal_planner_service as svc
    from app.services.macro_targets import MacroTarget
    print(f"\n{BOLD}10. The meal planner prompt{RESET}")

    payload = {"target_calories": 2000, "meals_per_day": 3, "food_preferences": [],
               "budget_per_day": 300, "work_hours_per_day": 8,
               "dietary_restrictions": [], "equipment": [], "time_per_meal_min": 30,
               "region_or_cuisine": "indian", "user_notes": ""}

    # Without a target the planner must be exactly what it was.
    plain = svc.build_query(payload)
    check("without a target, no macro figures are sent",
          "NUTRITIONAL TARGET" not in plain, plain[:200])
    # The original said "do not sacrifice the protein target" when no protein
    # target existed - the model was told to protect a number it never saw.
    check("no dangling reference to a target that was never given",
          "protein target" not in plain and "macro targets below" not in plain,
          [l for l in plain.splitlines() if "sacrifice" in l])

    target = MacroTarget(calories=2000, protein=150, carbs=200, fat=60,
                         basis="daily", meal_type="full_day", share=1.0)
    full = svc.build_query(payload, macro_target=target)

    check("with a target, all four macros are sent",
          all(m in full for m in ("Calories:", "Protein:", "Carbs:", "Fat:")), full[-700:])
    for value in ("2000", "150", "200", "60"):
        check(f"the {value} figure reaches the prompt", value in full)

    # The failure this exists to prevent: averaging across the week.
    check("the target applies to every day, not the weekly average",
          "EVERY SINGLE DAY" in full, full[-800:])
    check("...and averaging is explicitly forbidden",
          "Do NOT average" in full, full[-500:])

    # Structured output does not need the free-text TOTAL line.
    check("it asks for real per-meal macros in the JSON",
          "macros object on every meal" in full, full[-400:])
    check("...rather than a prose total line",
          "TOTAL: <n>" not in full, full[-400:])

    check("the budget line now refers to targets that exist",
          "macro targets below" in full,
          [l for l in full.splitlines() if "sacrifice" in l])


def test_structured_verification():
    """Summing the plan's own numbers beats trusting a stated total."""
    from app.services.macro_targets import (MacroTarget, retry_brief_structured,
                                            verify_structured)
    print(f"\n{BOLD}11. Checking a 7-day plan from its JSON{RESET}")

    target = MacroTarget(calories=2000, protein=150, carbs=200, fat=60,
                         basis="daily", meal_type="full_day", share=1.0)

    good = verify_structured(target, _fake_plan())
    check("a plan on target passes", good["hit"], good["summary"])
    check("...across all seven days", good["days_on_target"] == 7, good)

    # Protein nailed, calories blown - what the old planner could not detect.
    lopsided = verify_structured(target, _fake_plan(
        per_day={"calories": 3200, "protein": 155, "carbs": 400, "fat": 110}))
    check("hitting protein alone does not pass", not lopsided["hit"])
    check("...and calories is named", "calories" in lopsided["days"][0]["missed"],
          lopsided["days"][0]["missed"])

    # The averaging failure: 3 huge days + 4 tiny ones average correctly.
    mixed = {"plan": {}}
    for d in range(1, 8):
        heavy = d <= 3
        macros = ({"calories": 3400, "protein": 250, "carbs": 340, "fat": 100} if heavy
                  else {"calories": 950, "protein": 75, "carbs": 95, "fat": 30})
        mixed["plan"][f"day_{d}"] = [{"macros": {
            "calories": macros["calories"], "protein_g": macros["protein"],
            "carbs_g": macros["carbs"], "fat_g": macros["fat"]}}]
    averaged = verify_structured(target, mixed)
    weekly_mean = sum(
        sum(m["macros"]["calories"] for m in day)
        for day in mixed["plan"].values()) / 7
    check("a week that averages correctly is still caught",
          abs(weekly_mean - 2000) < 120 and not averaged["hit"],
          f"weekly mean {weekly_mean:.0f}, days on target {averaged['days_on_target']}")
    check("...and reports zero days on target", averaged["days_on_target"] == 0, averaged)

    # One bad day among six good ones must be visible, not averaged away.
    one_bad = _fake_plan()
    one_bad["plan"]["day_4"] = [{"macros": {"calories": 900, "protein_g": 20,
                                            "carbs_g": 120, "fat_g": 15}}]
    partial = verify_structured(target, one_bad)
    check("6 of 7 good days reports as 6 of 7",
          partial["days_on_target"] == 6, partial["summary"])
    check("...and names the day that failed",
          any(d["day"] == "day_4" and not d["hit"] for d in partial["days"]),
          [d["day"] for d in partial["days"] if not d["hit"]])

    # A model can state a total it never computed; summing catches it.
    liar = _fake_plan(per_day={"calories": 900, "protein": 40, "carbs": 100, "fat": 25})
    liar["summary"] = {"avg_daily_calories": 2000}
    check("a claimed summary does not override the summed meals",
          not verify_structured(target, liar)["hit"])

    check("an empty plan is unchecked, not failed",
          verify_structured(target, {})["checked"] is False)
    # `or True` used to make this assertion unconditionally true - it tested
    # nothing at all. A meal with no macros object totals zero for every
    # macro, which is genuinely a miss against any real target, and that is
    # what this now asserts.
    no_macros = verify_structured(target, {"plan": {"day_1": [{"recipe_name": "x"}]}})
    check("a plan whose meals have no macros does not pass",
          no_macros["days"][0]["hit"] is False, no_macros["days"][0])
    check("...and every macro reads as under target, not absent",
          all(no_macros["days"][0]["macros"][m]["status"] == "under"
              for m in ("calories", "protein", "carbs", "fat")),
          no_macros["days"][0]["macros"])

    brief = retry_brief_structured(partial, target)
    check("the retry brief names the failing day", "day_4" in brief, brief[:200])
    check("...and leaves the good days alone",
          "already correct" in brief, brief[:200])
    check("...and does not list days that passed",
          "day_1" not in brief, brief)


def test_preview_shape():
    """The picker renders straight from this, so it has to be complete."""
    from app.services import macro_targets as mt
    print(f"\n{BOLD}6. The preview the UI renders{RESET}")

    db = fresh_db()
    user = make_user(db)
    preview = mt.preview(db, user)

    check("has_goal is true", preview["has_goal"])
    for meal in ("full_day", "breakfast", "lunch", "dinner", "snack"):
        check(f"{meal} is present", meal in preview["meals"], list(preview["meals"]))
        entry = preview["meals"][meal]
        check(f"{meal} has all four macros",
              all(k in entry for k in ("calories", "protein", "carbs", "fat")), entry)
        check(f"{meal} values are rounded for display",
              all(isinstance(entry[k], int) for k in ("calories", "protein", "carbs", "fat")),
              entry)

    check("remaining is included", "remaining" in preview)
    check("...and flags whether it is usable", "usable" in preview["remaining"])
    db.close()


def main():
    test_daily_split()
    test_remaining()
    test_no_goal()
    test_prompt_block()
    test_endpoint()
    test_parsing_totals()
    test_verification()
    test_retry_only_when_better()
    test_planner_prompt()
    test_structured_verification()
    test_preview_shape()

    # A test function that is never called is worse than no test: the suite
    # goes green while the behaviour is unchecked. This caught exactly that -
    # two new functions written, defined, and never added to main().
    import inspect
    defined = {name for name, _ in inspect.getmembers(sys.modules[__name__])
               if name.startswith("test_")}
    called = set(re.findall(r"(test_\w+)\(\)", inspect.getsource(main)))
    orphans = sorted(defined - called)
    check("every test function is actually run", not orphans, orphans)

    print(f"\n{BOLD}{GREEN if not failed else RED}"
          f"{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
