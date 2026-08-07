#!/usr/bin/env python3
"""
Delete stored goals.

Goals created with the old form were hand-entered - users typed their own
calorie and macro numbers - so they do not reflect the calculated targets and
would show misleading comparisons on the dashboard. Clearing them lets everyone
set a goal properly through the new flow.

Weight logs are left alone: they are real measurements and the history is
worth keeping.

    python scripts/clear_goals.py            # ask first
    python scripts/clear_goals.py --yes      # no prompt
    python scripts/clear_goals.py --user 3   # just one user
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Goal, SessionLocal, User  # noqa: E402

GREEN, YELLOW, DIM, RESET = "\033[92m", "\033[93m", "\033[2m", "\033[0m"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="skip confirmation")
    ap.add_argument("--user", type=int, help="only this user id")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        query = db.query(Goal)
        if args.user:
            query = query.filter(Goal.user_id == args.user)

        goals = query.all()
        if not goals:
            print(f"{DIM}No goals stored - nothing to clear.{RESET}")
            return 0

        print(f"\n{len(goals)} goal(s) found:\n")
        names = {u.id: (u.username or u.email) for u in db.query(User).all()}
        for g in goals:
            who = names.get(g.user_id, f"user {g.user_id}")
            active = "active" if g.is_active else "inactive"
            print(
                f"  {DIM}#{g.id:<3}{RESET} {who:<24} {g.goal_type:<22} "
                f"{g.target_calories or '-'} kcal  {DIM}({active}){RESET}"
            )

        if not args.yes:
            print()
            answer = input(f"{YELLOW}Delete all of these? [y/N] {RESET}").strip().lower()
            if answer not in ("y", "yes"):
                print("Cancelled.")
                return 1

        deleted = query.delete(synchronize_session=False)
        db.commit()
        print(f"\n{GREEN}✓ Deleted {deleted} goal(s).{RESET}")
        print(f"{DIM}Weight logs kept. Set a new goal from Today → Goals.{RESET}\n")
        return 0

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
