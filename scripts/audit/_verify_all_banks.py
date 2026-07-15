"""
Verify atomic audit logging for all banks.
Run inside the backend container after copying.
"""
import sys, uuid, os, traceback
sys.path.insert(0, "/app")

from app.database.session import SessionLocal
from app.services.audit.audit_service import AuditService
from sqlalchemy import text

BANKS = [
    ("HDFC",          "app.services.banks.hdfc.processor",         "HDFCProcessor",         "/tmp/banks/hdfc/hdfc_bankstatement.pdf"),
    ("ICICI",         "app.services.banks.icici.processor",        "ICICIProcessor",        "/tmp/banks/icici/ICICI-3M_1685081454384.pdf"),
    ("Axis",          "app.services.banks.axis.processor",         "AxisProcessor",         "/tmp/banks/axis/Axis_bankstatement.pdf"),
    ("Kotak",         "app.services.banks.kotak.processor",        "KotakProcessor",        "/tmp/banks/kotak/statement(2)_1714803025747.pdf"),
    ("SBI",           "app.services.banks.sbi.processor",          "SBIProcessor",          "/tmp/banks/sbi/sbi.pdf"),
    ("BankOfBaroda",  "app.services.banks.bank_of_baroda.processor","BankOfBarodaProcessor", "/tmp/banks/bob/bankofbaroda.pdf"),
    ("Canara",        "app.services.banks.canara.processor",       "CanaraProcessor",       "/tmp/banks/canara/canara.pdf"),
    ("IDFC",          "app.services.banks.idfc.processor",         "IDFCProcessor",         "/tmp/banks/idfc/idfc.pdf"),
    ("Karnataka",     "app.services.banks.karnataka.processor",    "KarnatakaProcessor",    "/tmp/banks/karnataka/karnataka.pdf"),
    ("Paytm",         "app.services.banks.paytm.processor",        "PaytmProcessor",        "/tmp/banks/paytm/paytm.pdf"),
    ("Union",         "app.services.banks.union.processor",        "UnionProcessor",        "/tmp/banks/union/union.pdf"),
    ("Unknown",       "app.services.banks.unknown.processor",      "UnknownProcessor",      "/tmp/banks/unknown/unknown.pdf"),
]

def run_bank(bank_name, module_path, class_name, pdf_path):
    if not os.path.exists(pdf_path):
        return f"SKIP (no PDF at {pdf_path})"

    db = SessionLocal()
    try:
        audit_svc = AuditService(db)
        job_id = str(uuid.uuid4())
        audit_svc.create_processing_job(
            tenant_id="default", user_id="verify-test",
            job_id=job_id, original_filename=os.path.basename(pdf_path),
            file_hash="verify", file_size_bytes=os.path.getsize(pdf_path),
        )

        mod = __import__(module_path, fromlist=[class_name])
        proc_cls = getattr(mod, class_name)
        extra_kwargs = {"strict_mode": False} if bank_name == "SBI" else {}
        proc = proc_cls(audit_service=audit_svc, job_id=job_id, **extra_kwargs)

        result = proc.process(pdf_path, {"user_id": "verify-test", "bank_name": bank_name})

        # Get the UUID PK for this job
        pj = audit_svc.get_processing_job(job_id)
        pj_uuid = str(pj.id) if pj else None

        if not pj_uuid:
            return "FAIL (no processing_job found)"

        with db.bind.connect() as conn:
            rows = conn.execute(text("""
                SELECT
                  (SELECT COUNT(*) FROM hygiene_reports       WHERE job_id = :uuid) AS hygiene,
                  (SELECT COUNT(*) FROM parser_metrics        WHERE job_id = :uuid) AS metrics,
                  (SELECT COUNT(*) FROM raw_transactions      WHERE job_id = :uuid) AS raw_tx,
                  (SELECT COUNT(*) FROM report_generation_logs WHERE job_id = :uuid) AS rpt,
                  (SELECT COUNT(*) FROM job_events            WHERE job_id = :uuid) AS events,
                  (SELECT status   FROM processing_jobs       WHERE id     = :uuid) AS job_status
            """), {"uuid": pj_uuid}).fetchone()

        status = result.status
        return (
            f"proc={status}  "
            f"hygiene={rows.hygiene}  metrics={rows.metrics}  "
            f"raw_tx={rows.raw_tx}  rpt={rows.rpt}  events={rows.events}  "
            f"job_status={rows.job_status}"
        )
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}\n{traceback.format_exc()[-400:]}"
    finally:
        db.close()

print(f"\n{'Bank':<16} {'Result'}")
print("-" * 90)
for bank_name, module_path, class_name, pdf_path in BANKS:
    result = run_bank(bank_name, module_path, class_name, pdf_path)
    print(f"{bank_name:<16} {result}")
print()
