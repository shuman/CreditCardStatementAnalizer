"""Add income/savings fields to advisor_reports for holistic financial advice

Revision ID: 008
Revises: 007
Create Date: 2026-04-16

Adds 4 new columns to advisor_reports:
  - income_insights: JSON array of AI-generated income observations
  - income_tips: JSON array of actionable income growth tips with potential BDT amounts
  - savings_analysis: JSON object with savings rate, target, gap, and assessment
  - motivation: Text motivational message for income growth and financial progress
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("advisor_reports") as batch_op:
        batch_op.add_column(sa.Column("income_insights", JSON, nullable=True))
        batch_op.add_column(sa.Column("income_tips", JSON, nullable=True))
        batch_op.add_column(sa.Column("savings_analysis", JSON, nullable=True))
        batch_op.add_column(sa.Column("motivation", sa.Text, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("advisor_reports") as batch_op:
        batch_op.drop_column("motivation")
        batch_op.drop_column("savings_analysis")
        batch_op.drop_column("income_tips")
        batch_op.drop_column("income_insights")
