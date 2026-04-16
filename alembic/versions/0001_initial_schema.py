"""Initial schema — all tables for PostgreSQL

Revision ID: 0001_initial
Revises: 
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(150), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("google_id", sa.String(150), nullable=True),
        sa.Column("profile_picture", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("google_id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── financial_institutions ───────────────────────────────────────────────
    op.create_table(
        "financial_institutions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("short_name", sa.String(50), nullable=True),
        sa.Column("country", sa.String(3), nullable=False, server_default="BGD"),
        sa.Column("swift_code", sa.String(11), nullable=True),
        sa.Column("routing_number", sa.String(20), nullable=True),
        sa.Column("website", sa.String(200), nullable=True),
        sa.Column("logo_filename", sa.String(100), nullable=True),
        sa.Column("primary_color", sa.String(7), nullable=True),
        sa.Column("statement_format", sa.String(50), nullable=True),
        sa.Column("has_sidebar", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sidebar_crop_right_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_financial_institutions_name", "financial_institutions", ["name"])
    op.create_index("ix_financial_institutions_short_name", "financial_institutions", ["short_name"])
    op.create_index("ix_financial_institutions_country", "financial_institutions", ["country"])

    # ── accounts ─────────────────────────────────────────────────────────────
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("institution_id", sa.Integer(), nullable=True),
        sa.Column("account_type", sa.String(20), nullable=False, server_default="credit_card"),
        sa.Column("account_number_masked", sa.String(30), nullable=False),
        sa.Column("account_number_hash", sa.String(64), nullable=True),
        sa.Column("cardholder_name", sa.String(200), nullable=True),
        sa.Column("account_nickname", sa.String(100), nullable=True),
        sa.Column("card_network", sa.String(20), nullable=True),
        sa.Column("card_tier", sa.String(20), nullable=True),
        sa.Column("parent_account_id", sa.Integer(), nullable=True),
        sa.Column("billing_currency", sa.String(3), nullable=False, server_default="BDT"),
        sa.Column("credit_limit", sa.Numeric(15, 2), nullable=True),
        sa.Column("cash_limit", sa.Numeric(15, 2), nullable=True),
        sa.Column("reward_program_name", sa.String(100), nullable=True),
        sa.Column("reward_type", sa.String(20), nullable=True),
        sa.Column("reward_expiry_months", sa.Integer(), nullable=True),
        sa.Column("points_value_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("color_hex", sa.String(7), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["institution_id"], ["financial_institutions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_number_hash"),
    )
    op.create_index("ix_accounts_institution_id", "accounts", ["institution_id"])
    op.create_index("ix_accounts_account_number_hash", "accounts", ["account_number_hash"])
    op.create_index("ix_accounts_parent_account_id", "accounts", ["parent_account_id"])
    op.create_index("ix_accounts_user_id", "accounts", ["user_id"])

    # ── category_rules ───────────────────────────────────────────────────────
    op.create_table(
        "category_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("merchant_pattern", sa.String(200), nullable=False),
        sa.Column("normalized_merchant", sa.String(200), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("subcategory", sa.String(100), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="builtin"),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=False, server_default="0.80"),
        sa.Column("match_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_matched_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_merchant", "source", name="uq_rule_merchant_source"),
    )
    op.create_index("ix_category_rules_merchant_pattern", "category_rules", ["merchant_pattern"])
    op.create_index("ix_category_rules_normalized_merchant", "category_rules", ["normalized_merchant"])
    op.create_index("ix_category_rules_category", "category_rules", ["category"])
    op.create_index("ix_category_rules_user_id", "category_rules", ["user_id"])

    # ── statements ───────────────────────────────────────────────────────────
    op.create_table(
        "statements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("statement_date", sa.Date(), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("minimum_payment", sa.Numeric(15, 2), nullable=True),
        sa.Column("previous_balance", sa.Numeric(15, 2), nullable=True),
        sa.Column("opening_balance", sa.Numeric(15, 2), nullable=True),
        sa.Column("closing_balance", sa.Numeric(15, 2), nullable=True),
        sa.Column("available_credit", sa.Numeric(15, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BDT"),
        sa.Column("bank_name", sa.String(200), nullable=True),
        sa.Column("account_number", sa.String(50), nullable=True),
        sa.Column("cardholder_name", sa.String(200), nullable=True),
        sa.Column("transaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extraction_method", sa.String(30), nullable=True),
        sa.Column("ai_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("statement_type", sa.String(30), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="processed"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_statements_statement_date", "statements", ["statement_date"])
    op.create_index("ix_statements_account_id", "statements", ["account_id"])
    op.create_index("ix_statements_user_id", "statements", ["user_id"])

    # ── ai_extractions ───────────────────────────────────────────────────────
    op.create_table(
        "ai_extractions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=False, server_default="claude-haiku-4-5"),
        sa.Column("pages_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pages_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(8, 6), nullable=True),
        sa.Column("extraction_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("issues_flagged", sa.JSON(), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.Column("file_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_extractions_statement_id", "ai_extractions", ["statement_id"])
    op.create_index("ix_ai_extractions_file_hash", "ai_extractions", ["file_hash"])

    # ── transactions ─────────────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        sa.Column("posting_date", sa.Date(), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("merchant_name", sa.String(300), nullable=True),
        sa.Column("merchant_normalized", sa.String(200), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("billing_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("billing_currency", sa.String(3), nullable=True),
        sa.Column("original_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("original_currency", sa.String(3), nullable=True),
        sa.Column("fx_rate_applied", sa.Numeric(10, 6), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BDT"),
        sa.Column("transaction_type", sa.String(20), nullable=False, server_default="debit"),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("subcategory", sa.String(100), nullable=True),
        sa.Column("category_ai", sa.String(100), nullable=True),
        sa.Column("subcategory_ai", sa.String(100), nullable=True),
        sa.Column("category_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("category_source", sa.String(20), nullable=True),
        sa.Column("category_rule_id", sa.Integer(), nullable=True),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_international", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("points_earned", sa.Integer(), nullable=True),
        sa.Column("cashback_earned", sa.Numeric(10, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_rule_id"], ["category_rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_statement_id", "transactions", ["statement_id"])
    op.create_index("ix_transactions_transaction_date", "transactions", ["transaction_date"])
    op.create_index("ix_transactions_merchant_normalized", "transactions", ["merchant_normalized"])
    op.create_index("ix_transactions_category", "transactions", ["category"])
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])
    op.create_index("ix_transactions_category_ai", "transactions", ["category_ai"])

    # ── fees ─────────────────────────────────────────────────────────────────
    op.create_table(
        "fees",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("fee_type", sa.String(100), nullable=False),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BDT"),
        sa.Column("fee_date", sa.Date(), nullable=True),
        sa.Column("is_waived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fees_statement_id", "fees", ["statement_id"])

    # ── interest_charges ─────────────────────────────────────────────────────
    op.create_table(
        "interest_charges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("charge_type", sa.String(100), nullable=False),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BDT"),
        sa.Column("rate_applied", sa.Numeric(6, 4), nullable=True),
        sa.Column("charge_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interest_charges_statement_id", "interest_charges", ["statement_id"])

    # ── rewards_summary ──────────────────────────────────────────────────────
    op.create_table(
        "rewards_summary",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("reward_type", sa.String(50), nullable=False),
        sa.Column("points_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points_redeemed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points_balance", sa.Integer(), nullable=True),
        sa.Column("cashback_earned", sa.Numeric(10, 2), nullable=True),
        sa.Column("reward_program_name", sa.String(100), nullable=True),
        sa.Column("accelerated_tiers", sa.JSON(), nullable=True),
        sa.Column("estimated_value_bdt", sa.Numeric(15, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rewards_summary_statement_id", "rewards_summary", ["statement_id"])

    # ── category_summary ─────────────────────────────────────────────────────
    op.create_table(
        "category_summary",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("category_name", sa.String(100), nullable=False),
        sa.Column("subcategory_name", sa.String(100), nullable=True),
        sa.Column("transaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BDT"),
        sa.Column("percentage_of_total", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_category_summary_statement_id", "category_summary", ["statement_id"])

    # ── payments ─────────────────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BDT"),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_statement_id", "payments", ["statement_id"])

    # ── insights ─────────────────────────────────────────────────────────────
    op.create_table(
        "insights",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("insight_type", sa.String(50), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("period_from", sa.Date(), nullable=True),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("data_snapshot", sa.JSON(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_insights_insight_type", "insights", ["insight_type"])
    op.create_index("ix_insights_period_from", "insights", ["period_from"])
    op.create_index("ix_insights_period_to", "insights", ["period_to"])
    op.create_index("ix_insights_account_id", "insights", ["account_id"])
    op.create_index("ix_insights_user_id", "insights", ["user_id"])

    # ── budgets ──────────────────────────────────────────────────────────────
    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("subcategory", sa.String(100), nullable=True),
        sa.Column("monthly_limit", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BDT"),
        sa.Column("alert_at_pct", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category", "account_id", name="uq_budget_category_account"),
    )
    op.create_index("ix_budgets_category", "budgets", ["category"])
    op.create_index("ix_budgets_account_id", "budgets", ["account_id"])
    op.create_index("ix_budgets_user_id", "budgets", ["user_id"])

    # ── advisor_reports ──────────────────────────────────────────────────────
    op.create_table(
        "advisor_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("period_months", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("score_breakdown", sa.JSON(), nullable=True),
        sa.Column("total_spent", sa.Numeric(15, 2), nullable=True),
        sa.Column("insights", sa.JSON(), nullable=True),
        sa.Column("mistakes", sa.JSON(), nullable=True),
        sa.Column("recommendations", sa.JSON(), nullable=True),
        sa.Column("risks", sa.JSON(), nullable=True),
        sa.Column("total_income", sa.Numeric(15, 2), nullable=True),
        sa.Column("projection", sa.JSON(), nullable=True),
        sa.Column("signals", sa.JSON(), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_advisor_reports_report_date", "advisor_reports", ["report_date"])
    op.create_index("ix_advisor_reports_account_id", "advisor_reports", ["account_id"])

    # ── daily_expenses ───────────────────────────────────────────────────────
    op.create_table(
        "daily_expenses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BDT"),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("subcategory", sa.String(100), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("merchant_name", sa.String(300), nullable=True),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("enriched_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_daily_expenses_transaction_date", "daily_expenses", ["transaction_date"])
    op.create_index("ix_daily_expenses_category", "daily_expenses", ["category"])

    # ── daily_income ─────────────────────────────────────────────────────────
    op.create_table(
        "daily_income",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BDT"),
        sa.Column("source_type", sa.String(100), nullable=True),
        sa.Column("source_name", sa.String(300), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("enriched_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_daily_income_transaction_date", "daily_income", ["transaction_date"])
    op.create_index("ix_daily_income_source_type", "daily_income", ["source_type"])

    # ── liability_templates ──────────────────────────────────────────────────
    op.create_table(
        "liability_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("default_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BDT"),
        sa.Column("frequency", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── monthly_records ──────────────────────────────────────────────────────
    op.create_table(
        "monthly_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("year_month", sa.String(7), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year_month"),
    )

    # ── monthly_liabilities ──────────────────────────────────────────────────
    op.create_table(
        "monthly_liabilities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BDT"),
        sa.Column("due_date", sa.String(10), nullable=True),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("paid_date", sa.String(10), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["record_id"], ["monthly_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["liability_templates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_monthly_liabilities_record_id", "monthly_liabilities", ["record_id"])


def downgrade() -> None:
    op.drop_table("monthly_liabilities")
    op.drop_table("monthly_records")
    op.drop_table("liability_templates")
    op.drop_table("daily_income")
    op.drop_table("daily_expenses")
    op.drop_table("advisor_reports")
    op.drop_table("budgets")
    op.drop_table("insights")
    op.drop_table("payments")
    op.drop_table("category_summary")
    op.drop_table("rewards_summary")
    op.drop_table("interest_charges")
    op.drop_table("fees")
    op.drop_table("transactions")
    op.drop_table("ai_extractions")
    op.drop_table("statements")
    op.drop_table("category_rules")
    op.drop_table("accounts")
    op.drop_table("financial_institutions")
    op.drop_table("users")
