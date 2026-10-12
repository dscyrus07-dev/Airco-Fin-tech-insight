"""
Run this script once to create tables on Supabase.
Usage: python database/setup_supabase.py
"""
import os

import psycopg2

CONN_STRING = (
    f"host={os.environ.get('SUPABASE_DB_HOST', '')} "
    f"port={os.environ.get('SUPABASE_DB_PORT', '5432')} "
    "dbname=postgres "
    f"user={os.environ.get('SUPABASE_DB_USER', '')} "
    f"password={os.environ.get('SUPABASE_DB_PASSWORD', '')}"
)

SQL = """
CREATE TABLE IF NOT EXISTS merchants (
    id SERIAL PRIMARY KEY,
    normalized_name VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(100) NOT NULL,
    confidence FLOAT DEFAULT 0.95,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255),
    bank_name VARCHAR(100),
    account_type VARCHAR(50),
    date DATE,
    description TEXT,
    debit DECIMAL(15, 2),
    credit DECIMAL(15, 2),
    balance DECIMAL(15, 2),
    category VARCHAR(100),
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_bank ON transactions(bank_name);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_merchants_name ON merchants(normalized_name);
"""

def main():
    print("Connecting to Supabase PostgreSQL...")
    conn = psycopg2.connect(CONN_STRING)
    conn.autocommit = True
    cur = conn.cursor()

    print("Creating tables...")
    cur.execute(SQL)

    # Verify tables exist
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name IN ('merchants', 'transactions')
        ORDER BY table_name;
    """)
    tables = cur.fetchall()
    print(f"Tables found: {[t[0] for t in tables]}")

    cur.close()
    conn.close()
    print("Supabase database setup complete!")

if __name__ == "__main__":
    main()
