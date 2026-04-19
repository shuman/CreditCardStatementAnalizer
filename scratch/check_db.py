import asyncio
from sqlalchemy import text
from app.database import engine

async def check():
    async with engine.connect() as conn:
        print("--- NOT NULL Columns without defaults ---")
        result = await conn.execute(text("""
            SELECT table_name, column_name 
            FROM information_schema.columns 
            WHERE is_nullable = 'NO' 
            AND column_default IS NULL 
            AND table_schema = 'public'
            AND table_name != 'alembic_version'
        """))
        for row in result.fetchall():
            print(row)

if __name__ == "__main__":
    asyncio.run(check())
