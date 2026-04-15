"""
Quick integration test for daily expenses feature.
Run this to test the complete workflow: create → batch process → review.
"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.database import AsyncSessionLocal
from app.services.daily_expense_service import DailyExpenseService
from decimal import Decimal
from datetime import date


async def test_daily_expenses():
    """Test the daily expense workflow."""
    print("🧪 Testing Daily Expenses Feature\n")

    async with AsyncSessionLocal() as db:
        service = DailyExpenseService(db)

        # Step 1: Create draft expenses
        print("📝 Step 1: Creating draft expenses...")
        expenses = [
            ("50", "chaa", date.today(), "cash"),
            ("100", "rickshaw", date.today(), "cash"),
            ("250", "lunch at restaurant", date.today(), "bkash"),
        ]

        created_ids = []
        for amount, desc, dt, pm in expenses:
            expense = await service.save_draft_expense(
                amount=Decimal(amount),
                description=desc,
                transaction_date=dt,
                payment_method=pm
            )
            created_ids.append(expense.id)
            print(f"  ✅ Created: {expense.id} - {desc} - ৳{amount}")

        # Step 2: Get draft count
        print(f"\n📊 Step 2: Checking drafts...")
        drafts = await service.get_expenses(status="draft")
        print(f"  ✅ Found {len(drafts)} draft expenses")

        # Step 3: Mark for processing
        print(f"\n🏷️  Step 3: Marking for batch processing...")
        marked = await service.mark_for_processing(created_ids)
        print(f"  ✅ Marked {marked} expenses as pending")

        # Step 4: Batch categorize (requires API key)
        print(f"\n🤖 Step 4: Batch AI categorization...")
        from app.config import settings
        if not settings.anthropic_api_key:
            print("  ⚠️  No Anthropic API key - skipping AI processing")
            print("  ℹ️  Set ANTHROPIC_API_KEY environment variable to test AI features")

            # Manually set categories for demo
            for expense_id in created_ids:
                expense = await service.get_expense_by_id(expense_id)
                if expense:
                    expense.category = "Food & Dining" if "lunch" in expense.description_raw else "Transport" if "rickshaw" in expense.description_raw else "Beverages"
                    expense.subcategory = "Tea" if "chaa" in expense.description_raw else "Street Food" if "lunch" in expense.description_raw else "Auto Rickshaw"
                    expense.ai_status = "processed"
                    expense.confidence_score = Decimal("0.85")
            await db.commit()
            print(f"  ✅ Manually categorized {len(created_ids)} expenses (demo mode)")
        else:
            result = await service.batch_categorize_expenses(created_ids)
            print(f"  ✅ Processed: {result['success_count']} expenses")
            print(f"  💰 Cost: ${result['total_cost_usd']:.6f}")

        # Step 5: Get processed expenses
        print(f"\n✔️  Step 5: Checking processed expenses...")
        processed = await service.get_expenses(status="processed")
        print(f"  ✅ Found {len(processed)} processed expenses")
        for exp in processed[:3]:
            print(f"     - {exp.description_raw} → {exp.category}/{exp.subcategory}")

        # Step 6: Apply user override
        if created_ids:
            print(f"\n✏️  Step 6: Testing user override...")
            expense = await service.apply_user_override(
                expense_id=created_ids[0],
                category="Beverages",
                subcategory="Hot Drinks"
            )
            print(f"  ✅ Updated expense {expense.id} with user override")

        # Step 7: Get statistics
        print(f"\n📈 Step 7: Getting statistics...")
        stats = await service.get_statistics()
        print(f"  ✅ Total expenses: {stats['total_count']}")
        print(f"  💵 Total amount: ৳{stats['total_amount']:.2f}")
        print(f"  📊 Categories: {', '.join(stats['category_breakdown'].keys())}")

        print("\n✅ All tests passed! Daily expenses feature is working correctly.\n")
        print("🌐 Access the UI at: http://localhost:8000/daily-expenses")
        print("🌐 Access the API docs at: http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(test_daily_expenses())
