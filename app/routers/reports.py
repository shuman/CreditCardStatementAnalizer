"""
Reports router — dashboard and individual report endpoints.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Account
from app.services.report_engine import ReportEngine

router = APIRouter(prefix="/api/reports", tags=["reports"])

REPORT_METHODS = {
    "monthly_spending": "monthly_spending_breakdown",
    "merchant_concentration": "merchant_concentration",
    "subscription_waste": "subscription_waste",
    "lifestyle_creep": "lifestyle_creep",
    "health_score": "financial_health_score",
    "no_spend_tracker": "no_spend_day_tracker",
}


@router.get("/dashboard")
async def dashboard(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    account_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return all 6 reports for the dashboard."""
    from datetime import date as _date
    today = _date.today()
    year = year or today.year
    month = month or today.month

    engine = ReportEngine(db)
    data = await engine.generate_all(year, month, account_id)

    # Attach list of accounts for the filter dropdown
    acct_result = await db.execute(
        select(Account).where(Account.is_active == True).order_by(Account.id)
    )
    data["accounts"] = [
        {
            "id": a.id,
            "label": a.account_nickname
            or f"{a.account_type} {a.account_number_masked}",
            "masked": a.account_number_masked,
        }
        for a in acct_result.scalars().all()
    ]

    return data


@router.get("/{report_id}")
async def individual_report(
    report_id: str,
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    account_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return a single report by ID for drill-down view."""
    from datetime import date as _date
    today = _date.today()
    year = year or today.year
    month = month or today.month

    method_name = REPORT_METHODS.get(report_id)
    if not method_name:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown report: {report_id}. Available: {list(REPORT_METHODS.keys())}",
        )

    engine = ReportEngine(db)
    method = getattr(engine, method_name)
    return await method(year, month, account_id)
