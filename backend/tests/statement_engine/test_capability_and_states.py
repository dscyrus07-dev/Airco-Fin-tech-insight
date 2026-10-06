"""Capability check and state mapping. The real-PDF tests use PyMuPDF (already a dependency) to build tiny files."""
import pytest

from app.services.statement_engine import (
    Capability,
    Confidence,
    DocumentState,
    PageInfo,
    analyze_pdf,
    analyze_text_pages,
    classify_pages,
)
from app.services.statement_engine.capability import readable_chars


def test_text_pdf():
    r = classify_pages([PageInfo(900, 0), PageInfo(800, 0)])
    assert r.capability == Capability.TEXT


def test_all_image_pages_are_scanned():
    r = classify_pages([PageInfo(0, 1), PageInfo(3, 1)])
    assert r.capability == Capability.SCANNED
    assert "text-based" in r.reason


def test_no_text_and_no_images_is_scanned_too():
    assert classify_pages([PageInfo(0, 0)]).capability == Capability.SCANNED


def test_mixed_when_some_pages_are_images():
    r = classify_pages([PageInfo(900, 0), PageInfo(0, 1)])
    assert r.capability == Capability.MIXED and r.image_only_pages == 1 and r.text_pages == 1


def test_blank_trailing_page_does_not_make_it_mixed():
    r = classify_pages([PageInfo(900, 0), PageInfo(0, 0)])
    assert r.capability == Capability.TEXT and r.blank_pages == 1


def test_unmapped_font_garbage_is_not_text():
    garbage = "(cid:12)(cid:45)(cid:7) " * 100
    assert readable_chars(garbage) == 0
    assert classify_pages([PageInfo(readable_chars(garbage), 0)]).capability == Capability.SCANNED


def test_no_pages_is_unreadable():
    assert classify_pages([]).capability == Capability.UNREADABLE


def _states(cap, det_text=None, **kw):
    return analyze_text_pages("f.pdf", cap, det_text or [], **kw)


TEXT_CAP = classify_pages([PageInfo(900, 0)])
T = "\nDate Narration Withdrawal Deposit Balance\n01/04/2021 UPI/1/SHOP 100.00 5000.00"   # a transaction table: the detector requires one


def test_state_detected_when_high_and_supported():
    a = _states(TEXT_CAP, ["HDFC BANK LIMITED\nIFSC Code : HDFC0001234" + T])
    assert a.state == DocumentState.DETECTED


def test_state_unknown_bank():
    assert _states(TEXT_CAP, ["Some statement"]).state == DocumentState.UNKNOWN_BANK


def test_state_unsupported_bank():
    a = _states(TEXT_CAP, ["YES BANK LIMITED\nIFSC Code: YESB0000001" + T])
    assert a.state == DocumentState.UNSUPPORTED_BANK and "not supported yet" in a.message


def test_state_scanned_has_no_detection_and_clear_message():
    a = _states(classify_pages([PageInfo(0, 1)]), ["HDFC BANK LIMITED"])
    assert a.state == DocumentState.UNSUPPORTED_SCANNED_PDF
    assert a.detection is None, "no bank detection is attempted on a scanned PDF"
    assert "text-based" in a.message


def test_state_conflicting_hint_needs_confirmation():
    a = _states(TEXT_CAP, ["Axis Bank Limited\nIFSC: UTIB0000123" + T], user_hint="hdfc")
    assert a.state == DocumentState.AWAITING_CONFIRMATION


def test_analysis_serialises():
    import json

    json.dumps(_states(TEXT_CAP, ["Axis Bank Limited\nIFSC: UTIB0000123" + T]).to_dict())
