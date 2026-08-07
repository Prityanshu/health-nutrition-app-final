#!/usr/bin/env python3
"""
Test the SMTP credentials in .env, independently of the running server.

A failed send from the app has three possible causes and the error message
cannot tell them apart:

  1. the server is running with credentials from before .env was edited
     (uvicorn --reload watches .py files, not .env)
  2. EMAIL_USER and the app password belong to different Google accounts
  3. the app password is wrong, revoked, or 2FA is off

This script reads .env fresh every time, so if it succeeds while the app fails,
the answer is (1) and a full restart fixes it.

    python scripts/test_email.py                  # login only
    python scripts/test_email.py --send you@x.com # login and send a real email
"""

import argparse
import os
import re
import smtplib
import sys
from email.mime.text import MIMEText
from email.utils import formataddr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

GREEN, RED, YELLOW, DIM, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", metavar="ADDRESS", help="also send a real test email")
    args = ap.parse_args()

    # override=True so a stale value already in the shell environment cannot
    # mask what is actually written in .env.
    load_dotenv(override=True)

    server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "465"))
    user = os.getenv("EMAIL_USER", "").strip()
    raw_pass = os.getenv("EMAIL_PASS", "")
    password = re.sub(r"\s+", "", raw_pass)
    from_name = os.getenv("EMAIL_FROM_NAME", "NutriPlan")

    print()
    print("=" * 68)
    print("CONFIGURATION (read from .env just now)")
    print("=" * 68)

    if not user or not password:
        print(f"{RED}x EMAIL_USER or EMAIL_PASS is empty. Email is disabled.{RESET}")
        return 1

    print(f"  server   : {server}:{port}")
    print(f"  user     : {user}")
    print(f"  password : {len(password)} chars {DIM}(not shown){RESET}")

    problems = []
    if len(password) != 16:
        problems.append(
            f"App passwords are exactly 16 characters; this one is {len(password)}. "
            "You may have pasted your normal account password."
        )
    if not password.isalpha():
        problems.append(
            "App passwords are all lowercase letters; this one contains digits or "
            "symbols, which suggests it is not an app password."
        )
    if password.strip('"\'') != password:
        problems.append("Value is wrapped in quotes - remove them from .env.")
    if "@" not in user:
        problems.append(f"EMAIL_USER '{user}' is not an email address.")

    for p in problems:
        print(f"{YELLOW}  ! {p}{RESET}")

    print()
    print("=" * 68)
    print("LOGIN")
    print("=" * 68)

    try:
        with smtplib.SMTP_SSL(server, port, timeout=20) as smtp:
            smtp.login(user, password)
            print(f"{GREEN}v Login succeeded.{RESET}")

            if args.send:
                msg = MIMEText(
                    "If you are reading this, NutriPlan can send email.\n\n"
                    "Sent by scripts/test_email.py",
                    "plain",
                    "utf-8",
                )
                msg["From"] = formataddr((from_name, user))
                msg["To"] = args.send
                msg["Subject"] = "NutriPlan email test"
                smtp.sendmail(user, [args.send], msg.as_string())
                print(f"{GREEN}v Test email sent to {args.send}.{RESET}")
                print(f"{DIM}  Check the spam folder too - a new Gmail account has no")
                print(f"  sending reputation yet. Marking it 'not spam' builds one.{RESET}")

    except smtplib.SMTPAuthenticationError as e:
        code = getattr(e, "smtp_code", "?")
        detail = getattr(e, "smtp_error", b"")
        detail = detail.decode(errors="replace") if isinstance(detail, bytes) else str(detail)
        print(f"{RED}x Google rejected the login (SMTP {code}).{RESET}")
        print(f"{DIM}  {detail.strip()[:300]}{RESET}")
        print()
        print("  Check, in this order:")
        print(f"    1. The app password was generated while signed in as {user}")
        print("       - not as a different Google account.")
        print("    2. 2-Step Verification is ON for that account. Without it,")
        print("       app passwords do not work even if one was issued earlier.")
        print("    3. The app password has not been deleted at")
        print("       https://myaccount.google.com/apppasswords")
        print()
        print(f"{DIM}  If unsure, delete the entry and generate a fresh one - it takes"
              f" a minute\n  and rules out a bad copy-paste.{RESET}")
        return 1

    except (smtplib.SMTPException, OSError) as e:
        print(f"{RED}x Could not reach the mail server: {type(e).__name__}: {e}{RESET}")
        print(f"{DIM}  Network, firewall or DNS - not a credentials problem.{RESET}")
        return 1

    print()
    print(f"{GREEN}Credentials are good.{RESET}")
    print("If the app still reports a rejected login, it is running with the old")
    print("values: stop uvicorn completely and start it again. --reload watches")
    print(".py files only, so editing .env does not restart the process.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
