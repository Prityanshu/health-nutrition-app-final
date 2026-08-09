#!/usr/bin/env python3
"""
Create the injury tracking tables.

    python scripts/migrate_injuries.py

Safe to run more than once - create_all only creates what is missing and never
touches existing tables or data.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GREEN, RED, DIM, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[0m"


def main() -> int:
    from sqlalchemy import inspect

    from app.database import Base, Injury, InjuryCheckIn, engine

    print("\nCreating injury tables…")
    wanted = [Injury.__tablename__, InjuryCheckIn.__tablename__]

    before = set(inspect(engine).get_table_names())
    try:
        Base.metadata.create_all(bind=engine, tables=[Injury.__table__, InjuryCheckIn.__table__])
    except Exception as e:
        print(f"{RED}Failed: {type(e).__name__}: {e}{RESET}\n")
        return 1

    after = set(inspect(engine).get_table_names())

    for table in wanted:
        if table in after and table not in before:
            print(f"  {GREEN}created{RESET}  {table}")
        elif table in after:
            print(f"  {DIM}exists   {table}{RESET}")
        else:
            print(f"  {RED}missing  {table}{RESET}")
            return 1

    print(f"\n{GREEN}Done.{RESET} Injuries now persist across sessions and feed "
          f"plans, meals and challenges.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
