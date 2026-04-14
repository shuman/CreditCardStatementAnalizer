"""Add advisor_reports table for monthly AI diagnosis caching

Revision ID: 006
Revises: 005
Create Date: 2026-04-15

Stores monthly AI-generated financial diagnosis reports.
One report per month per account (UniqueConstraint on year, month, account_id).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "advisor_reports",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(100), nullable=True),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("account_id", sa.Integer, nullable=True),
        sa.Column("diagnosis", sa.Text, nullable=True),
        sa.Column("score", sa.Integer, nullable=True),
        sa.Column("score_breakdown", JSON, nullable=True),
        sa.Column("score_prev", sa.Integer, nullable=True),
        sa.Column("score_delta", sa.Integer, nullable=True),
        sa.Column("insights", JSON, nullable=True),
        sa.Column("mistakes", JSON, nullable=True),
        sa.Column("recommendations", JSON, nullable=True),
        sa.Column("risks", JSON, nullable=True),
        sa.Column("personality_type", sa.String(100), nullable=True),
        sa.Column("personality_detail", sa.Text, nullable=True),
        sa.Column("top_recommendation", sa.Text, nullable=True),
        sa.Column("projection", JSON, nullable=True),
        sa.Column("advisor_notes", sa.Text, nullable=True),
        sa.Column("signals", JSON, nullable=True),
        sa.Column("raw_ai_output", sa.Text, nullable=True),
        sa.Column("ai_model", sa.String(100), nullable=True),
        sa.Column("ai_input_tokens", sa.Integer, nullable=True),
        sa.Column("ai_output_tokens", sa.Integer, nullable=True),
        sa.Column("ai_cost_usd", sa.Numeric(8, 6), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("year", "month", "account_id", name="uq_advisor_report_month_account"),
    )

    with op.batch_alter_table("advisor_reports") as batch_op:
        batch_op.create_index("ix_advisor_reports_user_id", ["user_id"])
        batch_op.create_index("ix_advisor_reports_year", ["year"])
        batch_op.create_index("ix_advisor_reports_month", ["month"])
        batch_op.create_index("ix_advisor_reports_account_id", ["account_id"])


def downgrade() -> None:
    op.drop_table("advisor_reports")
