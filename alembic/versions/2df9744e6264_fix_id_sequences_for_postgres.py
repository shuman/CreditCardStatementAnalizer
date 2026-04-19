"""fix_id_sequences_for_postgres

Revision ID: 2df9744e6264
Revises: 0c28a4020a73
Create Date: 2026-04-20 01:10:11.627786

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2df9744e6264'
down_revision: Union[str, Sequence[str], None] = '0c28a4020a73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fix missing ID sequences for all tables except users."""
    tables = [
        "financial_institutions", "accounts", "category_rules", "ai_extractions",
        "insights", "budgets", "advisor_reports", "statements", "transactions", "fees",
        "interest_charges", "rewards_summary", "category_summary", "payments",
        "daily_expenses", "daily_income", "liability_templates", "monthly_records", "monthly_liabilities"
    ]
    
    for table in tables:
        seq_name = f"{table}_id_seq"
        # 1. Create sequence if not exists
        op.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq_name}")
        
        # 2. Set default for id column
        op.execute(f"ALTER TABLE {table} ALTER COLUMN id SET DEFAULT nextval('{seq_name}')")
        
        # 3. Synchronize sequence with existing data
        op.execute(f"SELECT setval('{seq_name}', COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)")
        
        # 4. Link sequence to the column (optional but good practice for SERIAL behavior)
        op.execute(f"ALTER SEQUENCE {seq_name} OWNED BY {table}.id")


def downgrade() -> None:
    """Remove sequences and defaults."""
    tables = [
        "financial_institutions", "accounts", "category_rules", "ai_extractions",
        "insights", "budgets", "advisor_reports", "statements", "transactions", "fees",
        "interest_charges", "rewards_summary", "category_summary", "payments",
        "daily_expenses", "daily_income", "liability_templates", "monthly_records", "monthly_liabilities"
    ]
    
    for table in tables:
        seq_name = f"{table}_id_seq"
        op.execute(f"ALTER TABLE {table} ALTER COLUMN id DROP DEFAULT")
        op.execute(f"DROP SEQUENCE IF EXISTS {seq_name}")
