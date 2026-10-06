"""Statement Engine (Slice 2): analyze-first bank detection. Observe-only until the 2C API wires it in."""
from .analyzer import analyze_pdf, analyze_text_pages, decide_state
from .capability import PageInfo, check_pdf, classify_pages
from .contracts import (
    Capability,
    CapabilityResult,
    Confidence,
    DetectionResult,
    DocumentAnalysis,
    DocumentState,
    Evidence,
    EvidenceKind,
)
from .detector import detect_bank
from .layouts import LayoutDefinition, LayoutRegistry, LayoutResult, UNKNOWN_LAYOUT_ID, default_layout_registry, detect_layout
from .registry import BankConfig, BankRegistry, default_registry, load_registry

__all__ = [
    "analyze_pdf", "analyze_text_pages", "decide_state", "PageInfo", "check_pdf", "classify_pages",
    "Capability", "CapabilityResult", "Confidence", "DetectionResult", "DocumentAnalysis",
    "DocumentState", "Evidence", "EvidenceKind", "detect_bank", "BankConfig", "BankRegistry",
    "default_registry", "load_registry", "LayoutDefinition", "LayoutRegistry", "LayoutResult", "UNKNOWN_LAYOUT_ID",
    "default_layout_registry", "detect_layout",
]
