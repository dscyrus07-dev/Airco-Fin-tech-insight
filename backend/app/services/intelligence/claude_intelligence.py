"""Claude-powered intelligence layer for selective transaction enrichment and learning."""

from __future__ import annotations

import json
import logging
import os
import time

from .groq_intelligence import GroqClassificationStats, GroqIntelligenceLayer

logger = logging.getLogger(__name__)


class ClaudeIntelligenceLayer(GroqIntelligenceLayer):
    """Drop-in Claude layer with the same interface as GroqIntelligenceLayer."""

    SYSTEM_PROMPT = (
        "You are a financial transaction classifier for Indian bank statements. "
        "You have expert knowledge of Indian payment systems (NEFT, RTGS, IMPS, UPI, NACH, ECS, BBPS), "
        "Indian banks (HDFC, SBI, ICICI, Axis, Kotak), Indian merchants, EMI patterns, salary credits, "
        "GST payments, and TDS deductions. Classify transactions into the provided categories only. "
        "Return strict JSON array named results. No markdown."
    )

    def __init__(
        self,
        api_key: str | None = None,
        bank_name: str = "",
        model: str | None = None,
        learning_store=None,
    ):
        super().__init__(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
            bank_name=bank_name,
            model=model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            learning_store=learning_store,
        )

    def classify(self, transactions, bank_name, account_type, allowed_categories):
        if not transactions:
            return [], GroqClassificationStats(0, 0, 0, 0.0, 0.0)

        bank_name = bank_name or self.bank_name or ""
        allowed = [str(cat) for cat in allowed_categories if str(cat).strip()]
        recent = self.learning_store.recent_learnings(bank_name=bank_name, limit=8)

        output = []
        pending = []
        for idx, txn in enumerate(transactions):
            txn_copy = dict(txn)
            cache_hit = self.learning_store.lookup(
                txn_copy.get("description") or txn_copy.get("Description") or "",
                bank_name=bank_name,
                account_type=account_type,
            )
            if cache_hit:
                txn_copy["category"] = cache_hit["category"]
                txn_copy["confidence"] = max(float(cache_hit.get("confidence", 0.9)), float(txn_copy.get("confidence") or txn_copy.get("Confidence") or 0.0))
                txn_copy["source"] = "learning_store"
                txn_copy["matched_rule"] = "learning_cache"
                output.append(txn_copy)
                continue
            pending.append((idx, txn_copy, cache_hit))
            output.append(txn_copy)

        if not pending:
            return output, GroqClassificationStats(len(output), len(transactions), 0, 0.0, 0.0)

        if not self.api_key:
            self.logger.warning("Claude API key not configured; using fallback classifications only.")
            for _, txn_copy, _ in pending:
                is_debit = self._is_debit(txn_copy)
                txn_copy["category"] = txn_copy.get("category") or ("Others Debit" if is_debit else "Others Credit")
                txn_copy["confidence"] = float(txn_copy.get("confidence") or txn_copy.get("Confidence") or 0.5)
                txn_copy["source"] = txn_copy.get("source") or "claude_disabled"
            usd, inr = self._cost_estimate(len(pending))
            return output, GroqClassificationStats(len(output) - len(pending), len(transactions), 0, usd, inr)

        try:
            import anthropic
        except Exception as exc:
            self.logger.error("Anthropic SDK unavailable: %s", exc)
            for _, txn_copy, _ in pending:
                is_debit = self._is_debit(txn_copy)
                txn_copy["category"] = txn_copy.get("category") or ("Others Debit" if is_debit else "Others Credit")
                txn_copy["confidence"] = float(txn_copy.get("confidence") or txn_copy.get("Confidence") or 0.5)
                txn_copy["source"] = txn_copy.get("source") or "claude_unavailable"
            usd, inr = self._cost_estimate(len(pending))
            return output, GroqClassificationStats(len(output) - len(pending), len(transactions), 0, usd, inr)

        client = anthropic.Anthropic(api_key=self.api_key)
        prompt = self._build_prompt([txn for _, txn, _ in pending], bank_name, account_type, allowed, recent)

        results = []
        for attempt in range(self.MAX_RETRIES):
            try:
                response = client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    temperature=0.1,
                    system=self.SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = ""
                for block in getattr(response, "content", []) or []:
                    if getattr(block, "type", "") == "text" or hasattr(block, "text"):
                        response_text += getattr(block, "text", "")
                results = self._parse_response(response_text)
                break
            except Exception as exc:
                error_str = str(exc)
                is_retryable = (
                    "429" in error_str
                    or "timeout" in error_str.lower()
                    or "connection" in error_str.lower()
                    or "rate_limit" in error_str.lower()
                )
                if not is_retryable or attempt == self.MAX_RETRIES - 1:
                    self.logger.error("Claude API failed after %d attempts: %s", attempt + 1, exc)
                    results = []
                    break
                self.logger.warning("Claude retry %d/%d in %ds: %s", attempt + 1, self.MAX_RETRIES, self.RETRY_DELAYS[attempt], exc)
                time.sleep(self.RETRY_DELAYS[attempt])

        result_map = {}
        for item in results:
            if not isinstance(item, dict):
                continue
            try:
                result_map[int(item.get("index"))] = item
            except Exception:
                continue

        classified_now = 0
        for rel_idx, (orig_idx, txn_copy, _) in enumerate(pending, start=1):
            ai_result = result_map.get(rel_idx, {})
            is_debit = self._is_debit(txn_copy)
            category = self._normalize_ai_category(ai_result, txn_copy, is_debit, allowed)
            confidence = ai_result.get("confidence", 0.5)
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = 0.5

            if confidence < self.CONFIDENCE_FLOOR:
                category = "Others Debit" if is_debit else "Others Credit"
                confidence = 0.5

            reason = str(ai_result.get("reason") or "")
            entity = str(ai_result.get("entity") or ai_result.get("normalized_entity") or "")
            recurring_type = str(ai_result.get("recurring_type") or "")
            pattern = str(ai_result.get("pattern") or "")
            should_learn = bool(ai_result.get("should_learn", confidence >= 0.85))

            txn_copy["category"] = category
            txn_copy["confidence"] = confidence
            txn_copy["source"] = "claude_llm"
            txn_copy["matched_rule"] = reason or "claude"
            if entity:
                txn_copy["matched_token"] = entity
            if recurring_type:
                txn_copy["recurring_type"] = recurring_type
            if ai_result.get("is_recurring") is not None:
                txn_copy["is_recurring"] = bool(ai_result.get("is_recurring"))

            if should_learn and confidence >= 0.85:
                self.learning_store.record_observation(
                    description=txn_copy.get("description") or txn_copy.get("Description") or entity or "",
                    category=category,
                    confidence=confidence,
                    source="llm",
                    bank_name=bank_name,
                    account_type=account_type,
                    pattern=pattern,
                    recurring_type=recurring_type,
                    metadata={"reason": reason, "entity": entity},
                )
            classified_now += 0 if category.startswith("Others") else 1

        usd, inr = self._cost_estimate(len(pending))
        return output, GroqClassificationStats(classified_now, len(transactions), 1 if pending else 0, usd, inr)

    def _normalize_ai_category(self, ai_result, txn_copy, is_debit, allowed):
        category = str(ai_result.get("category") or "").strip()
        category = self._normalize_category_value(category, is_debit)
        if allowed and category not in allowed:
            category = txn_copy.get("category") or ("Others Debit" if is_debit else "Others Credit")
        if not category:
            category = txn_copy.get("category") or ("Others Debit" if is_debit else "Others Credit")
        return category

    @staticmethod
    def _normalize_category_value(category, is_debit):
        from app.services.banks._shared.category_registry import normalize_category

        return normalize_category(category, is_debit=is_debit)
