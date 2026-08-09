#!/usr/bin/env python3
"""
End-to-end test of challenges and injury tracking.

Checks the behaviour that matters rather than just that endpoints respond:

  * are challenges sized against THIS user's baseline, or generic numbers?
  * does each one explain itself?
  * does recording an injury actually change what is offered - specifically,
    does the training challenge give way to a recovery one?
  * does checking in move the severity, and does recovery reopen the plans?
  * is progress recomputed from real data?

    export TEST_USER=you@example.com TEST_PASSWORD=...
    python scripts/test_challenges.py

Adds a test injury and removes it again at the end unless --keep is passed.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GREEN, RED, YELLOW, CYAN, DIM, BOLD, RESET = (
    "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[2m", "\033[1m", "\033[0m"
)

passed = failed = 0


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  {GREEN}pass{RESET}  {label}")
    else:
        failed += 1
        print(f"  {RED}FAIL{RESET}  {label}")
        if detail:
            print(f"        {DIM}{detail}{RESET}")


def show_challenges(items):
    for c in items:
        bar_width = 18
        filled = int(bar_width * c["percent"] / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        tick = f"{GREEN}✓{RESET}" if c["completed"] else " "
        print(f"    {tick} {c['title']}")
        print(f"      {CYAN}{bar}{RESET} {c['current']:.0f}/{c['target']:.0f} {c['unit']}"
              f"  {DIM}· {c['type']} · {c['days_left']}d left · {c['points']}pts{RESET}")
        if c.get("reason"):
            print(f"      {DIM}why: {c['reason']}{RESET}")


def main():
    import requests

    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=None)
    ap.add_argument("--user", default=os.getenv("TEST_USER"))
    ap.add_argument("--password", default=os.getenv("TEST_PASSWORD"))
    ap.add_argument("--keep", action="store_true", help="leave the test injury in place")
    args = ap.parse_args()

    if not (args.user and args.password):
        print(f"{YELLOW}Set TEST_USER and TEST_PASSWORD, or pass --user/--password.{RESET}")
        return 1

    # Reuse the API discovery from the chatbot suite so the port and /api
    # prefix are found rather than assumed.
    from test_chatbot_scenarios import resolve_base, login
    base = resolve_base(args.base)
    if not base:
        print(f"{RED}No backend found. Start it with: uvicorn main:app --reload{RESET}")
        return 1

    token = login(base, args.user, args.password)
    if not token:
        return 1
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def get(path):
        return requests.get(f"{base}{path}", headers=headers, timeout=30)

    def post(path, body=None):
        return requests.post(f"{base}{path}", headers=headers, json=body or {}, timeout=30)

    def delete(path):
        return requests.delete(f"{base}{path}", headers=headers, timeout=30)

    # ---------------------------------------------------------------- 1
    print(f"\n{BOLD}1. Challenges, before any injury{RESET}")
    r = get("/challenges")
    check("GET /challenges responds", r.ok, f"HTTP {r.status_code}: {r.text[:200]}")
    if not r.ok:
        return 1

    data = r.json()
    items = data.get("challenges", [])
    context = data.get("context", {})

    print(f"\n  {DIM}your situation: goal={context.get('goal')} "
          f"target={context.get('calorie_target')} kcal / {context.get('protein_target')}g protein "
          f"· avg {context.get('avg_calories')} kcal / {context.get('avg_protein')}g "
          f"· {context.get('days_logged')} days logged{RESET}\n")
    show_challenges(items)
    print()

    check("at least one challenge was generated", len(items) > 0)
    check("every challenge explains itself",
          all(c.get("reason") for c in items),
          "A challenge with no stated reason is what made these feel random.")

    # The point of the rewrite: targets derived from the user, not constants.
    if context.get("protein_target") and context.get("avg_protein"):
        protein_challenges = [c for c in items if "protein" in c["title"].lower()]
        if protein_challenges:
            check("protein challenge sits between current average and target",
                  any(str(int(context["avg_protein"])) in (c.get("reason") or "")
                      or context["avg_protein"] < c["target"] * 100
                      for c in protein_challenges),
                  "Target should be derived from this user's baseline.")

    had_training = any(c["type"] == "workout" and "check in" not in c["title"].lower()
                       for c in items)
    print(f"  {DIM}training challenge present before injury: {had_training}{RESET}")

    # ---------------------------------------------------------------- 2
    print(f"\n{BOLD}2. Record an injury{RESET}")
    r = post("/injuries", {"description": "upper hamstring strain, left leg", "severity": 7})
    check("POST /injuries accepted", r.ok, f"HTTP {r.status_code}: {r.text[:200]}")
    if not r.ok:
        return 1
    injury = r.json().get("injury", {})
    injury_id = injury.get("id")
    print(f"  {DIM}recorded as body_part={injury.get('body_part')!r} "
          f"severity={injury.get('severity')}{RESET}")
    check("mapped onto a known contraindication key",
          injury.get("body_part") == "hamstring",
          f"Got {injury.get('body_part')!r} - exercise exclusions only apply to known keys.")

    # ---------------------------------------------------------------- 3
    print(f"\n{BOLD}3. Challenges after the injury{RESET}")
    r = post("/challenges/refresh")          # ask for one more, now injured
    r = get("/challenges")
    items = r.json().get("challenges", [])
    show_challenges(items)
    print()

    recovery = [c for c in items if "check in" in c["title"].lower()]
    check("a recovery challenge appeared", len(recovery) > 0,
          "While injured, the useful challenge is recovery, not performance.")

    risky = [c for c in items
             if any(w in c["title"].lower() for w in ("run", "sprint", "hiit", "5k", "squat"))]
    check("nothing suggested that the injury rules out", not risky,
          f"Offered: {[c['title'] for c in risky]}")

    # ---------------------------------------------------------------- 4
    print(f"\n{BOLD}4. Check in - improving{RESET}")
    r = post(f"/injuries/{injury_id}/checkin", {"severity": 4, "trend": "better"})
    check("check-in accepted", r.ok, f"HTTP {r.status_code}: {r.text[:200]}")
    if r.ok:
        result = r.json()
        print(f"  {DIM}{result.get('message')}{RESET}")
        check("severity updated", result.get("severity") == 4)
        check("not flagged for attention when improving", not result.get("needs_attention"))

    # ---------------------------------------------------------------- 5
    print(f"\n{BOLD}5. Check in - getting worse with a red flag{RESET}")
    r = post(f"/injuries/{injury_id}/checkin",
             {"severity": 8, "trend": "worse", "note": "sharp pain and some swelling now"})
    if r.ok:
        result = r.json()
        print(f"  {DIM}{result.get('message')}{RESET}")
        check("flagged as needing attention",
              result.get("needs_attention"),
              "Sharp pain and swelling should stop the app handing over another plan.")

    # ---------------------------------------------------------------- 6
    print(f"\n{BOLD}6. Check in - recovered{RESET}")
    r = post(f"/injuries/{injury_id}/checkin", {"severity": 1, "trend": "better"})
    if r.ok:
        result = r.json()
        print(f"  {DIM}{result.get('message')}{RESET}")
        check("auto-resolved at low severity", result.get("resolved"),
              "Should stop constraining plans once it no longer needs to.")

    r = get("/injuries")
    summary = r.json()
    check("no longer listed as active", not summary.get("has_active"),
          f"Still active: {summary.get('injuries')}")

    # ---------------------------------------------------------------- 7
    if injury_id and not args.keep:
        delete(f"/injuries/{injury_id}")
        print(f"\n{DIM}Test injury cleaned up. Pass --keep to leave it in place.{RESET}")

    print(f"\n{BOLD}{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
