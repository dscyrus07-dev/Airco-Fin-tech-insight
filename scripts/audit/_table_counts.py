from app.database.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Get all tables in the database
    tables = conn.execute(text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)).fetchall()

    print(f"{'Table Name':<40} {'Columns':<10}")
    print("=" * 55)
    
    total_tables = 0
    total_columns = 0
    
    for table_row in tables:
        table_name = table_row[0]
        
        # Get column count for this table
        col_count = conn.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = :table_name AND table_schema = 'public'
        """), {"table_name": table_name}).scalar()
        
        print(f"{table_name:<40} {col_count:<10}")
        total_tables += 1
        total_columns += col_count
    
    print("=" * 55)
    print(f"Total Tables: {total_tables}")
    print(f"Total Columns: {total_columns}")
    print(f"Average Columns per Table: {total_columns/total_tables:.1f}" if total_tables > 0 else "N/A")
