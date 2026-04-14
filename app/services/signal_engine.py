"""
Signal Engine — precompute derived signals from transaction data
before sending to Claude for the monthly advisor report.

All signals are pure Python computation (zero tokens).
Results are passed as compact JSON to the AI prompt.
"""
import calendar
import logging
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction, Budget

logger = logging.getLogger(__name__)

# Discretionary categories that indicate impulse / lifestyle spending
DISCRETIONARY_CATEGORIES = {
    "food delivery", "restaurant", "dining", "shopping", "entertainment",
    "fashion", "gaming", "travel", "leisure", "beauty", "gym",
    "subscription", "streaming", "food & dining", "restaurants",
    "shopping & lifestyle",
}

CONVENIENCE_CATEGORIES = {
    "food delivery", "ride sharing", "rideshare", "fast food",
    "taxi", "delivery", "convenience",
}


class SignalEngine:
    """Precompute all derived signals from transaction data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def compute_all_signals(
        self, year: int, month: int, account_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Compute all signals for a given month. Returns a dict."""
        last_day = calendar.monthrange(year, month)[1]
        period_from = date(year, month, 1)
        period_to = date(year, month, last_day)

        # Fetch all debit transactions for the period
        txns = await self._get_debit_transactions(period_from, period_to, account_id)
        if not txns:
            return {"has_data": False, "total_transactions": 0}

        total_spend = sum(float(t.billing_amount or t.amount or 0) for t in txns)

        # Category distribution
        cat_dist = self._category_distribution(txns, total_spend)

        # Credit transactions for savings ratio
        credits = await self._get_credit_transactions(period_from, period_to, account_id)
        total_credits = sum(float(t.billing_amount or t.amount or 0) for t in credits)

        # Previous month for trend calculations
        prev_date = period_from - timedelta(days=1)
        prev_txns = await self._get_debit_transactions(
            date(prev_date.year, prev_date.month, 1), prev_date, account_id
        )
        prev_spend = sum(float(t.billing_amount or t.amount or 0) for t in prev_txns)

        # 6-month totals for lifestyle creep
        monthly_totals = await self._monthly_totals(6, account_id, end_year=year, end_month=month)

        # Budget adherence
        budget_adherence = await self._compute_budget_adherence(
            period_from, period_to, account_id, cat_dist
        )

        signals = {
            "has_data": True,
            "total_transactions": len(txns),
            "total_spend_bdt": round(total_spend, 2),
            "total_credits_bdt": round(total_credits, 2),
            "prev_spend_bdt": round(prev_spend, 2),
            "spend_change_pct": round(
                ((total_spend - prev_spend) / prev_spend * 100) if prev_spend > 0 else 0, 1
            ),
            "impulse_score": self._compute_impulse_score(txns, cat_dist, total_spend),
            "subscription_waste": self._compute_subscription_waste(txns, total_spend),
            "merchant_dependency": self._compute_merchant_dependency(txns, total_spend),
            "time_based_spending": self._compute_time_based_spending(txns),
            "lifestyle_creep_rate": self._compute_lifestyle_creep(monthly_totals),
            "savings_ratio": round(
                total_credits / total_spend if total_spend > 0 else 0, 2
            ),
            "convenience_cost": self._compute_convenience_cost(txns, total_spend),
            "category_breakdown": cat_dist,
            "budget_adherence": budget_adherence,
            "monthly_totals_6m": monthly_totals,
            "recurring_count": sum(1 for t in txns if t.is_recurring),
            "recurring_pct": round(
                sum(float(t.billing_amount or t.amount or 0) for t in txns if t.is_recurring)
                / total_spend * 100 if total_spend > 0 else 0, 1
            ),
            "period": {"year": year, "month": month, "from": str(period_from), "to": str(period_to)},
        }

        return signals

    # ------------------------------------------------------------------
    # Transaction queries
    # ------------------------------------------------------------------

    async def _get_debit_transactions(
        self, period_from: date, period_to: date, account_id: Optional[int] = None
    ) -> List[Transaction]:
        query = select(Transaction).where(
            Transaction.transaction_date.between(period_from, period_to),
            Transaction.debit_credit == "D",
        )
        if account_id:
            query = query.where(Transaction.account_id == account_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def _get_credit_transactions(
        self, period_from: date, period_to: date, account_id: Optional[int] = None
    ) -> List[Transaction]:
        query = select(Transaction).where(
            Transaction.transaction_date.between(period_from, period_to),
            Transaction.debit_credit == "C",
        )
        if account_id:
            query = query.where(Transaction.account_id == account_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def _monthly_totals(
        self, months_back: int, account_id: Optional[int] = None,
        end_year: Optional[int] = None, end_month: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        today = date.today()
        end_year = end_year or today.year
        end_month = end_month or today.month
        results = []
        for i in range(months_back - 1, -1, -1):
            m = end_month - i
            y = end_year
            while m <= 0:
                m += 12
                y -= 1
            last_day = calendar.monthrange(y, m)[1]
            period_from = date(y, m, 1)
            period_to = date(y, m, last_day)
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
    # Signal computations
    # ------------------------------------------------------------------

    def _category_distribution(
        self, txns: List[Transaction], total_spend: float
    ) -> List[Dict[str, Any]]:
        by_cat: Dict[str, float] = {}
        for t in txns:
            cat = t.category_ai or t.merchant_category or "Other"
            amount = float(t.billing_amount or t.amount or 0)
            by_cat[cat] = by_cat.get(cat, 0) + amount

        sorted_cats = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)[:10]
        return [
            {
                "category": cat,
                "amount": round(amount, 2),
                "pct": round(amount / total_spend * 100, 1) if total_spend > 0 else 0,
            }
            for cat, amount in sorted_cats
        ]

    def _compute_impulse_score(
        self, txns: List[Transaction], cat_dist: List[Dict], total_spend: float
    ) -> float:
        """% of non-recurring spending in discretionary categories."""
        discretionary_spend = 0.0
        for t in txns:
            if t.is_recurring:
                continue
            cat = (t.category_ai or t.merchant_category or "").lower()
            if any(dc in cat for dc in DISCRETIONARY_CATEGORIES):
                discretionary_spend += float(t.billing_amount or t.amount or 0)
        return round(
            discretionary_spend / total_spend * 100 if total_spend > 0 else 0, 1
        )

    def _compute_subscription_waste(
        self, txns: List[Transaction], total_spend: float
    ) -> Dict[str, Any]:
        """Total recurring costs + duplicate detection."""
        recurring = [
            t for t in txns if t.is_recurring
        ]
        total_recurring = sum(float(t.billing_amount or t.amount or 0) for t in recurring)

        # Detect duplicates (same merchant on multiple accounts)
        merchant_accounts: Dict[str, set] = {}
        for t in recurring:
            merchant = (t.merchant_name or "").lower().strip()
            if not merchant:
                continue
            if merchant not in merchant_accounts:
                merchant_accounts[merchant] = set()
            if t.account_id:
                merchant_accounts[merchant].add(t.account_id)

        duplicates = [
            {"merchant": m, "accounts": len(a)}
            for m, a in merchant_accounts.items() if len(a) > 1
        ]

        return {
            "total_recurring_bdt": round(total_recurring, 2),
            "recurring_pct": round(total_recurring / total_spend * 100 if total_spend > 0 else 0, 1),
            "subscription_count": len(recurring),
            "duplicate_services": duplicates,
        }

    def _compute_merchant_dependency(
        self, txns: List[Transaction], total_spend: float
    ) -> Dict[str, Any]:
        """Top-3 merchant concentration %."""
        merchant_spend: Dict[str, float] = {}
        for t in txns:
            name = t.merchant_name or (t.description_raw or "")[:30]
            amount = float(t.billing_amount or t.amount or 0)
            merchant_spend[name] = merchant_spend.get(name, 0) + amount

        sorted_merchants = sorted(merchant_spend.items(), key=lambda x: x[1], reverse=True)
        top3 = sorted_merchants[:3]
        top3_amount = sum(amount for _, amount in top3)

        return {
            "top3_pct": round(top3_amount / total_spend * 100 if total_spend > 0 else 0, 1),
            "top3_merchants": [
                {"name": name, "amount": round(amount, 2)}
                for name, amount in top3
            ],
            "total_merchants": len(merchant_spend),
        }

    def _compute_time_based_spending(
        self, txns: List[Transaction]
    ) -> Dict[str, Any]:
        """Weekend vs weekday average spend."""
        weekday_total = 0.0
        weekday_count = 0
        weekend_total = 0.0
        weekend_count = 0

        for t in txns:
            amount = float(t.billing_amount or t.amount or 0)
            # Python weekday(): 0=Mon, 5=Sat, 6=Sun
            if t.transaction_date.weekday() >= 5:
                weekend_total += amount
                weekend_count += 1
            else:
                weekday_total += amount
                weekday_count += 1

        return {
            "weekday_avg": round(weekday_total / weekday_count, 2) if weekday_count > 0 else 0,
            "weekend_avg": round(weekend_total / weekend_count, 2) if weekend_count > 0 else 0,
            "weekday_total": round(weekday_total, 2),
            "weekend_total": round(weekend_total, 2),
        }

    def _compute_lifestyle_creep(
        self, monthly_totals: List[Dict[str, Any]]
    ) -> float:
        """6-month spend trend %."""
        if len(monthly_totals) < 2:
            return 0.0
        first = monthly_totals[0]["total"]
        last = monthly_totals[-1]["total"]
        if first <= 0:
            return 0.0
        return round((last - first) / first * 100, 1)

    def _compute_convenience_cost(
        self, txns: List[Transaction], total_spend: float
    ) -> float:
        """Spend in convenience categories (delivery, rideshare, fast food)."""
        convenience_spend = 0.0
        for t in txns:
            cat = (t.category_ai or t.merchant_category or "").lower()
            desc = (t.description_raw or "").lower()
            if any(cc in cat for cc in CONVENIENCE_CATEGORIES) or \
               any(cc in desc for cc in CONVENIENCE_CATEGORIES):
                convenience_spend += float(t.billing_amount or t.amount or 0)
        return round(convenience_spend, 2)

    async def _compute_budget_adherence(
        self,
        period_from: date,
        period_to: date,
        account_id: Optional[int],
        cat_dist: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Active budgets vs actual spend."""
        result = await self.db.execute(
            select(Budget).where(Budget.is_active == True)
        )
        budgets = result.scalars().all()
        if not budgets:
            return {"has_budgets": False}

        # Map category -> spend from cat_dist
        cat_spend = {item["category"]: item["amount"] for item in cat_dist}

        statuses = []
        breached = 0
        for b in budgets:
            spent = cat_spend.get(b.category, 0)
            limit = float(b.monthly_limit)
            pct = round(spent / limit * 100, 1) if limit > 0 else 0
            is_breached = spent > limit
            if is_breached:
                breached += 1
            statuses.append({
                "category": b.category,
                "budget": limit,
                "spent": spent,
                "pct": pct,
                "breached": is_breached,
            })

        return {
            "has_budgets": True,
            "total_budgets": len(budgets),
            "breached": breached,
            "breach_pct": round(breached / len(budgets) * 100, 1),
            "details": statuses,
        }
