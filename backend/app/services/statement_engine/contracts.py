"""Frozen data contracts for the Statement Engine (Slice 2).

Pure data, no I/O. Nothing here changes how statements are parsed today.
These types are what the analyze-first API (2C) and the UI (2D) will exchange.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Capability(str, Enum):
    """Can AirCo read this PDF at all? Text layer only (OCR for SCANNED/MIXED is the optional T4 tier)."""

    TEXT = "TEXT"            # usable text layer
    MIXED = "MIXED"          # some pages have text, some are image-only
    SCANNED = "SCANNED"      # no usable text layer (image-only, or text drawn as vector outlines)
    LOCKED = "LOCKED"        # password needed (or wrong password)
    UNREADABLE = "UNREADABLE"  # corrupt / cannot be opened


class Confidence(str, Enum):
    """Rule-based category, not a probability."""

    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"

    @property
    def auto_routable(self) -> bool:
        """Only these may skip the review screen's 'needs attention' marker."""
        return self in (Confidence.VERY_HIGH, Confidence.HIGH)


class DocumentState(str, Enum):
    """Per-document lifecycle in the analyze-first flow (see plan, 'API, states and data')."""

    UPLOADED = "UPLOADED"
    ANALYZING = "ANALYZING"
    DETECTED = "DETECTED"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    # exceptions, each its own state so the UI can say what to do
    UNSUPPORTED_SCANNED_PDF = "UNSUPPORTED_SCANNED_PDF"
    PASSWORD_REQUIRED = "PASSWORD_REQUIRED"
    UNKNOWN_BANK = "UNKNOWN_BANK"
    UNSUPPORTED_BANK = "UNSUPPORTED_BANK"   # bank known, no processor yet
    UNKNOWN_LAYOUT = "UNKNOWN_LAYOUT"
    FAILED = "FAILED"


class EvidenceKind(str, Enum):
    IFSC_LABELLED = "IFSC_LABELLED"          # "IFSC: HDFC0001234" on page 1-2
    IFSC_HEADER = "IFSC_HEADER"              # unlabelled IFSC inside the page-1 header block
    HEADER_NAME = "HEADER_NAME"              # bank name in the page-1 header block
    RUNNING_HEADER = "RUNNING_HEADER"        # bank name in the header/footer of 2+ pages
    DOMAIN = "DOMAIN"                        # hdfcbank.com etc. on page 1-2 or in running header/footer
    PAGE1_NAME = "PAGE1_NAME"                # bank name elsewhere on page 1 (weak)
    STATEMENT_PHRASE = "STATEMENT_PHRASE"    # bank-specific wording in the header block (weak)
    # supporting only: never create confidence on their own
    FILENAME = "FILENAME"
    METADATA = "METADATA"
    USER_HINT = "USER_HINT"


# Evidence from the document itself. Supporting kinds are recorded but never counted toward confidence.
DOCUMENT_EVIDENCE = frozenset(
    {
        EvidenceKind.IFSC_LABELLED,
        EvidenceKind.IFSC_HEADER,
        EvidenceKind.HEADER_NAME,
        EvidenceKind.RUNNING_HEADER,
        EvidenceKind.DOMAIN,
        EvidenceKind.PAGE1_NAME,
        EvidenceKind.STATEMENT_PHRASE,
    }
)


@dataclass
class Evidence:
    kind: EvidenceKind
    bank_id: str
    weight: int
    matched: str = ""          # the text that matched (short)
    page: Optional[int] = None  # 1-based

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "bank_id": self.bank_id,
            "weight": self.weight,
            "matched": self.matched,
            "page": self.page,
        }


@dataclass
class DetectionResult:
    bank_id: Optional[str]                 # None when UNKNOWN
    bank_name: Optional[str]
    confidence: Confidence
    score: int = 0                         # document-evidence points for the winner
    runner_up_id: Optional[str] = None
    runner_up_score: int = 0
    supported: bool = False                # a processor exists for this bank today
    processor_key: Optional[str] = None
    evidence: List[Evidence] = field(default_factory=list)
    supporting: List[Evidence] = field(default_factory=list)   # filename / metadata / user hint
    hint_conflict: bool = False            # a user/metadata hint names a different bank than the document
    looks_like_statement: bool = True      # a transaction table was found; False caps confidence at LOW
    reason: str = ""                       # one plain sentence, safe to show

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bank_id": self.bank_id,
            "bank_name": self.bank_name,
            "confidence": self.confidence.value,
            "score": self.score,
            "runner_up_id": self.runner_up_id,
            "runner_up_score": self.runner_up_score,
            "supported": self.supported,
            "processor_key": self.processor_key,
            "evidence": [e.to_dict() for e in self.evidence],
            "supporting": [e.to_dict() for e in self.supporting],
            "hint_conflict": self.hint_conflict,
            "looks_like_statement": self.looks_like_statement,
            "reason": self.reason,
        }


@dataclass
class CapabilityResult:
    capability: Capability
    page_count: int = 0
    text_pages: int = 0
    image_only_pages: int = 0
    blank_pages: int = 0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability": self.capability.value,
            "page_count": self.page_count,
            "text_pages": self.text_pages,
            "image_only_pages": self.image_only_pages,
            "blank_pages": self.blank_pages,
            "reason": self.reason,
        }


@dataclass
class DocumentAnalysis:
    """Everything the review screen needs about one uploaded file."""

    filename: str
    state: DocumentState
    capability: CapabilityResult
    detection: Optional[DetectionResult] = None
    message: str = ""     # plain-language text for the user

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "state": self.state.value,
            "capability": self.capability.to_dict(),
            "detection": self.detection.to_dict() if self.detection else None,
            "message": self.message,
        }
