#!/usr/bin/env python3
"""
Logging a meal must not report failure after it has succeeded.

THE BUG THIS EXISTS FOR
-----------------------
Every meal logged from the UI returned 500 "failed to log" - but the meal was
already committed. The write happened, then building the RESPONSE raised
KeyError('cholesterol'), and the endpoint turned a completed action into an
error. Hence the two symptoms that look contradictory:

    the app said it failed
    the meal appeared on the dashboard a minute later

That is the worst shape a bug can take: the user retries, and a retry that
"fails" the same way can silently double-log.

Two more faults on the same path:

    asyncio.run() called from inside a running event loop, so the challenge
    update raised on every call and its coroutine was never awaited

    no points were awarded at all - the other logging route does it, this one
    never did, and this is the route the UI actually uses

    python scripts/test_meal_logging.py
"""

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_DB = Path(tempfile.mkdtemp()) / "meal_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

GREEN, RED, DIM, BOLD, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[1m", "\033[0m"
passed = failed = 0

TZ = "Asia/Kolkata"

# What the frontend actually sends after the user confirms an analysis. Note
# there is no `cholesterol` key - the UI has never sent one, which is what
# made the omission in _usable_nutrients fatal.
CLIENT_NUTRIENTS = {
    "calories": 155,
    "protein": 13,
    "carbohydrates": 1.1,
    "fat": 11,
    "fiber": 0,
    "sugar": 1.1,
    "sodium": 124,
    "health_tags": ["high protein"],
}


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


def stub_agno():
    """The service imports agno at module load; the model is never called."""
    import types
    for name in ["agno", "agno.agent", "agno.models", "agno.models.groq"]:
        sys.modules.setdefault(name, types.ModuleType(name))

    class Fake:
        def __init__(self, *a, **k):
            pass
    sys.modules["agno.agent"].Agent = Fake
    sys.modules["agno.models.groq"].Groq = Fake


def fresh_db():
    from app.database import Base, SessionLocal, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def make_user(db):
    from app.database import Goal, User
    user = User(email="t@t", username="tester", hashed_password="x",
                full_name="T", age=25, height=180, weight=75, timezone=TZ)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(Goal(user_id=user.id, goal_type="muscle_gain", target_calories=2000,
                target_protein=150, target_carbs=200, target_fat=60,
                is_active=True, created_at=datetime.utcnow()))
    db.commit()
    return user


# ---------------------------------------------------------------------------

def test_the_response_shape_matches():
    """
    The two dicts have to agree.

    _usable_nutrients builds the nutrient dict for the client-supplied path,
    and the response reads keys out of it. When they drift, the read raises
    AFTER the meal is committed.
    """
    import re
    print(f"\n{BOLD}1. Response keys exist in the nutrient dict{RESET}")

    src = (ROOT / "app/services/nutrient_analyzer_service.py").read_text()

    usable = src[src.index("def _usable_nutrients"):src.index("def log_meal_with_analysis")]
    provided = set(re.findall(r'"(\w+)":\s*float', usable)) | {"health_tags"}

    # Anything read with [] must be guaranteed; optional fields must use .get.
    required = set(re.findall(r'parsed_nutrients\["(\w+)"\]', src))
    missing = required - provided

    check("every key read with [] is guaranteed by _usable_nutrients",
          not missing, f"missing: {sorted(missing)}")
    check("cholesterol is provided", "cholesterol" in provided)
    check("optional nutrients in the response use .get, not []",
          'parsed_nutrients.get("cholesterol"' in src)


def test_client_nutrients_log_successfully():
    """The end-to-end case that was returning 500."""
    stub_agno()
    from app.services.nutrient_analyzer_service import nutrient_analyzer_service as svc
    print(f"\n{BOLD}2. Logging with client-supplied nutrients{RESET}")

    db = fresh_db()
    user = make_user(db)

    result = svc.log_meal_with_analysis(
        food_name="eggs", serving_size="2 eggs", meal_type="breakfast",
        user_id=user.id, db=db, nutrients=dict(CLIENT_NUTRIENTS),
    )

    check("it reports success", result.get("success"), result.get("error"))
    data = result.get("data") or {}
    check("...and returns the logged row", bool(data.get("id")), data)
    check("...with the macros intact",
          (data.get("calories"), data.get("protein")) == (155, 13), data)
    check("...and cholesterol defaulted rather than raising",
          data.get("cholesterol") == 0, data.get("cholesterol"))

    from app.database import MealLog
    rows = db.query(MealLog).filter(MealLog.user_id == user.id).all()
    check("exactly one meal was written", len(rows) == 1, len(rows))
    db.close()


def test_no_success_without_a_row_and_no_row_without_success():
    """
    The contract that was broken.

    Reporting failure after committing is worse than either a clean success or
    a clean failure: the user retries, and the retry writes a second row.
    """
    stub_agno()
    from app.database import MealLog
    from app.services.nutrient_analyzer_service import nutrient_analyzer_service as svc
    print(f"\n{BOLD}3. Success and persistence agree{RESET}")

    db = fresh_db()
    user = make_user(db)

    result = svc.log_meal_with_analysis(
        food_name="eggs", serving_size="2 eggs", meal_type="breakfast",
        user_id=user.id, db=db, nutrients=dict(CLIENT_NUTRIENTS),
    )
    count = db.query(MealLog).filter(MealLog.user_id == user.id).count()
    check("success reported AND a row exists",
          result.get("success") and count == 1, f"success={result.get('success')} rows={count}")

    # A genuine refusal must leave nothing behind.
    bad = svc.log_meal_with_analysis(
        food_name="water", serving_size="1 glass", meal_type="snack",
        user_id=user.id, db=db,
        nutrients={"calories": 0, "protein": 0, "carbohydrates": 0, "fat": 0},
    )
    after = db.query(MealLog).filter(MealLog.user_id == user.id).count()
    check("a zero-calorie parse is refused", not bad.get("success"), bad)
    check("...and writes nothing", after == count, f"{count} -> {after}")
    db.close()


def test_no_asyncio_run_from_async_context():
    """
    The service is sync but called from an async endpoint.

    asyncio.run() refuses to nest, so the challenge update raised every time
    and its coroutine was never awaited - a warning in the log and silently
    skipped work.
    """
    import asyncio
    stub_agno()
    from app.services.nutrient_analyzer_service import _run_coroutine
    print(f"\n{BOLD}4. Coroutines run from sync code, loop or no loop{RESET}")

    async def answer():
        await asyncio.sleep(0)
        return {"success": True, "count": 3}

    # No loop running: the plain case.
    check("works with no running loop",
          _run_coroutine(answer()) == {"success": True, "count": 3})

    # A loop running: the case that was raising.
    async def from_inside_a_loop():
        return _run_coroutine(answer())

    check("works from inside a running loop",
          asyncio.run(from_inside_a_loop()) == {"success": True, "count": 3})

    # And the whole log path must not raise from an async context.
    async def log_it():
        from app.services.nutrient_analyzer_service import nutrient_analyzer_service as svc
        db = fresh_db()
        user = make_user(db)
        out = svc.log_meal_with_analysis(
            food_name="eggs", serving_size="2 eggs", meal_type="breakfast",
            user_id=user.id, db=db, nutrients=dict(CLIENT_NUTRIENTS),
        )
        db.close()
        return out

    result = asyncio.run(log_it())
    check("logging a meal inside a running loop succeeds",
          result.get("success"), result.get("error"))

    src = (ROOT / "app/services/nutrient_analyzer_service.py").read_text()
    check("no bare asyncio.run left on the logging path",
          "asyncio.run(\n" not in src and "= asyncio.run(" not in src)


def test_points_are_awarded():
    """
    This route awards points now.

    /meals/log always did; this one never did, and this is the route the UI
    uses - so logging from the app earned nothing.
    """
    stub_agno()
    from app.services import points_engine
    from app.services.nutrient_analyzer_service import nutrient_analyzer_service as svc
    print(f"\n{BOLD}5. Points{RESET}")

    db = fresh_db()
    user = make_user(db)

    before = points_engine.total_points(db, user.id)
    svc.log_meal_with_analysis(
        food_name="eggs", serving_size="2 eggs", meal_type="breakfast",
        user_id=user.id, db=db, nutrients=dict(CLIENT_NUTRIENTS),
    )
    after = points_engine.total_points(db, user.id)
    check("logging a meal awards points", after > before, f"{before} -> {after}")

    # Logging a second meal must not re-award the first meal's points twice.
    svc.log_meal_with_analysis(
        food_name="rice", serving_size="1 bowl", meal_type="lunch",
        user_id=user.id, db=db,
        nutrients={**CLIENT_NUTRIENTS, "calories": 400, "protein": 8},
    )
    third = points_engine.total_points(db, user.id)
    check("a second meal adds more", third > after, f"{after} -> {third}")

    from app.database import PointsLedger
    rows = db.query(PointsLedger).filter(PointsLedger.user_id == user.id).all()
    reasons = [r.reason for r in rows]
    check("the ledger has no duplicate reasons for the day",
          len(reasons) == len(set(reasons)), reasons)
    db.close()


def test_analyser_path_still_works():
    """The path that does NOT supply nutrients must be unaffected."""
    stub_agno()
    from app.services.nutrient_analyzer_service import nutrient_analyzer_service as svc
    print(f"\n{BOLD}6. The analyse-first path is unchanged{RESET}")

    db = fresh_db()
    user = make_user(db)

    # Stand in for the model so no network call is made.
    def fake_analysis(food_name, serving_size):
        return {
            "success": True,
            "parsed_nutrients": {
                "calories": 300, "protein": 20, "carbohydrates": 30, "fat": 10,
                "fiber": 3, "sugar": 5, "sodium": 200, "cholesterol": 45,
                "health_tags": [],
            },
        }

    original = svc.analyze_food_nutrition
    svc.analyze_food_nutrition = fake_analysis
    try:
        result = svc.log_meal_with_analysis(
            food_name="dal", serving_size="1 bowl", meal_type="lunch",
            user_id=user.id, db=db, nutrients=None,
        )
    finally:
        svc.analyze_food_nutrition = original

    check("it succeeds", result.get("success"), result.get("error"))
    check("...and carries the analyser's cholesterol through",
          (result.get("data") or {}).get("cholesterol") == 45, result.get("data"))
    db.close()


def test_malformed_client_input():
    """Rubbish from the client falls back to analysis rather than crashing."""
    stub_agno()
    from app.services.nutrient_analyzer_service import nutrient_analyzer_service as svc
    print(f"\n{BOLD}7. Malformed input{RESET}")

    for label, payload in [
        ("missing a required macro", {"calories": 100, "protein": 5}),
        ("a string where a number belongs", {**CLIENT_NUTRIENTS, "protein": "lots"}),
        ("None", None),
        ("not a dict", ["calories", 100]),
        ("empty", {}),
    ]:
        usable = svc._usable_nutrients(payload)
        check(f"{label} is rejected rather than raising", usable is None, usable)

    # Valid input with extra unknown keys must still work.
    extra = svc._usable_nutrients({**CLIENT_NUTRIENTS, "vitamin_c": 12, "unknown": "x"})
    check("unknown extra keys are ignored, not fatal", extra is not None, extra)


def main():
    test_the_response_shape_matches()
    test_client_nutrients_log_successfully()
    test_no_success_without_a_row_and_no_row_without_success()
    test_no_asyncio_run_from_async_context()
    test_points_are_awarded()
    test_analyser_path_still_works()
    test_malformed_client_input()

    print(f"\n{BOLD}{GREEN if not failed else RED}"
          f"{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
