"""
Report Engine — generates data for the 6 core dashboard reports.
All queries run on existing Transaction, Statement, CategorySummary, and Budget tables.
"""
import calendar
import logging
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction, Statement, Budget

logger = logging.getLogger(__name__)


class ReportEngine:
    """Generates data dicts for each dashboard report card."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _period_bounds(self, year: int, month: int):
        """Return (period_from, period_to) for a given year/month."""
        period_from = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        period_to = date(year, month, last_day)
        return period_from, period_to

    async def _get_debit_transactions(
        self,
        period_from: date,
        period_to: date,
        account_id: Optional[int] = None,
    ) -> List[Transaction]:
        """Fetch all debit transactions for a period."""
        query = select(Transaction).where(
            Transaction.transaction_date.between(period_from, period_to),
            Transaction.debit_credit == "D",
        )
        if account_id:
            query = query.where(Transaction.account_id == account_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def _category_distribution(
        self,
        txns: List[Transaction],
    ) -> Dict[str, float]:
        """Return {category: total_amount} from a list of transactions."""
        dist: Dict[str, float] = {}
        for t in txns:
            cat = t.category_ai or t.merchant_category or "Other"
            amount = float(t.billing_amount or t.amount or 0)
            dist[cat] = dist.get(cat, 0) + amount
        return dist

    async def _monthly_totals(
        self,
        months_back: int,
        account_id: Optional[int] = None,
        end_year: Optional[int] = None,
        end_month: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return [{month: 'YYYY-MM', total: N}, ...] for the last N months."""
        today = date.today()
        end_year = end_year or today.year
        end_month = end_month or today.month

        results: List[Dict[str, Any]] = []
        for i in range(months_back - 1, -1, -1):
            # Walk backwards from end_month
            m = end_month - i
            y = end_year
            while m <= 0:
                m += 12
                y -= 1
            period_from, period_to = self._period_bounds(y, m)
            query = select(
                func.coalesce(func.sum(Transaction.billing_amount), 0),
            ).where(
                Transaction.transaction_date.between(period_from, period_to),
                Transaction.debit_credit == "D",
            )
            if account_id:
                query = query.where(Transaction.account_id == account_id)
            result = await self.db.execute(query)
            total = float(result.scalar() or 0)
            results.append({"month": f"{y}-{m:02d}", "total": round(total, 2)})
        return results

    # ------------------------------------------------------------------
    # Report #1: Monthly Spending Breakdown
    # ------------------------------------------------------------------

    async def monthly_spending_breakdown(
        self,
        year: int,
        month: int,
        account_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        period_from, period_to = self._period_bounds(year, month)

        # Current month
        txns = await self._get_debit_transactions(period_from, period_to, account_id)
        by_cat = await self._category_distribution(txns)
        total = sum(by_cat.values())

        # Previous month for trend arrows
        prev_month_date = period_from - timedelta(days=1)
        prev_from, prev_to = self._period_bounds(
            prev_month_date.year, prev_month_date.month
        )
        prev_txns = await self._get_debit_transactions(prev_from, prev_to, account_id)
        prev_by_cat = await self._category_distribution(prev_txns)
        prev_total = sum(prev_by_cat.values())

        categories = []
        for cat, amount in sorted(by_cat.items(), key=lambda x: x[1], reverse=True):
            pct = round(amount / total * 100, 1) if total else 0
            prev_amount = prev_by_cat.get(cat, 0)
            change_pct = (
                round((amount - prev_amount) / prev_amount * 100, 1)
                if prev_amount > 0
                else 0
            )
            categories.append({
                "name": cat,
                "amount": round(amount, 2),
                "pct": pct,
                "change_pct": change_pct,
            })

        top_cat = categories[0]["name"] if categories else "N/A"

        return {
            "categories": categories,
            "total": round(total, 2),
            "prev_total": round(prev_total, 2),
            "top_category": top_cat,
        }

    # ------------------------------------------------------------------
    # Report #2: Merchant Concentration
    # ------------------------------------------------------------------

    async def merchant_concentration(
        self,
        year: int,
        month: int,
        account_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        period_from, period_to = self._period_bounds(year, month)
        txns = await self._get_debit_transactions(period_from, period_to, account_id)

        merchant_data: Dict[str, Dict[str, Any]] = {}
        total = 0.0
        for t in txns:
            name = t.merchant_name or (t.description_raw or "")[:30]
            amount = float(t.billing_amount or t.amount or 0)
            total += amount
            if name not in merchant_data:
                merchant_data[name] = {"amount": 0.0, "txns": 0}
            merchant_data[name]["amount"] += amount
            merchant_data[name]["txns"] += 1

        # Sort by amount descending, take top 10
        sorted_merchants = sorted(
            merchant_data.items(), key=lambda x: x[1]["amount"], reverse=True
        )[:10]

        merchants = []
        for name, data in sorted_merchants:
            pct = round(data["amount"] / total * 100, 1) if total else 0
            merchants.append({
                "name": name,
                "amount": round(data["amount"], 2),
                "pct": pct,
                "txns": data["txns"],
            })

        top3_amount = sum(m["amount"] for m in merchants[:3])
        top3_pct = round(top3_amount / total * 100, 1) if total else 0
        total_merchants = len(merchant_data)

        return {
            "merchants": merchants,
            "top3_pct": top3_pct,
            "total_merchants": total_merchants,
            "insight": (
                f"Top 3 merchants = {top3_pct}% of total spending"
                if total_merchants > 3
                else "Spending concentrated in few merchants"
            ),
        }

    # ------------------------------------------------------------------
    # Report #7: Subscription Waste
    # ------------------------------------------------------------------

    async def subscription_waste(
        self,
        year: int,
        month: int,
        account_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        period_from, period_to = self._period_bounds(year, month)

        query = select(Transaction).where(
            Transaction.transaction_date.between(period_from, period_to),
            Transaction.debit_credit == "D",
            Transaction.is_recurring == True,
        )
        if account_id:
            query = query.where(Transaction.account_id == account_id)
        result = await self.db.execute(query)
        txns = result.scalars().all()

        subscriptions: Dict[str, Dict[str, float]] = {}
        for t in txns:
            merchant = t.merchant_name or (t.description_raw or "")[:30]
            amount = float(t.billing_amount or t.amount or 0)
            if merchant not in subscriptions:
                subscriptions[merchant] = {"monthly": 0.0, "count": 0}
            subscriptions[merchant]["monthly"] += amount
            subscriptions[merchant]["count"] += 1

        subs_list = []
        total_monthly = 0.0
        for merchant, data in sorted(
            subscriptions.items(), key=lambda x: x[1]["monthly"], reverse=True
        ):
            monthly = round(data["monthly"], 2)
            annual = round(monthly * 12, 2)
            total_monthly += monthly
            subs_list.append({
                "merchant": merchant,
                "monthly": monthly,
                "annual": annual,
            })

        total_annual = round(total_monthly * 12, 2)

        # Detect duplicate services across accounts (same merchant name)
        duplicate_services = []
        merchant_accounts: Dict[str, set] = {}
        for t in txns:
            merchant = t.merchant_name or (t.description_raw or "")[:30]
            if merchant not in merchant_accounts:
                merchant_accounts[merchant] = set()
            if t.account_id:
                merchant_accounts[merchant].add(t.account_id)
        for m, accts in merchant_accounts.items():
            if len(accts) > 1:
                duplicate_services.append(m)

        return {
            "subscriptions": subs_list,
            "total_monthly": round(total_monthly, 2),
            "total_annual": total_annual,
            "duplicate_services": duplicate_services,
        }

    # ------------------------------------------------------------------
    # Report #8: Lifestyle Creep Tracker
    # ------------------------------------------------------------------

    async def lifestyle_creep(
        self,
        year: int,
        month: int,
        account_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        months = await self._monthly_totals(6, account_id, end_year=year, end_month=month)

        if len(months) < 2:
            trend_pct = 0
            trend_direction = "stable"
        else:
            first = months[0]["total"]
            last = months[-1]["total"]
            if first > 0:
                trend_pct = round((last - first) / first * 100, 1)
            else:
                trend_pct = 0
            if trend_pct > 5:
                trend_direction = "increasing"
            elif trend_pct < -5:
                trend_direction = "decreasing"
            else:
                trend_direction = "stable"

        # Find category with biggest increase
        period_from, period_to = self._period_bounds(year, month)
        prev_month_date = period_from - timedelta(days=1)
        prev_from, prev_to = self._period_bounds(
            prev_month_date.year, prev_month_date.month
        )
        curr_txns = await self._get_debit_transactions(period_from, period_to, account_id)
        prev_txns = await self._get_debit_transactions(prev_from, prev_to, account_id)

        curr_cats = await self._category_distribution(curr_txns)
        prev_cats = await self._category_distribution(prev_txns)

        biggest_increase_cat = "N/A"
        biggest_increase_val = 0.0
        for cat, amount in curr_cats.items():
            diff = amount - prev_cats.get(cat, 0)
            if diff > biggest_increase_val:
                biggest_increase_val = diff
                biggest_increase_cat = cat

        return {
            "months": months,
            "trend_pct": trend_pct,
            "trend_direction": trend_direction,
            "biggest_increase_category": biggest_increase_cat,
        }

    # ------------------------------------------------------------------
    # Report #12: Financial Health Score
    # ------------------------------------------------------------------

    async def financial_health_score(
        self,
        year: int,
        month: int,
        account_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        period_from, period_to = self._period_bounds(year, month)

        # 1. Credit Utilization (0-20)
        utilization_score = 10  # default
        stmt_query = select(Statement).where(
            Statement.statement_date.between(period_from, period_to),
        )
        if account_id:
            stmt_query = stmt_query.where(Statement.account_id == account_id)
        stmt_result = await self.db.execute(stmt_query.order_by(Statement.statement_date.desc()))
        stmt = stmt_result.scalars().first()

        if stmt and stmt.credit_utilization_pct is not None:
            util_pct = float(stmt.credit_utilization_pct)
            if util_pct < 30:
                utilization_score = 20
            elif util_pct < 50:
                utilization_score = 15
            elif util_pct < 75:
                utilization_score = 10
            else:
                utilization_score = 5

        # 2. Fee Burden (0-20)
        fee_score = 20
        if stmt and stmt.fees_charged:
            fees = float(stmt.fees_charged)
            purchases = float(stmt.purchases or 0)
            if purchases > 0:
                fee_ratio = fees / purchases * 100
                if fee_ratio > 5:
                    fee_score = 5
                elif fee_ratio > 3:
                    fee_score = 10
                elif fee_ratio > 1:
                    fee_score = 15

        # 3. Budget Adherence (0-20)
        budget_score = 15
        budget_result = await self.db.execute(
            select(Budget).where(Budget.is_active == True)
        )
        budgets = budget_result.scalars().all()
        if budgets:
            txns = await self._get_debit_transactions(period_from, period_to, account_id)
            spending = await self._category_distribution(txns)
            breached = 0
            for b in budgets:
                spent = spending.get(b.category, 0)
                limit = float(b.monthly_limit)
                if limit > 0 and spent > limit:
                    breached += 1
            breach_ratio = breached / len(budgets) if budgets else 0
            if breach_ratio == 0:
                budget_score = 20
            elif breach_ratio < 0.25:
                budget_score = 15
            elif breach_ratio < 0.5:
                budget_score = 10
            else:
                budget_score = 5

        # 4. Recurring Ratio (0-20)
        recurring_score = 15
        txns = await self._get_debit_transactions(period_from, period_to, account_id)
        total_spend = sum(float(t.billing_amount or t.amount or 0) for t in txns)
        recurring_spend = sum(
            float(t.billing_amount or t.amount or 0)
            for t in txns
            if t.is_recurring
        )
        if total_spend > 0:
            recurring_pct = recurring_spend / total_spend * 100
            if recurring_pct < 15:
                recurring_score = 20
            elif recurring_pct < 30:
                recurring_score = 15
            elif recurring_pct < 50:
                recurring_score = 10
            else:
                recurring_score = 5

        # 5. Spending Trend (0-20)
        trend_score = 15
        prev_month_date = period_from - timedelta(days=1)
        prev_from, prev_to = self._period_bounds(
            prev_month_date.year, prev_month_date.month
        )
        prev_txns = await self._get_debit_transactions(prev_from, prev_to, account_id)
        prev_total = sum(float(t.billing_amount or t.amount or 0) for t in prev_txns)
        if prev_total > 0 and total_spend > 0:
            change_pct = (total_spend - prev_total) / prev_total * 100
            if change_pct < -10:
                trend_score = 20
            elif change_pct < 0:
                trend_score = 18
            elif change_pct < 10:
                trend_score = 15
            elif change_pct < 25:
                trend_score = 10
            else:
                trend_score = 5

        factors = [
            {"name": "Credit Utilization", "score": utilization_score, "max": 20},
            {"name": "Fee Burden", "score": fee_score, "max": 20},
            {"name": "Budget Adherence", "score": budget_score, "max": 20},
            {"name": "Recurring Ratio", "score": recurring_score, "max": 20},
            {"name": "Spending Trend", "score": trend_score, "max": 20},
        ]

        score = sum(f["score"] for f in factors)
        if score >= 80:
            grade = "Excellent"
        elif score >= 60:
            grade = "Good"
        elif score >= 40:
            grade = "Fair"
        else:
            grade = "Needs Work"

        return {
            "score": score,
            "max": 100,
            "grade": grade,
            "factors": factors,
        }

    # ------------------------------------------------------------------
    # Report #18: No-Spend Day Tracker
    # ------------------------------------------------------------------

    async def no_spend_day_tracker(
        self,
        year: int,
        month: int,
        account_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        period_from, period_to = self._period_bounds(year, month)
        total_days = (period_to - period_from).days + 1

        # Get distinct days with spending
        query = select(Transaction.transaction_date).where(
            Transaction.transaction_date.between(period_from, period_to),
            Transaction.debit_credit == "D",
        )
        if account_id:
            query = query.where(Transaction.account_id == account_id)
        result = await self.db.execute(query.distinct())
        spend_dates = {row[0] for row in result.all()}

        # Build calendar
        calendar_data = []
        no_spend_days = 0
        current_streak = 0
        best_streak = 0
        streak = 0
        today = date.today()

        for day_num in range(1, total_days + 1):
            day_date = date(year, month, day_num)
            spent = day_date in spend_dates
            if not spent and day_date <= today:
                no_spend_days += 1
                streak += 1
                best_streak = max(best_streak, streak)
            else:
                streak = 0
            calendar_data.append({"day": day_num, "spent": spent})

        # Current streak (from today backwards)
        current_streak = 0
        check_date = min(today, period_to)
        while check_date >= period_from:
            if check_date not in spend_dates:
                current_streak += 1
                check_date -= timedelta(days=1)
            else:
                break

        goal = max(10, total_days // 3)  # Roughly 1/3 of the month

        return {
            "no_spend_days": no_spend_days,
            "total_days": total_days,
            "goal": goal,
            "current_streak": current_streak,
            "best_streak": best_streak,
            "calendar": calendar_data,
        }

    # ------------------------------------------------------------------
    # Convenience: generate all 6 reports at once
    # ------------------------------------------------------------------

    async def generate_all(
        self,
        year: int,
        month: int,
        account_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run all 6 reports and return as a single dict."""
        return {
            "monthly_spending": await self.monthly_spending_breakdown(year, month, account_id),
            "merchant_concentration": await self.merchant_concentration(year, month, account_id),
            "subscription_waste": await self.subscription_waste(year, month, account_id),
            "lifestyle_creep": await self.lifestyle_creep(year, month, account_id),
            "health_score": await self.financial_health_score(year, month, account_id),
            "no_spend_tracker": await self.no_spend_day_tracker(year, month, account_id),
            "period": {"year": year, "month": month},
        }
