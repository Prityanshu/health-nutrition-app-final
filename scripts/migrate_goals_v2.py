#!/usr/bin/env python3
"""
Migration for the goal-setting rework.

  1. Adds users.sex          (needed by the Mifflin-St Jeor BMR equation)
  2. Creates weight_logs     (weekly check-ins so targets track current weight)
  3. Seeds one weight_log per user from their registration weight, so the
     progress chart and "current weight" lookups have a starting point.

WHY A SCRIPT: SQLAlchemy's Base.metadata.create_all() creates missing *tables*
but never alters existing ones, so a new column on `users` would silently not
exist and every query touching it would fail at runtime.

Safe to run repeatedly - each step checks before acting.

    python scripts/migrate_goals_v2.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402

GREEN, YELLOW, RED, DIM, RESET = "\033[92m", "\033[93m", "\033[91m", "\033[2m", "\033[0m"


def column_exists(table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(engine).get_columns(table)}


def table_exists(table: str) -> bool:
    return table in inspect(engine).get_table_names()


def main():
    print(f"\n{DIM}Database: {engine.url}{RESET}\n")
    changed = False

    # --- 1. users.sex ---------------------------------------------------
    if not table_exists("users"):
        print(f"{RED}✗ No 'users' table - run the app once to create the schema first.{RESET}")
        return 1

    if column_exists("users", "sex"):
        print(f"{DIM}·{RESET} users.sex already present")
    else:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN sex VARCHAR"))
        print(f"{GREEN}✓{RESET} added users.sex")
        changed = True

    # --- 2. weight_logs -------------------------------------------------
    if table_exists("weight_logs"):
        print(f"{DIM}·{RESET} weight_logs already present")
    else:
        Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["weight_logs"]])
        print(f"{GREEN}✓{RESET} created weight_logs")
        changed = True

    # --- 3. seed baseline weights ---------------------------------------
    db = SessionLocal()
    try:
        from app.database import User, WeightLog

        users = db.query(User).all()
        seeded = 0
        for user in users:
            if not user.weight:
                continue
            has_log = (
                db.query(WeightLog).filter(WeightLog.user_id == user.id).first() is not None
            )
            if not has_log:
                db.add(WeightLog(
                    user_id=user.id,
                    weight_kg=user.weight,
                    note="Starting weight from registration",
                ))
                seeded += 1
        if seeded:
            db.commit()
            print(f"{GREEN}✓{RESET} seeded {seeded} baseline weight entr{'y' if seeded == 1 else 'ies'}")
            changed = True
        else:
            print(f"{DIM}·{RESET} baseline weights already present")

        # --- report ------------------------------------------------------
        missing_sex = db.query(User).filter(
            (User.sex.is_(None)) | (User.sex == "")
        ).count()
        total = len(users)
        print()
        if missing_sex:
            print(f"{YELLOW}!{RESET} {missing_sex} of {total} users have no sex recorded.")
            print(f"  {DIM}Their BMR uses the midpoint constant, accurate to roughly ±80 kcal.")
            print(f"  The goal screen asks for it when missing.{RESET}")
        else:
            print(f"{GREEN}✓{RESET} all {total} users have sex recorded")

    finally:
        db.close()

    print()
    print(f"{GREEN}Migration complete.{RESET}" if changed else f"{DIM}Nothing to do - already migrated.{RESET}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
