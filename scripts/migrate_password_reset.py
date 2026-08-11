#!/usr/bin/env python3
"""
Add the password_reset_tokens table.

Passwords are bcrypt hashes, which is a one-way function - nobody, including
whoever runs the server, can read them. That is correct, and it means the only
way back into a locked-out account is to set a NEW password rather than recover
the old one. This table holds the one-shot tickets that allow that.

Nothing existing is touched. The table is new and starts empty.

    python scripts/migrate_password_reset.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect                            # noqa: E402

from app.database import Base, PasswordResetToken, engine  # noqa: E402

GREEN, YELLOW, DIM, BOLD, RESET = (
    "\033[92m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
)


def main() -> int:
    inspector = inspect(engine)
    table = PasswordResetToken.__tablename__

    if table in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns(table)}
        print(f"{GREEN}Already migrated.{RESET} `{table}` exists "
              f"with {len(columns)} columns.")
        return 0

    print(f"{BOLD}Creating {table}{RESET}")
    Base.metadata.create_all(bind=engine, tables=[PasswordResetToken.__table__])

    columns = {c["name"] for c in inspect(engine).get_columns(table)}
    print(f"{GREEN}Done.{RESET} {len(columns)} columns: {', '.join(sorted(columns))}")
    print()
    print(f"{DIM}Only a SHA-256 of each token is stored here - the token itself")
    print(f"exists solely in the email, so this table cannot be used to reset")
    print(f"anyone's password even with full database access.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
