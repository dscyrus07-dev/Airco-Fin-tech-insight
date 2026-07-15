"""
Tests for Airco Insights — Pipeline Orchestrator
===================================================
Uses mocks for all service dependencies to test orchestration logic
without requiring real PDFs, LibreOffice, or Supabase.

Test groups:
    1.  Input validation
    2.  PDF detection failures
    3.  Bank detection failures
    4.  Parser failures
    5.  Normalization failures
    6.  Free mode full pipeline
    7.  Hybrid mode full pipeline
    8.  AI fallback on failure
    9.  PDF conversion failure (non-fatal)
    10. DB persistence failure (non-fatal)
    11. Output structure
    12. Cleanup behavior
"""

import os
import copy
import pytest
from unittest.mock import patch, MagicMock

from app.services.pipeline_orchestrator import (
    process_statement,
    _validate_input,
    _tag_as_others,
    PipelineError,
    PipelineValidationError,
    PipelineAbortError,
)


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

def user_info():
    return {
        "full_name": "Test User",
        "account_type": "Salaried",
        "bank_name": "HDFC Bank",
    }


def make_normalized_txns(count=5):
    """Return normalized transactions (post-normalizer)."""
    txns = []
    for i in range(count):
        txns.append({
            "date": f"2025-06-{(i % 28) + 1:02d}",
            "description": f"TEST TXN {i}",
            "debit": 1000.0 + i if i % 2 == 0 else None,
            "credit": 5000.0 if i % 2 != 0 else None,
            "balance": 50000.0 - (i * 100),
            "txn_id": f"txn_{i:04d}",
        })
    return txns


def make_classified_txns(count=5):
    """Return classified transactions (post-rule-engine)."""
    txns = make_normalized_txns(count)
    for t in txns:
        if t["debit"] is not None:
            t["category"] = "Shopping"
            t["confidence"] = 0.95
            t["source"] = "rule_engine"
        else:
            t["category"] = "Salary"
            t["confidence"] = 0.95
            t["source"] = "rule_engine"
    return txns


def make_recurring_txns(count=5):
    """Return transactions post-recurring-engine."""
    txns = make_classified_txns(count)
    for i, t in enumerate(txns):
        t["is_recurring"] = i < 2
    return txns


MOCK_DETECTION = {
    "pdf_type": "digital",
    "text_content": "HDFC BANK STATEMENT ...",
    "first_page_text": "HDFC BANK ...",
    "total_pages": 5,
}

MOCK_BANK_RESULT = {
    "bank_key": "hdfc",
    "confidence": "high",
    "detection_method": "auto",
}

MOCK_RAW_ROWS = [
    {"date": "01/06/2025", "description": "UPI TXN", "debit": "1000.00", "credit": "", "balance": "49000.00"},
    {"date": "02/06/2025", "description": "SALARY CREDIT", "debit": "", "credit": "85000.00", "balance": "134000.00"},
]

MOCK_AGGREGATION = {
    "summary": {"2025-06": {
        "total_credit_count": 2, "total_credit_amount": 10000.0,
        "total_debit_count": 3, "total_debit_amount": 3003.0,
        "avg_balance": 49700.0, "min_balance": 49500.0, "max_balance": 50000.0,
        "start_of_month_balance": 50000.0, "end_of_month_balance": 49600.0,
    }},
    "category_analysis": {},
    "weekly_analysis": {},
    "recurring_analysis": {},
}


@pytest.fixture
def fake_pdf(tmp_path):
    """Create a fake PDF file for testing."""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake content for testing")
    return str(pdf_path)


# ---------------------------------------------------------------------------
# 1. Input Validation
# ---------------------------------------------------------------------------

class TestInputValidation:

    def test_missing_file(self):
        with pytest.raises(PipelineValidationError, match="non-empty string"):
            _validate_input("", user_info(), "free", None)

    def test_file_not_found(self):
        with pytest.raises(PipelineValidationError, match="not found"):
            _validate_input("/nonexistent/file.pdf", user_info(), "free", None)

    def test_invalid_extension(self, tmp_path):
        txt = tmp_path / "test.txt"
        txt.write_text("hello")
        with pytest.raises(PipelineValidationError, match="PDF"):
            _validate_input(str(txt), user_info(), "free", None)

    def test_empty_file(self, tmp_path):
        pdf = tmp_path / "empty.pdf"
        pdf.write_bytes(b"")
        with pytest.raises(PipelineValidationError, match="empty"):
            _validate_input(str(pdf), user_info(), "free", None)

    def test_invalid_mode(self, fake_pdf):
        with pytest.raises(PipelineValidationError, match="Invalid mode"):
            _validate_input(fake_pdf, user_info(), "turbo", None)

    def test_hybrid_no_key(self, fake_pdf):
        with pytest.raises(PipelineValidationError, match="API key"):
            _validate_input(fake_pdf, user_info(), "hybrid", None)

    def test_hybrid_empty_key(self, fake_pdf):
        with pytest.raises(PipelineValidationError, match="API key"):
            _validate_input(fake_pdf, user_info(), "hybrid", "  ")

    def test_valid_free(self, fake_pdf):
        _validate_input(fake_pdf, user_info(), "free", None)

    def test_valid_hybrid(self, fake_pdf):
        _validate_input(fake_pdf, user_info(), "hybrid", "sk-ant-api03-xxx")

    def test_bad_user_info(self, fake_pdf):
        with pytest.raises(PipelineValidationError, match="dict"):
            _validate_input(fake_pdf, "not a dict", "free", None)


# ---------------------------------------------------------------------------
# 2. PDF Detection Failures
# ---------------------------------------------------------------------------

class TestPDFDetectionFailure:

    @patch("app.services.pipeline_orchestrator.detect_pdf_type")
    def test_encrypted_pdf(self, mock_detect, fake_pdf):
        from app.services.pdf_detector import EncryptedPDFError
        mock_detect.side_effect = EncryptedPDFError("Encrypted PDF")
        with pytest.raises(PipelineAbortError, match="Encrypted"):
            process_statement(fake_pdf, user_info(), "free")

    @patch("app.services.pipeline_orchestrator.detect_pdf_type")
    def test_scanned_pdf(self, mock_detect, fake_pdf):
        mock_detect.return_value = {
            "pdf_type": "scanned", "text_content": "", "first_page_text": "", "total_pages": 1
        }
        with pytest.raises(PipelineAbortError, match="Scanned"):
            process_statement(fake_pdf, user_info(), "free")


# ---------------------------------------------------------------------------
# 3. Bank Detection Failures
# ---------------------------------------------------------------------------

class TestBankDetectionFailure:

    @patch("app.services.pipeline_orchestrator.resolve_bank")
    @patch("app.services.pipeline_orchestrator.detect_pdf_type", return_value=MOCK_DETECTION)
    def test_bank_mismatch(self, mock_detect, mock_bank, fake_pdf):
        from app.services.bank_detector import BankMismatchError
        mock_bank.side_effect = BankMismatchError("Bank mismatch")
        with pytest.raises(PipelineAbortError, match="mismatch"):
            process_statement(fake_pdf, user_info(), "free")


# ---------------------------------------------------------------------------
# 4. Parser Failures
# ---------------------------------------------------------------------------

class TestParserFailure:

    @patch("app.services.pipeline_orchestrator._get_bank_parser")
    @patch("app.services.pipeline_orchestrator.resolve_bank", return_value=MOCK_BANK_RESULT)
    @patch("app.services.pipeline_orchestrator.detect_pdf_type", return_value=MOCK_DETECTION)
    def test_parser_returns_empty(self, mock_detect, mock_bank, mock_parser, fake_pdf):
        mock_parser.return_value = MagicMock(return_value=[])
        with pytest.raises(PipelineAbortError, match="No transactions"):
            process_statement(fake_pdf, user_info(), "free")

    @patch("app.services.pipeline_orchestrator._get_bank_parser")
    @patch("app.services.pipeline_orchestrator.resolve_bank", return_value=MOCK_BANK_RESULT)
    @patch("app.services.pipeline_orchestrator.detect_pdf_type", return_value=MOCK_DETECTION)
    def test_parser_exception(self, mock_detect, mock_bank, mock_parser, fake_pdf):
        mock_parser.return_value = MagicMock(side_effect=Exception("Parse error"))
        with pytest.raises(PipelineAbortError, match="Failed to parse"):
            process_statement(fake_pdf, user_info(), "free")


# ---------------------------------------------------------------------------
# 5. Normalization Failures
# ---------------------------------------------------------------------------

class TestNormalizationFailure:

    @patch("app.services.pipeline_orchestrator.normalize_transactions")
    @patch("app.services.pipeline_orchestrator._get_bank_parser")
    @patch("app.services.pipeline_orchestrator.resolve_bank", return_value=MOCK_BANK_RESULT)
    @patch("app.services.pipeline_orchestrator.detect_pdf_type", return_value=MOCK_DETECTION)
    def test_excessive_corruption(self, mock_detect, mock_bank, mock_parser, mock_norm, fake_pdf):
        from app.services.normalizer import ExcessiveDataCorruptionError
        mock_parser.return_value = MagicMock(return_value=MOCK_RAW_ROWS)
        mock_norm.side_effect = ExcessiveDataCorruptionError("Too much corruption")
        with pytest.raises(PipelineAbortError, match="corruption"):
            process_statement(fake_pdf, user_info(), "free")

    @patch("app.services.pipeline_orchestrator.normalize_transactions", return_value=[])
    @patch("app.services.pipeline_orchestrator._get_bank_parser")
    @patch("app.services.pipeline_orchestrator.resolve_bank", return_value=MOCK_BANK_RESULT)
    @patch("app.services.pipeline_orchestrator.detect_pdf_type", return_value=MOCK_DETECTION)
    def test_empty_after_normalization(self, mock_detect, mock_bank, mock_parser, mock_norm, fake_pdf):
        mock_parser.return_value = MagicMock(return_value=MOCK_RAW_ROWS)
        with pytest.raises(PipelineAbortError, match="No valid"):
            process_statement(fake_pdf, user_info(), "free")


# ---------------------------------------------------------------------------
# 6. Free Mode Full Pipeline
# ---------------------------------------------------------------------------

class TestFreeModePipeline:

    @patch("app.services.pipeline_orchestrator.generate_excel")
    @patch("app.services.pipeline_orchestrator.convert_excel_to_pdf")
    @patch("app.services.pipeline_orchestrator.aggregate", return_value=MOCK_AGGREGATION)
    @patch("app.services.pipeline_orchestrator.detect_recurring")
    @patch("app.services.pipeline_orchestrator.apply_rule_engine")
    @patch("app.services.pipeline_orchestrator.normalize_transactions")
    @patch("app.services.pipeline_orchestrator._get_bank_parser")
    @patch("app.services.pipeline_orchestrator.resolve_bank", return_value=MOCK_BANK_RESULT)
    @patch("app.services.pipeline_orchestrator.detect_pdf_type", return_value=MOCK_DETECTION)
    def test_free_mode_success(
        self, mock_detect, mock_bank, mock_parser, mock_norm,
        mock_rules, mock_recurring, mock_agg, mock_pdf_conv, mock_excel,
        fake_pdf, tmp_path,
    ):
        normalized = make_normalized_txns(5)
        classified = make_classified_txns(3)
        unclassified = make_normalized_txns(2)
        recurring = make_recurring_txns(5)

        mock_parser.return_value = MagicMock(return_value=MOCK_RAW_ROWS)
        mock_norm.return_value = normalized
        mock_rules.return_value = (classified, unclassified)
        mock_recurring.return_value = recurring

        excel_out = str(tmp_path / "report.xlsx")
        # Create a fake file so os.path.isfile passes
        with open(excel_out, "w") as f:
            f.write("fake")
        mock_excel.return_value = excel_out

        pdf_out = str(tmp_path / "report.pdf")
        with open(pdf_out, "w") as f:
            f.write("fake")
        mock_pdf_conv.return_value = pdf_out

        result = process_statement(fake_pdf, user_info(), "free")

        assert result["status"] == "success"
        assert result["excel_path"] == excel_out
        assert result["pdf_path"] == pdf_out
        assert result["ai_usage"] is None
        assert result["stats"]["total_transactions"] == 5
        assert result["stats"]["rule_engine_classified"] == 3
        assert result["stats"]["ai_classified"] == 0


# ---------------------------------------------------------------------------
# 7. Hybrid Mode Full Pipeline
# ---------------------------------------------------------------------------

class TestHybridModePipeline:

    @patch("app.services.pipeline_orchestrator._run_ai_classification")
    @patch("app.services.pipeline_orchestrator.generate_excel")
    @patch("app.services.pipeline_orchestrator.convert_excel_to_pdf")
    @patch("app.services.pipeline_orchestrator.aggregate", return_value=MOCK_AGGREGATION)
    @patch("app.services.pipeline_orchestrator.detect_recurring")
    @patch("app.services.pipeline_orchestrator.apply_rule_engine")
    @patch("app.services.pipeline_orchestrator.normalize_transactions")
    @patch("app.services.pipeline_orchestrator._get_bank_parser")
    @patch("app.services.pipeline_orchestrator.resolve_bank", return_value=MOCK_BANK_RESULT)
    @patch("app.services.pipeline_orchestrator.detect_pdf_type", return_value=MOCK_DETECTION)
    def test_hybrid_mode_success(
        self, mock_detect, mock_bank, mock_parser, mock_norm,
        mock_rules, mock_recurring, mock_agg, mock_pdf_conv, mock_excel,
        mock_ai, fake_pdf, tmp_path,
    ):
        normalized = make_normalized_txns(5)
        classified = make_classified_txns(3)
        unclassified = make_normalized_txns(2)
        recurring = make_recurring_txns(5)

        # AI returns classified versions of the unclassified
        ai_classified = []
        for t in unclassified:
            tc = copy.deepcopy(t)
            tc["category"] = "UPI Payment" if tc.get("debit") else "UPI Credit"
            tc["confidence"] = 0.85
            tc["source"] = "ai_classifier"
            ai_classified.append(tc)

        mock_parser.return_value = MagicMock(return_value=MOCK_RAW_ROWS)
        mock_norm.return_value = normalized
        mock_rules.return_value = (classified, unclassified)
        mock_ai.return_value = (ai_classified, {
            "transactions_sent": 2,
            "api_calls": 1,
            "estimated_cost_usd": 0.001,
            "estimated_cost_inr": 0.08,
        })
        mock_recurring.return_value = recurring

        excel_out = str(tmp_path / "report.xlsx")
        with open(excel_out, "w") as f:
            f.write("fake")
        mock_excel.return_value = excel_out

        pdf_out = str(tmp_path / "report.pdf")
        with open(pdf_out, "w") as f:
            f.write("fake")
        mock_pdf_conv.return_value = pdf_out

        result = process_statement(
            fake_pdf, user_info(), "hybrid", api_key="sk-ant-api03-xxx"
        )

        assert result["status"] == "success"
        assert result["ai_usage"] is not None
        assert result["ai_usage"]["transactions_sent"] == 2
        assert result["stats"]["ai_classified"] == 2


# ---------------------------------------------------------------------------
# 8. AI Fallback on Failure
# ---------------------------------------------------------------------------

class TestAIFallback:

    @patch("app.services.pipeline_orchestrator._run_ai_classification")
    @patch("app.services.pipeline_orchestrator.generate_excel")
    @patch("app.services.pipeline_orchestrator.convert_excel_to_pdf")
    @patch("app.services.pipeline_orchestrator.aggregate", return_value=MOCK_AGGREGATION)
    @patch("app.services.pipeline_orchestrator.detect_recurring")
    @patch("app.services.pipeline_orchestrator.apply_rule_engine")
    @patch("app.services.pipeline_orchestrator.normalize_transactions")
    @patch("app.services.pipeline_orchestrator._get_bank_parser")
    @patch("app.services.pipeline_orchestrator.resolve_bank", return_value=MOCK_BANK_RESULT)
    @patch("app.services.pipeline_orchestrator.detect_pdf_type", return_value=MOCK_DETECTION)
    def test_ai_failure_fallback_to_others(
        self, mock_detect, mock_bank, mock_parser, mock_norm,
        mock_rules, mock_recurring, mock_agg, mock_pdf_conv, mock_excel,
        mock_ai, fake_pdf, tmp_path,
    ):
        normalized = make_normalized_txns(5)
        classified = make_classified_txns(3)
        unclassified = make_normalized_txns(2)

        # AI returns fallback "Others" due to error
        ai_fallback = []
        for t in unclassified:
            tc = copy.deepcopy(t)
            is_debit = tc.get("debit") is not None
            tc["category"] = "Others Debit" if is_debit else "Others Credit"
            tc["confidence"] = None
            tc["source"] = "ai_error_fallback"
            ai_fallback.append(tc)

        mock_parser.return_value = MagicMock(return_value=MOCK_RAW_ROWS)
        mock_norm.return_value = normalized
        mock_rules.return_value = (classified, unclassified)
        mock_ai.return_value = (ai_fallback, {
            "transactions_sent": 0, "api_calls": 0,
            "estimated_cost_usd": 0.0, "estimated_cost_inr": 0.0,
        })
        mock_recurring.return_value = make_recurring_txns(5)

        excel_out = str(tmp_path / "report.xlsx")
        with open(excel_out, "w") as f:
            f.write("fake")
        mock_excel.return_value = excel_out
        mock_pdf_conv.return_value = None

        result = process_statement(
            fake_pdf, user_info(), "hybrid", api_key="sk-ant-api03-xxx"
        )

        assert result["status"] == "success"
        assert result["stats"]["ai_classified"] == 0


# ---------------------------------------------------------------------------
# 9. PDF Conversion Failure (non-fatal)
# ---------------------------------------------------------------------------

class TestPDFConversionFailure:

    @patch("app.services.pipeline_orchestrator.generate_excel")
    @patch("app.services.pipeline_orchestrator.convert_excel_to_pdf")
    @patch("app.services.pipeline_orchestrator.aggregate", return_value=MOCK_AGGREGATION)
    @patch("app.services.pipeline_orchestrator.detect_recurring")
    @patch("app.services.pipeline_orchestrator.apply_rule_engine")
    @patch("app.services.pipeline_orchestrator.normalize_transactions")
    @patch("app.services.pipeline_orchestrator._get_bank_parser")
    @patch("app.services.pipeline_orchestrator.resolve_bank", return_value=MOCK_BANK_RESULT)
    @patch("app.services.pipeline_orchestrator.detect_pdf_type", return_value=MOCK_DETECTION)
    def test_pdf_failure_returns_excel_only(
        self, mock_detect, mock_bank, mock_parser, mock_norm,
        mock_rules, mock_recurring, mock_agg, mock_pdf_conv, mock_excel,
        fake_pdf, tmp_path,
    ):
        from app.services.pdf_converter import LibreOfficeNotFoundError

        mock_parser.return_value = MagicMock(return_value=MOCK_RAW_ROWS)
        mock_norm.return_value = make_normalized_txns(5)
        mock_rules.return_value = (make_classified_txns(5), [])
        mock_recurring.return_value = make_recurring_txns(5)

        excel_out = str(tmp_path / "report.xlsx")
        with open(excel_out, "w") as f:
            f.write("fake")
        mock_excel.return_value = excel_out
        mock_pdf_conv.side_effect = LibreOfficeNotFoundError("Not found")

        result = process_statement(fake_pdf, user_info(), "free")

        assert result["status"] == "success"
        assert result["excel_path"] == excel_out
        assert result["pdf_path"] is None


# ---------------------------------------------------------------------------
# 10. DB Persistence Failure (non-fatal for files)
# ---------------------------------------------------------------------------

class TestDBPersistenceFailure:

    @patch("app.services.pipeline_orchestrator.persist_all")
    @patch("app.services.pipeline_orchestrator.generate_excel")
    @patch("app.services.pipeline_orchestrator.convert_excel_to_pdf")
    @patch("app.services.pipeline_orchestrator.aggregate", return_value=MOCK_AGGREGATION)
    @patch("app.services.pipeline_orchestrator.detect_recurring")
    @patch("app.services.pipeline_orchestrator.apply_rule_engine")
    @patch("app.services.pipeline_orchestrator.normalize_transactions")
    @patch("app.services.pipeline_orchestrator._get_bank_parser")
    @patch("app.services.pipeline_orchestrator.resolve_bank", return_value=MOCK_BANK_RESULT)
    @patch("app.services.pipeline_orchestrator.detect_pdf_type", return_value=MOCK_DETECTION)
    def test_db_failure_still_returns_files(
        self, mock_detect, mock_bank, mock_parser, mock_norm,
        mock_rules, mock_recurring, mock_agg, mock_pdf_conv, mock_excel,
        mock_persist, fake_pdf, tmp_path,
    ):
        mock_parser.return_value = MagicMock(return_value=MOCK_RAW_ROWS)
        mock_norm.return_value = make_normalized_txns(5)
        mock_rules.return_value = (make_classified_txns(5), [])
        mock_recurring.return_value = make_recurring_txns(5)

        excel_out = str(tmp_path / "report.xlsx")
        with open(excel_out, "w") as f:
            f.write("fake")
        mock_excel.return_value = excel_out
        mock_pdf_conv.return_value = None
        mock_persist.side_effect = Exception("DB connection lost")

        # Pass a mock DB session so persistence step runs
        mock_db = MagicMock()
        result = process_statement(
            fake_pdf, user_info(), "free", db_session=mock_db
        )

        assert result["status"] == "success"
        assert result["excel_path"] == excel_out


# ---------------------------------------------------------------------------
# 11. Output Structure
# ---------------------------------------------------------------------------

class TestOutputStructure:

    @patch("app.services.pipeline_orchestrator.generate_excel")
    @patch("app.services.pipeline_orchestrator.convert_excel_to_pdf")
    @patch("app.services.pipeline_orchestrator.aggregate", return_value=MOCK_AGGREGATION)
    @patch("app.services.pipeline_orchestrator.detect_recurring")
    @patch("app.services.pipeline_orchestrator.apply_rule_engine")
    @patch("app.services.pipeline_orchestrator.normalize_transactions")
    @patch("app.services.pipeline_orchestrator._get_bank_parser")
    @patch("app.services.pipeline_orchestrator.resolve_bank", return_value=MOCK_BANK_RESULT)
    @patch("app.services.pipeline_orchestrator.detect_pdf_type", return_value=MOCK_DETECTION)
    def test_output_has_required_keys(
        self, mock_detect, mock_bank, mock_parser, mock_norm,
        mock_rules, mock_recurring, mock_agg, mock_pdf_conv, mock_excel,
        fake_pdf, tmp_path,
    ):
        mock_parser.return_value = MagicMock(return_value=MOCK_RAW_ROWS)
        mock_norm.return_value = make_normalized_txns(5)
        mock_rules.return_value = (make_classified_txns(5), [])
        mock_recurring.return_value = make_recurring_txns(5)

        excel_out = str(tmp_path / "report.xlsx")
        with open(excel_out, "w") as f:
            f.write("fake")
        mock_excel.return_value = excel_out
        mock_pdf_conv.return_value = None

        result = process_statement(fake_pdf, user_info(), "free")

        assert set(result.keys()) == {"status", "excel_path", "pdf_path", "stats", "ai_usage", "performance"}
        assert set(result["stats"].keys()) == {
            "total_transactions", "rule_engine_classified",
            "ai_classified", "others", "recurring", "coverage_percent",
        }


# ---------------------------------------------------------------------------
# 12. Tag as Others Helper
# ---------------------------------------------------------------------------

class TestTagAsOthers:

    def test_debit_gets_others_debit(self):
        txns = [{"debit": 1000.0, "credit": None}]
        result = _tag_as_others(txns)
        assert result[0]["category"] == "Others Debit"

    def test_credit_gets_others_credit(self):
        txns = [{"debit": None, "credit": 5000.0}]
        result = _tag_as_others(txns)
        assert result[0]["category"] == "Others Credit"

    def test_does_not_mutate_input(self):
        txns = [{"debit": 1000.0, "credit": None}]
        original = copy.deepcopy(txns)
        _tag_as_others(txns)
        assert txns == original

    def test_source_tag(self):
        txns = [{"debit": 1000.0, "credit": None}]
        result = _tag_as_others(txns)
        assert result[0]["source"] == "default_others"
