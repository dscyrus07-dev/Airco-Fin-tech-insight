"""Airco Insights - Paytm Bank Classifier."""

from __future__ import annotations

from typing import Optional

from .._shared.generic_bank import GenericClassifier

from .rule_engine import CONFIG


class PaytmClassifier(GenericClassifier):
    def __init__(self, keywords_file: Optional[str] = None):
        super().__init__(CONFIG, keywords_file=keywords_file)


__all__ = ["PaytmClassifier"]
