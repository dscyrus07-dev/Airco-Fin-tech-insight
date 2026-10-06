"""Analyze-first workflow (Slice 2C): upload -> analyze -> user confirms/corrects -> process.

Design rules
- Analysis NEVER starts processing. A document reaches the existing pipeline only after an explicit CONFIRM or OVERRIDE
  (enforced here, server side), and only for banks that have a processor today.
- The detector's answer is kept untouched. A user override is stored beside it (detected_* vs user_selected_*) as an
  auditable USER_OVERRIDE event.
- Every document is analyzed in isolation: one bad PDF becomes an ERROR/UNSUPPORTED row, never a failed batch.
- Records belong to one user. Every read/write checks ownership; a foreign id looks exactly like a missing id (404).
- PDF passwords are used in memory only: never stored, logged, or put on a queue. A locked PDF is stored as a
  decrypted copy once unlocked (7-day retention applies, and unconfirmed analyses are purged after ANALYSIS_TTL_SECONDS).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from ..core.config import settings
from ..utils.logging import get_logger
from .statement_engine import (
    Capability,
    Confidence,
    DocumentState,
    analyze_text_pages,
    check_pdf,
    default_registry,
    detect_layout,
)

logger = get_logger(__name__)

ANALYSIS_TTL_SECONDS = int(os.getenv("ANALYSIS_TTL_SECONDS", str(24 * 3600)))
ANALYZE_MAX_FILES = int(os.getenv("ANALYZE_MAX_FILES", "50"))
_CONCURRENCY = 4

# engine bank_id -> the bank name the existing pipeline/frontend already accepts
PIPELINE_BANK_NAME: Dict[str, str] = {
    "hdfc": "HDFC Bank", "icici": "ICICI Bank", "axis": "Axis Bank", "kotak": "Kotak Bank", "sbi": "SBI",
    "canara": "Canara Bank", "idfc": "IDFC First Bank", "karnataka": "Karnataka Bank", "paytm": "Paytm Bank",
    "union": "Union Bank of India", "bank_of_baroda": "Bank of Baroda", "bank_of_india": "Bank of India",
    "indian_bank": "Indian Bank",
}

# coarse, user-facing state (the engine's finer state is kept as detail_state)
_COARSE = {
    DocumentState.DETECTED: "DETECTED",
    DocumentState.AWAITING_CONFIRMATION: "REVIEW",
    DocumentState.PASSWORD_REQUIRED: "REVIEW",
    DocumentState.UNKNOWN_BANK: "UNKNOWN",
    DocumentState.UNSUPPORTED_BANK: "UNSUPPORTED",
    DocumentState.UNSUPPORTED_SCANNED_PDF: "UNSUPPORTED",
    DocumentState.FAILED: "ERROR",
}

_EVIDENCE_TYPE = {
    "IFSC_LABELLED": ("IFSC", "IFSC code on the statement"),
    "IFSC_HEADER": ("IFSC", "IFSC code in the statement header"),
    "HEADER_NAME": ("BANK_NAME", "Bank name in the statement header"),
    "RUNNING_HEADER": ("HEADER", "Bank name repeated on several pages"),
    "DOMAIN": ("DOMAIN", "Bank website address"),
    "PAGE1_NAME": ("BANK_NAME", "Bank name on the first page"),
    "STATEMENT_PHRASE": ("STATEMENT_PHRASE", "Wording specific to this bank's statements"),
    "FILENAME": ("FILENAME", "File name (hint only)"),
    "METADATA": ("METADATA", "PDF metadata (hint only)"),
    "USER_HINT": ("USER_HINT", "Your suggestion (hint only)"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_display_name(filename: Optional[str]) -> str:
    base = (filename or "statement.pdf").replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".", " ", "(", ")") else "_" for ch in base).strip(" .")
    return (cleaned or "statement.pdf")[:150]


def _object_name(filename: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in os.path.splitext(filename)[0])[:80] or "statement"


# --------------------------------------------------------------------------------------------- stores
class MemoryAnalysisStore:
    """In-process store (tests, and a safe fallback when Redis is not configured)."""

    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}

    async def save(self, record: Dict[str, Any]) -> None:
        self._data[record["analysis_id"]] = json.loads(json.dumps(record))

    async def get(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        rec = self._data.get(analysis_id)
        return json.loads(json.dumps(rec)) if rec else None

    async def delete(self, analysis_id: str) -> None:
        self._data.pop(analysis_id, None)

    async def expired_ids(self, now_ts: float) -> List[str]:
        return [i for i, r in self._data.items() if r.get("expires_at_ts", 0) <= now_ts]


class RedisAnalysisStore:
    PREFIX = "airco:analysis:"
    INDEX = "airco:analysis:index"

    def __init__(self, client_factory) -> None:
        self._client = client_factory  # callable returning an asyncio redis client for the running loop

    async def save(self, record: Dict[str, Any]) -> None:
        r = self._client()
        await r.set(self.PREFIX + record["analysis_id"], json.dumps(record), ex=ANALYSIS_TTL_SECONDS + 3600)
        await r.zadd(self.INDEX, {record["analysis_id"]: record["expires_at_ts"]})

    async def get(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        raw = await self._client().get(self.PREFIX + analysis_id)
        return json.loads(raw) if raw else None

    async def delete(self, analysis_id: str) -> None:
        r = self._client()
        await r.delete(self.PREFIX + analysis_id)
        await r.zrem(self.INDEX, analysis_id)

    async def expired_ids(self, now_ts: float) -> List[str]:
        return list(await self._client().zrangebyscore(self.INDEX, 0, now_ts))


def _default_store():
    from .redis_job_store import redis_job_store

    return RedisAnalysisStore(lambda: redis_job_store._redis_client)


class AnalysisError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code, self.code, self.message = status_code, code, message


# --------------------------------------------------------------------------------------------- storage hooks
# thin wrappers so tests can replace them; production uses the existing object-storage helpers
class _Storage:
    def put(self, local_path: str, key: str) -> bool:
        from ..utils.file_handler import upload_to_storage

        return bool(upload_to_storage(local_path, bucket=settings.S3_BUCKET_UPLOADS, object_key=key))

    def get(self, key: str) -> Optional[str]:
        from ..utils.file_handler import download_from_storage

        return download_from_storage(bucket=settings.S3_BUCKET_UPLOADS, object_key=key)

    def delete(self, key: str) -> None:
        from ..utils.file_handler import delete_from_storage

        delete_from_storage(settings.S3_BUCKET_UPLOADS, key)


# --------------------------------------------------------------------------------------------- the service
@dataclass
class UploadedPdf:
    filename: str
    content: bytes


class AnalysisService:
    def __init__(self, store=None, storage=None, submit_job=None):
        self._store = store
        self.storage = storage or _Storage()
        self._submit_job = submit_job  # async callable, replaced in tests

    @property
    def store(self):
        if self._store is None:
            self._store = _default_store()
        return self._store

    # ---- helpers
    @staticmethod
    def _owner(user: Dict[str, Any]) -> str:
        uid = (user or {}).get("id")
        if not uid:
            raise AnalysisError(401, "NOT_AUTHENTICATED", "Not authenticated")
        return str(uid)

    async def _load(self, analysis_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
        rec = await self.store.get(analysis_id)
        if not rec or rec.get("owner_id") != self._owner(user):
            raise AnalysisError(404, "ANALYSIS_NOT_FOUND", "Analysis not found")  # foreign id == missing id
        return rec

    @staticmethod
    def _find_doc(rec: Dict[str, Any], document_id: str) -> Optional[Dict[str, Any]]:
        return next((d for d in rec["documents"] if d["document_id"] == document_id), None)

    # ---- public view (never exposes storage keys, owner ids, or passwords)
    @staticmethod
    def public_view(rec: Dict[str, Any]) -> Dict[str, Any]:
        docs = []
        for d in rec["documents"]:
            docs.append({k: v for k, v in d.items() if k not in ("storage_key", "original_storage_key", "events_internal")})
        counts: Dict[str, int] = {}
        for d in rec["documents"]:
            counts[d["state"]] = counts.get(d["state"], 0) + 1
        return {
            "analysis_id": rec["analysis_id"],
            "created_at": rec["created_at"],
            "expires_at": rec["expires_at"],
            "documents": docs,
            "summary": {"total": len(docs), "by_state": counts, "groups": AnalysisService.group_by_bank(rec)},
        }

    @staticmethod
    def group_by_bank(rec: Dict[str, Any]) -> List[Dict[str, Any]]:
        groups: Dict[str, Dict[str, Any]] = {}
        for d in rec["documents"]:
            bank = d.get("effective_bank") or d.get("bank")
            key = (bank or {}).get("id") or ("unsupported" if d["state"] == "UNSUPPORTED" else "unknown")
            g = groups.setdefault(key, {"bank_id": (bank or {}).get("id"), "bank_name": (bank or {}).get("name") or ("Unsupported" if key == "unsupported" else "Unknown"),
                                        "count": 0, "document_ids": [], "confidences": []})
            g["count"] += 1
            g["document_ids"].append(d["document_id"])
            if (d.get("bank") or {}).get("confidence"):
                g["confidences"].append(d["bank"]["confidence"])
        order = ["VERY_HIGH", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]
        out = []
        for g in groups.values():
            confs = g.pop("confidences")
            g["confidence"] = min(confs, key=order.index) if confs else None  # the weakest confidence in the group
            out.append(g)
        return sorted(out, key=lambda g: -g["count"])

    # ---- analyze
    async def analyze(
        self,
        user: Dict[str, Any],
        files: Sequence[UploadedPdf],
        *,
        passwords: Optional[Dict[str, str]] = None,
        bank_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        owner = self._owner(user)
        if not files:
            raise AnalysisError(400, "NO_FILES", "Upload at least one PDF")
        if len(files) > ANALYZE_MAX_FILES:
            raise AnalysisError(400, "TOO_MANY_FILES", f"At most {ANALYZE_MAX_FILES} files per analysis")
        passwords = passwords or {}
        analysis_id = uuid.uuid4().hex
        sem = asyncio.Semaphore(_CONCURRENCY)

        async def one(f: UploadedPdf) -> Dict[str, Any]:
            async with sem:
                try:
                    return await asyncio.to_thread(
                        self._analyze_one, user, analysis_id, f, passwords.get(f.filename), bank_hint
                    )
                except Exception as exc:  # per-document isolation
                    logger.error("Document analysis failed", error=type(exc).__name__)
                    return self._error_doc(f, "The file could not be analyzed.")

        docs = await asyncio.gather(*(one(f) for f in files))
        now = time.time()
        rec = {
            "analysis_id": analysis_id,
            "owner_id": owner,
            "tenant_id": (user or {}).get("tenant_id") or "default",
            "owner_email": (user or {}).get("email"),
            "owner_name": (user or {}).get("preferred_username") or (user or {}).get("name"),
            "created_at": _now(),
            "expires_at": datetime.fromtimestamp(now + ANALYSIS_TTL_SECONDS, timezone.utc).isoformat(),
            "expires_at_ts": now + ANALYSIS_TTL_SECONDS,
            "documents": list(docs),
        }
        await self.store.save(rec)
        return self.public_view(rec)

    def _error_doc(self, f: UploadedPdf, message: str, code: str = "ANALYSIS_FAILED", state: str = "ERROR") -> Dict[str, Any]:
        return {
            "document_id": uuid.uuid4().hex,
            "filename": safe_display_name(f.filename),
            "size_bytes": len(f.content),
            "capability": None,
            "state": state,
            "detail_state": "FAILED",
            "message": message,
            "error_code": code,
            "requires_password": False,
            "requires_confirmation": False,
            "bank": None,
            "evidence": [],
            "supporting": [],
            "layout": {"id": "UNKNOWN", "confidence": "UNKNOWN", "description": "", "parser_family": None},
            "workflow_status": "BLOCKED",
            "effective_bank": None,
            "selection": None,
            "events": [{"event": "ANALYZED", "at": _now(), "state": state}],
            "job_id": None,
            "storage_key": None,
        }

    def _analyze_one(self, user, analysis_id: str, f: UploadedPdf, password: Optional[str], bank_hint: Optional[str]) -> Dict[str, Any]:
        name = safe_display_name(f.filename)
        if not name.lower().endswith(".pdf"):
            return self._error_doc(f, "Only PDF files are accepted.", "NOT_A_PDF")
        if len(f.content) > settings.MAX_FILE_SIZE_BYTES:
            return self._error_doc(f, f"File is larger than {settings.MAX_FILE_SIZE_MB} MB.", "FILE_TOO_LARGE")
        if not f.content[:1024].lstrip().startswith(b"%PDF"):
            return self._error_doc(f, "This file is not a valid PDF.", "NOT_A_PDF")

        doc_id = uuid.uuid4().hex
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        decrypted = None
        try:
            tmp.write(f.content)
            tmp.close()
            cap, texts = check_pdf(tmp.name, password=password)
            analysis = analyze_text_pages(name, cap, texts, user_hint=bank_hint)
            det = analysis.detection
            layout = detect_layout(texts, det.bank_id if det else None) if det and cap.capability in (Capability.TEXT, Capability.MIXED) else None

            store_path = tmp.name
            if password and cap.capability in (Capability.TEXT, Capability.MIXED, Capability.SCANNED):
                decrypted = self._decrypt_copy(tmp.name, password)  # None if the file was not encrypted
                store_path = decrypted or tmp.name

            storable = analysis.state not in (DocumentState.FAILED,)
            key = None
            if storable:
                folder = self._folder(user)
                key = f"users/{folder}/uploads/analysis/{analysis_id}/{doc_id}_{_object_name(name)}.pdf"
                if not self.storage.put(store_path, key):
                    return self._error_doc(f, "The file could not be stored for confirmation. Please retry.", "STORAGE_UPLOAD_FAILED")
            return self._build_doc(doc_id, name, f, analysis, layout, key)
        finally:
            for p in (tmp.name, decrypted):
                if p and os.path.exists(p):
                    try:
                        os.unlink(p)
                    except OSError:
                        pass

    @staticmethod
    def _folder(user: Dict[str, Any]) -> str:
        from ..utils.file_handler import storage_user_folder

        return storage_user_folder(user_email=user.get("email"), user_name=user.get("preferred_username"), user_id=user.get("id"))

    @staticmethod
    def _decrypt_copy(path: str, password: str) -> Optional[str]:
        try:
            import pikepdf

            out = path.replace(".pdf", "_dec.pdf")
            with pikepdf.open(path, password=password) as pdf:
                if not pdf.is_encrypted:
                    return None
                pdf.save(out)
            return out
        except Exception:
            return None

    def _build_doc(self, doc_id, name, f, analysis, layout, key) -> Dict[str, Any]:
        det = analysis.detection
        state = _COARSE.get(analysis.state, "ERROR")
        bank = None
        evidence: List[Dict[str, Any]] = []
        supporting: List[Dict[str, Any]] = []
        if det is not None:
            if det.bank_id and det.confidence not in (Confidence.UNKNOWN, Confidence.LOW):
                bank = {
                    "id": det.bank_id, "name": det.bank_name, "confidence": det.confidence.value,
                    "score": det.score, "supported": bool(det.supported and det.bank_id in PIPELINE_BANK_NAME),
                }
            for e in det.evidence:
                t, label = _EVIDENCE_TYPE.get(e.kind.value, (e.kind.value, e.kind.value))
                evidence.append({"type": t, "kind": e.kind.value, "label": label, "value": e.matched, "weight": e.weight, "page": e.page})
            for e in det.supporting:
                t, label = _EVIDENCE_TYPE.get(e.kind.value, (e.kind.value, e.kind.value))
                supporting.append({"type": t, "kind": e.kind.value, "label": label, "value": e.matched})
        # never present LOW/UNKNOWN as a trusted bank; keep the weak guess only as a suggestion
        suggestion = None
        if det is not None and det.bank_id and bank is None:
            suggestion = {"id": det.bank_id, "name": det.bank_name, "confidence": det.confidence.value}
        needs_password = analysis.state == DocumentState.PASSWORD_REQUIRED
        requires_confirmation = state in ("REVIEW", "UNKNOWN")
        workflow = "AWAITING_CONFIRMATION" if state in ("DETECTED", "REVIEW", "UNKNOWN") else "BLOCKED"
        if analysis.state == DocumentState.UNSUPPORTED_BANK or (state == "DETECTED" and bank and not bank["supported"]):
            state = "UNSUPPORTED"
            workflow = "AWAITING_CONFIRMATION"  # the user may still pick a supported bank if the detection is wrong
        return {
            "document_id": doc_id,
            "filename": name,
            "size_bytes": len(f.content),
            "capability": analysis.capability.to_dict(),
            "state": state,
            "detail_state": analysis.state.value,
            "message": analysis.message,
            "requires_password": needs_password,
            "requires_confirmation": requires_confirmation,
            "bank": bank,
            "suggestion": suggestion,
            "evidence": evidence,
            "supporting": supporting,
            "hint_conflict": bool(det.hint_conflict) if det else False,
            "layout": layout.to_dict() if layout else {"id": "UNKNOWN", "confidence": "UNKNOWN", "description": "", "parser_family": None},
            "workflow_status": workflow,
            "effective_bank": None,
            "selection": None,
            "events": [{"event": "ANALYZED", "at": _now(), "state": state}],
            "job_id": None,
            "storage_key": key,
        }

    # ---- read
    async def get(self, analysis_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
        return self.public_view(await self._load(analysis_id, user))

    # ---- unlock a locked document (password used once, in memory)
    async def unlock(self, analysis_id: str, document_id: str, user: Dict[str, Any], password: str) -> Dict[str, Any]:
        rec = await self._load(analysis_id, user)
        doc = self._find_doc(rec, document_id)
        if not doc:
            raise AnalysisError(404, "DOCUMENT_NOT_FOUND", "Document not found")
        if doc["detail_state"] != "PASSWORD_REQUIRED" or not doc.get("storage_key"):
            raise AnalysisError(409, "NOT_LOCKED", "This document does not need a password")
        local = self.storage.get(doc["storage_key"])
        if not local or not os.path.isfile(local):
            raise AnalysisError(410, "FILE_EXPIRED", "The uploaded file is no longer available. Please upload it again.")
        try:
            with open(local, "rb") as fh:
                content = fh.read()
        finally:
            try:
                os.unlink(local)
            except OSError:
                pass
        old_key = doc["storage_key"]
        new = await asyncio.to_thread(self._analyze_one, user, analysis_id, UploadedPdf(doc["filename"], content), password, None)
        if new.get("detail_state") == "PASSWORD_REQUIRED":
            new["message"] = "That password did not open the file. Please try again."
            if new.get("storage_key"):
                self.storage.delete(new["storage_key"])
            return {"document": {**self._public_doc(doc), "message": new["message"]}, "unlocked": False}
        new["document_id"] = document_id  # keep the identity the UI already holds
        new["events"] = doc["events"] + [{"event": "UNLOCKED", "at": _now(), "state": new["state"]}]
        rec["documents"] = [new if d["document_id"] == document_id else d for d in rec["documents"]]
        await self.store.save(rec)
        self.storage.delete(old_key)
        return {"document": self._public_doc(new), "unlocked": True}

    @staticmethod
    def _public_doc(d: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in d.items() if k not in ("storage_key",)}

    # ---- confirm / override
    async def confirm(
        self,
        analysis_id: str,
        user: Dict[str, Any],
        decisions: Sequence[Dict[str, Any]],
        *,
        confirm_all_detected: bool = False,
    ) -> Dict[str, Any]:
        rec = await self._load(analysis_id, user)
        actor = self._owner(user)
        results: List[Dict[str, Any]] = []
        seen = set()
        for dec in decisions:
            did, action = dec.get("document_id"), str(dec.get("action", "")).upper()
            seen.add(did)
            doc = self._find_doc(rec, did)
            if not doc:
                results.append({"document_id": did, "ok": False, "code": "DOCUMENT_NOT_FOUND", "message": "Document not found"})
                continue
            results.append(self._apply_decision(doc, action, dec.get("bank_id"), actor))
        if confirm_all_detected:
            for doc in rec["documents"]:
                if doc["document_id"] not in seen and doc["state"] == "DETECTED" and doc["workflow_status"] == "AWAITING_CONFIRMATION":
                    results.append(self._apply_decision(doc, "CONFIRM", None, actor))
        await self.store.save(rec)
        view = self.public_view(rec)
        view["results"] = results
        return view

    def _apply_decision(self, doc: Dict[str, Any], action: str, bank_id: Optional[str], actor: str) -> Dict[str, Any]:
        did = doc["document_id"]

        def fail(code: str, msg: str) -> Dict[str, Any]:
            return {"document_id": did, "ok": False, "code": code, "message": msg}

        if doc["workflow_status"] not in ("AWAITING_CONFIRMATION", "CONFIRMED"):
            return fail("NOT_CONFIRMABLE", doc.get("message") or "This document cannot be processed.")
        if doc.get("requires_password"):
            return fail("PASSWORD_REQUIRED", "Enter the PDF password first.")
        if action == "CONFIRM":
            bank = doc.get("bank")
            if not bank or not bank.get("supported"):
                return fail("BANK_REQUIRED", "The bank was not identified with enough confidence. Select the bank.")
            doc["effective_bank"] = {"id": bank["id"], "name": bank["name"]}
            doc["selection"] = {"action": "CONFIRM", "bank_id": bank["id"], "by": actor, "at": _now()}
            doc["events"].append({"event": "USER_CONFIRM", "at": _now(), "by": actor, "bank_id": bank["id"]})
        elif action == "OVERRIDE":
            cfg = default_registry().get(bank_id) if bank_id else None
            if not cfg or cfg.id not in PIPELINE_BANK_NAME:
                return fail("BANK_NOT_SUPPORTED", "Choose one of the supported banks.")
            det_bank = doc.get("bank") or doc.get("suggestion")
            doc["effective_bank"] = {"id": cfg.id, "name": cfg.display_name}
            doc["selection"] = {"action": "OVERRIDE", "bank_id": cfg.id, "by": actor, "at": _now()}
            doc["events"].append({
                "event": "USER_OVERRIDE", "at": _now(), "by": actor,
                "detected_bank": (det_bank or {}).get("id"),
                "detected_confidence": (det_bank or {}).get("confidence"),
                "user_selected_bank": cfg.id,
            })
        else:
            return fail("BAD_ACTION", "action must be CONFIRM or OVERRIDE")
        doc["workflow_status"] = "CONFIRMED"
        return {"document_id": did, "ok": True, "workflow_status": "CONFIRMED", "bank_id": doc["effective_bank"]["id"]}

    # ---- process confirmed documents with the EXISTING pipeline
    async def process_confirmed(self, analysis_id: str, user: Dict[str, Any], document_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
        rec = await self._load(analysis_id, user)
        submit = self._submit_job or self._submit_existing_pipeline
        started: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        for doc in rec["documents"]:
            if document_ids is not None and doc["document_id"] not in document_ids:
                continue
            if doc["workflow_status"] != "CONFIRMED":
                skipped.append({"document_id": doc["document_id"], "reason": "NOT_CONFIRMED" if doc["workflow_status"] == "AWAITING_CONFIRMATION" else "NOT_PROCESSABLE"})
                continue
            try:
                job_id = await submit(rec, doc, user)
            except Exception as exc:
                logger.error("Could not start processing", error=type(exc).__name__)
                skipped.append({"document_id": doc["document_id"], "reason": "START_FAILED"})
                continue
            doc["workflow_status"] = "PROCESSING"
            doc["job_id"] = job_id
            doc["events"].append({"event": "PROCESSING_STARTED", "at": _now(), "job_id": job_id})
            started.append({"document_id": doc["document_id"], "job_id": job_id})
        await self.store.save(rec)
        return {"analysis_id": analysis_id, "started": started, "skipped": skipped}

    async def _submit_existing_pipeline(self, rec: Dict[str, Any], doc: Dict[str, Any], user: Dict[str, Any]) -> str:
        """Same job/queue path as /upload/bank-statement-async, fed from the stored (unlocked) copy."""
        from ..models.job import Job, JobType
        from ..utils.correlation import generate_job_id, get_correlation_id
        from ..utils.file_handler import get_temp_dir
        from .event_publisher import event_publisher
        from .file_history_service import file_history_service
        from .redis_job_store import redis_job_store
        from .task_processor import task_processor

        local = await asyncio.to_thread(self.storage.get, doc["storage_key"])
        if not local or not os.path.isfile(local):
            raise RuntimeError("stored file unavailable")
        bank_name = PIPELINE_BANK_NAME[doc["effective_bank"]["id"]]
        user_id, email = rec["owner_id"], rec.get("owner_email")
        full_name = (user or {}).get("name") or rec.get("owner_name") or "anonymous"
        output_dir = get_temp_dir()
        user_info = {"full_name": full_name, "account_type": "", "bank_name": bank_name, "batch_id": rec["analysis_id"], "statement_label": None}
        job = Job(
            id=generate_job_id(), type=JobType.PDF_PROCESSING, correlation_id=get_correlation_id(), user_id=user_id, bank_name=bank_name,
            input_data={
                "file_path": local, "user_info": user_info, "mode": "free", "api_key": None, "output_dir": output_dir,
                "original_filename": doc["filename"], "upload_object_key": doc["storage_key"], "batch_id": rec["analysis_id"],
                "statement_label": None, "pdf_password": None,
                "analysis": {"analysis_id": rec["analysis_id"], "document_id": doc["document_id"],
                             "detected_bank": (doc.get("bank") or doc.get("suggestion") or {}).get("id"),
                             "selected_bank": doc["effective_bank"]["id"], "layout_id": doc["layout"]["id"]},
            },
        )
        job = await redis_job_store.create_job(job)
        file_history_service.upsert_upload(
            job_id=job.id, user_id=user_id, user_email=email, user_name=rec.get("owner_name"), full_name=full_name,
            account_type=None, bank_name=bank_name, batch_id=rec["analysis_id"], statement_label=None, mode="free",
            original_filename=doc["filename"], upload_object_key=doc["storage_key"],
        )
        published = await event_publisher.publish_file_processing_request(
            job_id=job.id, file_path=local, user_info=user_info, mode="free", correlation_id=job.correlation_id, api_key=None,
            bank_name=bank_name, user_id=user_id, user_email=email, user_name=rec.get("owner_name"),
            original_filename=doc["filename"], upload_object_key=doc["storage_key"], output_dir=output_dir, pdf_password=None,
        )
        if not published:
            await task_processor.submit_existing_job(job)
        return job.id

    # ---- retention
    async def purge_expired(self, now_ts: Optional[float] = None) -> int:
        purged = 0
        for aid in await self.store.expired_ids(now_ts or time.time()):
            rec = await self.store.get(aid)
            if rec:
                for d in rec["documents"]:
                    # documents already handed to the pipeline are owned by the file-history retention sweep
                    if d.get("storage_key") and d.get("workflow_status") != "PROCESSING":
                        try:
                            self.storage.delete(d["storage_key"])
                        except Exception:
                            logger.warning("Could not delete expired analysis file")
            await self.store.delete(aid)
            purged += 1
        return purged


analysis_service = AnalysisService()
