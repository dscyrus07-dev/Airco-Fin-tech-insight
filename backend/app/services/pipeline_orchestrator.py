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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_MODES = ("free", "hybrid")
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
    "unknown": "unknown",
    "unknown bank": "unknown",
}


# ---------------------------------------------------------------------------
# Input Validation
# ---------------------------------------------------------------------------

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

    if ProcessorClass is None and v2_plan is None:
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

    if ProcessorClass is None:
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
    )

    # =================================================================
    # STEP 4: Run Bank-Specific Processing
    # =================================================================
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
            result = processor.process(
                file_path=file_path,
                user_info=user_info,
                output_dir=output_dir,
            )
        else:
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

    except Exception as e:
        logger.error("Bank processor failed: %s", str(e), exc_info=True)
        
        # Convert to pipeline error
        if hasattr(e, 'stage') and hasattr(e, 'error_code'):
            raise PipelineAbortError(
                str(e),
                stage=e.stage,
                error_code=e.error_code
            )
        else:
            raise PipelineAbortError(
                f"Processing failed: {str(e)}",
                stage="bank_processor",
                error_code="PROCESSOR_ERROR"
            )
    
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

    # v2 serving: attach the additive block, audit the decision, and append the
    # Statement Check sheet when the block calls for it (never at mode off).
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


