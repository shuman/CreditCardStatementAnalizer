"""Add users table and user_id to all tables for multi-tenant support

Revision ID: 010
Revises: 009
Create Date: 2026-04-17

Multi-tenant refactoring: Creates users table and adds user_id foreign key
to all data tables. Includes data migration to assign existing data to
jobaer.shuman@gmail.com user.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON
from datetime import datetime
import uuid

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""

    # =========================================================================
    # Step 1: Create users table
    # =========================================================================
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(36), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime, nullable=True),
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.create_index("ix_users_uuid", ["uuid"])
        batch_op.create_index("ix_users_email", ["email"])

    # =========================================================================
    # Step 2: Insert default user (jobaer.shuman@gmail.com)
    # =========================================================================
    # Password is hashed version of "changeme123" (CHANGE THIS IN PRODUCTION!)
    # To generate: from passlib.context import CryptContext; CryptContext(schemes=["bcrypt"]).hash("your_password")

    # Using bcrypt hash for password "changeme123"
    default_password_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/lewKOjQvHmr/8X5bS"

    op.execute(
        f"""
        INSERT INTO users (uuid, email, hashed_password, full_name, is_active, is_admin, created_at, updated_at)
        VALUES (
            '{uuid.uuid4()}',
            'jobaer.shuman@gmail.com',
            '{default_password_hash}',
            'Jobaer Shuman',
            1,
            1,
            '{datetime.utcnow()}',
            '{datetime.utcnow()}'
        )
        """
    )

    # =========================================================================
    # Step 3: Add user_id column to all tables (nullable initially)
    # =========================================================================

    tables_to_update = [
        "financial_institutions",
        "accounts",
        "statements",
        "transactions",
        "fees",
        "interest_charges",
        "payments",
        "rewards_summary",
        "category_summary",
        "category_rules",
        "ai_extractions",
        "insights",
        "budgets",
        "daily_expenses",
        "daily_income",
        "liability_templates",
        "monthly_records",
        "monthly_liabilities",
    ]

    for table_name in tables_to_update:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.Integer, nullable=True))
            batch_op.create_index(f"ix_{table_name}_user_id", ["user_id"])

    # =========================================================================
    # Step 4: Convert advisor_reports.user_id from String to Integer FK
    # =========================================================================
    # advisor_reports already has user_id as String(100), we need to convert it

    # Create temporary column
    with op.batch_alter_table("advisor_reports") as batch_op:
        batch_op.add_column(sa.Column("user_id_new", sa.Integer, nullable=True))

    # Drop old user_id column and rename new one
    with op.batch_alter_table("advisor_reports") as batch_op:
        batch_op.drop_index("ix_advisor_reports_user_id")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("advisor_reports") as batch_op:
        batch_op.alter_column("user_id_new", new_column_name="user_id")
        batch_op.create_index("ix_advisor_reports_user_id", ["user_id"])

    # =========================================================================
    # Step 5: Backfill all existing data with jobaer.shuman@gmail.com user_id
    # =========================================================================

    # Get the user_id for jobaer.shuman@gmail.com (should be 1 since it's first insert)
    op.execute(
        """
        UPDATE financial_institutions
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE accounts
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE statements
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE transactions
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE fees
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE interest_charges
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE payments
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE rewards_summary
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE category_summary
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE category_rules
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE ai_extractions
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE insights
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE budgets
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE advisor_reports
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE daily_expenses
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE daily_income
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE liability_templates
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE monthly_records
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE monthly_liabilities
        SET user_id = (SELECT id FROM users WHERE email = 'jobaer.shuman@gmail.com' LIMIT 1)
        WHERE user_id IS NULL
        """
    )

    # =========================================================================
    # Step 6: Make user_id NOT NULL and add foreign key constraints
    # =========================================================================

    all_tables = tables_to_update + ["advisor_reports"]

    for table_name in all_tables:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column("user_id", nullable=False)
            batch_op.create_foreign_key(
                f"fk_{table_name}_user_id",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE"
            )


def downgrade() -> None:
    """Downgrade schema."""

    tables_with_user_id = [
        "financial_institutions",
        "accounts",
        "statements",
        "transactions",
        "fees",
        "interest_charges",
        "payments",
        "rewards_summary",
        "category_summary",
        "category_rules",
        "ai_extractions",
        "insights",
        "budgets",
        "advisor_reports",
        "daily_expenses",
        "daily_income",
        "liability_templates",
        "monthly_records",
        "monthly_liabilities",
    ]

    # Drop foreign key constraints and user_id columns
    for table_name in tables_with_user_id:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(f"fk_{table_name}_user_id", type_="foreignkey")
            batch_op.drop_index(f"ix_{table_name}_user_id")
            batch_op.drop_column("user_id")

    # Recreate old advisor_reports.user_id as String
    with op.batch_alter_table("advisor_reports") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(100), nullable=True))
        batch_op.create_index("ix_advisor_reports_user_id", ["user_id"])

    # Drop users table
    op.drop_table("users")
