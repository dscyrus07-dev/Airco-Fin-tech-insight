import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from types import SimpleNamespace

from sqlalchemy import and_, or_
from sqlalchemy.exc import OperationalError

from ..core.config import settings
from ..database.models import UserFileRecord
from ..database.session import SessionLocal
from ..utils.file_handler import cleanup_file, delete_from_storage



class FileHistoryService:
    def __init__(self):
        self._fallback_records: dict[str, dict[str, Any]] = {}

    def _record_value(self, record: Any, key: str, default: Any = None) -> Any:
        if isinstance(record, dict):
            return record.get(key, default)
        return getattr(record, key, default)

    def _format_batch_label(self, batch_id: str | None) -> str | None:
        if not batch_id:
            return None
        return batch_id if len(batch_id) <= 18 else f"{batch_id[:18]}…"

    def _format_batch_display_name(
        self,
        batch_id: str | None,
        bank_names: list[str],
        file_names: list[str] | None = None,
    ) -> str | None:
        banks = ", ".join(sorted(name for name in bank_names if name))
        files = [name for name in (file_names or []) if name]
        if len(files) == 1 and banks:
            return f"{files[0]} • {banks}"
        if len(files) == 1:
            return files[0]
        if files and banks:
            return f"{len(files)} files • {banks}"
        if files:
            return f"{len(files)} files"
        if banks:
            return banks
        return self._format_batch_label(batch_id)

    def _format_entry_display_name(self, record: Any, entry_type: str) -> str:
        bank_name = self._record_value(record, "bank_name") or "Unknown bank"
        statement_label = self._record_value(record, "statement_label")
        original_filename = self._record_value(record, "original_filename")
        report_filename = self._record_value(record, "report_filename")

        if entry_type == "report":
            if report_filename:
                return report_filename
            if original_filename:
                base = original_filename.rsplit(".", 1)[0]
                return f"{base}.xlsx"
            if statement_label:
                return f"{statement_label}.xlsx"
            return f"{bank_name} report"

        if original_filename:
            return original_filename
        if statement_label:
            return statement_label
        return f"{bank_name} statement"

    def _retention_expires_at(self, created_at: datetime | None) -> datetime | None:
        if not created_at:
            return None
        return created_at + timedelta(days=settings.DATA_RETENTION_DAYS)

    def _retention_days_left(self, retention_expires_at: datetime | None, current_time: datetime | None = None) -> int | None:
        if not retention_expires_at:
            return None
        now = current_time or datetime.now(timezone.utc)
        # Ensure both datetimes are offset-naive for comparison
        if retention_expires_at.tzinfo is not None:
            retention_expires_at = retention_expires_at.replace(tzinfo=None)
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        remaining_seconds = (retention_expires_at - now).total_seconds()
        if remaining_seconds <= 0:
            return 0
        return max(1, math.ceil(remaining_seconds / 86400))

    def _retention_status_label(self, record: Any, current_time: datetime | None = None) -> str:
        deletion_status = str(self._record_value(record, "deletion_status") or "active").lower()
        deleted_at = self._record_value(record, "deleted_at")
        deletion_requested_at = self._record_value(record, "deletion_requested_at")
        retention_expires_at = self._record_value(record, "retention_expires_at")
        if deletion_status == "deleted" or deleted_at:
            return "Deleted"
        if deletion_status in {"deleting", "scheduled"} or deletion_requested_at:
            return "Queued for deletion"
        days_left = self._retention_days_left(retention_expires_at, current_time=current_time)
        if days_left is None:
            return "Retention pending"
        if days_left <= 0:
            return "Deletes today"
        if days_left == 1:
            return "1 day left"
        return f"{days_left} days left"

    def _entry_payload(self, record: Any, entry_type: str, current_time: datetime | None = None) -> dict[str, Any]:
        created_at = self._record_value(record, "created_at")
        retention_expires_at = self._record_value(record, "retention_expires_at") or self._retention_expires_at(created_at)
        deletion_requested_at = self._record_value(record, "deletion_requested_at")
        deleted_at = self._record_value(record, "deleted_at")
        deletion_reason = self._record_value(record, "deletion_reason")
        deletion_status = self._record_value(record, "deletion_status") or "active"
        backup_purge_due_at = self._record_value(record, "backup_purge_due_at")
        backup_purge_status = self._record_value(record, "backup_purge_status")

        return {
            "job_id": self._record_value(record, "job_id"),
            "name": self._format_entry_display_name(record, entry_type),
            "display_name": self._format_entry_display_name(record, entry_type),
            "bank_name": self._record_value(record, "bank_name"),
            "account_type": self._record_value(record, "account_type"),
            "mode": self._record_value(record, "mode"),
            "batch_id": self._record_value(record, "batch_id"),
            "statement_label": self._record_value(record, "statement_label"),
            "status": self._record_value(record, "status"),
            "created_at": created_at.isoformat() if created_at else None,
            "upload_object_key": self._record_value(record, "upload_object_key") if entry_type == "upload" else None,
            "report_object_key": self._record_value(record, "report_object_key") if entry_type == "report" else self._record_value(record, "report_object_key"),
            "total_transactions": self._record_value(record, "total_transactions"),
            "retention_expires_at": retention_expires_at.isoformat() if retention_expires_at else None,
            "retention_days_left": self._retention_days_left(retention_expires_at, current_time=current_time),
            "retention_status": self._retention_status_label(record, current_time=current_time),
            "deletion_requested_at": deletion_requested_at.isoformat() if deletion_requested_at else None,
            "deleted_at": deleted_at.isoformat() if deleted_at else None,
            "deletion_reason": deletion_reason,
            "deletion_status": deletion_status,
            "backup_purge_due_at": backup_purge_due_at.isoformat() if backup_purge_due_at else None,
            "backup_purge_status": backup_purge_status,
        }

    def _delete_storage_artifacts(self, record: Any) -> None:
        upload_object_key = self._record_value(record, "upload_object_key")
        report_object_key = self._record_value(record, "report_object_key")
        report_filename = self._record_value(record, "report_filename")

        if upload_object_key:
            delete_from_storage(settings.S3_BUCKET_UPLOADS, upload_object_key)
        if report_object_key:
            delete_from_storage(settings.S3_BUCKET_REPORTS, report_object_key)

        if report_filename:
            cleanup_file(os.path.join(settings.TEMP_DIR, report_filename))

    def _mark_deleted_record(self, record: Any, *, reason: str, current_time: datetime | None = None) -> None:
        now = current_time or datetime.now(timezone.utc)
        retention_expires_at = self._record_value(record, "retention_expires_at") or self._retention_expires_at(self._record_value(record, "created_at"))

        if isinstance(record, dict):
            record["deletion_requested_at"] = record.get("deletion_requested_at") or now
            record["deleted_at"] = now
            record["deletion_reason"] = reason
            record["deletion_status"] = "deleted"
            record["backup_purge_due_at"] = record.get("backup_purge_due_at") or retention_expires_at or now
            record["backup_purge_status"] = "complete"
            record["status"] = "deleted"
            record["updated_at"] = now
            return

        record.deletion_requested_at = record.deletion_requested_at or now
        record.deleted_at = now
        record.deletion_reason = reason
        record.deletion_status = "deleted"
        record.backup_purge_due_at = record.backup_purge_due_at or retention_expires_at or now
        record.backup_purge_status = "complete"
        record.status = "deleted"
        record.updated_at = now

    def _make_fallback_record(
        self,
        *,
        job_id: str,
        user_id: str,
        original_filename: str,
    ) -> dict[str, Any]:
        existing = self._fallback_records.get(job_id, {})
        record = {
            "job_id": job_id,
            "user_id": user_id,
            "user_email": existing.get("user_email"),
            "user_name": existing.get("user_name"),
            "full_name": existing.get("full_name"),
            "account_type": existing.get("account_type"),
            "bank_name": existing.get("bank_name"),
            "batch_id": existing.get("batch_id"),
            "statement_label": existing.get("statement_label"),
            "mode": existing.get("mode"),
            "original_filename": original_filename,
            "upload_object_key": existing.get("upload_object_key"),
            "report_object_key": existing.get("report_object_key"),
            "report_filename": existing.get("report_filename"),
            "retention_expires_at": existing.get("retention_expires_at") or self._retention_expires_at(existing.get("created_at") or datetime.now(timezone.utc)),
            "deletion_requested_at": existing.get("deletion_requested_at"),
            "deleted_at": existing.get("deleted_at"),
            "deletion_reason": existing.get("deletion_reason"),
            "deletion_status": existing.get("deletion_status", "active"),
            "backup_purge_due_at": existing.get("backup_purge_due_at") or self._retention_expires_at(existing.get("created_at") or datetime.now(timezone.utc)),
            "backup_purge_status": existing.get("backup_purge_status", "pending"),
            "status": existing.get("status", "uploaded"),
            "total_transactions": existing.get("total_transactions"),
            "error_message": existing.get("error_message"),
            "created_at": existing.get("created_at") or datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "completed_at": existing.get("completed_at"),
        }
        self._fallback_records[job_id] = record
        return record

    def _fallback_namespace(self, record: dict[str, Any] | None) -> SimpleNamespace | None:
        return SimpleNamespace(**record) if record else None

    def _fallback_list_for_user(self, user_id: str) -> dict:
        records = [
            record
            for record in self._fallback_records.values()
            if record.get("user_id") == user_id
            and str(record.get("deletion_status") or "active").lower() != "deleted"
            and str(record.get("status") or "").lower() != "deleted"
        ]
        records.sort(key=lambda item: item.get("created_at") or datetime.now(timezone.utc), reverse=True)

        uploads: list[dict[str, Any]] = []
        reports: list[dict[str, Any]] = []
        processed_count = 0
        batch_groups: dict[str, dict[str, Any]] = {}

        for record in records:
            created_at = record.get("created_at")
            created_at_iso = created_at.isoformat() if created_at else None
            if record.get("status") == "completed":
                processed_count += 1

            batch_key = record.get("batch_id") or record.get("job_id")
            batch_group = batch_groups.setdefault(
                batch_key,
                {
                    "batch_id": record.get("batch_id") or record.get("job_id"),
                    "created_at": created_at_iso,
                    "updated_at": created_at_iso,
                    "display_name": None,
                    "file_names": [],
                    "bank_names": [],
                    "statement_count": 0,
                    "processed_count": 0,
                    "failed_count": 0,
                    "uploads": [],
                    "reports": [],
                    "bank_groups": {},
                },
            )

            if created_at_iso and (batch_group["created_at"] is None or created_at_iso < batch_group["created_at"]):
                batch_group["created_at"] = created_at_iso
            if created_at_iso and (batch_group["updated_at"] is None or created_at_iso > batch_group["updated_at"]):
                batch_group["updated_at"] = created_at_iso

            bank_name = record.get("bank_name")
            if bank_name and bank_name not in batch_group["bank_names"]:
                batch_group["bank_names"].append(bank_name)

            file_name = record.get("original_filename") or record.get("statement_label")
            if file_name and file_name not in batch_group["file_names"]:
                batch_group["file_names"].append(file_name)

            batch_group["display_name"] = self._format_batch_display_name(
                batch_group["batch_id"],
                batch_group["bank_names"],
                batch_group["file_names"],
            )

            batch_group["statement_count"] += 1
            if record.get("status") == "completed":
                batch_group["processed_count"] += 1
            elif record.get("status") == "failed":
                batch_group["failed_count"] += 1

            upload_entry = self._entry_payload(record, "upload")
            uploads.append(upload_entry)
            batch_group["uploads"].append(upload_entry)

            bank_key = bank_name or "Unknown"
            bank_group = batch_group["bank_groups"].setdefault(
                bank_key,
                {
                    "bank_name": bank_key,
                    "statement_count": 0,
                    "processed_count": 0,
                    "failed_count": 0,
                    "uploads": [],
                    "reports": [],
                },
            )
            bank_group["statement_count"] += 1
            if record.get("status") == "completed":
                bank_group["processed_count"] += 1
            elif record.get("status") == "failed":
                bank_group["failed_count"] += 1
            bank_group["uploads"].append(upload_entry)

            if record.get("status") == "completed":
                report_entry = self._entry_payload(record, "report")
                reports.append(report_entry)
                batch_group["reports"].append(report_entry)
                bank_group["reports"].append(report_entry)

        latest = records[0] if records else None
        return {
            "summary": {
                "total_uploads": len(records),
                "processed_files": processed_count,
                "generated_reports": len(reports),
                "total_batches": len(batch_groups),
                "latest_account_type": latest.get("account_type") if latest else None,
            },
            "uploads": uploads,
            "reports": reports,
            "batches": [
                {
                    **{k: v for k, v in batch.items() if k != "file_names"},
                    "bank_names": sorted(batch["bank_names"]),
                    "bank_groups": sorted(batch["bank_groups"].values(), key=lambda group: group["bank_name"].lower()),
                }
                for batch in batch_groups.values()
            ],
        }

    def _fallback_delete(self, user_id: str, job_id: str) -> bool:
        record = self._fallback_records.get(job_id)
        if not record or record.get("user_id") != user_id:
            return False
        if str(record.get("deletion_status") or "active").lower() == "deleted":
            return True
        self._delete_storage_artifacts(record)
        self._mark_deleted_record(record, reason="manual deletion requested")
        return True

    def get_by_job_id(self, job_id: str) -> UserFileRecord | None:
        db = SessionLocal()
        try:
            return db.query(UserFileRecord).filter(UserFileRecord.job_id == job_id).first()
        except OperationalError:
            return self._fallback_namespace(self._fallback_records.get(job_id))
        finally:
            db.close()

    def list_all(self) -> list[UserFileRecord]:
        db = SessionLocal()
        try:
            return db.query(UserFileRecord).order_by(UserFileRecord.created_at.desc()).all()
        except OperationalError:
            return [
                self._fallback_namespace(record)
                for record in sorted(self._fallback_records.values(), key=lambda item: item.get("created_at") or datetime.now(timezone.utc), reverse=True)
            ]
        finally:
            db.close()

    def upsert_upload(
        self,
        *,
        job_id: str,
        user_id: str,
        user_email: str | None,
        user_name: str | None,
        full_name: str | None,
        account_type: str | None,
        bank_name: str | None,
        batch_id: str | None,
        statement_label: str | None,
        mode: str | None,
        original_filename: str,
        upload_object_key: str | None,
        api_key_id: str | None = None,
    ) -> None:
        db = SessionLocal()
        try:
            record = db.query(UserFileRecord).filter(UserFileRecord.job_id == job_id).first()
            if record is None:
                record = UserFileRecord(job_id=job_id, user_id=user_id, original_filename=original_filename)
                db.add(record)
                db.flush()

            record.user_email = user_email
            record.user_name = user_name
            record.full_name = full_name
            record.account_type = account_type
            record.bank_name = bank_name
            record.batch_id = batch_id
            record.statement_label = statement_label
            record.mode = mode
            record.original_filename = original_filename
            record.upload_object_key = upload_object_key
            if api_key_id:
                record.api_key_id = api_key_id
            record.status = "uploaded"
            record.retention_expires_at = record.retention_expires_at or self._retention_expires_at(record.created_at or datetime.now(timezone.utc))
            record.deletion_status = record.deletion_status or "active"
            record.backup_purge_due_at = record.backup_purge_due_at or record.retention_expires_at
            record.backup_purge_status = record.backup_purge_status or "pending"
            db.commit()
        except OperationalError:
            record = self._make_fallback_record(job_id=job_id, user_id=user_id, original_filename=original_filename)
            record.update(
                {
                    "user_email": user_email,
                    "user_name": user_name,
                    "full_name": full_name,
                    "account_type": account_type,
                    "bank_name": bank_name,
                    "batch_id": batch_id,
                    "statement_label": statement_label,
                    "mode": mode,
                    "original_filename": original_filename,
                    "upload_object_key": upload_object_key,
                    "retention_expires_at": record.get("retention_expires_at") or self._retention_expires_at(record.get("created_at")),
                    "deletion_status": record.get("deletion_status") or "active",
                    "backup_purge_due_at": record.get("backup_purge_due_at") or self._retention_expires_at(record.get("created_at")),
                    "backup_purge_status": record.get("backup_purge_status") or "pending",
                    "status": "uploaded",
                    "updated_at": datetime.now(timezone.utc),
                }
            )
        finally:
            db.close()

    def mark_running(self, job_id: str) -> None:
        db = SessionLocal()
        try:
            record = db.query(UserFileRecord).filter(UserFileRecord.job_id == job_id).first()
            if record:
                record.status = "running"
                db.commit()
        except OperationalError:
            record = self._fallback_records.get(job_id)
            if record:
                record["status"] = "running"
                record["updated_at"] = datetime.now(timezone.utc)
        finally:
            db.close()

    def mark_completed(self, job_id: str, result_data: Dict[str, Any]) -> None:
        db = SessionLocal()
        try:
            record = db.query(UserFileRecord).filter(UserFileRecord.job_id == job_id).first()
            if not record:
                return

            record.status = "completed"
            record.completed_at = datetime.now(timezone.utc)
            record.report_object_key = result_data.get("excel_object_key")
            record.report_filename = os.path.basename(result_data.get("excel_path") or "") or None
            record.retention_expires_at = record.retention_expires_at or self._retention_expires_at(record.created_at or datetime.now(timezone.utc))
            record.deletion_status = record.deletion_status or "active"
            record.backup_purge_due_at = record.backup_purge_due_at or record.retention_expires_at
            record.backup_purge_status = record.backup_purge_status or "pending"
            stats = result_data.get("stats") or {}
            total_transactions = stats.get("total_transactions")
            record.total_transactions = int(total_transactions) if total_transactions is not None else None
            record.error_message = None
            db.commit()
        except OperationalError:
            record = self._fallback_records.get(job_id)
            if record:
                record["status"] = "completed"
                record["completed_at"] = datetime.now(timezone.utc)
                record["report_object_key"] = result_data.get("excel_object_key")
                record["report_filename"] = os.path.basename(result_data.get("excel_path") or "") or None
                record["retention_expires_at"] = record.get("retention_expires_at") or self._retention_expires_at(record.get("created_at"))
                record["deletion_status"] = record.get("deletion_status") or "active"
                record["backup_purge_due_at"] = record.get("backup_purge_due_at") or record.get("retention_expires_at")
                record["backup_purge_status"] = record.get("backup_purge_status") or "pending"
                stats = result_data.get("stats") or {}
                total_transactions = stats.get("total_transactions")
                record["total_transactions"] = int(total_transactions) if total_transactions is not None else None
                record["error_message"] = None
                record["updated_at"] = datetime.now(timezone.utc)
        finally:
            db.close()

    def mark_failed(self, job_id: str, error_message: str | None) -> None:
        db = SessionLocal()
        try:
            record = db.query(UserFileRecord).filter(UserFileRecord.job_id == job_id).first()
            if record:
                record.status = "failed"
                record.error_message = error_message
                record.retention_expires_at = record.retention_expires_at or self._retention_expires_at(record.created_at or datetime.now(timezone.utc))
                record.deletion_status = record.deletion_status or "active"
                record.backup_purge_due_at = record.backup_purge_due_at or record.retention_expires_at
                record.backup_purge_status = record.backup_purge_status or "pending"
                db.commit()
        except OperationalError:
            record = self._fallback_records.get(job_id)
            if record:
                record["status"] = "failed"
                record["error_message"] = error_message
                record["retention_expires_at"] = record.get("retention_expires_at") or self._retention_expires_at(record.get("created_at"))
                record["deletion_status"] = record.get("deletion_status") or "active"
                record["backup_purge_due_at"] = record.get("backup_purge_due_at") or record.get("retention_expires_at")
                record["backup_purge_status"] = record.get("backup_purge_status") or "pending"
                record["updated_at"] = datetime.now(timezone.utc)
        finally:
            db.close()

    def mark_cancelled(self, job_id: str) -> None:
        db = SessionLocal()
        try:
            record = db.query(UserFileRecord).filter(UserFileRecord.job_id == job_id).first()
            if record:
                record.status = "cancelled"
                record.error_message = None
                db.commit()
        except OperationalError:
            record = self._fallback_records.get(job_id)
            if record:
                record["status"] = "cancelled"
                record["error_message"] = None
                record["updated_at"] = datetime.now(timezone.utc)
        finally:
            db.close()

    def list_for_user(self, user_id: str) -> dict:
        db = SessionLocal()
        try:
            # Join with statement_metadata if available
            try:
                from ..database.audit_models import StatementMetadata
                records = (
                    db.query(UserFileRecord, StatementMetadata)
                    .outerjoin(StatementMetadata, UserFileRecord.job_id == StatementMetadata.job_id)
                    .filter(UserFileRecord.user_id == user_id)
                    .filter(
                        (UserFileRecord.deletion_status.is_(None))
                        | (UserFileRecord.deletion_status != "deleted")
                    )
                    .filter(
                        (UserFileRecord.status.is_(None))
                        | (UserFileRecord.status != "deleted")
                    )
                    .order_by(UserFileRecord.created_at.desc())
                    .all()
                )
                has_metadata = True
            except Exception:
                # Fallback if statement_metadata table doesn't exist yet
                records = (
                    db.query(UserFileRecord)
                    .filter(UserFileRecord.user_id == user_id)
                    .filter(
                        (UserFileRecord.deletion_status.is_(None))
                        | (UserFileRecord.deletion_status != "deleted")
                    )
                    .filter(
                        (UserFileRecord.status.is_(None))
                        | (UserFileRecord.status != "deleted")
                    )
                    .order_by(UserFileRecord.created_at.desc())
                    .all()
                )
                has_metadata = False

            uploads: list[dict[str, Any]] = []
            reports: list[dict[str, Any]] = []
            processed_count = 0
            batch_groups: dict[str, dict[str, Any]] = {}

            for row in records:
                if has_metadata:
                    record, metadata = row
                else:
                    record, metadata = row, None

                created_at = record.created_at.isoformat() if record.created_at else None
                if record.status == "completed":
                    processed_count += 1

                batch_key = record.batch_id or record.job_id
                batch_group = batch_groups.setdefault(
                    batch_key,
                    {
                        "batch_id": record.batch_id or record.job_id,
                        "created_at": created_at,
                        "updated_at": created_at,
                        "display_name": None,
                        "file_names": [],
                        "bank_names": [],
                        "statement_count": 0,
                        "processed_count": 0,
                        "failed_count": 0,
                        "uploads": [],
                        "reports": [],
                        "bank_groups": {},
                    },
                )

                if created_at and (batch_group["created_at"] is None or created_at < batch_group["created_at"]):
                    batch_group["created_at"] = created_at
                if created_at and (batch_group["updated_at"] is None or created_at > batch_group["updated_at"]):
                    batch_group["updated_at"] = created_at

                if record.bank_name and record.bank_name not in batch_group["bank_names"]:
                    batch_group["bank_names"].append(record.bank_name)

                file_name = record.original_filename or record.statement_label
                if file_name and file_name not in batch_group["file_names"]:
                    batch_group["file_names"].append(file_name)

                batch_group["display_name"] = self._format_batch_display_name(
                    batch_group["batch_id"],
                    batch_group["bank_names"],
                    batch_group["file_names"],
                )

                batch_group["statement_count"] += 1
                if record.status == "completed":
                    batch_group["processed_count"] += 1
                elif record.status == "failed":
                    batch_group["failed_count"] += 1

                upload_entry = self._entry_payload(record, "upload")
                # Add statement metadata if available
                if metadata:
                    metadata_extra = metadata.extra if isinstance(getattr(metadata, "extra", None), dict) else {}
                    upload_entry["statement_metadata"] = {
                        "has_salary": metadata.havesalary,
                        "salary_count": metadata.noofsalarycredit,
                        "salary_amount": float(metadata.amtofsalarycredit) if metadata.amtofsalarycredit else 0,
                        "has_loan_repayment": metadata.hasloanrepayment,
                        "loan_repayment_count": metadata.noofloanrepayments,
                        "loan_repayment_amount": float(metadata.amtofloanrepayments) if metadata.amtofloanrepayments else 0,
                        "total_credits": metadata.noofcredits,
                        "total_credits_amount": float(metadata.amtofcredits) if metadata.amtofcredits else 0,
                        "total_debits": metadata.noofdebits,
                        "total_debits_amount": float(metadata.amtofdebits) if metadata.amtofdebits else 0,
                        "statement_profile": metadata_extra.get("statement_profile"),
                        "financial_profile": metadata_extra.get("financial_profile"),
                    }
                uploads.append(upload_entry)
                batch_group["uploads"].append(upload_entry)

                bank_key = record.bank_name or "Unknown"
                bank_group = batch_group["bank_groups"].setdefault(
                    bank_key,
                    {
                        "bank_name": bank_key,
                        "statement_count": 0,
                        "processed_count": 0,
                        "failed_count": 0,
                        "uploads": [],
                        "reports": [],
                    },
                )
                bank_group["statement_count"] += 1
                if record.status == "completed":
                    bank_group["processed_count"] += 1
                elif record.status == "failed":
                    bank_group["failed_count"] += 1
                bank_group["uploads"].append(upload_entry)

                if record.status == "completed":
                    report_entry = self._entry_payload(record, "report")
                    # Add statement metadata if available
                    if metadata:
                        metadata_extra = metadata.extra if isinstance(getattr(metadata, "extra", None), dict) else {}
                        report_entry["statement_metadata"] = {
                            "has_salary": metadata.havesalary,
                            "salary_count": metadata.noofsalarycredit,
                            "salary_amount": float(metadata.amtofsalarycredit) if metadata.amtofsalarycredit else 0,
                            "has_loan_repayment": metadata.hasloanrepayment,
                            "loan_repayment_count": metadata.noofloanrepayments,
                            "loan_repayment_amount": float(metadata.amtofloanrepayments) if metadata.amtofloanrepayments else 0,
                            "total_credits": metadata.noofcredits,
                            "total_credits_amount": float(metadata.amtofcredits) if metadata.amtofcredits else 0,
                            "total_debits": metadata.noofdebits,
                            "total_debits_amount": float(metadata.amtofdebits) if metadata.amtofdebits else 0,
                            "statement_profile": metadata_extra.get("statement_profile"),
                            "financial_profile": metadata_extra.get("financial_profile"),
                        }
                    reports.append(report_entry)
                    batch_group["reports"].append(report_entry)
                    bank_group["reports"].append(report_entry)

            # Extract UserFileRecord from tuple if using outerjoin (has_metadata=True)
            latest = records[0] if records else None
            if latest and isinstance(latest, tuple):
                latest = latest[0]  # Extract UserFileRecord from (UserFileRecord, StatementMetadata) tuple
            # Use getattr with default to safely access account_type
            latest_account_type = getattr(latest, 'account_type', None) if latest else None
            return {
                "summary": {
                    "total_uploads": len(records),
                    "processed_files": processed_count,
                    "generated_reports": len(reports),
                    "total_batches": len(batch_groups),
                    "latest_account_type": latest_account_type,
                },
                "uploads": uploads,
                "reports": reports,
                "batches": [
                    {
                        **{k: v for k, v in batch.items() if k != "file_names"},
                        "bank_names": sorted(batch["bank_names"]),
                        "bank_groups": sorted(batch["bank_groups"].values(), key=lambda group: group["bank_name"].lower()),
                    }
                    for batch in batch_groups.values()
                ],
            }
        except OperationalError:
            return self._fallback_list_for_user(user_id)
        finally:
            db.close()

    def delete_file(self, user_id: str, job_id: str) -> bool:
        """Delete a file record for a user."""
        db = SessionLocal()
        try:
            record = db.query(UserFileRecord).filter(
                UserFileRecord.user_id == user_id,
                UserFileRecord.job_id == job_id,
            ).first()

            if record is None:
                return False

            if str(record.deletion_status or "active").lower() == "deleted":
                return True

            self._delete_storage_artifacts(record)
            self._mark_deleted_record(record, reason="manual deletion requested")
            db.commit()
            return True
        except OperationalError:
            return self._fallback_delete(user_id, job_id)
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def list_expired_records(self) -> list[UserFileRecord]:
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(days=settings.DATA_RETENTION_DAYS)
            return (
                db.query(UserFileRecord)
                .filter(
                    or_(
                        UserFileRecord.retention_expires_at <= now,
                        and_(
                            UserFileRecord.retention_expires_at.is_(None),
                            UserFileRecord.created_at <= cutoff,
                        ),
                    )
                )
                .filter((UserFileRecord.deletion_status.is_(None)) | (UserFileRecord.deletion_status != "deleted"))
                .order_by(UserFileRecord.retention_expires_at.asc())
                .all()
            )
        except OperationalError:
            now = datetime.now(timezone.utc)
            return [
                self._fallback_namespace(record)
                for record in sorted(
                    self._fallback_records.values(),
                    key=lambda item: item.get("retention_expires_at") or item.get("created_at") or now,
                )
                if (record.get("retention_expires_at") or self._retention_expires_at(record.get("created_at")))
                and (record.get("retention_expires_at") or self._retention_expires_at(record.get("created_at"))) <= now
                and str(record.get("deletion_status") or "active").lower() != "deleted"
            ]
        finally:
            db.close()

    def purge_expired_record(self, record: Any, *, reason: str = "retention expired") -> bool:
        """Physically delete storage artifacts and mark the file record as deleted."""
        if not record:
            return False

        try:
            self._delete_storage_artifacts(record)
            self._mark_deleted_record(record, reason=reason)
            db = SessionLocal()
            try:
                if isinstance(record, UserFileRecord):
                    db.merge(record)
                    db.commit()
                elif isinstance(record, dict):
                    db_record = db.query(UserFileRecord).filter(UserFileRecord.job_id == record.get("job_id")).first()
                    if db_record:
                        self._mark_deleted_record(db_record, reason=reason)
                        db.commit()
                return True
            finally:
                db.close()
        except Exception:
            return False


file_history_service = FileHistoryService()
