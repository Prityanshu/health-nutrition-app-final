#!/usr/bin/env python3
"""
Create the workout_logs and points_ledger tables, then backfill points.

    python scripts/migrate_points.py              # create tables + backfill
    python scripts/migrate_points.py --no-backfill

Safe to run more than once. create_all only creates what is missing, and the
backfill is idempotent - every award is keyed (user, day, reason) with a unique
constraint, so re-running awards nothing twice.

Backfilling matters: without it everybody starts at zero regardless of months
of logging, which reads as the app having forgotten what they did.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-backfill", action="store_true")
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()

    from sqlalchemy import inspect

    from app.database import Base, PointsLedger, SessionLocal, User, WorkoutLog, engine

    print(f"\n{BOLD}Creating tables…{RESET}")
    wanted = {
        WorkoutLog.__tablename__: WorkoutLog,
        PointsLedger.__tablename__: PointsLedger,
    }

    # Note: main.py calls Base.metadata.create_all() at import, so a running
    # backend on --reload will already have made these. A before/after diff
    # would therefore always report "exists" and tell you nothing; what
    # actually matters is whether the table is present with the right columns.
    try:
        Base.metadata.create_all(
            bind=engine, tables=[WorkoutLog.__table__, PointsLedger.__table__]
        )
    except Exception as e:
        print(f"{RED}Failed: {e}{RESET}")
        return 1

    inspector = inspect(engine)
    present = set(inspector.get_table_names())
    for table, model in wanted.items():
        if table not in present:
            print(f"  {RED}missing  {table}{RESET}")
            return 1
        have = {c["name"] for c in inspector.get_columns(table)}
        want = {c.name for c in model.__table__.columns}
        if want - have:
            print(f"  {RED}{table}: missing column(s) {sorted(want - have)}{RESET}")
            print(f"  {YELLOW}An older version of this table exists. Drop it and "
                  f"re-run, or add the columns by hand.{RESET}")
            return 1
        print(f"  {GREEN}ready{RESET}  {table}  ({len(have)} columns)")

    if args.no_backfill:
        print(f"\n{YELLOW}Skipping backfill.{RESET}\n")
        return 0

    from app.services import points_engine

    db = SessionLocal()
    try:
        users = db.query(User).all()
        print(f"\n{BOLD}Backfilling {args.days} days for {len(users)} user(s)…{RESET}")
        for user in users:
            try:
                result = points_engine.backfill(db, user, days=args.days)
                total = points_engine.total_points(db, user.id)
                level = points_engine.level_for(total)
                print(f"  {user.username:20} +{result['points_added']:>6} pts "
                      f"over {result['days_with_points']:>3} day(s)  "
                      f"→ {total} total, level {level['level']} ({level['title']})")
            except Exception as e:
                print(f"  {RED}{user.username}: {e}{RESET}")
                db.rollback()
    finally:
        db.close()

    print(f"\n{GREEN}Done.{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
