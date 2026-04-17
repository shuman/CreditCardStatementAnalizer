"""
Backfill existing data to default user (jobaer.shuman@gmail.com).
This script assigns all existing financial data with null user_id to the default user.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.database import async_session_maker
from app.models import User


async def backfill_user_data():
    """Backfill all existing data to default user."""

    async with async_session_maker() as db:
        # Get or create default user
        result = await db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": "jobaer.shuman@gmail.com"}
        )
        user_row = result.first()

        if not user_row:
            print("❌ Default user jobaer.shuman@gmail.com not found!")
            print("Please create this user first via signup.")
            return False

        user_id = user_row[0]
        print(f"✅ Found default user with ID: {user_id}")

        # List of tables to update
        tables_to_update = [
            "financial_institutions",
            "accounts",
            "statements",
            "transactions",
            "fees",
            "insights",
            "budgets",
            "category_rules",
            "ai_extractions",
            "advisor_reports",
            "daily_transactions",
            "daily_income_transactions",
            "monthly_liabilities",
            "liability_payment_history",
        ]

        total_updated = 0

        for table in tables_to_update:
            # Check if table has user_id column
            try:
                result = await db.execute(
                    text(f"UPDATE {table} SET user_id = :user_id WHERE user_id IS NULL")
                    , {"user_id": user_id}
                )
                rows_updated = result.rowcount

                if rows_updated > 0:
                    print(f"  📝 Updated {rows_updated} rows in {table}")
                    total_updated += rows_updated
                else:
                    print(f"  ✓ {table} - no rows to update")

            except Exception as e:
                print(f"  ⚠️  {table} - {str(e)}")

        await db.commit()

        print(f"\n🎉 Backfill complete! Updated {total_updated} total rows.")
        return True


if __name__ == "__main__":
    print("=" * 60)
    print("Backfilling existing data to default user")
    print("=" * 60)
    print()

    success = asyncio.run(backfill_user_data())

    if success:
        print("\n✅ All data successfully assigned to default user!")
    else:
        print("\n❌ Backfill failed. Please check the errors above.")
        sys.exit(1)
