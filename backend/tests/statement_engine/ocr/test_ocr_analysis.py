"""Analysis-time OCR bank detection: never trusted as verified."""
from app.services.statement_engine.analyzer import analyze_scanned_with_ocr, decide_state
from app.services.statement_engine.contracts import Capability, CapabilityResult, Confidence, DocumentState

CAP = CapabilityResult(Capability.SCANNED, 5, 0, 5, 0, reason="scan")
HDFC = "HDFC BANK LIMITED\nAccount Statement\nIFSC: HDFC0001234\nwww.hdfcbank.com\nDate Narration Chq./Ref.No. Withdrawal Amt. Deposit Amt. Closing Balance"


def test_scanned_without_ocr_is_still_unsupported():
    st, msg = decide_state(CAP, None)
    assert st == DocumentState.UNSUPPORTED_SCANNED_PDF and "text-based" in msg


def test_ocr_detected_bank_is_capped_so_the_user_must_confirm():
    a = analyze_scanned_with_ocr("s.pdf", CAP, [HDFC, ""])
    assert a.detection is not None and a.detection.bank_id
    assert a.detection.confidence == Confidence.MEDIUM          # never HIGH/VERY_HIGH from a scan
    assert a.state == DocumentState.AWAITING_CONFIRMATION and "OCR" in a.message


def test_no_ocr_text_means_the_user_picks_the_bank():
    a = analyze_scanned_with_ocr("s.pdf", CAP, [])
    assert a.state == DocumentState.UNKNOWN_BANK and a.detection is None and "select" in a.message.lower()
    b = analyze_scanned_with_ocr("s.pdf", CAP, ["", "  "])
    assert b.state == DocumentState.UNKNOWN_BANK


def test_garbage_ocr_text_does_not_identify_a_bank():
    a = analyze_scanned_with_ocr("s.pdf", CAP, ["lorem ipsum dolor sit amet"])
    assert a.state == DocumentState.UNKNOWN_BANK
