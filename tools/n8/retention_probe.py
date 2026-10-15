"""N8 retention probe: inventory every sink for one job_id, then after a
manual sweep_once() re-inventory. Prints counts and key PATTERNS only —
no keys, filenames, statement content or PII in output."""
import json, sys, os, re

JOB_ID = sys.argv[1]
PHASE = sys.argv[2]  # before|after

from app.database import SessionLocal
from app.database.models import UserFileRecord
from app.database.audit_models import ProcessingJob, RawTransaction, JobEvent, StatementMetadata
from app.utils.file_handler import _s3_client, get_temp_dir
TEMP_DIR = get_temp_dir()
from app.core.config import settings
import redis as redislib

out = {"phase": PHASE, "job8": JOB_ID[:8]}
db = SessionLocal()

rec = db.query(UserFileRecord).filter(UserFileRecord.job_id == JOB_ID).first()
out["file_record"] = None
if rec:
    out["file_record"] = {
        "deletion_status": rec.deletion_status, "deleted_at": str(rec.deleted_at),
        "retention_expires_at": str(rec.retention_expires_at),
        "status": rec.status,
        "upload_key_set": bool(rec.upload_object_key),
        "report_key_set": bool(rec.report_object_key),
    }

# S3 objects (existence check only — keys never printed)
s3 = _s3_client()
s3res = {}
if rec:
    for label, bucket, key in (
        ("upload", settings.S3_BUCKET_UPLOADS, rec.upload_object_key),
        ("report", settings.S3_BUCKET_REPORTS, rec.report_object_key),
    ):
        if key:
            try:
                s3.head_object(Bucket=bucket, Key=key); s3res[label] = "PRESENT"
            except Exception:
                s3res[label] = "GONE"
        else:
            s3res[label] = "no_key"
out["s3"] = s3res

# Audit tables — counts only
pj = db.query(ProcessingJob).filter(ProcessingJob.job_id == JOB_ID).first()
out["audit"] = {
    "processing_job": bool(pj),
    "raw_transaction_rows": db.query(RawTransaction).filter(RawTransaction.job_id == pj.id).count() if pj else 0,
    "job_events": db.query(JobEvent).filter(JobEvent.job_id == pj.id).count() if pj else 0,
    "statement_metadata": db.query(StatementMetadata).filter(StatementMetadata.job_id == JOB_ID).count(),
}

# Redis — key patterns only
r = redislib.Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379, decode_responses=True)
patterns = {}
for pat in ("*"+JOB_ID+"*", "*job*"+JOB_ID[:8]+"*"):
    for k in r.scan_iter(pat):
        kind = re.sub(r"[0-9a-f-]{8,}", "<id>", k)
        patterns[kind] = patterns.get(kind, 0) + 1
        out.setdefault("redis_keys_present", 0)
        out["redis_keys_present"] = out.get("redis_keys_present", 0) + 1
        # TTL check
        ttl = r.ttl(k)
        out.setdefault("redis_ttls", []).append(ttl)
out["redis_key_patterns"] = patterns

# index-set membership
for idx in r.scan_iter("*jobs*"):
    kind = re.sub(r"[0-9a-f-]{8,}", "<id>", idx)
    try:
        n = r.scard(idx) or r.zcard(idx)
        has = r.sismember(idx, JOB_ID) or (r.zscore(idx, JOB_ID) is not None)
        if has or n:
            out.setdefault("redis_indexes", {})[kind] = {"members": n, "contains_job": bool(has), "ttl": r.ttl(idx)}
    except Exception:
        pass

# Temp dirs — count matching files, no names
tmp_hits = 0
for root in (TEMP_DIR, "/tmp"):
    try:
        for dirpath, _, files in os.walk(root):
            for f in files:
                if JOB_ID[:8] in f or f.endswith("_decrypted.pdf"):
                    tmp_hits += 1
    except Exception:
        pass
out["temp_files_matching"] = tmp_hits
db.close()
print(json.dumps(out, indent=1, default=str))
