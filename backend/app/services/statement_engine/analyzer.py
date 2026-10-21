"""Analyze one PDF: capability check, then bank detection, then a state and a plain-language message.

Observe-only in Slice 2B: nothing here is called by the upload path yet. 2C wires it to the analyze endpoint.
"""
from __future__ import annotations

from typing import Optional, Sequence

from .capability import check_pdf
from .contracts import (
    Capability,
    CapabilityResult,
    Confidence,
    DetectionResult,
    DocumentAnalysis,
    DocumentState,
)
from .detector import detect_bank


def decide_state(cap: CapabilityResult, det: Optional[DetectionResult]) -> "tuple[DocumentState, str]":
    """Map capability + detection to the state the review screen shows. Pure."""
    if cap.capability == Capability.LOCKED:
        return DocumentState.PASSWORD_REQUIRED, cap.reason + " Enter the password to continue."
    if cap.capability == Capability.SCANNED:
        return DocumentState.UNSUPPORTED_SCANNED_PDF, (
            "This statement appears to be scanned or image-based. "
            "AirCo currently supports text-based PDF statements."
        )
    if cap.capability == Capability.UNREADABLE or det is None:
        return DocumentState.FAILED, cap.reason or "The file could not be read."

    if det.confidence in (Confidence.UNKNOWN, Confidence.LOW) or not det.bank_id:
        return DocumentState.UNKNOWN_BANK, "We could not confidently identify the bank. Please select it."
    if not det.supported:
        return DocumentState.UNSUPPORTED_BANK, f"This looks like a {det.bank_name} statement. That bank is not supported yet."
    if det.hint_conflict:
        return DocumentState.AWAITING_CONFIRMATION, (
            f"The document looks like {det.bank_name}, but a different bank was suggested. Please confirm."
        )
    if det.confidence == Confidence.MEDIUM:
        return DocumentState.AWAITING_CONFIRMATION, f"Probably {det.bank_name}. Please confirm."
    extra = " Some pages are images without text." if cap.capability == Capability.MIXED else ""
    return DocumentState.DETECTED, f"{det.bank_name}.{extra}"


def analyze_text_pages(
    filename: str,
    cap: CapabilityResult,
    page_texts: Sequence[str],
    *,
    metadata_bank: Optional[str] = None,
    user_hint: Optional[str] = None,
) -> DocumentAnalysis:
    det = None
    if cap.capability in (Capability.TEXT, Capability.MIXED):
        det = detect_bank(page_texts, filename=filename, metadata_bank=metadata_bank, user_hint=user_hint)
    state, message = decide_state(cap, det)
    return DocumentAnalysis(filename=filename, state=state, capability=cap, detection=det, message=message)


def analyze_pdf(
    path: str,
    *,
    filename: Optional[str] = None,
    password: Optional[str] = None,
    metadata_bank: Optional[str] = None,
    user_hint: Optional[str] = None,
) -> DocumentAnalysis:
    cap, texts = check_pdf(path, password=password)
    name = filename or path.replace("\\", "/").rsplit("/", 1)[-1]
    return analyze_text_pages(name, cap, texts, metadata_bank=metadata_bank, user_hint=user_hint)


def analyze_scanned_with_ocr(
    filename: str,
    cap: CapabilityResult,
    ocr_texts: Sequence[str],
    *,
    user_hint: Optional[str] = None,
) -> DocumentAnalysis:
    """SCANNED file with OCR available: detect the bank from the OCR text of pages 1-2.

    A bank read from a scan is never trusted as a verified identification: HIGH/VERY_HIGH is capped at MEDIUM so
    the user must confirm. No OCR text (service down, timeout, unreadable) -> UNKNOWN_BANK: the user picks the bank.
    """
    det = None
    if any((t or "").strip() for t in ocr_texts):
        det = detect_bank(ocr_texts, filename=filename, metadata_bank=None, user_hint=user_hint)
        if det.confidence in (Confidence.VERY_HIGH, Confidence.HIGH):
            det.confidence = Confidence.MEDIUM
        det.reason = (det.reason + " " if det.reason else "") + "Read from a scanned image, so please confirm."
    note = ("This statement is a scan, so we will read it with OCR. Results are always marked for review: "
            "please check the figures.")
    if det is None or det.confidence in (Confidence.UNKNOWN, Confidence.LOW) or not det.bank_id:
        return DocumentAnalysis(filename=filename, state=DocumentState.UNKNOWN_BANK, capability=cap, detection=det,
                                message="This is a scanned statement and we could not confidently identify the bank. "
                                        "Please select it. " + note)
    return DocumentAnalysis(filename=filename, state=DocumentState.AWAITING_CONFIRMATION, capability=cap,
                            detection=det, message=f"Probably {det.bank_name}. Please confirm. " + note)
