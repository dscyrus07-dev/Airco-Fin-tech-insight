import os
import traceback
from pathlib import Path

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

env_path = Path(r"x:\FinTech SAAS\Airco Insights Fintech\local.env")
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ[k.strip()] = v.strip()

engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
insp = inspect(engine)
print("tenant cols", [c["name"] for c in insp.get_columns("tenants")])
print("user cols", [c["name"] for c in insp.get_columns("users")])

with engine.begin() as c:
    try:
        c.execute(
            text(
                """
                insert into tenants (tenant_id, tenant_name, tenant_slug, plan)
                values ('default', 'Default', 'default', 'FREE')
                on conflict (tenant_id) do nothing
                """
            )
        )
        print("tenant insert ok")
    except Exception as e:
        print("tenant insert fail", type(e).__name__, e)

with engine.connect() as c:
    print("tenants", c.execute(text("select tenant_id, id from tenants")).fetchall())

from app.database.audit_models import User, Tenant
from app.services.audit.audit_service import AuditService
from app.services.banks._shared.hygiene_check import HygieneCheckResult

SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()
try:
    tenant = db.query(Tenant).filter(Tenant.tenant_id == "default").first()
    print("tenant", tenant.id if tenant else None)
    try:
        u = User(
            tenant_id=tenant.id,
            user_id="probe-user",
            email="probe-user@auto.local",
            full_name="probe-user",
            role="USER",
            auth_provider="KEYCLOAK",
            is_active=True,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        print("direct user ok", u.id)
    except Exception as e:
        db.rollback()
        print("direct user fail", type(e).__name__, e)
        if getattr(e, "orig", None) is not None:
            print("orig", e.orig)

    svc = AuditService(db)
    u2 = svc._get_or_create_user(user_id="probe-user-2", tenant_id="default")
    print("svc user", u2)
    if u2 is not None:
        job = svc.create_processing_job(
            tenant_id="default",
            user_id="probe-user-2",
            job_id="probe-job-003",
            original_filename="probe.pdf",
            file_hash="abc123def456",
            file_size_bytes=123,
            processing_mode="FREE",
        )
        print("created job", job.job_id, job.id)
        hr = HygieneCheckResult(
            is_healthy=True,
            file_name="probe.pdf",
            page_count=1,
            bank_name="hdfc",
            format_id="HDF_FMT_1P",
            transaction_count=5,
            start_date="2024-01-01",
            end_date="2024-01-31",
            user_id="probe-user-2",
            goal_id="GENERAL",
            issues=[],
            warnings=[],
        )
        svc.finalize_job_audit(job_id="probe-job-003", hygiene_result=hr, transaction_count=5)
        print("finalize done")
        counts = db.execute(
            text(
                """
                select
                  (select count(*) from tenants) as tenants,
                  (select count(*) from users) as users,
                  (select count(*) from processing_jobs) as jobs,
                  (select count(*) from hygiene_reports) as hygiene
                """
            )
        ).mappings().first()
        print("after", dict(counts))
except Exception:
    traceback.print_exc()
finally:
    db.close()

