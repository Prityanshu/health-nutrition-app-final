#!/usr/bin/env python3
"""
Add users.timezone, so "today" means the user's day rather than the UTC day.

    python scripts/migrate_timezone.py

Safe to run more than once. Existing rows are left NULL on purpose rather than
backfilled with a guess: NULL means "we don't know yet, use APP_TIMEZONE", and
the real value arrives the next time that user logs in. Writing a guess into
the column would make it indistinguishable from a value the user actually
confirmed.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GREEN, RED, YELLOW, DIM, RESET = (
    "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"
)


def main() -> int:
    from sqlalchemy import inspect, text

    from app.database import User, engine
    from app.services.daytime import DEFAULT_TIMEZONE

    table = User.__tablename__
    inspector = inspect(engine)

    if table not in inspector.get_table_names():
        print(f"{RED}No {table!r} table. Start the app once to create it.{RESET}")
        return 1

    columns = {c["name"] for c in inspector.get_columns(table)}
    if "timezone" in columns:
        print(f"{DIM}users.timezone already exists - nothing to do.{RESET}")
    else:
        print("Adding users.timezone…")
        try:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN timezone VARCHAR"))
        except Exception as e:
            print(f"{RED}Failed: {e}{RESET}")
            return 1
        print(f"{GREEN}Added.{RESET}")

    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
        unset = conn.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE timezone IS NULL")
        ).scalar() or 0

    print(f"\n{total} user(s), {unset} without a timezone.")
    if unset:
        print(f"{YELLOW}Those fall back to APP_TIMEZONE ({DEFAULT_TIMEZONE}) "
              f"until they next log in, when the browser sends the real one.{RESET}")

    print(f"\n{GREEN}Done.{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
