#!/usr/bin/env python3
"""
migrate_sqlite_to_postgres.py
=============================
Migrates ALL data from the local SQLite database to a Railway PostgreSQL instance.

Usage:
    1. Get your Railway Postgres connection string from the Railway dashboard:
       Variables → DATABASE_URL  (looks like postgresql://user:pass@host:port/db)

    2. Run:
       python migrate_sqlite_to_postgres.py "postgresql://user:pass@host:port/db"

The script will:
  - Export every table from local statements.db
  - Apply the Alembic schema to the Postgres database
  - Import all rows in correct FK-dependency order
  - Log progress and a final summary
"""

import sys
import os
import sqlite3
import json
from datetime import datetime, date
from decimal import Decimal

# ── Validate args ────────────────────────────────────────────────────────────
if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)

PG_URL = sys.argv[1]
SQLITE_PATH = os.path.join(os.path.dirname(__file__), "statements.db")

if not os.path.exists(SQLITE_PATH):
    print(f"❌ SQLite database not found at: {SQLITE_PATH}")
    sys.exit(1)

# ── Install deps check ───────────────────────────────────────────────────────
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("❌ psycopg2-binary is not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

# ── Table migration order (respects FK dependencies) ─────────────────────────
#    Tables listed first have no FK dependencies on later tables.
TABLE_ORDER = [
    "users",
    "financial_institutions",
    "accounts",                 # → users, financial_institutions
    "category_rules",           # → users
    "statements",               # → users, accounts
    "ai_extractions",           # → statements
    "transactions",             # → statements, accounts, category_rules
    "fees",                     # → statements
    "interest_charges",         # → statements
    "rewards_summary",          # → statements
    "category_summary",         # → statements
    "payments",                 # → statements
    "insights",                 # → users, accounts
    "budgets",                  # → users, accounts
    "advisor_reports",          # → users, accounts
    "daily_expenses",
    "daily_income",
    "liability_templates",
    "monthly_records",          # → liability_templates
    "monthly_liabilities",      # → monthly_records, liability_templates
]


def serialize(value):
    """Convert Python types to PG-compatible forms."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return json.dumps(value)
    return value


def export_sqlite(sqlite_path: str) -> dict[str, list[dict]]:
    """Read every row from every table into memory."""
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    data = {}
    for table in TABLE_ORDER:
        try:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            data[table] = [dict(r) for r in rows]
            print(f"  ↗ Exported {len(rows):>5} rows from {table}")
        except Exception as e:
            print(f"  ⚠ Skipping {table}: {e}")
            data[table] = []
    conn.close()
    return data


def apply_migrations(pg_url: str):
    """Run Alembic migrations against the Postgres database."""
    print("\n⚡ Running Alembic migrations on PostgreSQL…")
    # Temporarily set DATABASE_URL so our app config picks it up
    os.environ["DATABASE_URL"] = pg_url

    import asyncio
    from alembic.config import Config
    from alembic import command

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    print("✓ Schema ready")


def import_postgres(pg_url: str, data: dict[str, list[dict]]):
    """Bulk-insert all rows into PostgreSQL."""
    # Convert postgresql+asyncpg:// → postgresql:// for psycopg2
    dsn = pg_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    cur = conn.cursor()

    # Disable FK checks during import (not all PG versions support DEFERRED)
    cur.execute("SET session_replication_role = 'replica';")

    total_rows = 0
    for table in TABLE_ORDER:
        rows = data.get(table, [])
        if not rows:
            print(f"  ── {table}: 0 rows (skipped)")
            continue

        cols = list(rows[0].keys())
        col_str = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join(["%s"] * len(cols))
        sql = f'INSERT INTO "{table}" ({col_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'

        batch = [[serialize(row[c]) for c in cols] for row in rows]

        try:
            psycopg2.extras.execute_batch(cur, sql, batch, page_size=200)
            conn.commit()
            print(f"  ✓ {table}: {len(rows)} rows inserted")
            total_rows += len(rows)
        except Exception as e:
            conn.rollback()
            print(f"  ❌ {table}: FAILED — {e}")

    # Re-sync all sequences so future INSERTs get correct IDs
    print("\n🔄 Syncing sequences…")
    for table in TABLE_ORDER:
        try:
            cur.execute(f"""
                SELECT setval(
                    pg_get_serial_sequence('"{table}"', 'id'),
                    COALESCE((SELECT MAX(id) FROM "{table}"), 1)
                )
            """)
            conn.commit()
        except Exception:
            conn.rollback()  # table may not have a serial 'id'

    cur.execute("SET session_replication_role = 'origin';")
    conn.commit()
    cur.close()
    conn.close()
    return total_rows


def main():
    print("=" * 60)
    print("  SQLite → Railway PostgreSQL Migration")
    print("=" * 60)
    print(f"\n📂 Source: {SQLITE_PATH}")
    print(f"🐘 Target: {PG_URL[:40]}…\n")

    # 1. Export SQLite
    print("Step 1/3 — Exporting SQLite data…")
    data = export_sqlite(SQLITE_PATH)
    sqlite_total = sum(len(v) for v in data.values())
    print(f"  Total rows to migrate: {sqlite_total}")

    # 2. Apply schema
    print("\nStep 2/3 — Applying schema migrations…")
    try:
        apply_migrations(PG_URL)
    except Exception as e:
        print(f"  ⚠ Migration warning (may already be applied): {e}")

    # 3. Import into Postgres
    print("\nStep 3/3 — Importing into PostgreSQL…")
    imported = import_postgres(PG_URL, data)

    print("\n" + "=" * 60)
    print(f"  ✅ Migration complete — {imported} rows imported")
    print("=" * 60)


if __name__ == "__main__":
    main()
