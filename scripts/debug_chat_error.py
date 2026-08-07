#!/usr/bin/env python3
"""
Reproduce the chat failure in-process and print the real traceback.

Calls ConversationManager.handle_query directly - no HTTP, no FastAPI - so the
exception surfaces here instead of being swallowed by the outer handler and
turned into "Something went wrong on my end".

Usage (venv active, from project root):
    python scripts/debug_chat_error.py
    python scripts/debug_chat_error.py --query "I want a Kerala lunch recipe with chicken"
"""

import argparse
import asyncio
import logging
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Surface everything the manager logs, including the tool-call decision.
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-7s %(name)s: %(message)s",
)

GREEN, RED, YELLOW, DIM, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default="Plan a workout for muscle gain, 60 minutes, gym equipment")
    ap.add_argument("--user-id", type=int, default=None)
    ap.add_argument("--no-history", action="store_true",
                    help="Bypass stored history to test whether the DB rows are the trigger")
    args = ap.parse_args()

    print(f"\n{DIM}Importing application modules...{RESET}")
    try:
        from app.database import SessionLocal, User
        from app.services.conversation_manager import ConversationManager, MODEL_ID, TOOL_SCHEMAS
    except Exception:
        print(f"{RED}✗ Import failed - this alone would break every request:{RESET}\n")
        traceback.print_exc()
        return 1

    print(f"{GREEN}✓{RESET} imports OK  (model={MODEL_ID}, {len(TOOL_SCHEMAS)} tools)")

    db = SessionLocal()
    try:
        # Pick a user
        if args.user_id:
            user = db.query(User).filter(User.id == args.user_id).first()
        else:
            user = db.query(User).order_by(User.id.desc()).first()
        if not user:
            print(f"{RED}✗ No users in the database - register one first.{RESET}")
            return 1
        print(f"{GREEN}✓{RESET} user #{user.id} ({user.email})")

        try:
            cm = ConversationManager()
            print(f"{GREEN}✓{RESET} ConversationManager constructed "
                  f"{DIM}(all 6 agno services initialised){RESET}")
        except Exception:
            print(f"{RED}✗ Constructing ConversationManager failed:{RESET}\n")
            traceback.print_exc()
            return 1

        if args.no_history:
            cm.get_history = lambda *a, **k: []
            print(f"{YELLOW}!{RESET} history bypassed")
        else:
            hist = cm.get_history(user.id, db)
            print(f"{GREEN}✓{RESET} history loaded: {len(hist)} messages, "
                  f"{sum(len(m['content']) for m in hist)} chars")

        print(f"\n{DIM}{'='*72}{RESET}")
        print(f"QUERY: {args.query}")
        print(f"{DIM}{'='*72}{RESET}\n")

        # Call the internals directly so a failure points at the exact stage,
        # rather than being caught by handle_query's broad except.
        ctx = cm.get_user_context(user.id, db)
        print(f"{GREEN}✓{RESET} user context: {list(ctx.keys())}")

        history = [] if args.no_history else cm.get_history(user.id, db)
        messages = [{"role": "system", "content": cm.SYSTEM_PROMPT if hasattr(cm, "SYSTEM_PROMPT") else ""}]
        from app.services.conversation_manager import SYSTEM_PROMPT
        messages = [{"role": "system", "content": SYSTEM_PROMPT + cm._profile_block(ctx)}]
        messages.extend(history)
        messages.append({"role": "user", "content": args.query})

        total = sum(len(m["content"]) for m in messages)
        print(f"{GREEN}✓{RESET} prompt built: {len(messages)} messages, {total} chars")

        print(f"\n{DIM}Calling Groq with tools...{RESET}")
        try:
            reply = cm._complete(messages, use_tools=True)
        except Exception:
            print(f"\n{RED}✗ THE FAILURE IS HERE - _complete() raised:{RESET}\n")
            traceback.print_exc()
            print(f"\n{YELLOW}Retrying the same prompt WITHOUT tools to isolate...{RESET}")
            try:
                cm._complete(messages, use_tools=False)
                print(f"{YELLOW}-> Works without tools. The tool schemas are the trigger.{RESET}")
            except Exception:
                print(f"{RED}-> Also fails without tools. The messages are the trigger.{RESET}")
                traceback.print_exc()
            return 1

        calls = getattr(reply, "tool_calls", None)
        if calls:
            print(f"{GREEN}✓{RESET} model chose: {calls[0].function.name}"
                  f"({calls[0].function.arguments})")
        else:
            print(f"{GREEN}✓{RESET} model replied conversationally: "
                  f"{(reply.content or '')[:160]!r}")

        print(f"\n{DIM}Running the full handle_query end to end...{RESET}")
        result = await cm.handle_query(user.id, args.query, db)
        if result.get("success"):
            print(f"\n{GREEN}✓ SUCCESS{RESET}  tool_used={result.get('tool_used')}")
            print(f"{DIM}{str(result.get('response'))[:400]}{RESET}")
        else:
            print(f"\n{RED}✗ handle_query reported failure:{RESET} {result.get('error')}")
            return 1

    finally:
        db.close()

    print(f"\n{GREEN}No error reproduced. If the UI still fails, the difference is "
          f"the request itself - check auth and the uvicorn log.{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
