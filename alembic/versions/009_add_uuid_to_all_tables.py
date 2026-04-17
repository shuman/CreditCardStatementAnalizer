"""Add UUID column to all tables

Revision ID: 009
Revises: 65b8323be5e5
Create Date: 2026-04-17

Adds a uuid column (UUID v4) to all 19 database tables with the following:
  - String(36) column type for SQLite compatibility
  - NOT NULL constraint (after backfilling existing rows)
  - UNIQUE constraint for data integrity
  - Index on uuid field for query performance

Tables modified:
  From app/models/__init__.py (16 tables):
    financial_institutions, accounts, category_rules, ai_extractions,
    insights, budgets, advisor_reports, statements, transactions, fees,
    interest_charges, rewards_summary, category_summary, payments,
    daily_expenses, daily_income

  From app/models/liabilities.py (3 tables):
    liability_templates, monthly_records, monthly_liabilities

Migration approach (3 phases per table):
  1. Add nullable uuid column
  2. Backfill existing rows with generated UUID v4 values
  3. Alter column to NOT NULL and create unique index
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import uuid

revision = "009"
down_revision = "65b8323be5e5"
branch_labels = None
depends_on = None


# All tables that need uuid column
TABLES = [
    # From app/models/__init__.py
    "financial_institutions",
    "accounts",
    "category_rules",
    "ai_extractions",
    "insights",
    "budgets",
    "advisor_reports",
    "statements",
    "transactions",
    "fees",
    "interest_charges",
    "rewards_summary",
    "category_summary",
    "payments",
    "daily_expenses",
    "daily_income",
    # From app/models/liabilities.py
    "liability_templates",
    "monthly_records",
    "monthly_liabilities",
]


def add_uuid_to_table(table_name: str) -> None:
    """
    Add uuid column to a table with backfill and constraints.

    Three-phase approach:
      1. Add nullable uuid column
      2. Backfill existing rows with UUID v4
      3. Alter to NOT NULL and create unique index

    Args:
        table_name: Name of the table to modify
    """
    # Phase 1: Add nullable uuid column
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.add_column(sa.Column('uuid', sa.String(36), nullable=True))

    # Phase 2: Backfill UUIDs for existing rows
    connection = op.get_bind()
    rows = connection.execute(text(f"SELECT id FROM {table_name}")).fetchall()

    for row in rows:
        uuid_val = str(uuid.uuid4())
        connection.execute(
            text(f"UPDATE {table_name} SET uuid = :uuid WHERE id = :id"),
            {"uuid": uuid_val, "id": row[0]}
        )

    # Phase 3: Add NOT NULL constraint and create unique index
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.alter_column('uuid', nullable=False)
        batch_op.create_index(f'ix_{table_name}_uuid', ['uuid'], unique=True)


def remove_uuid_from_table(table_name: str) -> None:
    """
    Remove uuid column and index from a table.

    Args:
        table_name: Name of the table to modify
    """
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_index(f'ix_{table_name}_uuid')
        batch_op.drop_column('uuid')


def upgrade() -> None:
    """Add uuid column to all tables with backfill and constraints."""
    for table_name in TABLES:
        add_uuid_to_table(table_name)


def downgrade() -> None:
    """Remove uuid column and indexes from all tables."""
    for table_name in TABLES:
        remove_uuid_from_table(table_name)
