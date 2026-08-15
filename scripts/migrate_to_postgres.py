#!/usr/bin/env python3
"""
Copy every row from the local SQLite database into a Postgres database
(Neon, in practice) - a one-off when moving the hosted deployment off
SQLite while keeping local development on it.

    python scripts/migrate_to_postgres.py "postgresql://user:pass@host/db?sslmode=require"

Read-only against nutrition_app.db: this can never affect the local database
or anything currently reading from it.

Uses app.database.Base for BOTH sides rather than reflecting either schema,
so the same Column objects - and their Boolean/DateTime/etc. type processors
- read the SQLite values and write the Postgres ones. That is what makes a
SQLite 0/1 land as a real Postgres boolean without hand-written conversion.

Run this against the target only after the app has started up against it at
least once (main.py's Base.metadata.create_all creates the schema on boot) -
there has to be a table to copy into.

Safe to re-run: a target table that already has rows is skipped rather than
risking a duplicate. It is not an upsert - if you need to redo a table,
truncate it in Neon first.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GREEN, RED, YELLOW, DIM, RESET = (
    "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"
)


def main() -> int:
    if len(sys.argv) != 2:
        print(f"{RED}Usage: python scripts/migrate_to_postgres.py <postgres-url>{RESET}")
        return 1

    pg_url = sys.argv[1]
    if not pg_url.startswith("postgresql"):
        print(f"{RED}That doesn't look like a Postgres URL "
              f"(expected it to start with 'postgresql').{RESET}")
        return 1

    from sqlalchemy import create_engine, inspect, select, text

    from app.database import Base

    src_engine = create_engine("sqlite:///./nutrition_app.db")
    dst_engine = create_engine(pg_url)

    dst_tables = set(inspect(dst_engine).get_table_names())
    missing = [t.name for t in Base.metadata.sorted_tables if t.name not in dst_tables]
    if missing:
        print(f"{RED}Target is missing tables: {', '.join(missing)}{RESET}")
        print(f"{DIM}Start the app once against this DATABASE_URL first - "
              f"main.py creates the schema on boot.{RESET}")
        return 1

    total_copied = 0
    with src_engine.connect() as src, dst_engine.begin() as dst:
        for table in Base.metadata.sorted_tables:
            rows = [dict(r._mapping) for r in src.execute(select(table))]
            if not rows:
                print(f"{DIM}{table.name}: 0 rows locally, nothing to copy{RESET}")
                continue

            already_there = dst.execute(select(table).limit(1)).first()
            if already_there is not None:
                print(f"{YELLOW}{table.name}: target already has rows, skipping{RESET}")
                continue

            dst.execute(table.insert(), rows)

            # Explicit ids were just inserted; without this, the next
            # INSERT that relies on the identity default would collide
            # with one of them.
            if "id" in table.c:
                dst.execute(text(
                    f'SELECT setval('
                    f"pg_get_serial_sequence('{table.name}', 'id'), "
                    f'(SELECT COALESCE(MAX(id), 1) FROM "{table.name}"))'
                ))

            print(f"{GREEN}{table.name}: copied {len(rows)} rows{RESET}")
            total_copied += len(rows)

    print(f"\n{GREEN}Done - {total_copied} rows copied.{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
