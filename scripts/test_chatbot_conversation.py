#!/usr/bin/env python3
"""
End-to-end smoke test for the conversational chatbot.

Runs the exact multi-turn transcript that used to break (agent ping-pong) against
a live backend and reports whether context is being retained.

Usage:
    # start the backend first:  uvicorn main:app --reload --port 8001
    python scripts/test_chatbot_conversation.py

    # against a different host:
    python scripts/test_chatbot_conversation.py --url http://localhost:8001

    # with your own account instead of a throwaway test user:
    python scripts/test_chatbot_conversation.py --email you@example.com --password secret
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

GREEN, RED, YELLOW, DIM, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"

TEST_EMAIL = "chatbot_smoketest@example.com"
TEST_USERNAME = "chatbot_smoketest"
TEST_PASSWORD = "SmokeTest123!"


def request(url, data=None, token=None, method=None, form=False, timeout=120):
    headers = {}
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw or "{}")
        except json.JSONDecodeError:
            return e.code, {"detail": raw[:300]}
    except urllib.error.URLError as e:
        return 0, {"detail": str(e.reason)}


def login(base, email, password):
    status, body = request(
        f"{base}/api/auth/login",
        {"username": email, "password": password},
        form=True,
    )
    return body.get("access_token") if status == 200 else None


def ensure_user(base, email, password):
    """Log in, creating the throwaway test user first if it does not exist."""
    token = login(base, email, password)
    if token:
        return token, False, None

    # UserCreate requires age/weight/height - they have no defaults on the model.
    status, body = request(
        f"{base}/api/auth/register",
        {
            "email": email,
            "username": TEST_USERNAME,
            "password": password,
            "full_name": "Smoke Test",
            "age": 25,
            "weight": 70.0,
            "height": 175.0,
            "activity_level": "moderately_active",
            "health_conditions": "[]",
            "dietary_preferences": "[]",
        },
    )

    if status not in (200, 201):
        detail = body.get("detail", body)
        if isinstance(detail, list):  # pydantic validation errors
            detail = "; ".join(
                f"{'.'.join(str(p) for p in d.get('loc', [])[1:])}: {d.get('msg')}"
                for d in detail
            )
        return None, False, f"register returned {status} — {detail}"

    token = login(base, email, password)
    if not token:
        return None, True, "user was created but login still failed"
    return token, True, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8001")
    ap.add_argument("--email", default=TEST_EMAIL)
    ap.add_argument("--password", default=TEST_PASSWORD)
    args = ap.parse_args()
    base = args.url.rstrip("/")

    print(f"\n{DIM}Target: {base}{RESET}\n")

    # --- health ---------------------------------------------------------
    status, body = request(f"{base}/health")
    if status != 200:
        print(f"{RED}✗ Backend not reachable at {base}{RESET}")
        print(f"  {body.get('detail')}")
        print(f"\n  Start it with:  {YELLOW}uvicorn main:app --reload --port 8001{RESET}\n")
        return 1
    print(f"{GREEN}✓{RESET} Backend is up")

    status, body = request(f"{base}/api/chatbot/health")
    if status == 200:
        keys = body.get("groq_keys", {})
        print(f"{GREEN}✓{RESET} Chatbot service up — {body.get('tools_available')} tools, "
              f"{keys.get('active_keys', '?')}/{keys.get('total_keys', '?')} Groq keys active")
    else:
        print(f"{RED}✗ /api/chatbot/health returned {status}{RESET}")
        return 1

    # --- auth -----------------------------------------------------------
    token, created, err = ensure_user(base, args.email, args.password)
    if not token:
        print(f"{RED}✗ Could not authenticate as {args.email}{RESET}")
        if err:
            print(f"  {err}")
        print(f"\n  {DIM}If the account already exists with a different password, pass your own:")
        print(f"    python scripts/test_chatbot_conversation.py --email you@example.com --password yourpass{RESET}\n")
        return 1
    print(f"{GREEN}✓{RESET} Authenticated{' (new test user created)' if created else ''}")

    # --- clean slate ----------------------------------------------------
    request(f"{base}/api/chatbot/history", token=token, method="DELETE")
    print(f"{GREEN}✓{RESET} Conversation history cleared\n")

    # --- the transcript -------------------------------------------------
    turns = [
        ("I want to gain muscle",
         "Should ask a follow-up (equipment/time). Must NOT ask about ingredients."),
        ("Low fat paneer",
         "Should treat this as diet info in the muscle-gain thread. Must NOT switch to nutrition analysis."),
        ("Gym",
         "Now has goal + equipment — should produce a workout plan."),
    ]

    print("=" * 72)
    print("MULTI-TURN CONVERSATION TEST")
    print("=" * 72)

    replies = []
    for i, (msg, expectation) in enumerate(turns, 1):
        print(f"\n{DIM}[{i}/{len(turns)}] expectation: {expectation}{RESET}")
        print(f"  {YELLOW}You:{RESET} {msg}")
        t0 = time.time()
        status, body = request(f"{base}/api/chatbot/chat", {"query": msg}, token=token)
        elapsed = time.time() - t0

        if status != 200:
            print(f"  {RED}✗ HTTP {status}: {body.get('detail')}{RESET}")
            return 1

        reply = body.get("response", "")
        tool = body.get("tool_used")
        replies.append((reply, tool))

        preview = reply if len(reply) < 600 else reply[:600] + f"\n  {DIM}...[truncated]{RESET}"
        print(f"  {GREEN}Bot:{RESET} {preview}")
        print(f"  {DIM}tool_used={tool}  ({elapsed:.1f}s){RESET}")

    # --- assertions -----------------------------------------------------
    print("\n" + "=" * 72)
    print("CHECKS")
    print("=" * 72)

    passed = failed = 0

    def check(label, ok, detail=""):
        nonlocal passed, failed
        if ok:
            passed += 1
            print(f"{GREEN}✓{RESET} {label}")
        else:
            failed += 1
            print(f"{RED}✗ {label}{RESET}" + (f"\n    {DIM}{detail}{RESET}" if detail else ""))

    r1, t1 = replies[0]
    r2, t2 = replies[1]
    r3, t3 = replies[2]

    check("Turn 1 did not ask about ingredients",
          "ingredient" not in r1.lower(),
          "This was the original bug: 'want' matched a ChefGenius keyword.")

    check("Turn 2 did not derail into nutrition analysis",
          t2 != "analyze_food_nutrition" and "what food would you like to analyze" not in r2.lower(),
          "This was the original bug: 'fat' matched a nutrient_analyzer keyword.")

    check("Turn 2 stayed on the muscle-gain thread",
          any(w in r2.lower() for w in
              ["muscle", "protein", "gym", "home", "train", "workout", "equipment", "goal"]),
          f"Reply did not reference the ongoing topic:\n    {r2[:200]}")

    check("Turn 3 produced a workout plan",
          t3 == "generate_workout_plan",
          f"tool_used was {t3!r} instead of 'generate_workout_plan'.")

    check("No Python-generated form prompts anywhere",
          not any("I need just a bit more info" in r for r, _ in replies),
          "That string came from the old check_missing_fields().")

    # history endpoint
    status, hist = request(f"{base}/api/chatbot/history", token=token)
    check("History endpoint returns the full conversation",
          status == 200 and isinstance(hist, list) and len(hist) == len(turns) * 2,
          f"Expected {len(turns) * 2} messages, got {len(hist) if isinstance(hist, list) else hist}")

    print("\n" + "=" * 72)
    if failed == 0:
        print(f"{GREEN}All {passed} checks passed.{RESET}")
    else:
        print(f"{RED}{failed} failed{RESET}, {GREEN}{passed} passed{RESET}")
        print(f"\n{DIM}Note: turn-level checks depend on the LLM's wording and can vary "
              f"slightly between runs. Read the transcript above before concluding "
              f"something is broken.{RESET}")
    print("=" * 72 + "\n")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
