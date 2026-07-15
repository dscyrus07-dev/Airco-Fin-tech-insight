from app.database.session import engine
from sqlalchemy import text

migrations = [
    "ALTER TABLE hygiene_reports ADD COLUMN IF NOT EXISTS file_name VARCHAR(512)",
    "ALTER TABLE hygiene_reports ADD COLUMN IF NOT EXISTS bank_name VARCHAR(100)",
    "ALTER TABLE hygiene_reports ADD COLUMN IF NOT EXISTS user_id VARCHAR(255)",
    "ALTER TABLE hygiene_reports ADD COLUMN IF NOT EXISTS goal_id VARCHAR(255)",
    "CREATE INDEX IF NOT EXISTS ix_hygiene_reports_bank_name ON hygiene_reports (bank_name)",
    "CREATE INDEX IF NOT EXISTS ix_hygiene_reports_user_id ON hygiene_reports (user_id)",
]

with engine.begin() as conn:
    for sql in migrations:
        conn.execute(text(sql))
        print(f"OK: {sql[:60]}...")

print("\nMigration complete.")
