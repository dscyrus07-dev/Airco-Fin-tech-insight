"""
Comprehensive Supabase audit table check — run inside the backend container.
Reports: row counts, latest rows, and DONE / MISSING / EMPTY status per table.
"""
from app.database.session import engine
from sqlalchemy import text

TABLES = {
    "tenants":               "SELECT tenant_id, plan, created_at FROM tenants ORDER BY created_at DESC LIMIT 3",
    "users":                 "SELECT user_id, email, role, created_at FROM users ORDER BY created_at DESC LIMIT 3",
    "processing_jobs":       "SELECT job_id, status, bank_name, transaction_count, processing_mode, processing_time_ms, created_at FROM processing_jobs ORDER BY created_at DESC LIMIT 5",
    "job_events":            "SELECT event_type, event_name, status, created_at FROM job_events ORDER BY created_at DESC LIMIT 5",
    "audit_logs":            "SELECT event_type, event_name, status, created_at FROM audit_logs ORDER BY created_at DESC LIMIT 3",
    "parser_metrics":        "SELECT bank_name, parser_type, status, transactions_extracted, created_at FROM parser_metrics ORDER BY created_at DESC LIMIT 3",
    "hygiene_reports":       "SELECT is_healthy, health_score, transaction_count, created_at FROM hygiene_reports ORDER BY created_at DESC LIMIT 3",
    "report_generation_logs":"SELECT status, excel_filename, generation_time_ms, created_at FROM report_generation_logs ORDER BY created_at DESC LIMIT 3",
    "download_logs":         "SELECT file_type, user_id, status, created_at FROM download_logs ORDER BY created_at DESC LIMIT 3",
    "api_request_logs":      "SELECT method, path, status_code, duration_ms, created_at FROM api_request_logs ORDER BY created_at DESC LIMIT 3",
    "system_health_logs":    "SELECT status, cpu_percent, memory_percent, recorded_at FROM system_health_logs ORDER BY created_at DESC LIMIT 3",
    "error_logs":            "SELECT error_type, error_code, severity, created_at FROM error_logs ORDER BY created_at DESC LIMIT 3",
    "sessions":              "SELECT session_token, ip_address, created_at FROM sessions ORDER BY created_at DESC LIMIT 3",
    "unsupported_format_queue": "SELECT issue_type, issue_description, queue_status, created_at FROM unsupported_format_queue ORDER BY created_at DESC LIMIT 3",
}

DONE    = []
EMPTY   = []
ERRORS  = []

print("=" * 70)
print("SUPABASE AUDIT TABLE REPORT")
print("=" * 70)

with engine.connect() as conn:
    for tbl, sql in TABLES.items():
        try:
            cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
            rows = conn.execute(text(sql)).fetchall()
            keys = rows[0]._fields if rows else []

            status = "✅ POPULATED" if cnt > 0 else "❌ EMPTY"
            print(f"\n[{tbl}]  total={cnt}  {status}")

            if cnt > 0:
                DONE.append(f"{tbl} ({cnt} rows)")
                for r in rows:
                    print(f"   {dict(zip(keys, r))}")
            else:
                EMPTY.append(tbl)

        except Exception as e:
            print(f"\n[{tbl}]  ⚠️  ERROR: {e}")
            ERRORS.append(f"{tbl}: {e}")
            try:
                conn.execute(text("ROLLBACK"))
            except Exception:
                pass

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"\n✅ POPULATED ({len(DONE)}):")
for d in DONE:
    print(f"   • {d}")
print(f"\n❌ EMPTY ({len(EMPTY)}):")
for e in EMPTY:
    print(f"   • {e}")
if ERRORS:
    print(f"\n⚠️  ERRORS ({len(ERRORS)}):")
    for e in ERRORS:
        print(f"   • {e}")
print()
