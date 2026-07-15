"""
Airco Insights — Karnataka Bank AI Fallback
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

FALLBACK_CATEGORIES = [
    "Food & Dining", "Shopping", "Travel", "Entertainment", "Bills & Utilities",
    "Health & Medical", "Education", "Fuel & Transport", "Groceries", "Insurance",
    "Investment", "Loan Payment", "Salary", "Transfer", "ATM Withdrawal",
    "Refund", "Others",
]


@dataclass
class AIClassificationResult:
    total_classified: int; ai_classified: int; rule_classified: int; fallback_classified: int
    provider_used: str; cost_estimate: float = 0.0; errors: List[str] = field(default_factory=list)


class KarnatakaAIFallback:
    BATCH_SIZE = 20

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def classify(self, transactions: List[Dict[str, Any]], bank_name: str = "Karnataka Bank",
                 account_type: str = "savings") -> Tuple[List[Dict[str, Any]], AIClassificationResult]:
        if not transactions:
            return [], AIClassificationResult(0,0,0,0,"none")
        if not self.api_key:
            self.logger.warning("No API key — returning rule-fallback categories")
            result = [dict(t, category=t.get("category") or "Others") for t in transactions]
            return result, AIClassificationResult(len(transactions),0,0,len(transactions),"none")
        provider = "claude" if self.api_key.startswith("sk-ant-") else "groq"
        classified, ai_count, fb_count, errors = [], 0, 0, []
        for i in range(0, len(transactions), self.BATCH_SIZE):
            batch = transactions[i:i+self.BATCH_SIZE]
            try:
                results = self._classify_batch(batch, provider, bank_name, account_type)
                classified.extend(results); ai_count += len(results)
            except Exception as e:
                self.logger.warning("Batch %d failed: %s — using fallback", i//self.BATCH_SIZE, e)
                errors.append(str(e))
                for t in batch:
                    classified.append(dict(t, category=t.get("category") or "Others"))
                    fb_count += 1
        cost = self._estimate_cost(len(transactions), provider)
        return classified, AIClassificationResult(len(transactions), ai_count, 0, fb_count, provider, cost, errors)

    def _classify_batch(self, batch: List[Dict], provider: str, bank_name: str, account_type: str) -> List[Dict]:
        descriptions = [f"{i+1}. {t.get('description','')} | {t.get('debit') or ''} DR | {t.get('credit') or ''} CR"
                        for i, t in enumerate(batch)]
        prompt = (f"Classify these {bank_name} bank transactions into categories.\n"
                  f"Categories: {', '.join(FALLBACK_CATEGORIES)}\n"
                  f"Transactions:\n" + "\n".join(descriptions) +
                  f"\n\nReturn JSON array: [{{\"index\":1,\"category\":\"Food & Dining\"}}, ...]")
        raw_text = self._call_api(prompt, provider)
        return self._parse_and_merge(raw_text, batch)

    def _call_api(self, prompt: str, provider: str) -> str:
        if provider == "claude":
            from app.services.intelligence.claude_intelligence import ClaudeIntelligenceLayer
            client = ClaudeIntelligenceLayer(api_key=self.api_key)
            return client.complete(prompt)
        else:
            from app.services.intelligence.groq_intelligence import GroqIntelligenceLayer
            client = GroqIntelligenceLayer(api_key=self.api_key)
            return client.complete(prompt)

    def _parse_and_merge(self, raw: str, batch: List[Dict]) -> List[Dict]:
        results = list(batch)
        try:
            m = re.search(r'\[.*\]', raw, re.DOTALL)
            if m:
                items = json.loads(m.group())
                cat_map = {item["index"]: item.get("category","Others") for item in items if "index" in item}
                for i, t in enumerate(results):
                    results[i] = dict(t, category=cat_map.get(i+1, t.get("category","Others")))
        except Exception as e:
            self.logger.warning("JSON parse failed: %s", e)
            for i, t in enumerate(results):
                results[i] = dict(t, category=t.get("category","Others"))
        return results

    def _estimate_cost(self, n: int, provider: str) -> float:
        tokens = n * 50
        return round(tokens / 1_000_000 * (3.0 if provider == "claude" else 0.27), 6)

