"""Add file_hash column to ai_extractions for extraction caching

Revision ID: 005
Revises: 004
Create Date: 2026-04-14

Adds ai_extractions.file_hash (SHA-256 of raw PDF bytes).
This is the cache key — a non-null raw_response + matching file_hash
means the Claude API result is cached and can be returned without
a new API call.
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ai_extractions") as batch_op:
        batch_op.add_column(
            sa.Column("file_hash", sa.String(64), nullable=True)
        )
        batch_op.create_index("ix_ai_extractions_file_hash", ["file_hash"])


def downgrade() -> None:
    with op.batch_alter_table("ai_extractions") as batch_op:
        batch_op.drop_index("ix_ai_extractions_file_hash")
        batch_op.drop_column("file_hash")
