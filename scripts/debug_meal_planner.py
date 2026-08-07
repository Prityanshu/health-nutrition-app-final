#!/usr/bin/env python3
"""
Find out why the meal planner is failing.

Calls the service directly with the same payload the frontend sends, so the
real exception surfaces here instead of being flattened into a message.

The 7-day plan is a large JSON object - roughly 7 days x N meals with macros,
plus a shopping list - so the most likely failure is the model running out of
output tokens mid-object, leaving JSON that cannot be parsed. This prints the
raw agent output so that is immediately visible.

    python scripts/debug_meal_planner.py
    python scripts/debug_meal_planner.py --meals 2    # smaller plan
"""

import argparse
import json
import logging
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

GREEN, RED, YELLOW, DIM, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calories", type=int, default=2000)
    ap.add_argument("--meals", type=int, default=3)
    ap.add_argument("--raw", action="store_true", help="print the full agent output")
    args = ap.parse_args()

    print(f"\n{DIM}Importing service…{RESET}")
    try:
        from app.services.advanced_meal_planner_service import advanced_meal_planner_service
    except Exception:
        print(f"{RED}✗ Import failed:{RESET}\n")
        traceback.print_exc()
        return 1
    print(f"{GREEN}✓{RESET} service loaded")

    payload = {
        "target_calories": args.calories,
        "meals_per_day": args.meals,
        "food_preferences": ["paneer"],
        "budget_per_day": 300.0,
        "work_hours_per_day": 8,
        "dietary_restrictions": ["vegetarian"],
        "equipment": ["stove"],
        "time_per_meal_min": 30,
        "region_or_cuisine": "south indian",
        "user_notes": "",
    }
    print(f"{GREEN}✓{RESET} payload: {args.calories} kcal, {args.meals} meals/day\n")

    # --- the agent call, unwrapped ------------------------------------
    print("=" * 72)
    print("CALLING THE AGENT (this takes 20-40s for a full week)")
    print("=" * 72)

    agent = advanced_meal_planner_service.advanced_meal_agent
    query = advanced_meal_planner_service.build_query(payload)

    try:
        response = agent.run(query)
    except Exception as e:
        print(f"\n{RED}✗ The agent call itself raised{RESET}")
        print(f"  type   : {type(e).__name__}")
        print(f"  message: {str(e)!r}  {DIM}(empty message is why the UI showed nothing){RESET}")
        print()
        traceback.print_exc()
        return 1

    text = response.content if hasattr(response, "content") else str(response)
    if text is None:
        print(f"{RED}✗ Agent returned no content at all (response.content is None){RESET}")
        print(f"  response type: {type(response).__name__}")
        return 1

    print(f"{GREEN}✓{RESET} agent replied: {len(text):,} characters")

    # --- does it parse? -------------------------------------------------
    print()
    print("=" * 72)
    print("PARSING")
    print("=" * 72)

    ok = False
    try:
        parsed = json.loads(text)
        print(f"{GREEN}✓{RESET} parsed directly as JSON")
        ok = True
    except json.JSONDecodeError as e:
        print(f"{YELLOW}!{RESET} not pure JSON ({e.msg} at position {e.pos})")
        start = text.find("{")
        if start == -1:
            print(f"{RED}✗ No JSON object anywhere — the agent replied in prose.{RESET}")
        else:
            depth, end = 0, -1
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end == -1:
                print(f"{RED}✗ JSON starts but never closes — the reply was cut off.{RESET}")
                print(f"  {DIM}Unclosed braces: {depth}. This is the classic symptom of the")
                print(f"  model hitting its output limit partway through the object.{RESET}")
                print(f"\n  last 200 chars:\n  {DIM}…{text[-200:]}{RESET}")
            else:
                try:
                    parsed = json.loads(text[start:end])
                    print(f"{GREEN}✓{RESET} recovered JSON by brace matching")
                    ok = True
                except json.JSONDecodeError as e2:
                    print(f"{RED}✗ Recovered block still invalid: {e2.msg}{RESET}")

    if ok:
        plan = parsed.get("plan", {})
        print()
        print(f"  days returned : {len(plan)}")
        print(f"  top-level keys: {list(parsed.keys())}")
        if plan:
            first = sorted(plan.keys())[0]
            print(f"  {first}: {len(plan[first])} meals")
        print(f"\n{GREEN}The planner works. If the UI still fails, the problem is in the "
              f"frontend, not here.{RESET}")

    if args.raw or not ok:
        print()
        print("=" * 72)
        print("RAW AGENT OUTPUT")
        print("=" * 72)
        print(text[:3000])
        if len(text) > 3000:
            print(f"{DIM}… {len(text) - 3000:,} more characters{RESET}")

    if not ok:
        print()
        print(f"{YELLOW}If the JSON was cut off, try: python scripts/debug_meal_planner.py --meals 2{RESET}")
        print(f"{DIM}A smaller plan needs fewer output tokens and may complete.{RESET}")

    print()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
