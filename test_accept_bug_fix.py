#!/usr/bin/env python3
"""
Test that accepted expenses are removed from the review list.
Demonstrates the bug fix for expenses still showing after accept.
"""
import asyncio
from datetime import date
from decimal import Decimal
from app.database import AsyncSessionLocal
from app.services.daily_expense_service import DailyExpenseService

async def test_accept_removes_from_review():
    """Test that accepting an expense removes it from review list."""
    print("🔧 Testing Accept Bug Fix\n")

    async with AsyncSessionLocal() as db:
        service = DailyExpenseService(db)

        # Step 1: Create and process an expense
        print("📝 Step 1: Create draft expense")
        expense = await service.save_draft_expense(
            amount=Decimal("200.00"),
            description="lunch at kfc",
            transaction_date=date.today(),
            payment_method="cash"
        )
        print(f"  ✅ Created expense #{expense.id}: {expense.description_raw}")
        print(f"  📊 Status: {expense.ai_status}, Needs Review: {expense.needs_review}")

        # Step 2: Mark for processing and categorize
        print("\n🤖 Step 2: Process with AI (simulated)")
        await service.mark_for_processing([expense.id])

        # Simulate AI categorization by manual override
        await service.apply_user_override(
            expense_id=expense.id,
            category="Food & Dining",
            subcategory="Fast Food"
        )

        await db.refresh(expense)
        print(f"  ✅ Categorized: {expense.category} > {expense.subcategory}")
        print(f"  📊 Status: {expense.ai_status}, Needs Review: {expense.needs_review}")

        # Step 3: Check review list BEFORE accept
        print("\n👁️  Step 3: Check review list BEFORE accepting")
        review_expenses_before = await service.get_expenses(status="processed", needs_review=True)
        print(f"  📋 Found {len(review_expenses_before)} expense(s) needing review")
        print(f"  ✅ Expense #{expense.id} is in review list: {expense.id in [e.id for e in review_expenses_before]}")

        # Step 4: Accept the expense (user clicks "Accept & Finalize")
        print("\n✅ Step 4: User accepts the expense")
        accepted = await service.apply_user_override(
            expense_id=expense.id,
            category=expense.category,  # Keep same category
            subcategory=expense.subcategory
        )
        print(f"  ✅ Accepted expense #{accepted.id}")
        print(f"  📊 Status: {accepted.ai_status}, Needs Review: {accepted.needs_review}")

        # Step 5: Check review list AFTER accept
        print("\n👁️  Step 5: Check review list AFTER accepting")
        review_expenses_after = await service.get_expenses(status="processed", needs_review=True)
        print(f"  📋 Found {len(review_expenses_after)} expense(s) needing review")
        expense_still_in_list = accepted.id in [e.id for e in review_expenses_after]
        print(f"  ❌ Expense #{accepted.id} still in review list: {expense_still_in_list}")

        # Verify the fix worked
        print("\n🎯 Result:")
        if not expense_still_in_list:
            print("  ✅ BUG FIXED! Accepted expense removed from review list")
        else:
            print("  ❌ BUG STILL EXISTS! Accepted expense still showing")

        # Show the actual values
        print(f"\n📊 Final expense state:")
        print(f"  - ai_status: {accepted.ai_status}")
        print(f"  - needs_review: {accepted.needs_review}")
        print(f"  - category: {accepted.category}")
        print(f"  - Query filter: status='processed' AND needs_review=True")
        print(f"  - Matches filter: {accepted.ai_status == 'processed' and accepted.needs_review == True}")

        # Cleanup
        await service.delete_expense(expense.id)
        print("\n🧹 Cleanup: Test expense deleted")

if __name__ == "__main__":
    asyncio.run(test_accept_removes_from_review())
