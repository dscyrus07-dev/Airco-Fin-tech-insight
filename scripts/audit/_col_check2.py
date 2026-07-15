from app.database.session import engine
from sqlalchemy import inspect

insp = inspect(engine)
for tbl in ['download_logs', 'api_request_logs', 'unsupported_format_queue']:
    try:
        cols = [c['name'] for c in insp.get_columns(tbl)]
        print(f"{tbl}: {cols}")
    except Exception as e:
        print(f"{tbl}: ERROR {e}")
