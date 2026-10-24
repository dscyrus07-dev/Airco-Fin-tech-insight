"""
Airco Insights — Pipeline Orchestrator (Bank-Specific Architecture)
=======================================================================
Accuracy-first pipeline that routes to bank-specific processors.

ARCHITECTURE:
- User selects bank → No auto-detection needed
- Each bank has its own processor (BaseBankProcessor)
- Shared post-parse steps under app.services.pipeline
  (classification, reconciliation, aggregation, recurring, reporting)
- 100% validation before output

Supported Banks:
- HDFC (complete)
- ICICI (complete)
- Axis (complete)
- Kotak (complete)
- SBI (complete)

Design Principles:
- Bank-specific intelligence
- Deterministic parsing
- Strict validation at every step
- NO partial output
- Accuracy > Speed
"""

import importlib
import logging
import os
import time
from typing import Any, Dict, Optional, Type

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PipelineError(Exception):
    """Base exception for pipeline errors."""
    def __init__(self, message: str, stage: str = "unknown", error_code: str = "UNKNOWN"):
        self.stage = stage
        self.error_code = error_code
        self.message = message          # without the "[stage]" prefix str() adds, so re-wrapping cannot repeat it
        super().__init__(f"[{stage}] {message}")


class PipelineValidationError(PipelineError):
    """Input validation failed."""
    pass


class PipelineAbortError(PipelineError):
    """Non-recoverable failure."""
    pass


class UnsupportedBankError(PipelineError):
    """Bank not supported in new architecture."""
    pass


def _as_abort(e: BaseException) -> "PipelineAbortError":
    """The one exception a failed processing step surfaces as.

    A PipelineError's str() already carries its "[stage]" prefix, so re-wrapping one with str(e) printed the
    stage twice — "[ocr_reader] [ocr_reader] Scanned statement could not be read" (R10-B5), on every staged
    failure that passed through process_statement's handler. An abort now passes through untouched, and any
    other staged error is converted from its own message."""
    if isinstance(e, PipelineAbortError):
        return e
    if isinstance(e, PipelineError):
        return PipelineAbortError(e.message, stage=e.stage, error_code=e.error_code)
    if hasattr(e, "stage") and hasattr(e, "error_code"):
        return PipelineAbortError(str(e), stage=e.stage, error_code=e.error_code)
    return PipelineAbortError(f"Processing failed: {str(e)}", stage="bank_processor", error_code="PROCESSOR_ERROR")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_MODES = ("free", "hybrid")
try:  # one source of truth with the analysis stage (core.config.settings.MAX_FILE_SIZE_MB)
    from app.core.config import settings as _settings
    MAX_FILE_SIZE_BYTES = int(_settings.MAX_FILE_SIZE_BYTES)
except Exception:  # pragma: no cover - config import problem must not break the pipeline
    MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTENSIONS = (".pdf",)

# Supported banks with their processor modules
SUPPORTED_BANKS = {
    "hdfc": "HDFC Bank",
    "hdfc bank": "HDFC Bank",
    "icici": "ICICI Bank",
    "icici bank": "ICICI Bank",
    "axis": "Axis Bank",
    "axis bank": "Axis Bank",
    "kotak": "Kotak Bank",
    "kotak bank": "Kotak Bank",
    "sbi": "SBI",
    "state bank": "SBI",
    "canara": "Canara Bank",
    "canara bank": "Canara Bank",
    "idfc": "IDFC Bank",
    "idfc bank": "IDFC Bank",
    "idfc first": "IDFC Bank",
    "idfc first bank": "IDFC Bank",
    "karnataka": "Karnataka Bank",
    "karnataka bank": "Karnataka Bank",
    "paytm": "Paytm Bank",
    "paytm bank": "Paytm Bank",
    "union": "Union Bank of India",
    "union bank": "Union Bank of India",
    "union bank of india": "Union Bank of India",
    "bank of baroda": "Bank of Baroda",
    "bankofbaroda": "Bank of Baroda",
    "bob": "Bank of Baroda",
    "bank of india": "Bank of India",
    "bankofindia": "Bank of India",
    "bank_of_india": "Bank of India",
    "indian bank": "Indian Bank",
    "indianbank": "Indian Bank",
    "indian_bank": "Indian Bank",
    "unknown": "Unknown",
    "unknown bank": "Unknown",
}

SUPPORTED_BANK_PROCESSORS = {
    "hdfc": "hdfc",
    "hdfc bank": "hdfc",
    "icici": "icici",
    "icici bank": "icici",
    "axis": "axis",
    "axis bank": "axis",
    "kotak": "kotak",
    "kotak bank": "kotak",
    "sbi": "sbi",
    "state bank": "sbi",
    "canara": "canara",
    "canara bank": "canara",
    "idfc": "idfc",
    "idfc bank": "idfc",
    "idfc first": "idfc",
    "idfc first bank": "idfc",
    "karnataka": "karnataka",
    "karnataka bank": "karnataka",
    "paytm": "paytm",
    "paytm bank": "paytm",
    "union": "union",
    "union bank": "union",
    "union bank of india": "union",
    "bank of baroda": "bank_of_baroda",
    "bankofbaroda": "bank_of_baroda",
    "bob": "bank_of_baroda",
    "bank of india": "bank_of_india",
    "bankofindia": "bank_of_india",
    "bank_of_india": "bank_of_india",
    # south_indian has no legacy processor; the spec key is the pipeline key.
    "south indian bank": "south_indian",
    "southindianbank": "south_indian",
    "indian bank": "indian_bank",
    "indianbank": "indian_bank",
    "indian_bank": "indian_bank",
    # v2-served banks with no legacy processor: display names -> spec keys.
    # The bank key reaches the v2 serving plan; processor lookup returns None.
    "indusind": "indusind",
    "indusind bank": "indusind",
    "citibank": "citibank",
    "citi bank": "citibank",
    "city union": "city_union",
    "city union bank": "city_union",
    # v2-only onboarded banks (no legacy processor): display name -> spec key.
    # Exact-match entries only; the substring scan below never sees these.
    "standard chartered": "scb",
    "standard chartered bank": "scb",
    "scb": "scb",
    "dbs": "dbs",
    "dbs bank": "dbs",
    "ujjivan": "ujjivan_sfb",
    "ujjivan small finance": "ujjivan_sfb",
    "ujjivan small finance bank": "ujjivan_sfb",
    "au small finance bank": "au_sfb",
    "au sfb": "au_sfb",
    "au bank": "au_sfb",
    "dcb": "dcb",
    "dcb bank": "dcb",
    "federal": "federal",
    "federal bank": "federal",
    "idbi": "idbi",
    "idbi bank": "idbi",
    "yes": "yes",
    "yes bank": "yes",
    "punjab national bank": "pnb",
    "pnb": "pnb",
    "karur vysya": "kvb",
    "karur vysya bank": "kvb",
    "kvb": "kvb",
    "indian overseas bank": "iob",
    "iob": "iob",
    "central bank of india": "central_bank",
    "central bank": "central_bank",
    "equitas": "equitas_sfb",
    "equitas small finance": "equitas_sfb",
    "equitas small finance bank": "equitas_sfb",
    "bank of maharashtra": "bank_of_maharashtra",
    "bandhan": "bandhan",
    "bandhan bank": "bandhan",
    "hsbc": "hsbc",
    # apgv wired after the APGB collision check: APGV docs carry APGV/"AP GRAMEENA
    # VIKAS BANK" evidence only; APGB docs carry ANDHRA PRAGATHI GRAMEENA BANK /
    # APGB and never APGV evidence -> detector separates them cleanly.
    "apgv": "apgv",
    "apgv bank": "apgv",
    "ap grameena vikas bank": "apgv",
    "csb": "csb",
    "csb bank": "csb",
    "uco": "uco",
    "uco bank": "uco",
    "airtel": "airtel_pb",
    "airtel bank": "airtel_pb",
    "airtel payments bank": "airtel_pb",
    "india post payments bank": "ippb",
    "india post": "ippb",
    "ippb": "ippb",
    "dhanlaxmi": "dhanlaxmi",
    "dhanlaxmi bank": "dhanlaxmi",
    "unknown": "unknown",
    "unknown bank": "unknown",
}


# ---------------------------------------------------------------------------
# Input Validation
# ---------------------------------------------------------------------------

# legacy wrong-bank guard: cheap detector re-check after a legacy success.
# env-gated; "0" disables completely (no behaviour change at all).
_MISMATCH_GUARD_ENV = "STATEMENT_ENGINE_MISMATCH_GUARD"


def _mismatch_guard_enabled() -> bool:
    return os.getenv(_MISMATCH_GUARD_ENV, "1").strip().lower() in ("1", "true", "yes", "on")


def _mismatch_detect(file_path: str):
    """Cheap detector probe: first-3-page text only, no extraction. Returns
    the DetectionResult or None on any failure."""
    try:
        import pdfplumber
        from app.services.statement_engine import detect_bank
        texts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:3]:
                texts.append(page.extract_text() or "")
        return detect_bank(texts)
    except Exception as exc:
        logger.warning("mismatch guard skipped (%s)", type(exc).__name__)
        return None


def _apply_mismatch_flag(det, bank_key: str, v2_block: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """If det is HIGH/VERY_HIGH confidence for a *different* supported bank,
    return the block flagged needs_review + BANK_MISMATCH; else the block
    unchanged. Pure — never raises, never blocks, never switches banks."""
    if det is None:
        return v2_block
    try:
        from app.services.statement_engine import Confidence
        confident = det.confidence in (Confidence.HIGH, Confidence.VERY_HIGH)
    except Exception:
        confident = False
    if not (confident and det.supported and det.processor_key and det.processor_key != bank_key):
        return v2_block
    block = dict(v2_block or {})
    codes = list(block.get("review_codes") or [])
    if "BANK_MISMATCH" not in codes:
        codes.append("BANK_MISMATCH")
    block["needs_review"] = True
    block["review_codes"] = codes
    block["detected_bank"] = {
        "key": det.bank_id, "name": det.bank_name,
        "confidence": det.confidence.name, "source": "detector",
    }
    logger.warning(
        "mismatch guard: file processed as %s but detector is %s for %s",
        bank_key, det.confidence.name, det.bank_id,
    )
    return block


def _maybe_flag_bank_mismatch(file_path: str, bank_key: str, v2_block: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Flag-gated wrapper around the mismatch detector + flagger."""
    if not _mismatch_guard_enabled():
        return v2_block
    return _apply_mismatch_flag(_mismatch_detect(file_path), bank_key, v2_block)


def _validate_input(
    file_path: str,
    user_info: dict,
    mode: str,
    api_key: Optional[str],
) -> None:
    """Validate all inputs before processing."""
    
    # File existence
    if not file_path or not isinstance(file_path, str):
        raise PipelineValidationError(
            "file_path must be a non-empty string",
            stage="input_validation",
            error_code="INVALID_FILE_PATH"
        )
    
    if not os.path.isfile(file_path):
        raise PipelineValidationError(
            f"File not found: {file_path}",
            stage="input_validation",
            error_code="FILE_NOT_FOUND"
        )
    
    # File extension
    if not file_path.lower().endswith(ALLOWED_EXTENSIONS):
        raise PipelineValidationError(
            "Invalid file type. Only PDF files are accepted.",
            stage="input_validation",
            error_code="INVALID_FILE_TYPE"
        )
    
    # File size
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        raise PipelineValidationError(
            "Uploaded file is empty (0 bytes).",
            stage="input_validation",
            error_code="EMPTY_FILE"
        )
    if file_size > MAX_FILE_SIZE_BYTES:
        raise PipelineValidationError(
            f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // (1024*1024)}MB.",
            stage="input_validation",
            error_code="FILE_TOO_LARGE"
        )
    
    # Mode
    if mode not in VALID_MODES:
        raise PipelineValidationError(
            f"Invalid mode '{mode}'. Must be one of: {VALID_MODES}",
            stage="input_validation",
            error_code="INVALID_MODE"
        )
    
    # API key for hybrid mode
    if mode == "hybrid" and (not api_key or not api_key.strip()):
        raise PipelineValidationError(
            "Anthropic API key is required for hybrid mode.",
            stage="input_validation",
            error_code="MISSING_API_KEY"
        )
    
    # User info
    if not isinstance(user_info, dict):
        raise PipelineValidationError(
            "user_info must be a dict.",
            stage="input_validation",
            error_code="INVALID_USER_INFO"
        )
    
    # Bank name required
    bank_name = user_info.get("bank_name", "").lower().strip()
    if not bank_name:
        raise PipelineValidationError(
            "Bank name is required. Please select a bank.",
            stage="input_validation",
            error_code="MISSING_BANK_NAME"
        )
    
    logger.info(
        "Input validation passed: file=%s mode=%s bank=%s size=%d",
        os.path.basename(file_path), mode, bank_name, file_size
    )


def _normalize_bank_name(bank_name: str) -> str:
    """Normalize bank name to standard key."""
    bank_lower = " ".join(bank_name.lower().replace("_", " ").replace("-", " ").split())
    bank_compact = bank_lower.replace(" ", "")

    if bank_lower in SUPPORTED_BANK_PROCESSORS:
        return SUPPORTED_BANK_PROCESSORS[bank_lower]

    if bank_compact in SUPPORTED_BANK_PROCESSORS:
        return SUPPORTED_BANK_PROCESSORS[bank_compact]

    for alias, processor_key in SUPPORTED_BANK_PROCESSORS.items():
        alias_compact = alias.replace(" ", "")
        if alias in bank_lower or alias_compact in bank_compact:
            return processor_key

    return bank_compact or bank_lower


# processor package key -> module:Class (lazy import)
_PROCESSOR_IMPORTS = {
    "hdfc": "app.services.banks.hdfc:HDFCProcessor",
    "axis": "app.services.banks.axis:AxisProcessor",
    "icici": "app.services.banks.icici:ICICIProcessor",
    "bank_of_india": "app.services.banks.bank_of_india:BankOfIndiaProcessor",
    "indian_bank": "app.services.banks.indian_bank:IndianBankProcessor",
    "kotak": "app.services.banks.kotak:KotakProcessor",
    "sbi": "app.services.banks.sbi:SBIProcessor",
    "canara": "app.services.banks.canara:CanaraProcessor",
    "idfc": "app.services.banks.idfc:IDFCProcessor",
    "karnataka": "app.services.banks.karnataka:KarnatakaProcessor",
    "paytm": "app.services.banks.paytm:PaytmProcessor",
    "union": "app.services.banks.union:UnionProcessor",
    "bank_of_baroda": "app.services.banks.bank_of_baroda:BankOfBarodaProcessor",
    "unknown": "app.services.banks.unknown:UnknownProcessor",
}


def _get_bank_processor(bank_key: str):
    """Resolve processor class for a normalized bank key (lazy import)."""
    key = SUPPORTED_BANK_PROCESSORS.get(bank_key, bank_key)
    if key == "kotakmahindra":
        key = "kotak"
    import_spec = _PROCESSOR_IMPORTS.get(key)
    if not import_spec:
        return None
    module_path, _, class_name = import_spec.partition(":")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)



# ---------------------------------------------------------------------------
# Main Processing Function
# ---------------------------------------------------------------------------

def process_statement(
    file_path: str,
    user_info: dict,
    mode: str = "free",
    api_key: Optional[str] = None,
    output_dir: Optional[str] = None,
    audit_service=None,
    job_id: Optional[str] = None,
) -> dict:
    """
    Process bank statement using bank-specific processor.
    
    This is the accuracy-first entry point.
    
    Args:
        file_path: Absolute path to the uploaded PDF file
        user_info: Dict with full_name, account_type, bank_name
        mode: Processing mode — "free" or "hybrid"
        api_key: Anthropic API key (required for hybrid mode)
        output_dir: Output directory for generated files
        audit_service: Audit service for logging
        job_id: Job ID for audit tracking
        
    Returns:
        {
            "status": "success",
            "excel_path": str,
            "stats": {...},
            "validation": {...},
            "performance": {...},
        }
        
    Raises:
        PipelineValidationError: If input validation fails
        PipelineAbortError: If processing fails
        UnsupportedBankError: If bank is not supported
    """
    pipeline_start = time.monotonic()
    
    # =================================================================
    # STEP 1: Validate Input
    # =================================================================
    _validate_input(file_path, user_info, mode, api_key)
    
    # Extract and normalize bank name
    bank_name = user_info.get("bank_name", "")
    bank_key = _normalize_bank_name(bank_name)

    logger.info("Processing %s statement: bank_key=%s job_id=%s", bank_name, bank_key, job_id)

    # =================================================================
    # STEP 1b: v2 serve decision (flag-gated; additive statement_engine block)
    # =================================================================
    from app.services.statement_engine import serve as _v2serve

    try:
        _v2_mode = _v2serve.v2_mode()
    except Exception:
        _v2_mode = "off"
    v2_plan = None
    v2_block = _v2serve.minimal_block(_v2_mode)

    from app.services.statement_engine.universal import serve as _userv
    _u_mode = _userv.mode()
    _u_block = None

    # T4 OCR tier (flag STATEMENT_ENGINE_OCR_MODE, default off). With the flag off nothing below runs and the
    # text path is untouched: not even the capability check is performed.
    from app.services.statement_engine.ocr import serve as _oserve
    _o_mode = _oserve.mode() if _oserve.enabled() else "off"
    _o_block = None
    _o_cap = None
    _o_pages = None
    if _o_mode != "off":
        try:
            from app.services.statement_engine.capability import check_pdf as _check_pdf
            _cap_res, _ = _check_pdf(file_path, max_pages=12)
            _o_cap, _o_pages = _cap_res.capability.value, _cap_res.page_count
        except Exception:
            _o_cap = None
    _o_active = _o_mode != "off" and _oserve.wants(_o_cap)
    _o_serving = _o_active and _o_mode == "serve"

    if _v2_mode == "serve" and _v2serve.serving_enabled_for(bank_key):
        _spec_key = _v2serve.spec_key_for(bank_key)
        try:
            _routed, _det, _ms = _v2serve.route_for_serve(file_path, _spec_key)
        except Exception:
            _routed, _det, _ms = None, None, 0.0
        _routed_key = _v2serve._spec_key_of_routed(_routed, _spec_key)
        _legacy_key = bank_key if _spec_key not in _v2serve._AUTO_KEYS else _v2serve.pipeline_key_for(_routed_key)
        v2_plan = _v2serve.decide_serve(
            bank_key=bank_key,
            spec_key=_spec_key,
            routed=_routed,
            det=_det,
            legacy_available=_get_bank_processor(_legacy_key) is not None,
            routed_ms=_ms,
        )
        v2_block = v2_plan.block

    # =================================================================
    # STEP 2: Get Bank-Specific Processor
    # =================================================================
    ProcessorClass = _get_bank_processor(bank_key)

    if ProcessorClass is None and v2_plan is None and _u_mode != "serve" and not _o_serving:
        raise UnsupportedBankError(
            f"Bank '{bank_name}' is not yet supported. "
            f"Supported banks: {', '.join(SUPPORTED_BANKS.values())}",
            stage="bank_routing",
            error_code="UNSUPPORTED_BANK"
        )
    
    # =================================================================
    # STEP 3: Initialize Processor
    # =================================================================
    enable_ai = mode == "hybrid"

    if v2_plan is not None and v2_plan.serve_v2:
        # v2 rows are served through the (routed) bank's own downstream steps;
        # v2-only banks use the generic unknown processor.
        _serve_key = _v2serve.pipeline_key_for(v2_plan.v2_spec_key)
        ProcessorClass = _get_bank_processor(_serve_key) or _get_bank_processor("unknown")

    if ProcessorClass is None and _u_mode != "serve" and not _o_serving:
        raise UnsupportedBankError(
            f"Bank '{bank_name}' is not yet supported. "
            f"Supported banks: {', '.join(SUPPORTED_BANKS.values())}",
            stage="bank_routing",
            error_code="UNSUPPORTED_BANK"
        )

    processor = ProcessorClass(
        strict_mode=False,  # Allow processing to continue with warnings
        enable_ai=enable_ai,
        api_key=api_key if enable_ai else None,
        audit_service=audit_service,
        job_id=job_id,
    ) if ProcessorClass is not None else None

    # =================================================================
    # STEP 4: Run Bank-Specific Processing
    # =================================================================
    result = None
    _t2_failed = False
    try:
        if output_dir is None:
            from app.utils.file_handler import get_temp_dir
            output_dir = get_temp_dir()

        if v2_plan is not None and v2_plan.serve_v2:
            _row_source = _v2serve.row_source_from_routed(v2_plan.routed)
            result = processor._run_pipeline(
                file_path, user_info, output_dir, row_source=_row_source
            )
            if getattr(result, "status", "") != "success":
                # serving v2 rows failed downstream: serve legacy instead when possible
                logger.error("v2 served pipeline failed; falling back to legacy processing")
                v2_plan.serve_v2 = False
                v2_block = _v2serve.engine_block(
                    engine="legacy", mode="serve", routed=v2_plan.routed,
                    verdict=None, needs_review=False, codes=[],
                    detected_bank=v2_block.get("detected_bank"),
                    advisory=_v2serve.advisory_block(v2_plan.routed),
                )
                if _get_bank_processor(bank_key) is not None:
                    processor = _get_bank_processor(bank_key)(
                        strict_mode=False, enable_ai=enable_ai,
                        api_key=api_key if enable_ai else None,
                        audit_service=audit_service, job_id=job_id,
                    )
                    result = processor.process(
                        file_path=file_path, user_info=user_info, output_dir=output_dir,
                    )
        elif ProcessorClass is not None:
            if _u_mode == "serve" or _o_serving:
                # T2 failure must not abort before the T3/T4 attempt below.
                try:
                    result = processor.process(
                        file_path=file_path, user_info=user_info, output_dir=output_dir,
                    )
                except Exception as _t2_exc:
                    logger.warning("legacy processing failed; T3 attempt follows (%s)", type(_t2_exc).__name__)
                    result = None
                    _t2_failed = _t2_exc
            else:
                result = processor.process(
                    file_path=file_path,
                    user_info=user_info,
                    output_dir=output_dir,
                )
        elif _u_mode == "off" and not _o_serving:
            raise UnsupportedBankError(
                f"Bank '{bank_name}' is not yet supported. "
                f"Supported banks: {', '.join(SUPPORTED_BANKS.values())}",
                stage="bank_routing",
                error_code="UNSUPPORTED_BANK"
            )

        # REVIEW + no usable legacy outcome -> serve the v2 rows flagged for review
        if (
            v2_plan is not None and not v2_plan.serve_v2
            and _v2serve.v2_verdict(v2_plan.routed) == "REVIEW"
            and not v2_plan.mismatch
            and (result is None or getattr(result, "status", "") != "success")
        ):
            _serve_key = _v2serve.pipeline_key_for(v2_plan.v2_spec_key)
            _rev_class = _get_bank_processor(_serve_key) or _get_bank_processor("unknown")
            if _rev_class is not None:
                _row_source = _v2serve.row_source_from_routed(v2_plan.routed)
                if _row_source is not None:
                    _rev_result = _rev_class(
                        strict_mode=False, enable_ai=enable_ai,
                        api_key=api_key if enable_ai else None,
                        audit_service=audit_service, job_id=job_id,
                    )._run_pipeline(file_path, user_info, output_dir, row_source=_row_source)
                    if getattr(_rev_result, "status", "") == "success":
                        result = _rev_result
                        v2_block = _v2serve.engine_block(
                            engine="v2", mode="serve", routed=v2_plan.routed,
                            verdict="REVIEW", needs_review=True,
                            codes=_v2serve.review_codes(v2_plan.routed),
                            detected_bank=v2_block.get("detected_bank"),
                            advisory=None,
                        )

        # T3 universal reader: only when T1/T2 produced nothing usable (flag-gated;
        # shadow records the block only; serve feeds REVIEW rows downstream or
        # fails honestly — FAILED carries no data).
        _served = (
            result is not None
            and getattr(result, "status", "") == "success"
            and getattr(getattr(result, "metrics", None), "transaction_count", 0) or 0
        ) > 0
        # T4 OCR: scanned/mixed files only. When T4 is serving and cannot produce rows the job fails honestly with
        # the OCR code: T3 is NOT tried afterwards, because on a MIXED file it would silently read only the text pages.
        if _o_active and not _served:
            _o_res, _o_rs = _oserve.attempt(
                file_path,
                bank_hint=(v2_block.get("detected_bank") and v2_block["detected_bank"].get("name")) or bank_name or "Unknown bank",
                page_count=_o_pages,
                reading=(user_info or {}).get("ocr_reading"),
            )
            _o_block = _oserve.block_for(_o_res, served=False, o_mode=_o_mode)
            if _o_serving:
                if _o_res.ok:
                    _o_class = _get_bank_processor("unknown")
                    _o_result = _o_class(
                        strict_mode=False, enable_ai=enable_ai,
                        api_key=api_key if enable_ai else None,
                        audit_service=audit_service, job_id=job_id,
                    )._run_pipeline(file_path, user_info, output_dir, row_source=_o_rs) if (_o_class and _o_rs) else None
                    if getattr(_o_result, "status", "") == "success":
                        result = _o_result
                        _o_block = _oserve.block_for(_o_res, served=True, o_mode=_o_mode)
                        v2_block = _oserve.engine_block_for(_o_res, _o_mode, detected_bank=v2_block.get("detected_bank"))
                        _served = True
                if not _served:
                    _oserve.audit_attempt(audit_service, job_id, _o_block)
                    raise PipelineAbortError(
                        f"Scanned statement could not be read ({_o_res.code or _o_res.verdict})",
                        stage="ocr_reader",
                        error_code=_o_res.code or "OCR_FAILED",
                    )

        if _u_mode != "off" and not _served:
            _u_res, _u_rs = _userv.attempt(file_path, bank_hint=v2_block.get("detected_bank") and
                                           v2_block["detected_bank"].get("name") or bank_name or "Unknown bank")
            if _u_mode == "shadow":
                _u_block = _userv.block_for(_u_res, served=False, u_mode=_u_mode)
            elif _u_res.ok:
                _u_class = _get_bank_processor("unknown")
                _u_result = _u_class(
                    strict_mode=False, enable_ai=enable_ai,
                    api_key=api_key if enable_ai else None,
                    audit_service=audit_service, job_id=job_id,
                )._run_pipeline(file_path, user_info, output_dir, row_source=_u_rs) if (_u_class and _u_rs) else None
                if getattr(_u_result, "status", "") == "success":
                    result = _u_result
                    _u_block = _userv.block_for(_u_res, served=True, u_mode=_u_mode)
                    v2_block = _userv.engine_block_for(_u_res, _u_mode,
                                                       detected_bank=v2_block.get("detected_bank"))
                else:
                    _u_block = _userv.block_for(_u_res, served=False, u_mode=_u_mode)
            else:
                _u_block = _userv.block_for(_u_res, served=False, u_mode=_u_mode)
                if isinstance(_t2_failed, Exception):
                    raise _t2_failed
                raise PipelineAbortError(
                    f"Statement could not be read ({_u_res.code or _u_res.verdict})",
                    stage="universal_reader",
                    error_code="GENERAL_READER_FAILED" if _u_res.ok is False else _u_res.code,
                )

    except Exception as e:
        logger.error("Bank processor failed: %s", str(e), exc_info=True)
        err = _as_abort(e)
        if err is e:
            raise
        raise err from e
    
    # =================================================================
    # STEP 4b: v2 shadow (flag-gated; never changes the legacy response)
    # =================================================================
    from app.services.statement_engine.shadow import run_v2_shadow

    if getattr(result, "status", "") == "success":
        try:
            run_v2_shadow(file_path, bank_key, result, audit_service=audit_service, job_id=job_id)
        except Exception as exc:    # defence in depth: shadow work can never change the legacy response
            logger.error("v2 shadow hook failed (%s); legacy result unaffected", type(exc).__name__)

    # =================================================================
    # STEP 5: Build Response
    # =================================================================
    total_time_ms = round((time.monotonic() - pipeline_start) * 1000, 1)

    response = result.to_dict()
    response["performance"]["total_pipeline_ms"] = total_time_ms
    response["bank_key"] = bank_key
    response["mode"] = mode

    # wrong-bank guard on the successful result: flag BANK_MISMATCH when the
    # detector is HIGH-confidence for a different supported bank (flag-gated).
    if getattr(result, "status", "") == "success":
        v2_block = _maybe_flag_bank_mismatch(file_path, bank_key, v2_block)

    if getattr(result, "status", "") == "success" and v2_plan is not None:
        v2_block = _v2serve.apply_row_count_guard(
            v2_block, v2_plan.routed, getattr(result.metrics, "transaction_count", None)
        )

    # v2 serving: attach the additive block, audit the decision, and append the
    # Statement Check sheet when the block calls for it (never at mode off).
    if _u_block is not None and "universal" not in v2_block:
        v2_block["universal"] = _u_block
        _userv.audit_attempt(audit_service, job_id, _u_block)
    if _o_block is not None and "ocr" not in v2_block:
        v2_block["ocr"] = _o_block
    if _o_block is not None:
        _oserve.audit_attempt(audit_service, job_id, _o_block)
    response["statement_engine"] = v2_block
    _v2serve.audit_serve_decision(audit_service, job_id, v2_block)
    if _v2serve.wants_statement_check(v2_block):
        try:
            _v2serve.append_statement_check_sheet(result.excel_path, v2_block)
        except Exception:
            logger.debug("statement check sheet append failed", exc_info=True)
    
    logger.info(
        "Pipeline complete: bank=%s transactions=%d time=%.1fms",
        bank_key,
        result.metrics.transaction_count,
        total_time_ms
    )
    
    return response


