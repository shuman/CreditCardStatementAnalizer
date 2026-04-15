"""Add daily_expenses and daily_income tables for manual transaction logging

Revision ID: 007
Revises: 006
Create Date: 2026-04-16

Stores user-entered daily cash expenses and income transactions.
Supports batch AI categorization with user review workflow.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create daily_expenses table
    op.create_table(
        "daily_expenses",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BDT"),
        sa.Column("description_raw", sa.String(500), nullable=False),
        sa.Column("description_normalized", sa.String(500), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("subcategory", sa.String(100), nullable=True),
        sa.Column("tags", JSON, nullable=True),
        sa.Column("payment_method", sa.String(20), nullable=False, server_default="cash"),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("transaction_time", sa.Time, nullable=True),
        sa.Column("ai_status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("needs_review", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("enriched_at", sa.DateTime, nullable=True),
    )

    with op.batch_alter_table("daily_expenses") as batch_op:
        batch_op.create_index("ix_daily_expenses_transaction_date", ["transaction_date"])
        batch_op.create_index("ix_daily_expenses_ai_status", ["ai_status"])
        batch_op.create_index("ix_daily_expenses_created_at", ["created_at"])
        batch_op.create_index("ix_daily_expenses_category", ["category"])
        batch_op.create_index("ix_daily_expenses_payment_method", ["payment_method"])

    # Create daily_income table
    op.create_table(
        "daily_income",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BDT"),
        sa.Column("description_raw", sa.String(500), nullable=False),
        sa.Column("description_normalized", sa.String(500), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("tags", JSON, nullable=True),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("ai_status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("enriched_at", sa.DateTime, nullable=True),
    )

    with op.batch_alter_table("daily_income") as batch_op:
        batch_op.create_index("ix_daily_income_transaction_date", ["transaction_date"])
        batch_op.create_index("ix_daily_income_ai_status", ["ai_status"])
        batch_op.create_index("ix_daily_income_created_at", ["created_at"])
        batch_op.create_index("ix_daily_income_source_type", ["source_type"])


def downgrade() -> None:
    op.drop_table("daily_income")
    op.drop_table("daily_expenses")
