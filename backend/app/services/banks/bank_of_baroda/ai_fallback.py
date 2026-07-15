"""
Airco Insights — Bank of Baroda AI Fallback
=============================================
Full-grade AI fallback mirroring HDFCAIFallback:
estimate_cost(), _classify_batch(), _fallback_to_others(),
batch processing with Claude (sk-ant-) or Groq provider selection.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

USD_TO_INR = 83
BATCH_SIZE  = 20

CATEGORIES = [
    "Salary", "Transfer", "Cash Deposit", "Refund", "Interest", "Loan Credit",
    "ATM Withdrawal", "Bank Charges", "Bounce", "Loan Payment", "Food",
    "Shopping", "Transport", "Bill Payment", "Entertainment", "Insurance",
    "Travel", "Investment", "Others Debit", "Others Credit",
]


@dataclass
class AIClassificationResult:
    classified_count: int
    unclassified_count: int
    estimated_cost_inr: float
    model_used: str
    batches_processed: int
    errors: List[str]


class BankOfBarodaAIFallback:
    """AI-driven fallback classifier for Bank of Baroda unresolved transactions."""

    INPUT_COST_PER_1K  = 0.003
    OUTPUT_COST_PER_1K = 0.015
    TOKENS_PER_TXN     = 40
    OUTPUT_TOKENS      = 20

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def estimate_cost(self, transaction_count: int) -> Dict[str, Any]:
        input_tokens  = transaction_count * self.TOKENS_PER_TXN
        output_tokens = transaction_count * self.OUTPUT_TOKENS
        input_cost    = (input_tokens  / 1000) * self.INPUT_COST_PER_1K
        output_cost   = (output_tokens / 1000) * self.OUTPUT_COST_PER_1K
        total_usd     = input_cost + output_cost
        return {
            "transaction_count": transaction_count,
            "estimated_cost_usd": round(total_usd, 4),
            "estimated_cost_inr": round(total_usd * USD_TO_INR, 2),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    def classify(
        self,
        transactions: List[Dict[str, Any]],
        bank_name: str = "Bank of Baroda",
        account_type: str = "Salaried",
    ) -> Tuple[List[Dict[str, Any]], AIClassificationResult]:
        if not transactions:
            return [], AIClassificationResult(0, 0, 0.0, "none", 0, [])

        if not self.api_key:
            self.logger.warning("No API key — returning default categories for BOB AI fallback")
            return self._fallback_to_others(transactions), AIClassificationResult(
                0, len(transactions), 0.0, "none", 0, ["No API key provided"]
            )

        use_claude = self.api_key.startswith("sk-ant-")
        model_used = "claude" if use_claude else "groq"

        classified, errors, batches = [], [], 0
        for i in range(0, len(transactions), BATCH_SIZE):
            batch = transactions[i: i + BATCH_SIZE]
            try:
                batch_result = self._classify_batch(batch, bank_name, account_type, use_claude)
                classified.extend(batch_result)
            except Exception as exc:
                self.logger.error("BOB AI fallback batch %d failed: %s", batches, exc)
                errors.append(str(exc))
                classified.extend(self._fallback_to_others(batch))
            batches += 1

        cost = self.estimate_cost(len(transactions))
        result = AIClassificationResult(
            classified_count=sum(1 for t in classified if not t.get("category", "").startswith("Others")),
            unclassified_count=sum(1 for t in classified if t.get("category", "").startswith("Others")),
            estimated_cost_inr=cost["estimated_cost_inr"],
            model_used=model_used,
            batches_processed=batches,
            errors=errors,
        )
        return classified, result

    def _classify_batch(
        self,
        batch: List[Dict[str, Any]],
        bank_name: str,
        account_type: str,
        use_claude: bool,
    ) -> List[Dict[str, Any]]:
        prompt = self._build_prompt(batch, bank_name, account_type)
        if use_claude:
            raw = self._call_claude(prompt)
        else:
            raw = self._call_groq(prompt)
        return self._parse_response(raw, batch)

    def _build_prompt(self, batch: List[Dict], bank_name: str, account_type: str) -> str:
        cats = ", ".join(CATEGORIES)
        lines = "\n".join(
            f"{i+1}. {t.get('description','')[:80]} | "
            f"{'Dr' if t.get('debit') else 'Cr'} "
            f"{t.get('debit') or t.get('credit', 0):.2f}"
            for i, t in enumerate(batch)
        )
        return (
            f"Classify each Bank of Baroda ({account_type}) transaction into exactly one category.\n"
            f"Categories: {cats}\n"
            f"Transactions:\n{lines}\n\n"
            f"Reply ONLY as JSON array: [{{\"index\":1,\"category\":\"...\",\"confidence\":0.9}}, ...]"
        )

    def _call_claude(self, prompt: str) -> str:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            msg = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text
        except Exception as exc:
            raise RuntimeError(f"Claude API error: {exc}") from exc

    def _call_groq(self, prompt: str) -> str:
        try:
            from groq import Groq
            client = Groq(api_key=self.api_key)
            resp = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
                temperature=0.1,
            )
            return resp.choices[0].message.content
        except Exception as exc:
            raise RuntimeError(f"Groq API error: {exc}") from exc

    def _parse_response(self, raw: str, batch: List[Dict]) -> List[Dict[str, Any]]:
        result = [dict(t) for t in batch]
        try:
            start = raw.find("[")
            end   = raw.rfind("]") + 1
            if start == -1 or end == 0:
                return self._fallback_to_others(batch)
            items = json.loads(raw[start:end])
            for item in items:
                idx = int(item.get("index", 0)) - 1
                if 0 <= idx < len(result):
                    cat  = item.get("category", "")
                    conf = float(item.get("confidence", 0.7))
                    if cat in CATEGORIES:
                        result[idx]["category"]   = cat
                        result[idx]["confidence"] = conf
                        result[idx]["source"]     = "ai_fallback"
        except Exception as exc:
            self.logger.warning("BOB AI response parse error: %s", exc)
        return result

    def _fallback_to_others(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        for txn in transactions:
            t = dict(txn)
            if not t.get("category") or t["category"].startswith("Others"):
                t["category"]   = "Others Debit" if t.get("debit") else "Others Credit"
                t["confidence"] = 0.5
                t["source"]     = "ai_fallback_default"
            result.append(t)
        return result


__all__ = ["BankOfBarodaAIFallback", "AIClassificationResult"]
