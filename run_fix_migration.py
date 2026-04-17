"""
Fix migration 010: Add missing user_id columns and constraints
Run with: source .venv/bin/activate && python run_fix_migration.py
"""
import asyncio
from app.database import engine
from sqlalchemy import text


async def run_fix():
    """Execute migration fix SQL statements one by one."""
    
    print("Starting migration fix...")
    print("=" * 80)
    
    # SQL statements to execute
    statements = []
    
    # Step 1: Add missing user_id columns
    tables_needing_user_id = [
        'financial_institutions', 'transactions', 'fees', 'interest_charges',
        'rewards_summary', 'category_summary', 'payments', 'daily_expenses',
        'daily_income', 'liability_templates', 'monthly_records', 
        'monthly_liabilities', 'budgets', 'insights', 'ai_extractions',
        'advisor_reports'
    ]
    
    for table in tables_needing_user_id:
        statements.append(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id BIGINT")
    
    # Step 2: Backfill with user_id = 2 (jobaer.shuman@gmail.com)
    all_tables = tables_needing_user_id + ['accounts', 'category_rules', 'statements']
    
    for table in all_tables:
        statements.append(f"UPDATE {table} SET user_id = 2 WHERE user_id IS NULL")
    
    # Step 3: Make user_id NOT NULL
    for table in all_tables:
        statements.append(f"ALTER TABLE {table} ALTER COLUMN user_id SET NOT NULL")
    
    # Step 4: Add foreign key constraints
    for table in all_tables:
        constraint_name = f"fk_{table}_user_id"
        statements.append(
            f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint_name}"
        )
        statements.append(
            f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} "
            f"FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
        )
    
    # Step 5: Create indexes
    for table in all_tables:
        index_name = f"ix_{table}_user_id"
        statements.append(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}(user_id)")
    
    # Step 6: Update alembic version
    statements.append("UPDATE alembic_version SET version_num = '010'")
    
    # Execute all statements
    async with engine.begin() as conn:
        for i, stmt in enumerate(statements, 1):
            try:
                print(f"[{i}/{len(statements)}] {stmt[:80]}{'...' if len(stmt) > 80 else ''}")
                await conn.execute(text(stmt))
            except Exception as e:
                error_msg = str(e)
                if "already exists" in error_msg or "does not exist" in error_msg:
                    print(f"    ⚠ Skipped (already done): {error_msg.split(':')[0]}")
                else:
                    print(f"    ✗ Error: {e}")
                    raise
    
    print("=" * 80)
    print("✓ Migration fix completed successfully!")
    print()
    print("Verification:")
    
    # Verify the fix
    async with engine.begin() as conn:
        # Check user_id columns
        result = await conn.execute(text("""
            SELECT 
                table_name,
                is_nullable,
                data_type
            FROM information_schema.columns 
            WHERE column_name = 'user_id' 
            AND table_schema = 'public'
            ORDER BY table_name
        """))
        
        print(f"\n{'Table':<30} {'Type':<12} {'Nullable':<10}")
        print("-" * 55)
        for row in result:
            print(f"{row[0]:<30} {row[2]:<12} {row[1]:<10}")
        
        # Count records with user_id = 2
        result = await conn.execute(text("""
            SELECT 
                'financial_institutions' as table_name,
                COUNT(*) as count
            FROM financial_institutions WHERE user_id = 2
            UNION ALL
            SELECT 'transactions', COUNT(*) FROM transactions WHERE user_id = 2
            UNION ALL
            SELECT 'statements', COUNT(*) FROM statements WHERE user_id = 2
        """))
        
        print(f"\nRecords assigned to user ID 2 (jobaer.shuman@gmail.com):")
        print("-" * 40)
        for row in result:
            print(f"  {row[0]}: {row[1]}")
        
        # Check alembic version
        result = await conn.execute(text("SELECT version_num FROM alembic_version"))
        version = result.scalar()
        print(f"\nAlembic version: {version}")


if __name__ == "__main__":
    asyncio.run(run_fix())
