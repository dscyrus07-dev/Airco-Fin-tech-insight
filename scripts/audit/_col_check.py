from app.database.session import engine
from sqlalchemy import text

tables = ["download_logs", "api_request_logs", "unsupported_format_queue",
          "job_events", "audit_logs", "parser_metrics", "hygiene_reports", "report_generation_logs"]

with engine.connect() as conn:
    for tbl in tables:
        try:
            rows = conn.execute(text(
                "SELECT column_name, data_type FROM information_schema.columns "
                f"WHERE table_schema='public' AND table_name='{tbl}' ORDER BY ordinal_position"
            )).fetchall()
            cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
            print(f"\n[{tbl}] total={cnt}")
            for r in rows:
                print(f"   {r[0]:<40} {r[1]}")
        except Exception as e:
            print(f"\n[{tbl}] ERROR: {e}")
