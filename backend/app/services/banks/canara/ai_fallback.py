"""
Airco Insights — Canara Bank AI Fallback
==========================================
Full-grade AI classifier mirroring HDFCAIFallback:
cost estimation, batch processing, Claude/Groq routing,
fallback to Others when AI unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ...intelligence import ClaudeIntelligenceLayer, GroqIntelligenceLayer, LearningStore

from .._shared.category_registry import (
    get_allowed_categories,
    normalize_category,
)

logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = get_allowed_categories()


@dataclass
class AIClassificationResult:
    classified_count: int
    total_sent: int
    api_calls: int
    estimated_cost_usd: float
    estimated_cost_inr: float


class CanaraAIFallback:
    """AI fallback classifier for Canara Bank transactions."""

    COST_PER_1K_INPUT  = 0.003
    COST_PER_1K_OUTPUT = 0.015
    AVG_TOKENS_PER_TXN = 50
    AVG_OUTPUT_TOKENS  = 20
    MAX_BATCH_SIZE     = 20
    USD_TO_INR         = 83

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        if api_key:
            from ...intelligence import ClaudeIntelligenceLayer, GroqIntelligenceLayer, LearningStore
            self.learning_store = LearningStore()
            intelligence_cls = (
                ClaudeIntelligenceLayer if api_key.startswith("sk-ant-") else GroqIntelligenceLayer
            )
            self.intelligence = intelligence_cls(
                api_key=api_key,
                bank_name="Canara",
                learning_store=self.learning_store,
            )
        else:
            self.intelligence = None

    def estimate_cost(self, transaction_count: int) -> Dict[str, Any]:
        batches = (transaction_count + self.MAX_BATCH_SIZE - 1) // self.MAX_BATCH_SIZE
        input_tokens  = transaction_count * self.AVG_TOKENS_PER_TXN + batches * 500
        output_tokens = transaction_count * self.AVG_OUTPUT_TOKENS
        cost_usd = (
            (input_tokens  / 1000) * self.COST_PER_1K_INPUT +
            (output_tokens / 1000) * self.COST_PER_1K_OUTPUT
        )
        return {
            "transaction_count": transaction_count,
            "estimated_batches": batches,
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": output_tokens,
            "estimated_cost_usd": round(cost_usd, 4),
            "estimated_cost_inr": round(cost_usd * self.USD_TO_INR, 2),
        }

    def classify(
        self,
        transactions: List[Dict[str, Any]],
        bank_name: str = "Canara",
        account_type: str = "Salaried",
    ) -> Tuple[List[Dict[str, Any]], AIClassificationResult]:
        if not transactions:
            return [], AIClassificationResult(0, 0, 0, 0.0, 0.0)

        if not self.intelligence:
            self.logger.warning("No API key — using fallback_to_others")
            return self._fallback_to_others(transactions), AIClassificationResult(
                0, len(transactions), 0, 0.0, 0.0
            )

        classified, stats = self.intelligence.classify(
            transactions=transactions,
            bank_name=bank_name,
            account_type=account_type,
            allowed_categories=set(ALLOWED_CATEGORIES),
        )
        return classified, AIClassificationResult(
            classified_count=stats.classified_count,
            total_sent=stats.total_sent,
            api_calls=stats.api_calls,
            estimated_cost_usd=stats.estimated_cost_usd,
            estimated_cost_inr=stats.estimated_cost_inr,
        )

    def _classify_batch(
        self,
        batch: List[Dict[str, Any]],
        bank_name: str,
        account_type: str,
    ) -> List[Dict[str, Any]]:
        try:
            import anthropic
        except ImportError:
            return self._fallback_to_others(batch)

        client = anthropic.Anthropic(api_key=self.api_key)
        txn_lines = []
        for i, txn in enumerate(batch):
            is_debit = txn.get("debit") is not None
            amount = txn.get("debit") or txn.get("credit") or 0
            txn_lines.append(
                f"{i+1}. [{txn.get('date')}] {str(txn.get('description', ''))[:100]} | "
                f"{'DEBIT' if is_debit else 'CREDIT'}: \u20b9{amount:,.2f}"
            )

        cats = ", ".join(ALLOWED_CATEGORIES)
        prompt = (
            f"Classify these Canara Bank transactions for a {account_type} account.\n"
            f"Categories: {cats}\n\nTransactions:\n" + "\n".join(txn_lines) +
            "\n\nRespond with JSON array only. Each object: "
            '{"index": 1, "category": "...", "confidence": 0.85}'
        )

        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            import json
            text = response.content[0].text.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            results = json.loads(text)
            result_map = {r["index"]: r for r in results}
            classified = []
            for i, txn in enumerate(batch):
                txn_copy = dict(txn)
                ai_res = result_map.get(i + 1, {})
                cat    = ai_res.get("category", "")
                conf   = float(ai_res.get("confidence", 0.5))
                is_debit = txn.get("debit") is not None
                if cat not in ALLOWED_CATEGORIES:
                    cat  = "Others Debit" if is_debit else "Others Credit"
                    conf = 0.5
                txn_copy["category"]   = cat
                txn_copy["confidence"] = conf
                txn_copy["source"]     = "ai_classifier"
                classified.append(txn_copy)
            return classified
        except Exception as e:
            self.logger.error("AI batch failed: %s", e)
            return self._fallback_to_others(batch)

    def _fallback_to_others(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        for txn in transactions:
            txn_copy = dict(txn)
            is_debit = txn.get("debit") is not None
            txn_copy["category"]   = "Others Debit" if is_debit else "Others Credit"
            txn_copy["confidence"] = 0.5
            txn_copy["source"]     = "ai_fallback_default"
            result.append(txn_copy)
        return result


__all__ = ["AIClassificationResult", "CanaraAIFallback"]
