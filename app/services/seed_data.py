"""
Seed data for financial institutions.
Called once on startup — idempotent.
"""
import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import FinancialInstitution

logger = logging.getLogger(__name__)

INSTITUTIONS = [
    {
        "name": "City Bank - American Express",
        "short_name": "CBL-AMEX",
        "country": "BD",
        "swift_code": "CIBLBDDH",
        "statement_format_hint": "city_bank_amex",
        "detection_keywords": [
            "city bank", "citybank", "cbl", "american express",
            "amex", "376948", "membership rewards", "mr points"
        ],
        "has_sidebar": False,
        "sidebar_crop_right_pct": 0,
        "page_structure": "chronological",
        "default_currency": "BDT",
    },
    {
        "name": "BRAC Bank",
        "short_name": "BRAC",
        "country": "BD",
        "swift_code": "BRAKBDDH",
        "statement_format_hint": "brac_visa",
        "detection_keywords": [
            "brac bank", "bracbank", "brac", "432145",
            "cl consumer", "astha app", "astha diye"
        ],
        "has_sidebar": True,
        "sidebar_crop_right_pct": 30,
        "page_structure": "sectioned",
        "default_currency": "BDT",
    },
    {
        "name": "Dutch-Bangla Bank",
        "short_name": "DBBL",
        "country": "BD",
        "swift_code": "DBBLBDDH",
        "statement_format_hint": "generic",
        "detection_keywords": ["dutch bangla", "dutch-bangla", "dbbl", "nexus"],
        "has_sidebar": False,
        "sidebar_crop_right_pct": 0,
        "page_structure": "chronological",
        "default_currency": "BDT",
    },
    {
        "name": "Eastern Bank",
        "short_name": "EBL",
        "country": "BD",
        "swift_code": "EBLDBDDH",
        "statement_format_hint": "generic",
        "detection_keywords": ["eastern bank", "ebl"],
        "has_sidebar": False,
        "sidebar_crop_right_pct": 0,
        "page_structure": "chronological",
        "default_currency": "BDT",
    },
    {
        "name": "Standard Chartered Bangladesh",
        "short_name": "SCB",
        "country": "BD",
        "swift_code": "SCBLBDDX",
        "statement_format_hint": "generic",
        "detection_keywords": ["standard chartered", "scb"],
        "has_sidebar": False,
        "sidebar_crop_right_pct": 0,
        "page_structure": "chronological",
        "default_currency": "BDT",
    },
]


async def seed_institutions(db: AsyncSession):
    """Seed financial_institutions table. Idempotent."""
    inserted = 0
    for data in INSTITUTIONS:
        existing = await db.execute(
            select(FinancialInstitution).where(FinancialInstitution.name == data["name"])
        )
        if existing.scalar_one_or_none():
            continue

        institution = FinancialInstitution(
            name=data["name"],
            short_name=data["short_name"],
            country=data["country"],
            swift_code=data.get("swift_code"),
            statement_format_hint=data["statement_format_hint"],
            detection_keywords=data["detection_keywords"],
            has_sidebar=data["has_sidebar"],
            sidebar_crop_right_pct=data["sidebar_crop_right_pct"],
            page_structure=data["page_structure"],
            default_currency=data["default_currency"],
            created_at=datetime.utcnow(),
        )
        db.add(institution)
        inserted += 1

    if inserted > 0:
        await db.commit()
        logger.info(f"Seeded {inserted} financial institutions")
    else:
        logger.debug("Financial institutions already seeded")
