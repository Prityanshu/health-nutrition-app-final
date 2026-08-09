#!/usr/bin/env python3
"""
Goal adherence: did they hit target, and does that change anything?

The claim being tested is not "we can add up calories". It is:

  * a day is judged against all four macros, on the agreed bands
  * a day nobody logged is not a failure, and neither is today at 2pm
  * the week's record actually reaches the recommendation engine and moves
    what it suggests - otherwise this is a display feature wearing a
    personalisation costume

    python scripts/test_adherence.py
"""

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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


class Goal:
    def __init__(self, cal=2000, pro=150, carb=200, fat=60):
        self.target_calories, self.target_protein = cal, pro
        self.target_carbs, self.target_fat = carb, fat


class Meal:
    def __init__(self, calories=0, protein=0, carbs=0, fat=0):
        self.calories, self.protein, self.carbs, self.fat = calories, protein, carbs, fat


GOAL = Goal()
DAY = date(2026, 8, 9)


def perfect():
    return [Meal(2000, 150, 200, 60)]


# ---------------------------------------------------------------------------

def test_bands():
    """The agreed bands: +/-15% on calories, carbs and fat; 70% floor on protein."""
    from app.services.adherence import evaluate_day
    print(f"\n{BOLD}1. Band edges{RESET}")

    for label, meal, expect in [
        ("exactly on target",        Meal(2000, 150, 200, 60), True),
        ("calories +14.9%",          Meal(2298, 150, 200, 60), True),
        ("calories +15.1%",          Meal(2302, 150, 200, 60), False),
        ("calories -14.9%",          Meal(1702, 150, 200, 60), True),
        ("calories -15.1%",          Meal(1698, 150, 200, 60), False),
        ("protein exactly 70%",      Meal(2000, 105, 200, 60), True),
        ("protein 69%",              Meal(2000, 103, 200, 60), False),
        ("protein double target",    Meal(2000, 300, 200, 60), True),
        ("carbs +16%",               Meal(2000, 150, 232, 60), False),
        ("fat -16%",                 Meal(2000, 150, 200, 50), False),
    ]:
        result = evaluate_day(DAY, [meal], GOAL)
        check(f"{label} -> {'hit' if expect else 'miss'}",
              result.hit == expect, f"status={result.status} {result.summary()}")

    # Protein over is never a miss. This is the asymmetry that matters most:
    # a symmetric band would penalise the exact behaviour the app promotes.
    over_protein = evaluate_day(DAY, [Meal(2000, 400, 200, 60)], GOAL)
    check("no amount of extra protein is a miss", over_protein.hit,
          over_protein.summary())


def test_all_four_required():
    """All four macros. One miss fails the day."""
    from app.services.adherence import evaluate_day
    print(f"\n{BOLD}2. All four macros must be in band{RESET}")

    for macro, meal in [
        ("calories", Meal(2600, 150, 200, 60)),
        ("protein",  Meal(2000, 80, 200, 60)),
        ("carbs",    Meal(2000, 150, 300, 60)),
        ("fat",      Meal(2000, 150, 200, 90)),
    ]:
        result = evaluate_day(DAY, [meal], GOAL)
        check(f"{macro} out of band fails the day", not result.hit)
        check(f"{macro} is named as the miss", macro in result.missed, result.missed)
        check(f"the summary says which and by how much",
              macro in result.summary(), result.summary())

    # Worst first, so the UI can show one thing and show the right one.
    bad = evaluate_day(DAY, [Meal(2000, 30, 400, 60)], GOAL)
    check("misses are ordered worst first", bad.missed[0] == "carbs", bad.missed)


def test_not_a_miss():
    """Days that should not count against anyone."""
    from app.services.adherence import evaluate_day
    print(f"\n{BOLD}3. Unlogged, partial, no-goal and in-progress days{RESET}")

    empty = evaluate_day(DAY, [], GOAL)
    check("a day with nothing logged is 'unlogged'", empty.status == "unlogged")
    check("...and is not a miss", not empty.hit and not empty.assessable)
    check("...and names no missed macro", empty.missed == [])

    tiny = evaluate_day(DAY, [Meal(90, 0.5, 25, 0.3)], GOAL)
    check("one logged apple is 'partial', not a 90-calorie day",
          tiny.status == "partial", tiny.summary())
    check("...and is excluded from scoring", not tiny.assessable)

    no_goal = evaluate_day(DAY, perfect(), None)
    check("no target set is 'no_goal'", no_goal.status == "no_goal")
    check("...and is not scored", not no_goal.assessable)

    # Today. The one most likely to be got wrong.
    partial_day = evaluate_day(DAY, [Meal(600, 40, 60, 15)], GOAL)
    partial_day.in_progress = True
    check("a day in progress is never 'missed'",
          partial_day.status == "in_progress", partial_day.status)
    check("...and says what is left", "to go" in partial_day.summary(),
          partial_day.summary())
    check("...and is not counted in the week", not partial_day.assessable)

    # But an in-progress day CAN already be over. Hiding that is dishonest.
    blown = evaluate_day(DAY, [Meal(2600, 150, 200, 60)], GOAL)
    blown.in_progress = True
    check("already over the ceiling is reported, not hidden",
          blown.status == "over_already", blown.status)
    check("...and says by how much", "over on calories" in blown.summary(),
          blown.summary())


def test_summary_and_streaks():
    from app.services.adherence import evaluate_day, summarise
    print(f"\n{BOLD}4. Weekly summary and streaks{RESET}")

    def week(specs):
        out = []
        for i, spec in enumerate(specs):
            day = DAY - timedelta(days=len(specs) - 1 - i)
            meals = [] if spec is None else [spec]
            out.append(evaluate_day(day, meals, GOAL))
        return out

    hit, miss = Meal(2000, 150, 200, 60), Meal(2600, 90, 300, 90)

    all_hit = summarise(week([hit] * 7))
    check("7/7 hits", all_hit["hits"] == 7 and all_hit["hit_rate"] == 1.0)
    check("streak is 7", all_hit["current_streak"] == 7)
    check("headline says every day", "every one" in all_hit["headline"], all_hit["headline"])

    none_hit = summarise(week([miss] * 7))
    check("0/7 hits", none_hit["hits"] == 0)
    check("streak is 0", none_hit["current_streak"] == 0)

    # Rates are over ASSESSABLE days. Dividing by 7 when 4 were unlogged
    # reports a failure that is really a logging gap - and that number would
    # then drive recommendations.
    gappy = summarise(week([hit, None, None, None, None, hit, hit]))
    check("hit rate ignores unlogged days", gappy["hit_rate"] == 1.0, gappy)
    check("unlogged days are counted separately", gappy["unlogged_days"] == 4, gappy)
    check("logging rate is reported", gappy["logging_rate"] == round(3 / 7, 2), gappy)

    # A gap BREAKS the streak: claiming consecutive days across a day we know
    # nothing about would be asserting something unevidenced.
    broken = summarise(week([hit, hit, hit, None, hit, hit, hit]))
    check("an unlogged day breaks the streak", broken["current_streak"] == 3, broken)
    check("best streak is still recorded", broken["best_streak"] == 3, broken)

    trailing = summarise(week([hit] * 6 + [miss]))
    check("a miss yesterday zeroes the current streak",
          trailing["current_streak"] == 0)
    check("...but best streak remembers the 6", trailing["best_streak"] == 6)


def test_weak_points():
    """The output that drives recommendations."""
    from app.services.adherence import evaluate_day, summarise
    print(f"\n{BOLD}5. Weak points{RESET}")

    # Five days, consistently 60g short on protein, everything else fine.
    days = [evaluate_day(DAY - timedelta(days=i), [Meal(2000, 90, 200, 60)], GOAL)
            for i in range(5)]
    summary = summarise(days)
    check("a repeated shortfall is identified", summary["weak_points"], summary)

    worst = summary["weak_points"][0]
    check("the right macro", worst["macro"] == "protein", worst)
    check("counted on every day", worst["days"] == 5, worst)
    check("direction is 'short'", worst["direction"] == "short", worst)
    check("average shortfall is the distance from the FLOOR, not the target",
          worst["average_delta"] == -15.0, worst)
    check("the headline names it", "protein" in summary["headline"], summary["headline"])

    # Over, not under - the correction has to work both ways.
    over = summarise([evaluate_day(DAY - timedelta(days=i),
                                   [Meal(2000, 150, 200, 90)], GOAL) for i in range(4)])
    check("a repeated excess is identified as 'over'",
          over["weak_points"][0]["direction"] == "over", over["weak_points"][:1])

    # Nothing to say when there is nothing wrong.
    clean = summarise([evaluate_day(DAY - timedelta(days=i), perfect(), GOAL)
                       for i in range(5)])
    check("no weak points on a clean week", clean["weak_points"] == [], clean)


def test_headlines_never_lie():
    """The headline is user-facing text. It must not overclaim."""
    from app.services.adherence import evaluate_day, summarise
    print(f"\n{BOLD}6. Headlines on empty and partial history{RESET}")

    check("no history at all", summarise([])["headline"] == "No history yet.")

    nothing_logged = summarise([evaluate_day(DAY - timedelta(days=i), [], GOAL)
                                for i in range(7)])
    check("nothing logged says so",
          "Nothing logged" in nothing_logged["headline"], nothing_logged["headline"])
    check("...and reports no hit rate rather than 0%",
          nothing_logged["hit_rate"] is None, nothing_logged["hit_rate"])

    no_goal = summarise([evaluate_day(DAY - timedelta(days=i), perfect(), None)
                         for i in range(7)])
    check("no goal set is explained, not scored",
          "target" in no_goal["headline"], no_goal["headline"])


def test_feeds_recommendations():
    """
    The point of the whole feature: does a week of missed protein change what
    gets suggested? If the ranking is identical, this is a chart, not
    personalisation.
    """
    from app.services.personalization import recommend_foods
    print(f"\n{BOLD}7. The week changes what gets recommended{RESET}")

    class Food:
        _next = 1

        def __init__(self, name, cal, pro, carb, fat):
            self.id, Food._next = Food._next, Food._next + 1
            self.name, self.calories = name, cal
            self.protein_g, self.carbs_g, self.fat_g = pro, carb, fat
            self.fiber_g = self.sugar_g = self.gi = 0
            self.cuisine_type = "indian"
            self.cost = 20
            self.prep_complexity = "LOW"
            self.tags = self.ingredients = ""
            self.diabetic_friendly = self.hypertension_friendly = True

    foods = [
        Food("Grilled chicken", 220, 40, 0, 5),      # protein dense
        Food("Paneer bhurji", 280, 20, 8, 18),
        Food("Plain rice", 260, 5, 56, 1),           # protein poor
        Food("Roti", 120, 3, 24, 1),
    ]

    class FakeQuery:
        def all(self_inner): return foods

    class FakeDB:
        def query(self_inner, *a, **k): return FakeQuery()

    user = type("U", (), {"id": 1, "dietary_preferences": None,
                          "health_conditions": None, "timezone": "UTC"})()
    profile = {"vegetarian": False, "health_conditions": [], "budget": None,
               "cuisine_affinity": {}, "favourites": [], "recent_food_ids": [],
               "variety": {}, "prep_preference": None}
    gap = {"remaining": {"calories": 800, "protein": 40}}

    def scores(week):
        return {f["name"]: f["score"] for f in recommend_foods(
            user, FakeDB(), profile, gap, goal_type="muscle_gain", limit=4, week=week)}

    def rank(week):
        return [f["name"] for f in recommend_foods(
            user, FakeDB(), profile, gap, goal_type="muscle_gain", limit=4, week=week)]

    TARGETS = {"calories": 2000, "protein": 150, "carbs": 200, "fat": 60}

    def week_of(macro, days, of, delta, direction):
        return {"assessable_days": of, "targets": TARGETS,
                "weak_points": [{"macro": macro, "days": days, "of": of,
                                 "average_delta": delta, "direction": direction}]}

    PROTEIN_SHORT = week_of("protein", 5, 6, -45.0, "short")
    FAT_OVER = week_of("fat", 5, 6, 30.0, "over")

    # Assert on SCORES, not on the final order. Ordering is a downstream
    # consequence and depends on how far apart the candidates happen to be -
    # an earlier version of this test used a fixture whose gaps were far too
    # wide to flip and so reported "no effect" while the mechanism worked
    # perfectly. Scores measure the thing being claimed.
    baseline = scores(None)
    short = scores(PROTEIN_SHORT)

    check("a protein shortfall raises the protein-dense food",
          short["Grilled chicken"] > baseline["Grilled chicken"],
          f"{baseline['Grilled chicken']} -> {short['Grilled chicken']}")
    check("...and lowers the protein-poor one",
          short["Plain rice"] < baseline["Plain rice"],
          f"{baseline['Plain rice']} -> {short['Plain rice']}")
    check("the protein-dense food ends up top", rank(PROTEIN_SHORT)[0] == "Grilled chicken")

    over_fat = scores(FAT_OVER)
    check("being over on fat penalises the fattiest option",
          over_fat["Paneer bhurji"] < baseline["Paneer bhurji"],
          f"{baseline['Paneer bhurji']} -> {over_fat['Paneer bhurji']}")
    check("...and rewards the leanest",
          over_fat["Plain rice"] > baseline["Plain rice"],
          f"{baseline['Plain rice']} -> {over_fat['Plain rice']}")
    check("the two corrections push in opposite directions",
          (short["Plain rice"] < baseline["Plain rice"]
           < over_fat["Plain rice"]),
          f"short={short['Plain rice']} base={baseline['Plain rice']} "
          f"over={over_fat['Plain rice']}")

    # The correction must scale with how bad the pattern is. A fixed weight
    # treated "3 of 6 days, 5g short" and "6 of 6 days, 80g short" as the same
    # problem, which is either too timid for one or too aggressive for the other.
    mild = scores(week_of("protein", 3, 6, -5.0, "short"))
    severe = scores(week_of("protein", 6, 6, -80.0, "short"))
    check("a severe shortfall steers harder than a mild one",
          severe["Grilled chicken"] > mild["Grilled chicken"] > baseline["Grilled chicken"],
          f"base={baseline['Grilled chicken']} mild={mild['Grilled chicken']} "
          f"severe={severe['Grilled chicken']}")

    # Prove the ORDER really changes, not just the numbers. Chronically over on
    # fat, the fattier option drops below a leaner one it previously beat.
    foods.clear()
    foods.extend([Food("Paneer tikka", 300, 24, 6, 19),
                  Food("Chana masala", 300, 17, 38, 7)])
    before, after = rank(None), rank(FAT_OVER)
    check("being over on fat flips the ranking",
          before[0] == "Paneer tikka" and after[0] == "Chana masala",
          f"{before} -> {after}")

    # THE guarantee. A recurring shortfall must never promote a food that is
    # bad for the goal just because it is dense in the missing macro - which is
    # exactly how "high protein" turns into deep-fried chicken.
    foods.clear()
    foods.extend([Food("Grilled chicken", 220, 40, 0, 5),
                  Food("Fried chicken", 560, 28, 30, 38)])
    desperate = [f["name"] for f in recommend_foods(
        user, FakeDB(), profile, gap, goal_type="weight_loss", limit=2,
        week=week_of("protein", 6, 6, -90.0, "short"))]
    check("even a severe protein shortfall does not promote fried chicken",
          desperate[0] == "Grilled chicken", desperate)

    foods.clear()
    foods.extend([Food("Grilled chicken", 220, 40, 0, 5),
                  Food("Paneer bhurji", 280, 20, 8, 18),
                  Food("Plain rice", 260, 5, 56, 1),
                  Food("Roti", 120, 3, 24, 1)])

    # It must say why, or the user cannot tell it is personalised.
    detail = recommend_foods(user, FakeDB(), profile, gap, goal_type="muscle_gain",
                             limit=4, week=PROTEIN_SHORT)
    top_reasons = " ".join(detail[0]["reasons"]).lower()
    check("the reason names the recurring shortfall",
          "short on" in top_reasons and "protein" in top_reasons, detail[0]["reasons"])

    # One bad day inside a good week is noise, not a pattern.
    one_off = scores({
        "assessable_days": 6,
        "weak_points": [{"macro": "protein", "days": 1, "of": 6,
                         "average_delta": -45.0, "direction": "short"}],
    })
    check("a single off day changes nothing", one_off == baseline,
          f"{one_off} vs {baseline}")

    # Too little history is not a pattern either.
    thin = scores({
        "assessable_days": 2,
        "weak_points": [{"macro": "protein", "days": 2, "of": 2,
                         "average_delta": -45.0, "direction": "short"}],
    })
    check("two days is not enough evidence to steer on", thin == baseline,
          f"{thin} vs {baseline}")


def test_chat_context_carries_it():
    """The assistant has to be told, or it will keep saying 'doing well'."""
    from app.services.chat_context import ChatContext, render_for_prompt
    print(f"\n{BOLD}8. The assistant is told how the week went{RESET}")

    ctx = ChatContext()
    ctx.days_on_target, ctx.days_assessable = 2, 6
    ctx.current_streak = 0
    ctx.yesterday_status, ctx.yesterday_summary = "missed", "short on protein by 40g"
    ctx.weak_points = [{"macro": "protein", "days": 5, "of": 6,
                        "average_delta": -40.0, "direction": "short"}]
    text = render_for_prompt(ctx)

    check("the record reaches the prompt", "2 of the last 6" in text, text)
    check("yesterday is named", "Yesterday" in text, text)
    check("the recurring gap is named", "protein" in text.lower(), text)
    check("...with an instruction, not just a fact",
          "correct this" in text.lower(), text)

    # A good week should read differently, or the model cannot tell them apart.
    good = ChatContext()
    good.days_on_target, good.days_assessable = 6, 6
    good.current_streak = 6
    good.yesterday_status = "hit"
    good_text = render_for_prompt(good)
    check("a good week renders differently", good_text != text)
    check("the streak is mentioned", "6 days running" in good_text, good_text)
    check("...but told to mention it once, not every message",
          "not every message" in good_text, good_text)

    # An empty context must not claim anything.
    blank = render_for_prompt(ChatContext())
    check("an empty context makes no adherence claim",
          "on target" not in blank.lower(), blank)


def test_timezone_correctness():
    """Adherence days are local days. This is the bug from the last pass."""
    from app.services import daytime
    from app.services.adherence import history
    print(f"\n{BOLD}9. Days are the user's days{RESET}")

    src = (ROOT / "app/services/adherence.py").read_text()
    check("adherence never calls utcnow/date.today directly",
          "datetime.now()" not in src and "date.today()" not in src)
    check("it groups by local day", "group_by_local_day" in src)
    check("it uses local day bounds", "day_bounds" in src)

    # todays_gap was still on a UTC boundary after the timezone pass.
    personal = (ROOT / "app/services/personalization.py").read_text()
    check("personalization.todays_gap now uses local day bounds",
          "today_bounds" in personal and
          "datetime.utcnow().replace(hour=0" not in personal)

    tracking = (ROOT / "app/routers/tracking.py").read_text()
    check("the day endpoint uses local bounds", "today_bounds" in tracking)


def main():
    test_bands()
    test_all_four_required()
    test_not_a_miss()
    test_summary_and_streaks()
    test_weak_points()
    test_headlines_never_lie()
    test_feeds_recommendations()
    test_chat_context_carries_it()
    test_timezone_correctness()

    print(f"\n{BOLD}{GREEN if not failed else RED}"
          f"{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
