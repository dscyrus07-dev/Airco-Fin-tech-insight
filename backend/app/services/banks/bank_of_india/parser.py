"""Airco Insights - Bank of India Parser"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

import pdfplumber

from .._shared.generic_bank import GenericParseError, GenericTransaction

from .structure_validator import BANK_OF_INDIA_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class BankOfIndiaParseResult:
    transactions: List[GenericTransaction]
    total_count: int
    parse_method: str
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    total_credits: float = 0.0
    total_debits: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_count": self.total_count,
            "parse_method": self.parse_method,
            "opening_balance": self.opening_balance,
            "closing_balance": self.closing_balance,
            "total_credits": self.total_credits,
            "total_debits": self.total_debits,
            "warnings": self.warnings,
        }


class BankOfIndiaParser:
    BANK_NAME = "Bank of India"

    ROW_RE = re.compile(r"^(?P<serial>\d+)\s+(?P<date>\d{2}[\-/]\d{2}[\-/]\d{4})\s+(?P<rest>.*)$")
    HEADER_RE = re.compile(r"\b(sr\s*no|date|remarks|debit|credit|balance)\b", re.IGNORECASE)
    IGNORE_RE = re.compile(r"^(transaction date|amount|cheque|from:|to:)", re.IGNORECASE)

    def __init__(self, audit_service=None, job_id=None):
        self.bank_name = self.BANK_NAME
        self.audit_service = audit_service
        self.job_id = job_id
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._hygiene_result = None
        self._collected_parser_metrics = []

    def parse(self, file_path: str, text_content: str = "") -> BankOfIndiaParseResult:
        # Try coordinate/table extraction first — it correctly separates Debit/Credit columns
        table_txns, table_open, table_close, table_warnings = self._parse_table(file_path)

        raw_text = text_content or self._extract_text(file_path)
        if not raw_text.strip() and not table_txns:
            raise GenericParseError(
                "Could not extract readable text from this Bank of India PDF.",
                error_code="NO_TEXT",
                details={"file": file_path},
            )

        text_txns, text_open, text_close, text_warnings = self._parse_text(raw_text) if raw_text.strip() else ([], None, None, [])

        # Use whichever parse produced more transactions
        if len(table_txns) >= len(text_txns) and table_txns:
            transactions = table_txns
            opening_balance = table_open
            closing_balance = table_close
            warnings = table_warnings
            parse_method = "table"
        elif text_txns:
            transactions = text_txns
            opening_balance = text_open
            closing_balance = text_close
            warnings = text_warnings
            parse_method = "text"
        else:
            raise GenericParseError(
                "Could not extract transactions from this Bank of India PDF.",
                error_code="NO_TRANSACTIONS",
                details={"file": file_path},
            )

        if opening_balance is None and transactions:
            first = transactions[0]
            if first.balance is not None:
                opening_balance = round(float(first.balance) + float(first.debit or 0) - float(first.credit or 0), 2)

        if closing_balance is None and transactions:
            closing_balance = self._as_float(transactions[-1].balance)

        total_credits = sum(float(getattr(txn, "credit", 0) or 0) for txn in transactions)
        total_debits = sum(float(getattr(txn, "debit", 0) or 0) for txn in transactions)

        return BankOfIndiaParseResult(
            transactions=transactions,
            total_count=len(transactions),
            parse_method=parse_method,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits,
            warnings=warnings,
        )

    def _parse_table(self, file_path: str) -> Tuple[List[GenericTransaction], Optional[float], Optional[float], List[str]]:
        """Extract transactions using pdfplumber's table extractor.

        Columns: Sr No | Date | Remarks | Debit | Credit | Balance
        Direction is determined solely by balance-delta to avoid being misled
        by '/DR/' tokens embedded in UPI reference numbers.
        Handles both forward-chronological and reversed-chronological statements.
        """
        warnings: List[str] = []

        # ── Step 1: collect raw rows from all pages ──────────────────────────
        raw_rows: List[dict] = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    table = page.extract_table()
                    if not table:
                        continue
                    for row in table:
                        if not row or len(row) < 4:
                            continue
                        row_str = " ".join(str(c or "") for c in row).lower()
                        # Skip pure header rows (no date present)
                        if not re.search(r"\d{2}[\-/]\d{2}[\-/]\d{4}", row_str):
                            continue
                        cells = [str(c or "").strip() for c in row]
                        date_text = desc_text = None
                        debit_val = credit_val = 0.0
                        balance_val: Optional[float] = None
                        for idx in range(len(cells)):
                            if re.fullmatch(r"\d{2}[\-/]\d{2}[\-/]\d{4}", cells[idx]):
                                date_text = cells[idx]
                                desc_text = cells[idx + 1] if idx + 1 < len(cells) else ""
                                debit_val = self._as_float(cells[idx + 2].replace(",", "").replace("₹", "").strip()) or 0.0 if idx + 2 < len(cells) else 0.0
                                credit_val = self._as_float(cells[idx + 3].replace(",", "").replace("₹", "").strip()) or 0.0 if idx + 3 < len(cells) else 0.0
                                raw_bal = cells[idx + 4].replace(",", "").replace("₹", "").strip() if idx + 4 < len(cells) else ""
                                balance_val = self._as_float(raw_bal)
                                break
                        if date_text is None or balance_val is None:
                            continue
                        try:
                            norm_date = self._normalize_date(date_text)
                        except Exception:
                            continue
                        raw_rows.append({
                            "date": norm_date,
                            "desc": self._normalize_spacing(desc_text or ""),
                            "debit_col": debit_val,
                            "credit_col": credit_val,
                            "balance": balance_val,
                        })
        except Exception as exc:
            logger.warning("BOI table extraction failed: %s", exc)
            return [], None, None, [str(exc)]

        if not raw_rows:
            return [], None, None, warnings

        # ── Step 2: detect statement order ───────────────────────────────────
        # In a reversed (most-recent-first) statement:
        #   row[i].balance - row[i+1].balance ≈ ±row[i].amount
        # In a forward statement:
        #   row[i+1].balance - row[i].balance ≈ ±row[i+1].amount
        fwd_hits = rev_hits = 0
        for i in range(len(raw_rows) - 1):
            curr = raw_rows[i]
            nxt = raw_rows[i + 1]
            amt_curr = curr["debit_col"] if curr["debit_col"] > 0 else curr["credit_col"]
            amt_nxt = nxt["debit_col"] if nxt["debit_col"] > 0 else nxt["credit_col"]
            delta = round(nxt["balance"] - curr["balance"], 2)
            if abs(abs(delta) - amt_nxt) <= 1.0:
                fwd_hits += 1
            if abs(abs(delta) - amt_curr) <= 1.0:
                rev_hits += 1
        is_reversed = rev_hits > fwd_hits

        # ── Step 3: assign debit/credit using correct delta direction ─────────
        transactions: List[GenericTransaction] = []
        for i, row in enumerate(raw_rows):
            amount = row["debit_col"] if row["debit_col"] > 0 else row["credit_col"]
            debit = credit = 0.0

            if is_reversed:
                # Reference balance is the NEXT row (earlier in time)
                ref_bal = raw_rows[i + 1]["balance"] if i + 1 < len(raw_rows) else None
            else:
                ref_bal = raw_rows[i - 1]["balance"] if i > 0 else None

            if ref_bal is not None and amount > 0:
                delta = round(row["balance"] - ref_bal, 2)
                if delta >= 0:
                    credit = amount
                else:
                    debit = amount
            elif row["debit_col"] > 0:
                debit = row["debit_col"]
            elif row["credit_col"] > 0:
                credit = row["credit_col"]

            transactions.append(GenericTransaction(
                date=row["date"],
                description=row["desc"],
                debit=debit,
                credit=credit,
                balance=row["balance"],
            ))

        # ── Step 4: derive opening/closing balance ────────────────────────────
        if is_reversed:
            # Last row in PDF is the earliest transaction → opening balance
            last = raw_rows[-1]
            amt = last["debit_col"] if last["debit_col"] > 0 else last["credit_col"]
            t_last = transactions[-1]
            opening_balance = round(last["balance"] + t_last.debit - t_last.credit, 2) if amt > 0 else last["balance"]
            closing_balance = transactions[0].balance
        else:
            first = raw_rows[0]
            t_first = transactions[0]
            opening_balance = round(first["balance"] + t_first.debit - t_first.credit, 2)
            closing_balance = transactions[-1].balance

        return transactions, opening_balance, closing_balance, warnings

    def _parse_text(self, raw_text: str) -> Tuple[List[GenericTransaction], Optional[float], Optional[float], List[str]]:
        lines = [self._clean_line(line) for line in raw_text.splitlines()]
        lines = [line for line in lines if line]

        transactions: List[GenericTransaction] = []
        warnings: List[str] = []
        opening_balance: Optional[float] = None
        prev_balance: Optional[float] = None
        in_table = False
        i = 0

        while i < len(lines):
            line = lines[i]

            if self._is_header_line(line):
                in_table = True
                i += 1
                continue

            if not in_table:
                maybe_opening = self._extract_opening_balance(line)
                if opening_balance is None and maybe_opening is not None:
                    opening_balance = maybe_opening
                i += 1
                continue

            if self._is_ignored_line(line):
                i += 1
                continue

            row_match = self.ROW_RE.match(line)
            if not row_match:
                i += 1
                continue

            row_lines = [line]
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if self._is_header_line(next_line) or self._is_ignored_line(next_line):
                    break
                if self.ROW_RE.match(next_line):
                    break
                row_lines.append(next_line)
                j += 1

            transaction = self._build_transaction(row_lines, None)
            if transaction is not None:
                transactions.append(transaction)
            else:
                warnings.append(f"Skipped unparsable row starting with: {line[:120]}")

            i = j

        # Post-process: fix direction for unmarked rows using balance-delta
        transactions = self._fix_directions_from_balance(transactions)

        closing_balance_final = self._as_float(transactions[-1].balance) if transactions else None
        return transactions, opening_balance, closing_balance_final, warnings

    def _build_transaction(self, row_lines: List[str], prev_balance: Optional[float]) -> Optional[GenericTransaction]:
        first_line = row_lines[0]
        row_match = self.ROW_RE.match(first_line)
        if not row_match:
            return None

        date_text = row_match.group("date")
        rest = " ".join(part.strip() for part in [row_match.group("rest"), *row_lines[1:]] if part and part.strip())
        rest = self._normalize_spacing(rest)

        amount, balance = self._extract_amount_and_balance(rest)
        if balance is None:
            return None

        description = self._strip_amount_tail(rest)
        description = self._normalize_spacing(description)
        description = description.strip(" -|")

        direction = self._infer_direction(description, amount, balance, prev_balance)
        if amount is None and prev_balance is not None and balance is not None:
            amount = abs(round(balance - prev_balance, 2))

        debit = amount if direction == "debit" else 0.0
        credit = amount if direction == "credit" else 0.0

        reference = self._extract_reference(description)
        normalized_date = self._normalize_date(date_text)

        return GenericTransaction(
            date=normalized_date,
            description=description or f"Transaction {row_match.group('serial')}",
            debit=debit or 0.0,
            credit=credit or 0.0,
            balance=balance,
            reference=reference or None,
            raw_line=" | ".join(row_lines),
        )

    def _fix_directions_from_balance(self, transactions: list) -> list:
        """Post-processing pass: re-classify direction for rows that had no explicit
        DR/CR marker, using the correct adjacent-balance delta.

        Handles both forward-chronological and reversed-chronological statements.
        """
        if len(transactions) < 2:
            return transactions

        # Determine statement order: compare dates of first vs last row
        # Also verify using balance chain: if balance[1] = balance[0] - dr[1] + cr[1] => forward
        #   if balance[1] = balance[0] + dr[1] - cr[1] => reversed
        # Use balance continuity to detect order
        def has_explicit_marker(desc: str) -> bool:
            upper = desc.upper()
            return bool(re.search(r'/(CR|CREDIT)/|\bCREDIT\b|/(DR|DEBIT)/|\bDEBIT\b', upper))

        # Find the balance delta between consecutive rows to detect ordering
        # In forward order: next_bal = curr_bal - curr_dr + curr_cr
        # In reversed order: next_bal = curr_bal + next_dr - next_cr
        forward_errors = 0
        reversed_errors = 0
        for i in range(len(transactions) - 1):
            curr = transactions[i]
            nxt = transactions[i + 1]
            if curr.balance is None or nxt.balance is None:
                continue
            fwd = round(curr.balance - nxt.debit + nxt.credit, 2)
            rev = round(curr.balance + nxt.debit - nxt.credit, 2)
            if abs(fwd - nxt.balance) > 1.0:
                forward_errors += 1
            if abs(rev - nxt.balance) > 1.0:
                reversed_errors += 1

        is_reversed = reversed_errors < forward_errors

        fixed = list(transactions)
        for i, txn in enumerate(fixed):
            if has_explicit_marker(txn.description):
                continue
            if txn.balance is None:
                continue

            # Determine the reference balance (prev-in-time)
            if is_reversed:
                # Reversed list: next entry is earlier in time
                ref_bal = fixed[i + 1].balance if i + 1 < len(fixed) else None
            else:
                ref_bal = fixed[i - 1].balance if i > 0 else None

            if ref_bal is None:
                continue

            amount = txn.debit if txn.debit > 0 else txn.credit
            if amount is None or amount == 0:
                continue

            delta = round(txn.balance - ref_bal, 2)
            if abs(delta - amount) <= 1.0:
                new_dir = 'credit'
            elif abs(delta + amount) <= 1.0:
                new_dir = 'debit'
            elif delta > 0:
                new_dir = 'credit'
            else:
                new_dir = 'debit'

            current_dir = 'credit' if txn.credit > 0 else 'debit'
            if new_dir != current_dir:
                fixed[i] = GenericTransaction(
                    date=txn.date,
                    description=txn.description,
                    debit=amount if new_dir == 'debit' else 0.0,
                    credit=amount if new_dir == 'credit' else 0.0,
                    balance=txn.balance,
                    reference=txn.reference,
                    raw_line=txn.raw_line,
                )

        return fixed

    def _infer_direction(
        self,
        description: str,
        amount: Optional[float],
        balance: Optional[float],
        prev_balance: Optional[float],
    ) -> str:
        upper = description.upper()

        # Explicit CR/DR markers in description are authoritative
        if re.search(r"/(CR|CREDIT)/|\bCREDIT\b", upper):
            return "credit"
        if re.search(r"/(DR|DEBIT)/|\bDEBIT\b", upper):
            return "debit"

        # Balance-delta is the most reliable signal — use it before keyword guesses
        if prev_balance is not None and balance is not None and amount is not None:
            delta = round(balance - prev_balance, 2)
            if abs(delta - amount) <= 1.0:
                return "credit"
            if abs(delta + amount) <= 1.0:
                return "debit"
            # delta sign as tiebreaker when amount doesn't exactly match
            if abs(delta) > 0.004:
                return "credit" if delta > 0 else "debit"

        # Keyword fallbacks only when balance-delta is unavailable
        if any(token in upper for token in ("BY CASH", "CASH DEP", "CASH DEPOSIT", "NEFT CR", "RTGS CR", "IMPS CR")):
            return "credit"

        if any(token in upper for token in ("ATM", "UPI", "CHARGE", "FEE", "FUND", "TRANSFER")):
            return "debit"

        return "debit" if amount is not None else "credit"

    def _extract_amount_and_balance(self, text: str) -> Tuple[Optional[float], Optional[float]]:
        amounts = re.findall(r"\d[\d,]*\.\d{2}", text)
        if not amounts:
            return None, None
        if len(amounts) == 1:
            return self._as_float(amounts[0]), None
        return self._as_float(amounts[-2]), self._as_float(amounts[-1])

    def _strip_amount_tail(self, text: str) -> str:
        cleaned = text.replace("₹", " ")
        cleaned = re.sub(r"\s*[\d,]+\.\d{2}\s+[\d,]+\.\d{2}\s*$", "", cleaned)
        cleaned = re.sub(r"\s*[\d,]+\.\d{2}\s*$", "", cleaned)
        return cleaned

    def _extract_reference(self, description: str) -> str:
        patterns = [
            r"\b(UPI/[A-Z0-9/.-]+)",
            r"\b(IMPS/[A-Z0-9/.-]+)",
            r"\b(NEFT/[A-Z0-9/.-]+)",
            r"\b(RTGS/[A-Z0-9/.-]+)",
            r"\b(ATM/[A-Z0-9/.-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return match.group(1)[:120]
        return ""

    def _extract_opening_balance(self, line: str) -> Optional[float]:
        match = re.search(r"Opening Balance\s*[:\-]?\s*INR\s*([\d,]+\.\d{2})", line, re.IGNORECASE)
        if match:
            return self._as_float(match.group(1))
        return None

    def _is_header_line(self, line: str) -> bool:
        normalized = self._normalize_spacing(line).lower()
        return bool(
            normalized.startswith("sr no date remarks debit credit balance")
            or normalized.startswith("sr no date remarks debit credit")
            or normalized == "sr no date remarks debit credit balance"
            or self.HEADER_RE.search(normalized)
            or normalized.startswith("detailed statement")
        )

    def _is_ignored_line(self, line: str) -> bool:
        normalized = self._normalize_spacing(line).lower()
        if not normalized:
            return True
        if self.IGNORE_RE.search(normalized):
            return True
        if normalized.startswith(("customer id:", "account holder address:", "account holder name:", "account number:", "transaction type:")):
            return True
        if normalized.startswith(("detailed statement", "page ", "opening balance", "closing balance")):
            return True
        return False

    @staticmethod
    def _clean_line(line: str) -> str:
        value = (line or "").replace("\xa0", " ").replace("₹", "₹ ")
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _normalize_spacing(value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    @staticmethod
    def _normalize_date(date_text: str) -> str:
        return datetime.strptime(date_text.replace("/", "-"), "%d-%m-%Y").strftime("%Y-%m-%d")

    @staticmethod
    def _extract_text(file_path: str) -> str:
        try:
            with pdfplumber.open(file_path) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as exc:
            logger.warning("Unable to extract text from Bank of India PDF via pdfplumber: %s", exc)
            return ""

    @staticmethod
    def _as_float(value) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except Exception:
            try:
                return float(str(value).replace(",", ""))
            except Exception:
                return None


BankOfIndiaParseError = GenericParseError
