#!/usr/bin/env python3
"""
Test the improved rule matching logic.
"""
import asyncio
from app.database import AsyncSessionLocal
from app.services.category_engine import CategoryEngine

async def test_rule_matching():
    print("🧪 Testing Improved Rule Matching\n")

    async with AsyncSessionLocal() as db:
        engine = CategoryEngine(db)

        # Test cases that were failing
        test_cases = [
            ("GitHub", "Purchase,github,inc.,san francisco,united states"),
            ("Netflix", "Purchase,netflix.com 545706,los gatos,singapore"),
            ("OpenAI", "Purchase,openai,chatgpt subscr,san francisco,united states"),
            ("Desh Logistics Co Ltd.", "Purchase,desh logistics co ltd,dhaka zila,bangladesh"),
        ]

        for merchant_name, description in test_cases:
            print(f"🔍 Testing: {merchant_name}")
            print(f"   Description: {description}")

            try:
                category, subcategory, source, confidence = await engine.categorize(
                    merchant_name=merchant_name,
                    description_raw=description,
                    country="BD"
                )

                print(f"   ✅ Result: {category} > {subcategory}")
                print(f"   📊 Source: {source}, Confidence: {confidence:.0%}")

                if source == "fallback":
                    print(f"   ⚠️  WARNING: Used fallback instead of rule!")
            except Exception as e:
                print(f"   ❌ Error: {e}")

            print()

if __name__ == "__main__":
    asyncio.run(test_rule_matching())
