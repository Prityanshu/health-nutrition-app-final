#!/usr/bin/env python3
"""
Diagnose Groq connectivity, key health and model availability.

Answers, in order:
  1. Are the API keys loaded and valid?
  2. Are the two models the app currently asks for still available on Groq?
  3. Does a plain completion work on the reasoning model?
  4. Does a tool-calling completion work on the reasoning model?
  5. Are we actually rate limited?

Run from the project root with the venv active:
    python scripts/diagnose_groq.py
"""

import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

GREEN, RED, YELLOW, DIM, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"

# Read from config rather than hardcoded here, so this script can never drift
# out of sync with what the app actually requests the way it did when Groq
# retired llama-3.3-70b-versatile out from under a hardcoded string.
from app.config.groq_config import get_fast_model, get_reasoning_model  # noqa: E402

FAST_MODEL = get_fast_model()
REASONING_MODEL = get_reasoning_model()
# The tool-calling / plain-completion checks below need one concrete target;
# the reasoning model is the one that actually has to support tool calling
# (the chat orchestrator), so it's the more important of the two to verify live.
EXPECTED_MODEL = REASONING_MODEL


def main():
    try:
        from groq import Groq
    except ImportError:
        print(f"{RED}groq package not installed{RESET}")
        return 1

    # --- keys ---------------------------------------------------------
    keys = []
    for name, env in [("primary", "GROQ_API_KEY"), ("secondary", "GROQ_API_KEY_2"), ("tertiary", "GROQ_API_KEY_3")]:
        val = os.getenv(env)
        if val:
            keys.append((name, env, val.strip().strip('"')))

    if not keys:
        print(f"{RED}✗ No Groq keys found in environment{RESET}")
        return 1
    print(f"{GREEN}✓{RESET} {len(keys)} key(s) loaded: {', '.join(n for n, _, _ in keys)}\n")

    working_key = None
    available = []
    orgs = {}

    # --- per-key validity, org identity and live quota ------------------
    #
    # models.list() proves a key is valid but consumes no quota, so it cannot
    # reveal whether two keys belong to the same organisation. Since rate
    # limits are per-org, two keys on one account share a quota and the second
    # is worthless. A tiny real completion is what actually distinguishes them:
    # a 429 body names the org, and a shared quota shows up as both keys being
    # limited at once.
    print("=" * 72)
    print("KEY VALIDITY, ORGANISATION AND QUOTA")
    print("=" * 72)
    for name, env, key in keys:
        client = Groq(api_key=key)
        try:
            ids = sorted(m.id for m in client.models.list().data)
        except Exception as e:
            msg = str(e)
            if "401" in msg or "invalid" in msg.lower() or "authentication" in msg.lower():
                print(f"{RED}✗ {name} ({env}) REJECTED — bad or revoked key{RESET}")
            else:
                print(f"{RED}✗ {name} ({env}) error: {msg[:120]}{RESET}")
            continue

        # Cheapest possible real call - a few tokens against the daily budget.
        probe_model = EXPECTED_MODEL if EXPECTED_MODEL in ids else (ids[0] if ids else None)
        status, org = "unknown", None
        try:
            client.chat.completions.create(
                model=probe_model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            status = f"{GREEN}quota available{RESET}"
            if not working_key:
                working_key, available = key, ids
        except Exception as e:
            msg = str(e)
            m = re.search(r"organization `([^`]+)`", msg)
            if m:
                org = m.group(1)
            if "429" in msg or "rate" in msg.lower():
                wait = re.search(r"try again in ([^.\"']+)", msg)
                status = f"{YELLOW}EXHAUSTED{RESET}" + (f" (resets in {wait.group(1)})" if wait else "")
            else:
                status = f"{RED}error: {msg[:80]}{RESET}"

        orgs[name] = org
        org_label = f" org={org[:16]}…" if org else ""
        print(f"  {name:10} {len(ids):2} models  {status}{DIM}{org_label}{RESET}")

    # Same-org detection
    known = {n: o for n, o in orgs.items() if o}
    if len(known) > 1 and len(set(known.values())) == 1:
        print(f"\n{RED}✗ These keys share one organisation — they share a quota.{RESET}")
        print(f"  {DIM}A second key on the same account buys nothing. Use a key from a "
              f"genuinely separate account.{RESET}")
    elif len(known) > 1:
        print(f"\n{GREEN}✓ Keys are on separate organisations — independent quotas.{RESET}")

    if not working_key:
        print(f"\n{YELLOW}Every key is currently out of quota.{RESET}")
        print(f"{DIM}Rotation cannot help until one resets. The app will now say so "
              f"explicitly instead of 'something went wrong'.{RESET}")
        return 1

    # --- model availability -------------------------------------------
    print()
    print("=" * 72)
    print("MODEL AVAILABILITY (both tiers - see groq_config.py)")
    print("=" * 72)

    tier_ok = True
    for label, model_id in [("GROQ_FAST_MODEL", FAST_MODEL), ("GROQ_REASONING_MODEL", REASONING_MODEL)]:
        if model_id in available:
            print(f"{label:20} {model_id:28} {GREEN}✓ available{RESET}")
        else:
            print(f"{label:20} {model_id:28} {RED}✗ NOT AVAILABLE{RESET}")
            tier_ok = False

    if not tier_ok:
        print(f"\n{DIM}Models your key can currently use:{RESET}")
        for m in available:
            print(f"    {m}")
        print(f"\n{YELLOW}Update GROQ_FAST_MODEL / GROQ_REASONING_MODEL in .env to one of "
              f"the above, then re-run this script.{RESET}")

    target = REASONING_MODEL if REASONING_MODEL in available else None
    if not target:
        return 1

    client = Groq(api_key=working_key)

    # --- plain completion ---------------------------------------------
    print()
    print("=" * 72)
    print("LIVE CALLS")
    print("=" * 72)
    t0 = time.time()
    try:
        r = client.chat.completions.create(
            model=target,
            messages=[{"role": "user", "content": "Say OK and nothing else."}],
            max_tokens=10,
        )
        print(f"{GREEN}✓{RESET} plain completion ({time.time()-t0:.1f}s): {r.choices[0].message.content!r}")
    except Exception as e:
        print(f"{RED}✗ plain completion failed ({time.time()-t0:.1f}s){RESET}\n    {str(e)[:400]}")
        return 1

    # --- tool calling --------------------------------------------------
    tools = [{
        "type": "function",
        "function": {
            "name": "generate_workout_plan",
            "description": "Create a workout plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fitness_goal": {"type": "string"},
                    "equipment": {"type": "string"},
                },
                "required": ["fitness_goal", "equipment"],
            },
        },
    }]
    t0 = time.time()
    try:
        r = client.chat.completions.create(
            model=target,
            messages=[{"role": "user", "content": "Plan a workout for muscle gain, 60 minutes, gym equipment"}],
            tools=tools,
            tool_choice="auto",
            max_tokens=300,
        )
        calls = r.choices[0].message.tool_calls
        if calls:
            print(f"{GREEN}✓{RESET} tool calling ({time.time()-t0:.1f}s): "
                  f"{calls[0].function.name}({calls[0].function.arguments})")
        else:
            print(f"{YELLOW}!{RESET} tool calling returned text, not a call ({time.time()-t0:.1f}s): "
                  f"{(r.choices[0].message.content or '')[:120]!r}")
            print(f"    {DIM}Model works but may not reliably use tools.{RESET}")
    except Exception as e:
        print(f"{RED}✗ tool calling failed ({time.time()-t0:.1f}s){RESET}\n    {str(e)[:400]}")
        print(f"    {DIM}Model exists but does not support tools - pick a tool-capable model.{RESET}")
        return 1

    # --- fast tier sanity check -----------------------------------------
    #
    # The fast tier is deliberately NOT expected to handle tools (it failed
    # that test when the split was chosen - see groq_config.py) - this just
    # confirms it can still do a plain completion, which is all six of the
    # agents on it ever ask of it.
    print()
    print("=" * 72)
    print(f"FAST TIER CHECK  ({FAST_MODEL})")
    print("=" * 72)
    if FAST_MODEL == target:
        print(f"{DIM}Fast and reasoning tier are the same model right now - nothing "
              f"further to check.{RESET}")
    elif FAST_MODEL not in available:
        print(f"{RED}✗ not available - see MODEL AVAILABILITY above{RESET}")
    else:
        try:
            t0 = time.time()
            r = client.chat.completions.create(
                model=FAST_MODEL,
                messages=[{"role": "user", "content": "Say OK and nothing else."}],
                max_tokens=10,
            )
            print(f"{GREEN}✓{RESET} plain completion ({time.time()-t0:.1f}s): "
                  f"{r.choices[0].message.content!r}")
        except Exception as e:
            print(f"{RED}✗ plain completion failed ({time.time()-t0:.1f}s){RESET}\n    {str(e)[:400]}")

    print()
    print("=" * 72)
    if tier_ok:
        print(f"{GREEN}Groq is healthy - both tiers available and working.{RESET}")
    else:
        print(f"{YELLOW}Reasoning tier works, but see MODEL AVAILABILITY above - "
              f"one tier is misconfigured.{RESET}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
