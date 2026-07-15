from app.database.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT
            file_name,
            bank_name,
            format_id,
            page_count,
            transaction_count,
            start_date,
            end_date,
            user_id,
            goal_id,
            is_healthy,
            has_valid_structure,
            has_valid_transactions,
            has_valid_dates,
            warnings,
            issues,
            created_at
        FROM hygiene_reports
        ORDER BY created_at DESC
        LIMIT 3
    """)).fetchall()

print(f"Total hygiene_reports rows checked: {len(rows)}\n")
print("=" * 70)

metrics = ["file_name","bank_name","format_id","page_count","transaction_count",
           "start_date","end_date","user_id","goal_id","is_healthy",
           "has_valid_structure","has_valid_transactions","has_valid_dates",
           "warnings","issues"]

for i, row in enumerate(rows, 1):
    d = dict(row._mapping)
    print(f"\n--- Report #{i} ({d['created_at']}) ---")
    for m in metrics:
        val = d.get(m)
        status = "✅" if val not in (None, "", "unknown", [], {}) else "❌ MISSING"
        print(f"  {m:<28}: {status}  {val}")

print("\n" + "=" * 70)
print("PASS CRITERIA:")
print("  ✓ file_name, bank_name, format_id, page_count > 0")
print("  ✓ transaction_count > 0, start_date, end_date")
print("  ✓ is_healthy flag, has_valid_* booleans set")
