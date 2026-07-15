"""Shared classification package (Phase 2b+)."""

from .rule_engine import ClassificationResult, JsonRuleEngine, RuleEngine, default_rules_path, load_rules

__all__ = [
    "ClassificationResult",
    "JsonRuleEngine",
    "RuleEngine",
    "default_rules_path",
    "load_rules",
]
