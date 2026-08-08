#!/usr/bin/env python3
"""
Scenario tests for the NutriCoach chatbot.

Every case here maps to an ID in docs/chatbot-audit.md, so a failure tells you
which documented scenario is broken rather than just which assertion tripped.

Two modes, because AI quota is the scarce resource:

  offline (default)
      Pure-function checks - smalltalk classification, injury trigger matching,
      tool-result unwrapping, context building. No network, no Groq, no cost.
      This covers most of the matrix and is the one to run on every change.

  live (--live)
      Real conversations against a running backend. Costs quota and takes a
      minute or two per case, so it is opt-in and filterable.

Usage
-----
    python scripts/test_chatbot_scenarios.py                    # offline, all
    python scripts/test_chatbot_scenarios.py --group smalltalk  # one group
    python scripts/test_chatbot_scenarios.py --live --user me@x.com --password pw
    python scripts/test_chatbot_scenarios.py --live --group injury
"""

import argparse
import os
import sys
import textwrap
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
)

results = []          # (scenario_id, group, description, passed, detail)
_group_filter = None  # set from --group; checks outside it are skipped entirely
_printed_headers = set()


def set_group_filter(group):
    global _group_filter
    _group_filter = group


def heading(title, group=None):
    """Print a section title, but only if that section will produce output."""
    if group and _group_filter and group != _group_filter:
        return
    if title not in _printed_headers:
        _printed_headers.add(title)
        print(f"\n{BOLD}{title}{RESET}")


def check(scenario_id, group, description, passed, detail=""):
    # Filter before recording and before printing, so --group shows only what
    # was asked for instead of printing everything and counting a subset.
    if _group_filter and group != _group_filter:
        return

    results.append((scenario_id, group, description, bool(passed), detail))
    mark = f"{GREEN}pass{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  [{mark}] {scenario_id:<4} {description}")
    if not passed and detail:
        for line in textwrap.wrap(detail, 92):
            print(f"         {DIM}{line}{RESET}")


# ===========================================================================
# OFFLINE
# ===========================================================================

def offline_smalltalk():
    """C1-C5: is a message social filler, or a real answer?"""
    from app.services.conversation_manager import is_smalltalk

    heading("Smalltalk classification", "smalltalk")

    # These genuinely are filler.
    for msg in ["hi", "Hello!", "thanks so much", "ok", "cool", "good morning",
                "see ya", "haha", "hi there"]:
        check("C4", "smalltalk", f"{msg!r} treated as smalltalk",
              is_smalltalk(msg),
              "Should be filler but was routed to the full tool-enabled path.")

    # These are NOT filler - they carry a real request.
    for msg in ["i want a workout plan", "what should i eat for dinner",
                "i have a hamstring injury", "make it cheaper",
                "is paneer high in protein"]:
        check("C5", "smalltalk", f"{msg!r} NOT treated as smalltalk",
              not is_smalltalk(msg),
              "Classified as filler, so tools were withheld and history collapsed.")

    # C1/C2: bare answers to a question the assistant just asked. Filler on
    # their own, but the answer to "do you have gym access?" when there is a
    # pending question. Requires the context-aware signature.
    import inspect
    sig = inspect.signature(is_smalltalk)
    context_aware = len(sig.parameters) > 1

    for msg in ["no", "yes", "yeah", "sure", "nope"]:
        if context_aware:
            passed = not is_smalltalk(msg, True)   # True = assistant just asked
            detail = f"{msg!r} discarded even though a question was pending."
        else:
            passed = False
            detail = (f"is_smalltalk() takes no conversational context, so {msg!r} "
                      "is always filler - the answer to a yes/no question is lost.")
        check("C1", "smalltalk", f"{msg!r} kept when a question is pending",
              passed, detail)

    check("C3", "smalltalk", "'help' is not silently swallowed",
          (not is_smalltalk("help")) if not context_aware else True,
          "'help' routes to the greeting prompt, which is instructed NOT to list "
          "capabilities - so asking for help returns a greeting.")


def offline_injury_triggers():
    """S4-S6: does the injury guidance load when it should, and only then?"""
    from app.services import conversation_manager as cm

    heading("Injury detection", "injury")

    def triggers(text):
        if hasattr(cm, "mentions_injury"):
            return cm.mentions_injury(text)
        return any(t in text.lower() for t in cm.INJURY_TRIGGERS)

    # Must fire.
    must_fire = [
        ("hamstring", "i pulled my hamstring"),
        ("S6-sciatica", "i have sciatica"),
        ("S6-shin", "shin splints are killing me"),
        ("S6-plantar", "plantar fasciitis in my left foot"),
        ("S6-elbow", "tennis elbow"),
        ("S6-itband", "IT band syndrome"),
        ("S6-asthma", "i have asthma"),
        ("S6-arthritis", "arthritis in my knees"),
        ("S6-acl", "recovering from an ACL tear"),
        ("S6-rotator", "rotator cuff problem"),
        ("S6-disc", "slipped disc"),
        ("S6-achilles", "achilles tendonitis"),
    ]
    for sid, text in must_fire:
        check(sid, "injury", f"fires on {text!r}", triggers(text),
              "Injury guidance would not be loaded, so the plan is generated "
              "with no anatomical exclusions.")

    # Must NOT fire - ordinary language that happens to contain a trigger.
    must_not_fire = [
        ("S4", "i want to get back into running"),
        ("S4", "take me back to the meal plan"),
        ("S5", "i have a headache"),
        ("S5", "my hip hop class is on tuesday"),
        ("S5", "what is a good back to school breakfast"),
    ]
    for sid, text in must_not_fire:
        check(sid, "injury", f"does NOT fire on {text!r}", not triggers(text),
              "~700 tokens of injury guidance loaded for a message with no injury "
              "in it. Wasted quota on every such turn.")


def offline_unwrap():
    """F2: a service result must never render as a raw Python dict."""
    from app.services.conversation_manager import ConversationManager

    heading("Tool result unwrapping", "unwrap")
    unwrap = ConversationManager._unwrap

    ok, text, _ = unwrap({"success": True, "recipe": "## Paneer bhurji\n..."}, "recipe")
    check("F4", "unwrap", "string field is extracted", ok and "Paneer" in text)

    ok, text, _ = unwrap({"success": False, "error": "rate limited"}, "recipe")
    check("F4", "unwrap", "failure is reported as failure", not ok)

    # The dangerous one: success, but nothing string-shaped to show.
    ok, text, _ = unwrap({"success": True, "plan": {"day1": ["squats"]}}, "workout_plan")
    looks_like_dict = text.strip().startswith("{") or "': '" in text or "\": \"" in text
    check("F2", "unwrap", "nested-dict result does not leak into the chat",
          not (ok and looks_like_dict),
          f"Returned {text[:90]!r} - a stringified Python dict shown to the user.")


def offline_context():
    """P1-P8: what actually reaches the prompt."""
    heading("Personalisation context", "context")

    try:
        from app.services import chat_context
    except ImportError:
        check("P1", "context", "chat_context module exists", False,
              "app/services/chat_context.py not found - the assistant has no way "
              "to see logged meals, weight trend, goal progress or saved plans.")
        return

    for fn in ("build_chat_context", "render_for_prompt"):
        check("P1", "context", f"chat_context.{fn} exists",
              hasattr(chat_context, fn),
              f"{fn} missing; the context cannot be built or rendered.")

    # The router must actually pass it - a built context that is never sent is
    # exactly the bug this whole audit started from.
    router = open(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "app", "routers", "chatbot.py"),
        encoding="utf-8",
    ).read()
    check("P1", "context", "chat router passes extra_context to handle_query",
          "extra_context" in router,
          "handle_query is called without extra_context, so any personalisation "
          "built is discarded before it reaches the model.")


def offline_prompt_budget():
    """C7: an enormous user message must not reach the model unbounded."""
    from app.services import conversation_manager as cm

    heading("Prompt budget", "budget")
    has_cap = hasattr(cm, "_USER_CHAR_CAP") or hasattr(cm, "clamp_user_message")
    check("C7", "budget", "user messages are length-capped", has_cap,
          "Only assistant messages are truncated (_HISTORY_CHAR_CAP). A user who "
          "pastes a long article sends it verbatim on every subsequent turn.")


def offline_sport():
    """S2: can the workout tool express a sport?"""
    from app.services.conversation_manager import TOOL_SCHEMAS

    heading("Workout tool schema", "sport")
    workout = next(
        (t["function"] for t in TOOL_SCHEMAS
         if t["function"]["name"] == "generate_workout_plan"), None
    )
    check("S2", "sport", "generate_workout_plan schema found", workout is not None)
    if not workout:
        return

    props = workout["parameters"]["properties"]
    check("S2", "sport", "a sport / activity field exists",
          any(k in props for k in ("sport", "activity", "sport_or_activity")),
          "No way to express 'footballer'. fitness_goal only offers muscle_gain, "
          "weight_loss, endurance, flexibility, general_fitness - so a sport "
          "request silently becomes general_fitness.")

    check("S1", "sport", "constraints field is present",
          "constraints" in props,
          "Injuries cannot be passed into the generator at all.")


def offline_persona():
    """I4: one coach, one voice."""
    from app.services import conversation_manager as cm

    heading("Persona consistency", "persona")
    check("I4", "persona", "a single shared persona definition exists",
          hasattr(cm, "PERSONA") or hasattr(cm, "COACH_PERSONA"),
          "The main prompt and the smalltalk prompt each describe NutriCoach "
          "separately, so the assistant's voice changes between a greeting and "
          "a real question.")


# ===========================================================================
# LIVE
# ===========================================================================

def live_scenarios(base, token, group_filter, show_replies=False):
    import requests

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def say(message):
        t0 = time.time()
        try:
            r = requests.post(f"{base}/chatbot/chat/simple", headers=headers,
                              json={"query": message}, timeout=180)
        except requests.exceptions.Timeout:
            return "", time.time() - t0
        elapsed = time.time() - t0
        body = r.json() if r.ok else {}
        return body.get("response", ""), elapsed

    # Each entry: (id, group, [messages], predicate over the final reply)
    conversations = [
        ("S1", "injury",
         ["I'm a footballer and I have an upper hamstring injury. "
          "Can you build me a training plan?"],
         lambda r: ("hamstring" in r.lower())
                   and not any(x in r.lower() for x in
                               ("deadlift", "romanian", "good morning",
                                "leg curl", "bent-over row", "bent over row")),
         "Plan must acknowledge the hamstring and contain no hip-hinge work."),

        ("C1", "smalltalk",
         ["I want a workout plan", "no"],
         lambda r: len(r) > 120,
         "After answering 'no' to the assistant's question the reply should "
         "continue the thread, not return a greeting."),

        ("P1", "context",
         ["What should I eat for dinner tonight?"],
         lambda r: any(x in r.lower() for x in
                       ("kcal", "calorie", "left", "remaining", "today", "logged")),
         "Dinner advice should reference today's intake or remaining calories."),

        ("P3", "context",
         ["Am I on track with my goal?"],
         lambda r: any(x in r.lower() for x in
                       ("kg", "weight", "week", "trend", "progress", "target")),
         "Should reference the actual weight trend, not give generic advice."),

        ("C3", "smalltalk",
         ["help"],
         lambda r: any(x in r.lower() for x in
                       ("recipe", "workout", "meal plan", "can ", "i can")),
         "'help' should explain capabilities, not return a bare greeting."),

        ("I2", "immersion",
         ["hi"],
         lambda r: len(r) < 400,
         "A greeting should stay short and must not recap earlier plans."),
    ]

    print(f"\n{BOLD}Live conversations{RESET} {DIM}(each costs AI quota){RESET}")
    for sid, group, messages, predicate, detail in conversations:
        if group_filter and group != group_filter:
            continue
        try:
            reply, elapsed = "", 0.0
            for message in messages:
                reply, elapsed = say(message)
            check(sid, group, f"{messages[-1]!r} ({elapsed:.0f}s)",
                  predicate(reply), f"{detail}\n         Got: {reply[:220]!r}")

            # An assertion can only confirm the reply mentions the right words.
            # Whether it sounds like a coach who knows you is a judgement call,
            # so print it and let a human make that call.
            if show_replies and reply:
                for line in reply.strip().splitlines()[:12]:
                    for wrapped in textwrap.wrap(line, 88) or [""]:
                        print(f"         {DIM}{wrapped}{RESET}")
                if len(reply.strip().splitlines()) > 12:
                    print(f"         {DIM}…{RESET}")
                print()
        except Exception as e:
            check(sid, group, f"{messages[-1]!r}", False, f"Request failed: {e}")


def resolve_base(explicit=None):
    """
    Find where the API actually is.

    Routers are mounted under /api and the app runs on 8000 or 8001 depending
    on how it was started, so a hardcoded base is wrong about as often as it is
    right. FastAPI publishes every route in openapi.json, so one request per
    candidate host tells us both the port and the prefix - no guessing.
    """
    import requests

    if explicit:
        return explicit

    for root in ("http://localhost:8000", "http://localhost:8001",
                 "http://127.0.0.1:8000", "http://127.0.0.1:8001"):
        try:
            r = requests.get(f"{root}/openapi.json", timeout=3)
            if not r.ok:
                continue
            paths = r.json().get("paths", {})
            login_path = next(
                (p for p in paths if p.endswith("/auth/login") or p == "/auth/login"),
                None,
            )
            if login_path:
                prefix = login_path[: -len("/auth/login")]
                base = f"{root}{prefix}"
                print(f"{DIM}Found the API at {base}{RESET}")
                return base
        except Exception:
            continue

    return None


def login(base, username, password):
    """Authenticate for the live suite, reporting problems in one line."""
    import requests

    try:
        r = requests.post(f"{base}/auth/login",
                          data={"username": username, "password": password}, timeout=30)
    except requests.exceptions.ConnectionError:
        print(f"\n{RED}Cannot reach the backend at {base}.{RESET}")
        print(f"{DIM}  Start it first:  uvicorn main:app --reload{RESET}")
        print(f"{DIM}  Or point elsewhere with --base http://host:port{RESET}")
        return None
    except requests.exceptions.Timeout:
        print(f"\n{RED}The backend at {base} did not respond within 30s.{RESET}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"\n{RED}Login request failed: {type(e).__name__}{RESET}")
        return None

    if r.status_code == 401:
        print(f"\n{RED}Login rejected - wrong username or password.{RESET}")
        print(f"{DIM}  The username field accepts either your username or your email.{RESET}")
        return None
    if not r.ok:
        print(f"\n{RED}Login failed with HTTP {r.status_code}.{RESET}")
        return None

    token = r.json().get("access_token")
    if not token:
        print(f"\n{RED}Login succeeded but returned no token.{RESET}")
        return None
    return token


# ===========================================================================

OFFLINE_SUITES = [
    offline_smalltalk, offline_injury_triggers, offline_unwrap,
    offline_context, offline_prompt_budget, offline_sport, offline_persona,
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also run real conversations")
    ap.add_argument("--show", action="store_true",
                    help="print each live reply in full, to judge tone as well as content")
    ap.add_argument("--base", default=None,
                    help="API base, e.g. http://localhost:8001/api. "
                         "Auto-detected from openapi.json if omitted.")
    ap.add_argument("--user", help="username or email for --live")
    ap.add_argument("--password", help="password for --live")
    ap.add_argument("--group", help="only run one group "
                                    "(smalltalk, injury, context, sport, unwrap, "
                                    "budget, persona, immersion)")
    args = ap.parse_args()

    print(f"\n{BOLD}NutriCoach scenario tests{RESET}")
    print(f"{DIM}IDs match docs/chatbot-audit.md{RESET}")

    set_group_filter(args.group)

    for suite in OFFLINE_SUITES:
        suite()

    if args.live:
        # Fall back to the environment so credentials need not be retyped - and
        # so they stay out of shell history.
        user = args.user or os.getenv("TEST_USER")
        password = args.password or os.getenv("TEST_PASSWORD")

        if not (user and password):
            print(f"\n{YELLOW}--live needs credentials.{RESET}")
            print(f"{DIM}  Either:  --user you@example.com --password ...{RESET}")
            print(f"{DIM}  Or set:  export TEST_USER=... TEST_PASSWORD=...{RESET}")
        else:
            base = resolve_base(args.base)
            if not base:
                print(f"\n{RED}Could not find a running backend.{RESET}")
                print(f"{DIM}  Tried ports 8000 and 8001 on localhost.{RESET}")
                print(f"{DIM}  Start it with:  uvicorn main:app --reload --port 8001{RESET}")
                print(f"{DIM}  Or pass it directly:  --base http://localhost:PORT/api{RESET}")
            else:
                token = login(base, user, password)
                if token:
                    live_scenarios(base, token, args.group, show_replies=args.show)

    passed = sum(1 for *_, ok, _ in results if ok)
    total = len(results)
    print(f"\n{BOLD}{passed}/{total} passed{RESET}")

    failures = [(sid, desc, detail) for sid, _, desc, ok, detail in results if not ok]
    if failures:
        print(f"\n{BOLD}Failing scenarios{RESET}")
        seen = set()
        for sid, desc, _ in failures:
            if sid not in seen:
                seen.add(sid)
                print(f"  {RED}{sid}{RESET}  {desc}")
        print(f"\n{DIM}Each ID is described in docs/chatbot-audit.md.{RESET}")

    print()
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
