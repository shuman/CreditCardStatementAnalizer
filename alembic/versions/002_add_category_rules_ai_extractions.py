"""Add category_rules and ai_extractions tables

Revision ID: 002
Revises: 001
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "category_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("merchant_pattern", sa.String(200), nullable=False),
        sa.Column("normalized_merchant", sa.String(200), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("subcategory", sa.String(100), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="builtin"),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=False, server_default="0.80"),
        sa.Column("match_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_matched_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_merchant", "source", name="uq_rule_merchant_source"),
    )
    op.create_index("ix_category_rules_merchant_pattern", "category_rules", ["merchant_pattern"])
    op.create_index("ix_category_rules_normalized_merchant", "category_rules", ["normalized_merchant"])
    op.create_index("ix_category_rules_category", "category_rules", ["category"])

    op.create_table(
        "ai_extractions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=False, server_default="claude-sonnet-4-5"),
        sa.Column("pages_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pages_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(8, 6), nullable=True),
        sa.Column("extraction_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("issues_flagged", JSON(), nullable=True),
        sa.Column("raw_response", JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_extractions_statement_id", "ai_extractions", ["statement_id"])


def downgrade() -> None:
    op.drop_table("ai_extractions")
    op.drop_table("category_rules")
