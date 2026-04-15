"""
AI Financial Advisor service.
Generates personalized financial insights using Claude claude-sonnet-4-5.

Token efficiency strategy:
  - NEVER sends PDF images to Claude — only compact JSON data snapshots
  - Snapshots are pure Python computation (zero tokens)
  - Each insight type produces a snapshot < 2,000 tokens
  - Insights are stored in DB and never regenerated until data changes
"""
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    Transaction, Statement, Account, RewardsSummary,
    Insight, Budget, AdvisorReport,
)

logger = logging.getLogger(__name__)

# Claude claude-sonnet-4-5 pricing
COST_PER_M_INPUT = 3.0
COST_PER_M_OUTPUT = 15.0


class AdvisorService:
    """
    Generates and stores financial insights.
    All insights are stored in the `insights` table and served from there
    (never regenerated on each request).
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._client = None

    def _get_client(self):
        if self._client is None and settings.anthropic_api_key:
            import anthropic
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        return self._client

    # ------------------------------------------------------------------
    # Main analysis entry point
    # ------------------------------------------------------------------

    async def analyze_period(
        self,
        period_from: date,
        period_to: date,
        account_id: Optional[int] = None,
    ) -> List[Insight]:
        """
        Run all insight generators for the given period.
        Returns list of newly created Insight objects.
        """
        new_insights: List[Insight] = []

        # 1. Monthly spending report (uses Claude)
        report = await self._generate_monthly_report(period_from, period_to, account_id)
        if report:
            new_insights.append(report)

        # 2. Overspending alerts (pure Python — no Claude)
        overspending = await self._detect_overspending(period_from, period_to, account_id)
        new_insights.extend(overspending)

        # 3. FX cost analysis (pure Python — no Claude)
        fx_insight = await self._fx_cost_report(period_from, period_to, account_id)
        if fx_insight:
            new_insights.append(fx_insight)

        # 4. Duplicate subscription detection (pure Python)
        dup_insight = await self._detect_duplicate_subscriptions(period_from, period_to)
        if dup_insight:
            new_insights.append(dup_insight)

        # 5. Reward expiry alert (pure Python)
        reward_insights = await self._check_reward_expiry()
        new_insights.extend(reward_insights)

        # 6. Budget breach alerts (pure Python)
        budget_insights = await self._check_budget_breaches(period_from, period_to)
        new_insights.extend(budget_insights)

        logger.info(f"Generated {len(new_insights)} insights for {period_from} – {period_to}")
        return new_insights

    # ------------------------------------------------------------------
    # Insight 1: Monthly Report (uses Claude)
    # ------------------------------------------------------------------

    async def _generate_monthly_report(
        self,
        period_from: date,
        period_to: date,
        account_id: Optional[int],
    ) -> Optional[Insight]:
        """Generate a full markdown monthly spending report via Claude."""
        client = self._get_client()
        if not client:
            return None

        snapshot = await self._build_spending_snapshot(period_from, period_to, account_id)
        if not snapshot["transactions"]:
            return None

        prompt = f"""You are a personal financial advisor analyzing spending data for a user in Bangladesh.

Here is the spending data for {period_from.strftime('%B %Y')}:

```json
{json.dumps(snapshot, indent=2, default=str)}
```

Write a concise personal financial report in Markdown. Include:
1. **Summary** — Total spending, top 3 categories, notable patterns
2. **Insights** — 2-3 specific observations (mention exact amounts in BDT)
3. **Recommendations** — 2-3 actionable tips to save money next month
4. **FX Note** — If there are USD/foreign transactions, mention the FX cost estimate

Keep it friendly, personal, and under 400 words. Use BDT for all amounts."""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens
            cost = (tokens_in * COST_PER_M_INPUT + tokens_out * COST_PER_M_OUTPUT) / 1_000_000
            logger.info(f"Monthly report generated: {tokens_in}+{tokens_out} tokens, ${cost:.4f}")
        except Exception as e:
            logger.error(f"Claude monthly report failed: {e}")
            return None

        insight = Insight(
            insight_type="monthly_report",
            scope="monthly",
            period_from=period_from,
            period_to=period_to,
            account_id=account_id,
            title=f"Monthly Report — {period_from.strftime('%B %Y')}",
            content=content,
            data_snapshot=snapshot,
            priority=3,
            is_read=False,
        )
        self.db.add(insight)
        await self.db.commit()
        await self.db.refresh(insight)
        return insight

    # ------------------------------------------------------------------
    # Insight 2: Overspending Detection (pure Python)
    # ------------------------------------------------------------------

    async def _detect_overspending(
        self,
        period_from: date,
        period_to: date,
        account_id: Optional[int],
    ) -> List[Insight]:
        """Detect categories where spending increased >20% vs 3-month average."""
        # Current period spending by category
        current = await self._spending_by_category(period_from, period_to, account_id)

        # 3-month lookback
        lookback_to = period_from - timedelta(days=1)
        lookback_from = lookback_to - timedelta(days=90)
        historical = await self._spending_by_category(lookback_from, lookback_to, account_id)

        insights = []
        for category, current_amount in current.items():
            if category in ("Fees & Charges", "Financial Services"):
                continue
            hist_amount = historical.get(category, 0)
            if hist_amount > 0:
                monthly_avg = hist_amount / 3
                increase_pct = ((float(current_amount) - monthly_avg) / monthly_avg) * 100
                if increase_pct > 20 and float(current_amount) > 500:  # BDT 500 threshold
                    insight = Insight(
                        insight_type="overspending",
                        scope="monthly",
                        period_from=period_from,
                        period_to=period_to,
                        account_id=account_id,
                        title=f"Overspending Alert: {category}",
                        content=(
                            f"## Overspending Detected: {category}\n\n"
                            f"You spent **BDT {float(current_amount):,.0f}** on {category} this month, "
                            f"which is **{increase_pct:.0f}% higher** than your 3-month average "
                            f"of BDT {monthly_avg:,.0f}/month.\n\n"
                            f"Consider reviewing your {category} spending to get back on track."
                        ),
                        data_snapshot={
                            "category": category,
                            "current_amount": float(current_amount),
                            "monthly_avg": monthly_avg,
                            "increase_pct": round(increase_pct, 1),
                        },
                        priority=2,
                        is_read=False,
                    )
                    self.db.add(insight)
                    insights.append(insight)

        if insights:
            await self.db.commit()
        return insights

    # ------------------------------------------------------------------
    # Insight 3: FX Cost Report (pure Python)
    # ------------------------------------------------------------------

    async def _fx_cost_report(
        self,
        period_from: date,
        period_to: date,
        account_id: Optional[int],
    ) -> Optional[Insight]:
        """Calculate how much was lost to FX markup on foreign transactions."""
        query = select(Transaction).where(
            Transaction.transaction_date.between(period_from, period_to),
            Transaction.original_currency.isnot(None),
            Transaction.original_currency != "BDT",
            Transaction.debit_credit == "D",
        )
        if account_id:
            query = query.where(Transaction.account_id == account_id)

        result = await self.db.execute(query)
        foreign_txns = result.scalars().all()

        if not foreign_txns:
            return None

        total_billed = sum(float(t.billing_amount or t.amount or 0) for t in foreign_txns)
        total_original_usd = sum(
            float(t.original_amount or 0)
            for t in foreign_txns
            if t.original_currency == "USD"
        )

        # Estimate FX markup (typical card markup ~2% above interbank)
        # This is illustrative — real FX cost requires interbank rates
        est_markup_pct = 2.0
        est_markup_bdt = total_billed * est_markup_pct / 100

        if est_markup_bdt < 50:  # Skip if trivial
            return None

        usd_txn_count = sum(1 for t in foreign_txns if t.original_currency == "USD")
        currencies = list({t.original_currency for t in foreign_txns})

        insight = Insight(
            insight_type="fx_cost_report",
            scope="monthly",
            period_from=period_from,
            period_to=period_to,
            account_id=account_id,
            title=f"FX Cost Report — {period_from.strftime('%B %Y')}",
            content=(
                f"## Foreign Currency Transaction Summary\n\n"
                f"You made **{len(foreign_txns)} international transactions** "
                f"in {', '.join(currencies)} this month.\n\n"
                f"- Total billed in BDT: **{total_billed:,.0f}**\n"
                f"- Estimated FX markup (~{est_markup_pct}%): **BDT {est_markup_bdt:,.0f}**\n\n"
                f"**Tip:** Consider a zero-forex card for your USD subscriptions "
                f"(Cursor.ai, Claude, GitHub, etc.) to save approximately "
                f"**BDT {est_markup_bdt * 12:,.0f}/year**."
            ),
            data_snapshot={
                "foreign_txn_count": len(foreign_txns),
                "currencies": currencies,
                "total_billed_bdt": total_billed,
                "est_markup_bdt": round(est_markup_bdt, 2),
            },
            priority=3,
            is_read=False,
        )
        self.db.add(insight)
        await self.db.commit()
        await self.db.refresh(insight)
        return insight

    # ------------------------------------------------------------------
    # Insight 4: Duplicate Subscriptions (pure Python)
    # ------------------------------------------------------------------

    async def _detect_duplicate_subscriptions(
        self, period_from: date, period_to: date
    ) -> Optional[Insight]:
        """Detect the same subscription appearing on multiple cards."""
        query = select(Transaction).where(
            Transaction.transaction_date.between(period_from, period_to),
            Transaction.debit_credit == "D",
            Transaction.is_recurring == True,
        )
        result = await self.db.execute(query)
        txns = result.scalars().all()

        # Group by normalized merchant, count distinct accounts
        merchant_accounts: Dict[str, set] = {}
        for t in txns:
            merchant = (t.merchant_name or "").lower().strip()
            if not merchant:
                continue
            if merchant not in merchant_accounts:
                merchant_accounts[merchant] = set()
            if t.account_id:
                merchant_accounts[merchant].add(t.account_id)

        duplicates = {m: accts for m, accts in merchant_accounts.items() if len(accts) > 1}
        if not duplicates:
            return None

        dup_list = "\n".join(f"- **{m.title()}** on {len(a)} cards" for m, a in duplicates.items())
        insight = Insight(
            insight_type="duplicate_subscription",
            scope="monthly",
            period_from=period_from,
            period_to=period_to,
            account_id=None,
            title="Possible Duplicate Subscriptions Detected",
            content=(
                f"## Duplicate Subscriptions\n\n"
                f"These subscriptions appear on multiple cards this month:\n\n"
                f"{dup_list}\n\n"
                f"Review these to avoid paying twice for the same service."
            ),
            data_snapshot={"duplicates": {m: list(a) for m, a in duplicates.items()}},
            priority=2,
            is_read=False,
        )
        self.db.add(insight)
        await self.db.commit()
        await self.db.refresh(insight)
        return insight

    # ------------------------------------------------------------------
    # Insight 5: Reward Expiry Alert (pure Python)
    # ------------------------------------------------------------------

    async def _check_reward_expiry(self) -> List[Insight]:
        """Alert if reward points are expiring within 30 days."""
        result = await self.db.execute(
            select(RewardsSummary)
            .where(RewardsSummary.points_expiring_next_month > 0)
            .order_by(RewardsSummary.statement_date.desc())
        )
        summaries = result.scalars().all()

        insights = []
        seen_accounts = set()

        for rs in summaries:
            if rs.account_number in seen_accounts:
                continue
            seen_accounts.add(rs.account_number)

            if rs.points_expiring_next_month <= 0:
                continue

            insight = Insight(
                insight_type="reward_expiry_alert",
                scope="monthly",
                period_from=date.today(),
                period_to=date.today() + timedelta(days=30),
                account_id=None,
                title=f"Reward Points Expiring Soon!",
                content=(
                    f"## Reward Points Expiry Alert\n\n"
                    f"**{rs.points_expiring_next_month:,} {rs.reward_program_name or 'points'}** "
                    f"are expiring within the next 30 days on card ending "
                    f"**{rs.account_number[-4:]}**.\n\n"
                    f"Current balance: **{rs.closing_balance:,} points**\n\n"
                    f"**Act now:** Redeem your expiring points before they are lost forever."
                ),
                data_snapshot={
                    "account_number": rs.account_number,
                    "expiring_points": rs.points_expiring_next_month,
                    "current_balance": rs.closing_balance,
                },
                priority=1,  # Critical
                is_read=False,
            )
            self.db.add(insight)
            insights.append(insight)

        if insights:
            await self.db.commit()
        return insights

    # ------------------------------------------------------------------
    # Insight 6: Budget Breach Alerts (pure Python)
    # ------------------------------------------------------------------

    async def _check_budget_breaches(
        self, period_from: date, period_to: date
    ) -> List[Insight]:
        """Check if any budgets are breached or near the alert threshold."""
        result = await self.db.execute(
            select(Budget).where(Budget.is_active == True)
        )
        budgets = result.scalars().all()

        current_spending = await self._spending_by_category(period_from, period_to, None)
        insights = []

        for budget in budgets:
            spent = float(current_spending.get(budget.category, 0))
            limit = float(budget.monthly_limit)
            if limit <= 0:
                continue

            pct_used = (spent / limit) * 100

            if pct_used >= 100:
                priority, status = 1, "exceeded"
                title = f"Budget Exceeded: {budget.category}"
            elif pct_used >= budget.alert_at_pct:
                priority, status = 2, f"{pct_used:.0f}% used"
                title = f"Budget Alert: {budget.category} ({pct_used:.0f}% used)"
            else:
                continue

            insight = Insight(
                insight_type="budget_breach",
                scope="monthly",
                period_from=period_from,
                period_to=period_to,
                account_id=budget.account_id,
                title=title,
                content=(
                    f"## Budget Alert: {budget.category}\n\n"
                    f"You have spent **BDT {spent:,.0f}** of your "
                    f"**BDT {limit:,.0f}** monthly budget "
                    f"for {budget.category} ({pct_used:.0f}% used).\n\n"
                    f"{'**You have exceeded your budget!**' if pct_used >= 100 else f'You have BDT {limit - spent:,.0f} remaining.'}"
                ),
                data_snapshot={
                    "category": budget.category,
                    "budget_limit": limit,
                    "spent": spent,
                    "pct_used": round(pct_used, 1),
                },
                priority=priority,
                is_read=False,
            )
            self.db.add(insight)
            insights.append(insight)

        if insights:
            await self.db.commit()
        return insights

    # ------------------------------------------------------------------
    # Helper: Build spending snapshot for Claude
    # ------------------------------------------------------------------

    async def _build_spending_snapshot(
        self,
        period_from: date,
        period_to: date,
        account_id: Optional[int],
    ) -> Dict[str, Any]:
        """Build a compact spending summary (pure Python, zero tokens)."""
        query = select(Transaction).where(
            Transaction.transaction_date.between(period_from, period_to),
            Transaction.debit_credit == "D",
        )
        if account_id:
            query = query.where(Transaction.account_id == account_id)

        result = await self.db.execute(query)
        txns = result.scalars().all()

        if not txns:
            return {"transactions": [], "total_bdt": 0}

        # Category breakdown
        by_category: Dict[str, float] = {}
        for t in txns:
            cat = t.category_ai or t.merchant_category or "Other"
            amount = float(t.billing_amount or t.amount or 0)
            by_category[cat] = by_category.get(cat, 0) + amount

        # Foreign transactions
        foreign = [
            {
                "merchant": t.merchant_name,
                "original": f"{t.original_currency} {float(t.original_amount or 0):.2f}",
                "bdt": float(t.billing_amount or t.amount or 0),
                "fx_rate": float(t.fx_rate_applied or 0),
            }
            for t in txns
            if t.original_currency and t.original_currency != "BDT"
        ]

        # Top merchants
        merchant_spend: Dict[str, float] = {}
        for t in txns:
            m = t.merchant_name or t.description_raw[:30]
            merchant_spend[m] = merchant_spend.get(m, 0) + float(t.billing_amount or t.amount or 0)
        top_merchants = sorted(merchant_spend.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "period": f"{period_from} to {period_to}",
            "currency": "BDT",
            "total_bdt": sum(by_category.values()),
            "transactions": len(txns),
            "by_category": dict(sorted(by_category.items(), key=lambda x: x[1], reverse=True)),
            "top_merchants": [{"merchant": m, "bdt": round(a, 0)} for m, a in top_merchants],
            "foreign_transactions": foreign[:10],
            "recurring_count": sum(1 for t in txns if t.is_recurring),
        }

    async def _spending_by_category(
        self,
        period_from: date,
        period_to: date,
        account_id: Optional[int],
    ) -> Dict[str, Decimal]:
        """Sum spending by category for a date range."""
        query = select(Transaction).where(
            Transaction.transaction_date.between(period_from, period_to),
            Transaction.debit_credit == "D",
        )
        if account_id:
            query = query.where(Transaction.account_id == account_id)

        result = await self.db.execute(query)
        txns = result.scalars().all()

        by_cat: Dict[str, Decimal] = {}
        for t in txns:
            cat = t.category_ai or t.merchant_category or "Other"
            amount = Decimal(str(t.billing_amount or t.amount or 0))
            by_cat[cat] = by_cat.get(cat, Decimal("0")) + amount
        return by_cat

    # ------------------------------------------------------------------
    # Monthly Advisor Report (Claude Sonnet, cached in advisor_reports)
    # ------------------------------------------------------------------

    async def generate_advisor_report(
        self,
        year: int,
        month: int,
        account_id: Optional[int] = None,
        force_regenerate: bool = False,
    ) -> Optional[AdvisorReport]:
        """
        Generate or retrieve a cached monthly AI advisor report.

        1. Check cache (query AdvisorReport by year/month/account_id)
        2. Compute signals via SignalEngine
        3. Get previous month score for delta
        4. Call Claude Sonnet with structured prompt
        5. Parse JSON response
        6. Compute total score from breakdown
        7. Store as AdvisorReport row
        """
        # Check cache
        if not force_regenerate:
            cached = await self._get_cached_report(year, month, account_id)
            if cached:
                logger.info(f"Returning cached advisor report for {year}-{month:02d}")
                return cached

        # If forcing, delete any existing cached report
        if force_regenerate:
            await self._delete_cached_report(year, month, account_id)

        # Compute signals
        from app.services.signal_engine import SignalEngine
        signal_engine = SignalEngine(self.db)
        signals = await signal_engine.compute_all_signals(year, month, account_id)

        if not signals.get("has_data"):
            logger.warning(f"No transaction data for {year}-{month:02d}")
            return None

        # Get previous month score for delta
        prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
        prev_report = await self._get_cached_report(prev_year, prev_month, account_id)
        prev_score = prev_report.score if prev_report else None

        # Call Claude
        client = self._get_client()
        if not client:
            logger.error("No Anthropic API key configured")
            return None

        from app.services.advisor_prompt import ADVISOR_SYSTEM_PROMPT, ADVISOR_USER_PROMPT_TEMPLATE

        signals_json = json.dumps(signals, indent=2, default=str)
        user_prompt = ADVISOR_USER_PROMPT_TEMPLATE.format(signals_json=signals_json)

        try:
            response = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=4096,
                system=ADVISOR_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw_text = response.content[0].text
            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens
            stop_reason = response.stop_reason
            cost = (tokens_in * COST_PER_M_INPUT + tokens_out * COST_PER_M_OUTPUT) / 1_000_000
            logger.info(
                f"Advisor report generated: {tokens_in}+{tokens_out} tokens, "
                f"stop_reason={stop_reason}, ${cost:.4f}"
            )
            if stop_reason == "max_tokens":
                logger.error(
                    "Claude stopped due to max_tokens — response was truncated. "
                    "Increase max_tokens further."
                )
        except Exception as e:
            logger.error(f"Claude advisor report failed: {e}")
            return None

        # Parse JSON response (strip markdown fences if present)
        parsed = self._parse_ai_json(raw_text)
        if not parsed:
            logger.error("Failed to parse Claude JSON response for advisor report")
            return None

        # Compute total score from breakdown (5 dimensions × 20 max = 100)
        breakdown = parsed.get("score_breakdown", {})
        total_score = sum(breakdown.values()) if breakdown else 0
        score_delta = total_score - prev_score if prev_score is not None else None

        # Store as AdvisorReport
        report = AdvisorReport(
            year=year,
            month=month,
            account_id=account_id,
            diagnosis=parsed.get("diagnosis"),
            score=total_score,
            score_breakdown=breakdown,
            score_prev=prev_score,
            score_delta=score_delta,
            insights=parsed.get("insights"),
            mistakes=parsed.get("mistakes"),
            recommendations=parsed.get("recommendations"),
            risks=parsed.get("risks"),
            personality_type=parsed.get("personality_type"),
            personality_detail=parsed.get("personality_detail"),
            top_recommendation=parsed.get("top_recommendation"),
            projection=parsed.get("projection"),
            advisor_notes=parsed.get("advisor_notes"),
            # New holistic income & savings fields
            income_insights=parsed.get("income_insights"),
            income_tips=parsed.get("income_tips"),
            savings_analysis=parsed.get("savings_analysis"),
            motivation=parsed.get("motivation"),
            signals=signals,
            raw_ai_output=raw_text,
            ai_model="claude-sonnet-4-5",
            ai_input_tokens=tokens_in,
            ai_output_tokens=tokens_out,
            ai_cost_usd=cost,
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)

        logger.info(
            f"Stored advisor report: score={total_score}, "
            f"personality={parsed.get('personality_type')}"
        )
        return report

    async def _get_cached_report(
        self, year: int, month: int, account_id: Optional[int]
    ) -> Optional[AdvisorReport]:
        """Retrieve a cached advisor report."""
        query = select(AdvisorReport).where(
            AdvisorReport.year == year,
            AdvisorReport.month == month,
        )
        if account_id:
            query = query.where(AdvisorReport.account_id == account_id)
        else:
            query = query.where(AdvisorReport.account_id.is_(None))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _delete_cached_report(
        self, year: int, month: int, account_id: Optional[int]
    ) -> None:
        """Delete a cached advisor report."""
        report = await self._get_cached_report(year, month, account_id)
        if report:
            await self.db.delete(report)
            await self.db.commit()

    @staticmethod
    def _parse_ai_json(raw_text: str) -> Optional[Dict[str, Any]]:
        """Parse Claude's JSON response, stripping markdown fences."""
        text = raw_text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.error(f"Raw Claude output (first 500 chars): {raw_text[:500]!r}")
            logger.error(f"Raw Claude output (last 500 chars): {raw_text[-500:]!r}")
            # Try to find JSON object in text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError as e2:
                    logger.error(f"Fallback JSON parse also failed: {e2}")
            return None
