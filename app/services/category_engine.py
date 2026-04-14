"""
Smart Category Engine.
Replaces scikit-learn TF-IDF with a persistent rule memory system
backed by Claude AI (claude-haiku) for new merchants.

Flow:
  1. Normalize merchant name
  2. Check category_rules table (zero tokens — free)
  3. If no match → call Claude Haiku (cheapest model) to categorize
  4. Store result as a category_rules row (source="claude_ai")
  5. If user later overrides → update/insert with source="user_override", confidence=1.0
     → future transactions from same merchant auto-match this rule
"""
import json
import logging
import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import CategoryRule, Transaction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bangladesh-relevant seed rules
# ---------------------------------------------------------------------------

SEED_RULES = [
    # Groceries & Online Grocery
    ("chaldal", "Groceries", "Online Grocery", "user_override"),
    ("shajgoj", "Groceries", "Online Grocery", "user_override"),
    ("meena bazar", "Groceries", "Supermarket", "user_override"),
    ("shwapno", "Groceries", "Supermarket", "user_override"),
    ("agora", "Groceries", "Supermarket", "user_override"),
    ("unimart", "Groceries", "Supermarket", "user_override"),
    ("amana big bazar", "Groceries", "Supermarket", "user_override"),
    ("momota super shop", "Groceries", "Supermarket", "user_override"),
    ("kc bazar", "Groceries", "Supermarket", "user_override"),

    # Food & Dining
    ("transcom foods", "Food & Dining", "Restaurant", "user_override"),
    ("kfc", "Food & Dining", "Fast Food", "user_override"),
    ("pizza hut", "Food & Dining", "Fast Food", "user_override"),
    ("burger king", "Food & Dining", "Fast Food", "user_override"),
    ("pathao food", "Food & Dining", "Delivery", "user_override"),
    ("foodpanda", "Food & Dining", "Delivery", "user_override"),
    ("sunmoon pharma", "Food & Dining", "Pharmacy / Food", "user_override"),

    # Transport & Fuel
    ("sheba green filling", "Transport", "Fuel", "user_override"),
    ("intraco cng", "Transport", "CNG / Fuel", "user_override"),
    ("brac aarong", "Shopping", "Clothing", "user_override"),
    ("padma oil", "Transport", "Fuel", "user_override"),
    ("meghna petroleum", "Transport", "Fuel", "user_override"),
    ("uber", "Transport", "Ride Share", "user_override"),
    ("pathao", "Transport", "Ride Share", "user_override"),
    ("shohoz", "Transport", "Ride Share", "user_override"),

    # Health & Medical
    ("ibn sina", "Health", "Hospital / Diagnostic", "user_override"),
    ("square hospital", "Health", "Hospital", "user_override"),
    ("popular diagnostic", "Health", "Diagnostic", "user_override"),
    ("safeway pharma", "Health", "Pharmacy", "user_override"),
    ("sunmoon pharma and super shop", "Health", "Pharmacy", "user_override"),
    ("aspara", "Health", "Pharmacy", "user_override"),

    # Utilities & Mobile
    ("robi.com", "Utilities", "Mobile Recharge", "user_override"),
    ("grameenphone", "Utilities", "Mobile Recharge", "user_override"),
    ("banglalink", "Utilities", "Mobile Recharge", "user_override"),
    ("teletalk", "Utilities", "Mobile Recharge", "user_override"),
    ("desco", "Utilities", "Electricity", "user_override"),
    ("desco prepaid", "Utilities", "Electricity", "user_override"),
    ("wasa", "Utilities", "Water", "user_override"),

    # Shopping
    ("apex footwear", "Shopping", "Footwear", "user_override"),
    ("bata shoe", "Shopping", "Footwear", "user_override"),
    ("brand zone", "Shopping", "Clothing", "user_override"),
    ("fair cosmetics", "Shopping", "Beauty & Cosmetics", "user_override"),
    ("maisha enterprise", "Shopping", "Shopping", "user_override"),
    ("miclo bangladesh", "Shopping", "Shopping", "user_override"),
    ("sanvees", "Shopping", "Shopping", "user_override"),
    ("daraz", "Shopping", "Online Shopping", "user_override"),

    # Software & Dev Tools
    ("cursor.ai", "Software & Tools", "Dev Tools", "user_override"),
    ("github", "Software & Tools", "Dev Tools", "user_override"),
    ("openai", "Software & Tools", "AI Services", "user_override"),
    ("claude.ai", "Software & Tools", "AI Services", "user_override"),
    ("anthropic", "Software & Tools", "AI Services", "user_override"),
    ("canva", "Software & Tools", "Design Tools", "user_override"),
    ("figma", "Software & Tools", "Design Tools", "user_override"),
    ("notion", "Software & Tools", "Productivity", "user_override"),
    ("1password", "Software & Tools", "Security", "user_override"),
    ("adobe", "Software & Tools", "Design Tools", "user_override"),

    # Freelancing
    ("upwork", "Freelancing", "Platform Fee", "user_override"),
    ("fiverr", "Freelancing", "Platform Fee", "user_override"),
    ("toptal", "Freelancing", "Platform Fee", "user_override"),

    # Entertainment & Streaming
    ("netflix", "Entertainment", "Streaming Video", "user_override"),
    ("spotify", "Entertainment", "Streaming Music", "user_override"),
    ("youtube premium", "Entertainment", "Streaming Video", "user_override"),
    ("youtubepremium", "Entertainment", "Streaming Video", "user_override"),
    ("amazon prime", "Entertainment", "Streaming Video", "user_override"),
    ("disney", "Entertainment", "Streaming Video", "user_override"),
    ("apple music", "Entertainment", "Streaming Music", "user_override"),

    # Cloud & Hosting
    ("google cloud", "Software & Tools", "Cloud Services", "user_override"),
    ("amazon web services", "Software & Tools", "Cloud Services", "user_override"),
    ("aws", "Software & Tools", "Cloud Services", "user_override"),
    ("digitalocean", "Software & Tools", "Cloud Services", "user_override"),
    ("namecheap", "Software & Tools", "Domain / Hosting", "user_override"),
    ("godaddy", "Software & Tools", "Domain / Hosting", "user_override"),

    # Google services
    ("google play", "Software & Tools", "App Store", "user_override"),
    ("google one", "Software & Tools", "Cloud Storage", "user_override"),
    ("google storage", "Software & Tools", "Cloud Storage", "user_override"),

    # Financial / Fees
    ("annual fees", "Fees & Charges", "Annual Fee", "builtin"),
    ("annual fee", "Fees & Charges", "Annual Fee", "builtin"),
    ("late fee", "Fees & Charges", "Late Payment Fee", "builtin"),
    ("vat on annual", "Fees & Charges", "Tax", "builtin"),
    ("vat on online", "Fees & Charges", "Tax", "builtin"),
    ("finance charge", "Fees & Charges", "Interest", "builtin"),
]


# ---------------------------------------------------------------------------
# Category Engine
# ---------------------------------------------------------------------------

class CategoryEngine:
    """
    Persistent category rule lookup with Claude Haiku fallback.
    Thread-safe for async use.
    """

    # Standard category list for Claude to choose from
    CATEGORIES = [
        "Groceries", "Food & Dining", "Transport", "Health",
        "Utilities", "Shopping", "Software & Tools", "Freelancing",
        "Entertainment", "Fees & Charges", "Financial Services",
        "Travel & Hotels", "Education", "Insurance", "Charity",
        "Government & Tax", "Other",
    ]

    def __init__(self, db: AsyncSession):
        self.db = db
        self._claude_client = None

    def _get_claude_client(self):
        if self._claude_client is None and settings.anthropic_api_key:
            import anthropic
            self._claude_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        return self._claude_client

    async def categorize(
        self,
        merchant_name: Optional[str],
        description_raw: str,
        country: str = "BD",
    ) -> Tuple[str, Optional[str], str, float]:
        """
        Categorize a transaction.

        Returns:
            (category, subcategory, source, confidence)
            source: "rule" | "claude_ai" | "builtin" | "fallback"
        """
        normalized = self._normalize(merchant_name or description_raw)

        # Step 1: Check rules table
        rule = await self._lookup_rule(normalized)
        if rule:
            # Update hit stats (fire and forget)
            rule.match_count += 1
            rule.last_matched_at = datetime.utcnow()
            await self.db.flush()
            return rule.category, rule.subcategory, "rule", float(rule.confidence)

        # Step 2: Claude Haiku categorization (cheapest model)
        if settings.anthropic_api_key:
            try:
                category, subcategory, confidence = await self._claude_categorize(
                    merchant_name, description_raw, country
                )
                # Store as a new rule for future use
                await self._store_rule(
                    merchant_pattern=merchant_name or description_raw,
                    normalized=normalized,
                    category=category,
                    subcategory=subcategory,
                    source="claude_ai",
                    confidence=confidence,
                )
                return category, subcategory, "claude_ai", confidence
            except Exception as e:
                logger.warning(f"Claude categorization failed: {e}, using fallback")

        # Step 3: Simple keyword fallback
        category = self._keyword_fallback(normalized)
        return category, None, "fallback", 0.5

    async def override_category(
        self,
        transaction_id: int,
        new_category: str,
        new_subcategory: Optional[str] = None,
    ) -> bool:
        """
        Apply a user category override to a transaction and persist a rule.
        Future transactions from the same merchant will auto-match.
        """
        result = await self.db.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()
        if not transaction:
            return False

        # Update the transaction
        transaction.category_ai = new_category
        transaction.subcategory_ai = new_subcategory
        transaction.category_source = "user_override"
        transaction.category_manual = new_category
        transaction.merchant_category = new_category

        # Persist the override as a rule (highest priority)
        merchant = transaction.merchant_name or transaction.description_raw
        normalized = self._normalize(merchant)

        await self._upsert_user_override_rule(
            merchant_pattern=merchant,
            normalized=normalized,
            category=new_category,
            subcategory=new_subcategory,
        )

        await self.db.commit()
        return True

    async def _lookup_rule(self, normalized: str) -> Optional[CategoryRule]:
        """Look up category_rules by normalized merchant."""
        result = await self.db.execute(
            select(CategoryRule)
            .where(
                CategoryRule.normalized_merchant == normalized,
                CategoryRule.is_active == True,
            )
            .order_by(
                # user_override > claude_ai > builtin
                CategoryRule.source.desc(),
                CategoryRule.confidence.desc(),
                CategoryRule.match_count.desc(),
            )
            .limit(1)
        )
        rule = result.scalar_one_or_none()

        # Try partial match if exact not found
        if not rule:
            result = await self.db.execute(
                select(CategoryRule).where(
                    CategoryRule.is_active == True,
                )
            )
            all_rules = result.scalars().all()
            for r in all_rules:
                if r.normalized_merchant and r.normalized_merchant in normalized:
                    return r

        return rule

    async def _claude_categorize(
        self,
        merchant_name: Optional[str],
        description_raw: str,
        country: str,
    ) -> Tuple[str, Optional[str], float]:
        """Call Claude Haiku to categorize a merchant."""
        client = self._get_claude_client()
        if not client:
            raise ValueError("No Anthropic API key")

        categories_str = ", ".join(self.CATEGORIES)
        prompt = (
            f"Categorize this financial transaction. "
            f"Merchant: {merchant_name or 'unknown'}. "
            f"Description: {description_raw}. "
            f"Country: {country}. "
            f"Choose ONE category from: {categories_str}. "
            f"Also provide a subcategory (2-4 words max). "
            f'Return JSON only: {{"category": "...", "subcategory": "...", "confidence": 0.0-1.0}}'
        )

        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        # Strip markdown if present
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = "\n".join(raw.split("\n")[:-1])

        data = json.loads(raw.strip())
        category = data.get("category", "Other")
        subcategory = data.get("subcategory")
        confidence = float(data.get("confidence", 0.8))

        logger.debug(f"Claude categorized '{merchant_name}' → {category} / {subcategory} ({confidence})")
        return category, subcategory, confidence

    async def _store_rule(
        self,
        merchant_pattern: str,
        normalized: str,
        category: str,
        subcategory: Optional[str],
        source: str,
        confidence: float,
    ):
        """Store a new category rule (unless one already exists)."""
        existing = await self.db.execute(
            select(CategoryRule).where(
                CategoryRule.normalized_merchant == normalized,
                CategoryRule.source == source,
            )
        )
        rule = existing.scalar_one_or_none()

        if rule:
            rule.category = category
            rule.subcategory = subcategory
            rule.confidence = Decimal(str(confidence))
            rule.updated_at = datetime.utcnow()
        else:
            rule = CategoryRule(
                merchant_pattern=merchant_pattern[:200],
                normalized_merchant=normalized[:200],
                category=category,
                subcategory=subcategory,
                source=source,
                confidence=Decimal(str(confidence)),
                match_count=0,
                is_active=True,
            )
            self.db.add(rule)

        await self.db.flush()

    async def _upsert_user_override_rule(
        self,
        merchant_pattern: str,
        normalized: str,
        category: str,
        subcategory: Optional[str],
    ):
        """Upsert a user override rule (always wins, confidence=1.0)."""
        existing = await self.db.execute(
            select(CategoryRule).where(
                CategoryRule.normalized_merchant == normalized,
                CategoryRule.source == "user_override",
            )
        )
        rule = existing.scalar_one_or_none()

        if rule:
            rule.category = category
            rule.subcategory = subcategory
            rule.confidence = Decimal("1.00")
            rule.updated_at = datetime.utcnow()
        else:
            rule = CategoryRule(
                merchant_pattern=merchant_pattern[:200],
                normalized_merchant=normalized[:200],
                category=category,
                subcategory=subcategory,
                source="user_override",
                confidence=Decimal("1.00"),
                match_count=0,
                is_active=True,
            )
            self.db.add(rule)

        await self.db.flush()

    def _normalize(self, text: str) -> str:
        """Normalize merchant name for rule matching."""
        if not text:
            return ""
        # Lowercase
        s = text.lower()
        # Remove accents
        s = unicodedata.normalize("NFKD", s)
        s = "".join(c for c in s if not unicodedata.combining(c))
        # Remove common prefixes from Amex descriptions
        s = re.sub(r"^purchase,", "", s)
        s = re.sub(r"^merchandize return,", "", s)
        s = re.sub(r"^merchandise return,", "", s)
        # Keep only alphanumeric and spaces
        s = re.sub(r"[^a-z0-9\s]", " ", s)
        # Collapse whitespace
        s = re.sub(r"\s+", " ", s).strip()
        # Take first 3 tokens (usually the merchant name before city/country)
        tokens = s.split()
        return " ".join(tokens[:3])

    def _keyword_fallback(self, normalized: str) -> str:
        """Simple keyword-based fallback (no API call)."""
        keywords = {
            "Groceries": ["grocery", "bazar", "shop", "mart", "super"],
            "Food & Dining": ["food", "restaurant", "cafe", "kitchen", "dining"],
            "Transport": ["cng", "fuel", "petrol", "uber", "pathao", "taxi"],
            "Health": ["pharma", "hospital", "clinic", "diagnostic", "medical"],
            "Utilities": ["robi", "grameenphone", "banglalink", "electricity", "water"],
            "Entertainment": ["netflix", "spotify", "youtube", "disney"],
            "Software & Tools": ["cursor", "github", "openai", "claude", "canva"],
        }
        for category, patterns in keywords.items():
            if any(p in normalized for p in patterns):
                return category
        return "Other"


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

async def seed_category_rules(db: AsyncSession):
    """
    Seed the category_rules table with Bangladesh-relevant merchant rules.
    Called once on startup (idempotent — skips existing entries).
    """
    inserted = 0
    for merchant, category, subcategory, source in SEED_RULES:
        normalized = re.sub(r"[^a-z0-9\s]", " ", merchant.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        # Take first 3 tokens
        normalized = " ".join(normalized.split()[:3])

        existing = await db.execute(
            select(CategoryRule).where(
                CategoryRule.normalized_merchant == normalized,
                CategoryRule.source == source,
            )
        )
        if existing.scalar_one_or_none():
            continue  # Already seeded

        rule = CategoryRule(
            merchant_pattern=merchant,
            normalized_merchant=normalized,
            category=category,
            subcategory=subcategory,
            source=source,
            confidence=Decimal("0.95"),
            match_count=0,
            is_active=True,
        )
        db.add(rule)
        inserted += 1

    if inserted > 0:
        await db.commit()
        logger.info(f"Seeded {inserted} category rules")
    else:
        logger.debug("Category rules already seeded")
