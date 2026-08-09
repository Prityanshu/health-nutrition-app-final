#!/usr/bin/env python3
"""
Create the challenge outcome table.

    python scripts/migrate_challenges.py

This is what gives challenges a memory: which ones were completed, which were
missed, and therefore whether the next one should ask more or less. Safe to run
repeatedly.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GREEN, RED, DIM, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[0m"


def main() -> int:
    from sqlalchemy import inspect

    from app.database import Base, ChallengeOutcome, engine

    print("\nCreating challenge history table…")
    before = set(inspect(engine).get_table_names())
    try:
        Base.metadata.create_all(bind=engine, tables=[ChallengeOutcome.__table__])
    except Exception as e:
        print(f"{RED}Failed: {type(e).__name__}: {e}{RESET}\n")
        return 1

    after = set(inspect(engine).get_table_names())
    table = ChallengeOutcome.__tablename__

    if table in after and table not in before:
        print(f"  {GREEN}created{RESET}  {table}")
    elif table in after:
        print(f"  {DIM}exists   {table}{RESET}")
    else:
        print(f"  {RED}missing  {table}{RESET}")
        return 1

    print(f"\n{GREEN}Done.{RESET} Challenges now escalate when you clear them and "
          f"ease off when you miss.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
