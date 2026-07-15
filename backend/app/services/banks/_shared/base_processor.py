"""
Airco Insights — Base Bank Processor
=====================================
Single shared pipeline that every bank processor delegates to.
Banks supply a CONFIG (GenericBankConfig) and bank-specific module
instances; this class owns the entire 10-step processing loop.

Migration approach
------------------
Existing per-bank processors can adopt this base incrementally:
  1. Keep the existing bank-specific classes as type aliases.
  2. Replace the body of process() with:
         return self._run_pipeline(file_path, user_info, output_dir)
  3. Gradually migrate bank-specific overrides into the config.
"""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .data_quality import compute_data_quality
from .date_normalizer import analyze_statement_dates, normalize_date_value
from .hygiene_check import HygieneCheck
from .generic_bank import (
    GenericBankConfig,
    GenericParseError,
    GenericProcessingMetrics,
    GenericProcessingResult,
    GenericProcessorError,
    GenericReconciliationError,
    GenericStructureError,
    GenericValidationError,
)

logger = logging.getLogger(__name__)


@dataclass
class BasePipelineResult(GenericProcessingResult):
    """Extended result carrying audit + quality fields."""
    integrity_result: Any = None
    data_quality: str = "high"
    reconciliation_status: str = "passed"
    data_quality_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = super().to_dict()
        payload["stats"]["ai_classified"] = getattr(self.metrics, "ai_classified_count", 0)
        payload["validation"]["integrity_passed"] = getattr(self.metrics, "integrity_passed", False)
        payload["data_quality"] = self.data_quality
        payload["reconciliation_status"] = self.reconciliation_status
        payload["data_quality_warnings"] = self.data_quality_warnings
        return payload


class BaseBankProcessor:
    """
    Shared processing pipeline for all bank processors.

    Subclasses MUST set:
        CONFIG  = GenericBankConfig(...)
        BANK_LABEL = "CANARA"  (uppercase, used in audit template names)

    Subclasses MUST call super().__init__() and then assign:
        self.pdf_validator, self.structure_validator, self.parser,
        self.transaction_validator, self.reconciliation, self.rule_engine,
        self.ai_fallback, self.recurring_engine, self.aggregation_engine,
        self.integrity_guard
        (Excel is always LiteExcelGenerator — no per-bank formula/legacy generators.)
    """

    CONFIG: GenericBankConfig
    BANK_LABEL: str = ""

    def __init__(
        self,
        strict_mode: bool = True,
        enable_ai: bool = False,
        api_key: Optional[str] = None,
        audit_service=None,
        job_id: Optional[str] = None,
    ):
        self.strict_mode = strict_mode
        self.enable_ai = enable_ai
        self.api_key = api_key
        self.audit_service = audit_service
        self.job_id = job_id
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def _run_pipeline(
        self,
        file_path: str,
        user_info: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> BasePipelineResult:
        """Execute the 10-step bank statement processing pipeline."""
        pipeline_start = time.monotonic()
        metrics = GenericProcessingMetrics()
        cfg = self.CONFIG

        try:
            # ── STEP 1: PDF Integrity Validation ─────────────────────────────
            pdf_result = self._time_step(
                "pdf_validation",
                lambda: self.pdf_validator.validate(file_path),
                metrics,
            )

            # ── STEP 2: Bank Structure Validation ────────────────────────────
            structure_result = self._time_step(
                "structure_validation",
                lambda: self.structure_validator.validate(
                    pdf_result.text_content, pdf_result.first_page_text
                ),
                metrics,
            )

            # ── STEP 3: Transaction Parsing ───────────────────────────────────
            parse_result = self._time_step(
                "parsing",
                lambda: self.parser.parse(file_path, pdf_result.text_content),
                metrics,
            )
            if parse_result.total_count <= 0:
                raise GenericParseError(
                    f"Could not extract transactions from this {cfg.bank_name} PDF.",
                    error_code="NO_TRANSACTIONS",
                )

            # ── STEP 4: Transaction Validation ───────────────────────────────
            # Validators have two return shapes:
            #   a) Tuple[List[dict], XxxValidationResult]  (Canara, Union, IDFC, …)
            #   b) XxxValidationResult with .validated_transactions  (HDFC, SBI, Kotak, …)
            _val_raw = self._time_step(
                "transaction_validation",
                lambda: self.transaction_validator.validate(
                    [txn.to_dict() if hasattr(txn, "to_dict") else txn
                     for txn in parse_result.transactions]
                ),
                metrics,
            )
            if isinstance(_val_raw, tuple):
                validated = _val_raw[0]
            elif hasattr(_val_raw, "validated_transactions"):
                validated = _val_raw.validated_transactions
            else:
                validated = list(_val_raw)
            metrics.transaction_count = len(validated)

            # ── STEP 5: Balance Reconciliation ───────────────────────────────
            # Repair debit/credit sides from running balance when parse sides
            # are wrong (RECON-HIGH-MISMATCH accuracy path). Then reconcile.
            _recon_opening = (
                structure_result.metadata.opening_balance
                or parse_result.opening_balance
            )
            _recon_closing = (
                structure_result.metadata.closing_balance
                or parse_result.closing_balance
            )
            try:
                from app.services.pipeline.reconciliation import repair_transaction_sides

                validated, _repair_stats = repair_transaction_sides(
                    validated,
                    opening_balance=_recon_opening,
                )
                if (_repair_stats.get("swap") or 0) + (_repair_stats.get("delta_repair") or 0):
                    self.logger.info(
                        "%s recon repair: swap=%s delta=%s unfixed=%s",
                        cfg.bank_name,
                        _repair_stats.get("swap"),
                        _repair_stats.get("delta_repair"),
                        _repair_stats.get("unfixed"),
                    )
            except Exception:
                self.logger.debug("recon repair skipped", exc_info=True)

            # reconcile() returns either a plain dict or an XxxReconciliationResult object.
            _recon_raw = self._time_step(
                "reconciliation",
                lambda: self.reconciliation.reconcile(
                    validated,
                    expected_opening=_recon_opening,
                    expected_closing=_recon_closing,
                ),
                metrics,
            )
            if isinstance(_recon_raw, dict):
                reconciliation = _recon_raw
            elif hasattr(_recon_raw, "to_dict"):
                reconciliation = _recon_raw.to_dict()
            else:
                reconciliation = {"is_reconciled": getattr(_recon_raw, "is_reconciled", True)}
            # Normalise key: some dict-banks use "passed", others use "is_reconciled"
            _recon_passed = reconciliation.get("is_reconciled", reconciliation.get("passed", True))
            metrics.reconciliation_passed = bool(_recon_passed)

            # ── STEP 6: Rule Engine Classification ───────────────────────────
            classified, unclassified = self._time_step(
                "classification",
                lambda: self.rule_engine.classify(validated),
                metrics,
            )
            all_transactions: List[Dict[str, Any]] = classified
            metrics.classified_count = len(classified)
            metrics.unclassified_count = len(unclassified)

            # ── STEP 7: AI Fallback (optional) ───────────────────────────────
            ai_classified_count = 0
            if self.enable_ai and self.api_key and self.ai_fallback and unclassified:
                _ai_raw = self._time_step(
                    "ai_fallback",
                    lambda: self.ai_fallback.classify(
                        unclassified, cfg.bank_name, user_info.get("account_type", "")
                    ),
                    metrics,
                )
                # classify() returns either Tuple[list, stats] or a plain list
                ai_results = _ai_raw[0] if isinstance(_ai_raw, tuple) else _ai_raw
                ai_classified_count = sum(
                    1 for t in ai_results
                    if not str(t.get("category", "")).startswith("Others")
                )
                ai_iter = iter(ai_results)
                merged: List[Dict[str, Any]] = []
                for txn in all_transactions:
                    if str(txn.get("category", "")).startswith("Others"):
                        merged.append(next(ai_iter, txn))
                    else:
                        merged.append(txn)
                all_transactions = merged
                metrics.unclassified_count = sum(
                    1 for t in all_transactions
                    if str(t.get("category", "")).startswith("Others")
                )
            else:
                # Preserve statement order (critical for running-balance integrity).
                # classified+unclassified reorders rows and breaks recon repairs.
                by_id = {id(x): x for x in classified}
                by_id.update({id(x): x for x in unclassified})
                # Prefer category-bearing copies from engine output while keeping
                # original sequence of validated rows when possible.
                all_transactions = list(classified) + [
                    u for u in unclassified
                    if id(u) not in {id(c) for c in classified}
                ]
                # If engine returned copies, rebuild order from validated sequence keys
                def _k(txn):
                    return (
                        str(txn.get('date') or ''),
                        str(txn.get('description') or ''),
                        str(txn.get('ref_no') or txn.get('chq_no') or ''),
                        str(txn.get('debit') or ''),
                        str(txn.get('credit') or ''),
                        str(txn.get('balance') or ''),
                    )
                eng_map = {}
                for t2 in list(classified) + list(unclassified):
                    eng_map.setdefault(_k(t2), t2)
                ordered = []
                used = set()
                for src in validated:
                    key = _k(src)
                    hit = eng_map.get(key)
                    if hit is not None and id(hit) not in used:
                        ordered.append(hit)
                        used.add(id(hit))
                    else:
                        ordered.append(src)
                for t2 in list(classified) + list(unclassified):
                    if id(t2) not in used:
                        ordered.append(t2)
                        used.add(id(t2))
                all_transactions = ordered

            # Some bank-specific rule engines return the unclassified rows as a
            # subset of the main classified list (for example, Canara returns all
            # rows in the first bucket and a filtered Others bucket in the second).
            # Concatenating those buckets would duplicate those rows in Excel.
            if classified and unclassified:
                def _txn_key(txn: Dict[str, Any]) -> tuple:
                    return (
                        str(txn.get("date", "") or "").strip(),
                        str(txn.get("description", "") or "").strip(),
                        str(txn.get("ref_no", "") or txn.get("chq_no", "") or txn.get("cheque_no", "") or "").strip(),
                        str(txn.get("debit", "") or "").strip(),
                        str(txn.get("credit", "") or "").strip(),
                        str(txn.get("balance", "") or "").strip(),
                    )

                classified_keys = {_txn_key(txn) for txn in classified}
                unclassified_keys = {_txn_key(txn) for txn in unclassified}
                if unclassified_keys and unclassified_keys.issubset(classified_keys):
                    self.logger.warning(
                        "%s classifier returned %d unclassified rows already present in the main classified bucket; skipping concatenation to avoid duplicates",
                        cfg.bank_name,
                        len(unclassified),
                    )
                    all_transactions = classified


            # Always restore statement order after classification (free or hybrid).
            # Rule engines return (classified, unclassified) buckets that reorder rows
            # and undo running-balance repairs.
            def _txn_order_key(txn: Dict[str, Any]) -> tuple:
                return (
                    str(txn.get("date") or ""),
                    str(txn.get("description") or ""),
                    str(txn.get("ref_no") or txn.get("chq_no") or txn.get("cheque_no") or ""),
                    str(txn.get("debit") or ""),
                    str(txn.get("credit") or ""),
                    str(txn.get("balance") or ""),
                )

            eng_map: Dict[tuple, Dict[str, Any]] = {}
            for t2 in all_transactions:
                eng_map.setdefault(_txn_order_key(t2), t2)
            ordered: List[Dict[str, Any]] = []
            used_ids: set = set()
            for src in validated:
                key = _txn_order_key(src)
                hit = eng_map.get(key)
                if hit is not None and id(hit) not in used_ids:
                    ordered.append(hit)
                    used_ids.add(id(hit))
                else:
                    ordered.append(src)
            for t2 in all_transactions:
                if id(t2) not in used_ids:
                    ordered.append(t2)
                    used_ids.add(id(t2))
            all_transactions = ordered

            # Normalize transaction dates once so every downstream consumer sees
            # the same bank-aware ISO date values.
            for txn in all_transactions:
                normalized_date = normalize_date_value(
                    txn.get("date"),
                    bank_name=cfg.bank_name,
                )
                if normalized_date.iso_date:
                    txn["date"] = normalized_date.iso_date

            # ── STEP 8: Recurring Detection ───────────────────────────────────
            all_transactions = self._time_step(
                "recurring_detection",
                lambda: self.recurring_engine.detect(all_transactions),
                metrics,
            )
            metrics.recurring_count = sum(
                1 for t in all_transactions if t.get("is_recurring")
            )

            # ── STEP 9: Aggregation ───────────────────────────────────────────
            # Use positional args — banks use either opening=/closing= or
            # opening_balance=/closing_balance= as param names.
            _agg_opening = structure_result.metadata.opening_balance or parse_result.opening_balance
            _agg_closing = structure_result.metadata.closing_balance or parse_result.closing_balance
            _agg_raw = self._time_step(
                "aggregation",
                lambda: self.aggregation_engine.aggregate(
                    all_transactions,
                    _agg_opening,
                    _agg_closing,
                ),
                metrics,
            )
            # Normalise: some banks (unknown) return a plain dict; wrap so getattr() works.
            if isinstance(_agg_raw, dict):
                from types import SimpleNamespace
                aggregation = SimpleNamespace(**_agg_raw)
            else:
                aggregation = _agg_raw

            # ── STEP 9b: Data Integrity Guard (non-blocking) ─────────────────
            integrity_result = None
            try:
                from app.services.core.data_integrity_guard import (
                    DataIntegrityGuard, IntegrityError,
                )
                integrity_result = self._time_step(
                    "integrity_check",
                    lambda: self.integrity_guard.validate(
                        all_transactions,
                        expected_count=structure_result.metadata.expected_transaction_count,
                        expected_opening_balance=(
                            structure_result.metadata.opening_balance
                            or parse_result.opening_balance
                        ),
                        expected_closing_balance=(
                            structure_result.metadata.closing_balance
                            or parse_result.closing_balance
                        ),
                        expected_total_credits=parse_result.total_credits,
                        expected_total_debits=parse_result.total_debits,
                    ),
                    metrics,
                )
                setattr(metrics, "integrity_passed", integrity_result.is_valid)
            except Exception:
                if self.strict_mode:
                    raise
                setattr(metrics, "integrity_passed", False)

            # ── Data Quality Score ────────────────────────────────────────────
            data_quality, recon_status, dq_warnings = compute_data_quality(
                recon_passed=metrics.reconciliation_passed,
                corrections=0,
                total=len(all_transactions),
                mismatches=0 if _recon_passed else 1,
            )

            # ── STEP 10: Excel Generation ─────────────────────────────────────
            if output_dir is None:
                output_dir = os.path.dirname(file_path) or "."

            structure_meta = getattr(structure_result, "metadata", None)
            structure_meta_dict = (
                structure_meta.to_dict()
                if structure_meta is not None and hasattr(structure_meta, "to_dict")
                else {}
            )

            formula_transactions = [
                {
                    "date": t.get("date", ""),
                    "description": t.get("description", ""),
                    "debit": t.get("debit"),
                    "credit": t.get("credit"),
                    "balance": t.get("balance"),
                    "category": t.get("category", ""),
                    "confidence": t.get("confidence", ""),
                    "recurring": "Yes" if t.get("is_recurring") or t.get("recurring") else "No",
                    "ref_no": t.get("ref_no") or t.get("chq_no") or t.get("cheque_no") or t.get("reference_number") or "",
                }
                for t in all_transactions
            ]

            date_audit = analyze_statement_dates(
                all_transactions,
                bank_name=cfg.bank_name,
                header_start=getattr(structure_meta, "statement_from", None),
                header_end=getattr(structure_meta, "statement_to", None),
                header_text=getattr(pdf_result, "first_page_text", None),
            )

            def _slug(value: Any, fallback: str = "report") -> str:
                text = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip())
                text = re.sub(r"_+", "_", text).strip("_")
                return text[:48] if text else fallback

            _acct_slug = _slug(
                structure_meta_dict.get("account_number")
                or (user_info or {}).get("account_no")
                or (user_info or {}).get("account_number"),
                "account",
            )
            _bank_slug = _slug(cfg.bank_name or cfg.file_prefix or self.BANK_LABEL, "bank")
            _holder_slug = _slug(
                structure_meta_dict.get("account_holder")
                or (user_info or {}).get("full_name")
                or (user_info or {}).get("name"),
                "customer",
            )
            _period_slug = _slug(
                f"{date_audit.startdate or structure_meta_dict.get('statement_from') or ''}"
                f"_to_"
                f"{date_audit.enddate or structure_meta_dict.get('statement_to') or ''}",
                "period",
            )
            # Human-readable export name: Bank_Account_Customer_Period_shortid.xlsx
            excel_filename = (
                f"{_bank_slug}_{_acct_slug}_{_holder_slug}_{_period_slug}"
                f"_{uuid.uuid4().hex[:8]}.xlsx"
            )
            excel_path = os.path.join(output_dir, excel_filename)

            # Prefer statement-extracted identity fields; user_info only fills gaps.
            _holder = (
                structure_meta_dict.get("account_holder")
                or user_info.get("full_name")
                or user_info.get("name")
                or ""
            )
            _acct_no = (
                structure_meta_dict.get("account_number")
                or user_info.get("account_no")
                or user_info.get("account_number")
                or ""
            )
            _ifsc = structure_meta_dict.get("ifsc") or user_info.get("ifsc") or ""
            _email = structure_meta_dict.get("email") or user_info.get("email") or ""
            _mobile = (
                structure_meta_dict.get("mobile")
                or user_info.get("mobile")
                or user_info.get("phone")
                or ""
            )
            _pan = structure_meta_dict.get("pan") or user_info.get("pan") or ""
            _address = structure_meta_dict.get("address") or user_info.get("address") or ""
            _acct_type = (
                structure_meta_dict.get("account_type")
                or user_info.get("account_type")
                or ""
            )
            _joint = (
                structure_meta_dict.get("joint_holders")
                or user_info.get("jointHolderName")
                or user_info.get("joint_holders")
                or []
            )
            _open_date = (
                structure_meta_dict.get("account_open_date")
                or user_info.get("account_open_date")
                or ""
            )
            _closing = (
                structure_meta_dict.get("closing_balance")
                if structure_meta_dict.get("closing_balance") is not None
                else getattr(aggregation, "closing_balance", None)
            )
            if _closing is None and formula_transactions:
                _closing = formula_transactions[-1].get("balance")
            _opening = (
                structure_meta_dict.get("opening_balance")
                if structure_meta_dict.get("opening_balance") is not None
                else getattr(aggregation, "opening_balance", None)
            )

            excel_metadata = {
                "name": _holder,
                "accountName": _holder,
                "account_holder": _holder,
                "account_no": _acct_no,
                "account_number": _acct_no,
                "accountNumber": _acct_no,
                "statement_from": date_audit.startdate or structure_meta_dict.get("statement_from"),
                "statement_to": date_audit.enddate or structure_meta_dict.get("statement_to"),
                "date_validation_status": date_audit.status,
                "date_confidence": date_audit.date_confidence,
                "account_type": _acct_type,
                "accountType": _acct_type,
                "bank_name": cfg.bank_name,
                "bankName": cfg.bank_name,
                "ifsc": _ifsc,
                "IFSC": _ifsc,
                "mobile": _mobile,
                "email": _email,
                "pan": _pan,
                "address": _address,
                "jointHolderName": _joint,
                "joint_holders": _joint,
                "account_open_date": _open_date,
                "accountOpenDate": _open_date,
                "opening_balance": _opening if _opening is not None else 0,
                "closing_balance": _closing if _closing is not None else 0,
                "currentBalance": _closing if _closing is not None else "",
                "total_credits": getattr(aggregation, "total_credits", 0),
                "total_debits": getattr(aggregation, "total_debits", 0),
                "total_transactions": len(formula_transactions),
                "data_quality": data_quality.value,
                "reconciliation_status": recon_status,
                "data_quality_warnings": dq_warnings,
            }

            # Lite export only (shared 9-sheet generator). No formula/legacy fallback.
            from app.services.pipeline.reporting import LiteExcelGenerator

            self._time_step(
                "excel_generation",
                lambda: LiteExcelGenerator().generate(
                    formula_transactions, excel_metadata, excel_path
                ),
                metrics,
            )

            metrics.total_time_ms = round((time.monotonic() - pipeline_start) * 1000, 1)

            # ── Audit Logging ─────────────────────────────────────────────────
            if self.audit_service and self.job_id:
                try:
                    self.audit_service.finalize_job_audit(
                        self.job_id,
                        hygiene_result=getattr(self.parser, "_hygiene_result", None),
                        parser_metrics_collected=getattr(
                            self.parser, "_collected_parser_metrics", []
                        ),
                        raw_transactions=all_transactions,
                        excel_path=excel_path,
                        sheet_count=9,
                        template_used=f"{self.BANK_LABEL}_LITE",
                        generation_time_ms=int(
                            metrics.step_timings.get("excel_generation", 0)
                        ),
                        transaction_count=len(all_transactions),
                        classified_transactions=all_transactions,
                        statement_header={
                            "userid": (user_info or {}).get("user_id"),
                            "filename": (
                                (file_path or "")
                                .replace("\\", "/")
                                .rsplit("/", 1)[-1]
                            ),
                            "bankname": getattr(
                                self.parser, "BANK_NAME", cfg.bank_name
                            ),
                            "accountno": (
                                (user_info or {}).get("account_number")
                                or (user_info or {}).get("account_no")
                            ),
                            "statement_from": getattr(
                                getattr(structure_result, "metadata", None),
                                "statement_from",
                                None,
                            ),
                            "statement_to": getattr(
                                getattr(structure_result, "metadata", None),
                                "statement_to",
                                None,
                            ),
                            "header_text": getattr(pdf_result, "first_page_text", None),
                            "raw_header_text": getattr(pdf_result, "first_page_text", None),
                            "formatidentify": (
                                lambda bank_label, page_count: f"{HygieneCheck.BANK_CODE_MAP.get(bank_label, bank_label[:3].upper() if bank_label else 'UNK')}_FMT_{page_count}P"
                            )(
                                str(getattr(self.parser, "BANK_NAME", cfg.bank_name) or cfg.bank_name or "unknown").strip().lower(),
                                int(getattr(getattr(self.parser, "_hygiene_result", None), "page_count", 0) or 0),
                            ),
                        },
                    )
                except Exception as _ae:
                    self.logger.error(
                        "finalize_job_audit failed (non-fatal): %s", _ae, exc_info=True
                    )

            return BasePipelineResult(
                status="success",
                excel_path=excel_path,
                transactions=all_transactions,
                aggregation=aggregation,
                metrics=metrics,
                bank_key=cfg.bank_key,
                integrity_result=integrity_result,
                data_quality=data_quality.value,
                reconciliation_status=recon_status,
                data_quality_warnings=dq_warnings,
            )

        except Exception as exc:
            self.logger.error("%s processing failed", cfg.bank_name, exc_info=True)
            try:
                from app.services.core.pdf_integrity_validator import PDFIntegrityError
                from app.services.core.data_integrity_guard import IntegrityError
                if isinstance(exc, PDFIntegrityError):
                    error_code = exc.error_code
                elif isinstance(
                    exc,
                    (
                        GenericStructureError,
                        GenericParseError,
                        GenericValidationError,
                        GenericReconciliationError,
                    ),
                ):
                    error_code = getattr(exc, "error_code", "PROCESSING_ERROR")
                elif isinstance(exc, IntegrityError):
                    error_code = "INTEGRITY_FAILED"
                else:
                    error_code = "PROCESSING_ERROR"
            except Exception:
                error_code = "PROCESSING_ERROR"

            metrics.total_time_ms = round((time.monotonic() - pipeline_start) * 1000, 1)
            return BasePipelineResult(
                status="failed",
                excel_path=None,
                transactions=[],
                aggregation=None,
                metrics=metrics,
                bank_key=cfg.bank_key,
                error_message=str(exc),
                error_code=error_code,
            )

    @staticmethod
    def _time_step(step_name: str, func, metrics: GenericProcessingMetrics):
        started = time.time()
        result = func()
        metrics.step_timings[step_name] = round((time.time() - started) * 1000, 1)
        return result
