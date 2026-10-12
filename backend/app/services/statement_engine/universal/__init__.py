"""T3 universal reader: infers a runtime LayoutSpec for any text-layer statement and runs the
ordinary engine + checks on it. Verdict is capped at REVIEW (code GENERAL_READER); FAILED on
any undecidable structure, budget overrun or failed check. Never raises.
"""
from .reader import (GENERAL_READER, UniversalResult, quick_verdict, read)

__all__ = ["GENERAL_READER", "UniversalResult", "quick_verdict", "read"]
