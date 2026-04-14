"""Add insights and budgets tables

Revision ID: 003
Revises: 002
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "insights",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("insight_type", sa.String(50), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("period_from", sa.Date(), nullable=True),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("data_snapshot", JSON(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_insights_insight_type", "insights", ["insight_type"])
    op.create_index("ix_insights_period_from", "insights", ["period_from"])
    op.create_index("ix_insights_period_to", "insights", ["period_to"])
    op.create_index("ix_insights_account_id", "insights", ["account_id"])

    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("subcategory", sa.String(100), nullable=True),
        sa.Column("monthly_limit", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BDT"),
        sa.Column("alert_at_pct", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category", "account_id", name="uq_budget_category_account"),
    )
    op.create_index("ix_budgets_category", "budgets", ["category"])
    op.create_index("ix_budgets_account_id", "budgets", ["account_id"])


def downgrade() -> None:
    op.drop_table("budgets")
    op.drop_table("insights")
