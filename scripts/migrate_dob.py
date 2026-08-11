#!/usr/bin/env python3
"""
Add `date_of_birth` to users.

A stored age is a snapshot: correct on the day it was typed, and wrong from the
next birthday onwards. It would not matter much if it were only shown on a
profile page - but age is an input to the Mifflin-St Jeor BMR equation, so a
stale age quietly biases every calorie and macro target the app produces, for
as long as the account exists.

NOTHING IS DESTROYED HERE
-------------------------
The `age` column stays exactly as it is. `User.current_age` prefers the birth
date and falls back to `age`, so accounts created before this migration keep
working untouched and can add a birth date whenever they feel like it.

No age is back-filled into a birth date either. "25" only tells you the year
within a twelve-month window, so inventing 1 January of the implied year would
replace an honestly imprecise number with a precise-looking wrong one.

    python scripts/migrate_dob.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect, text          # noqa: E402

from app.database import engine               # noqa: E402

GREEN, YELLOW, DIM, BOLD, RESET = (
    "\033[92m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
)


def main() -> int:
    inspector = inspect(engine)

    if "users" not in inspector.get_table_names():
        print(f"{YELLOW}No `users` table yet - nothing to migrate.{RESET}")
        print(f"{DIM}It will be created with the column already present.{RESET}")
        return 0

    columns = {c["name"] for c in inspector.get_columns("users")}

    if "date_of_birth" in columns:
        print(f"{GREEN}Already migrated.{RESET} `users.date_of_birth` exists.")
        return 0

    print(f"{BOLD}Adding users.date_of_birth{RESET}")
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN date_of_birth DATE"))

        total = conn.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
        with_age = conn.execute(
            text("SELECT COUNT(*) FROM users WHERE age IS NOT NULL")
        ).scalar() or 0

    print(f"{GREEN}Done.{RESET}")
    print(f"  {total} accounts, {with_age} with a stored age.")
    print()
    print(f"{DIM}Those accounts keep using their stored age until someone sets")
    print(f"a birth date on them - no age was guessed at or overwritten.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
