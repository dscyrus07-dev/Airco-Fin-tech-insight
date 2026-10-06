"""Bank registry: one JSON file per bank in ./banks (data, not code).

Adding a bank = adding a JSON file (+ golden PDFs). Fields:
    id, display_name, names (full names), short_names (distinctive bare tokens, header-block only),
    ifsc_prefixes, domains, statement_phrases, processor_key (None = no processor yet), corpus_folder.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BANKS_DIR = Path(__file__).parent / "banks"


@dataclass(frozen=True)
class BankConfig:
    id: str
    display_name: str
    names: Tuple[str, ...] = ()
    short_names: Tuple[str, ...] = ()
    ifsc_prefixes: Tuple[str, ...] = ()
    domains: Tuple[str, ...] = ()
    statement_phrases: Tuple[str, ...] = ()
    strong_phrases: Tuple[str, ...] = ()  # the bank's own template wording, matched on compacted page-1 text
    processor_key: Optional[str] = None
    corpus_folder: Optional[str] = None

    @property
    def supported(self) -> bool:
        return self.processor_key is not None


@dataclass
class BankRegistry:
    banks: Dict[str, BankConfig] = field(default_factory=dict)
    masks: Tuple[str, ...] = ()

    def get(self, bank_id: Optional[str]) -> Optional[BankConfig]:
        return self.banks.get(bank_id) if bank_id else None

    def by_folder(self, folder: str) -> Optional[BankConfig]:
        f = (folder or "").strip().lower()
        for b in self.banks.values():
            if b.corpus_folder and b.corpus_folder.lower() == f:
                return b
        return None

    def ifsc_owner(self, prefix: str) -> Optional[str]:
        p = prefix.upper()
        for b in self.banks.values():
            if p in b.ifsc_prefixes:
                return b.id
        return None

    def validate(self) -> List[str]:
        """Human-readable problems; empty list = registry is consistent."""
        problems: List[str] = []
        seen_prefix: Dict[str, str] = {}
        seen_name: Dict[str, str] = {}
        for b in self.banks.values():
            if not b.names:
                problems.append(f"{b.id}: no names")
            for p in b.ifsc_prefixes:
                if not re.fullmatch(r"[A-Z]{4}", p):
                    problems.append(f"{b.id}: bad IFSC prefix {p!r}")
                if p in seen_prefix and seen_prefix[p] != b.id:
                    problems.append(f"IFSC prefix {p} used by {seen_prefix[p]} and {b.id}")
                seen_prefix[p] = b.id
            for n in list(b.names) + list(b.short_names):
                if n != n.lower():
                    problems.append(f"{b.id}: name {n!r} must be lower-case")
                if n in seen_name and seen_name[n] != b.id:
                    problems.append(f"name {n!r} used by {seen_name[n]} and {b.id}")
                seen_name[n] = b.id
        return problems


def _tuple(v) -> Tuple[str, ...]:
    return tuple(v or ())


def load_registry(directory: Optional[Path] = None) -> BankRegistry:
    d = Path(directory) if directory else BANKS_DIR
    banks: Dict[str, BankConfig] = {}
    masks: Tuple[str, ...] = ()
    for path in sorted(d.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if path.name == "_masks.json":
            masks = tuple(m.lower() for m in data.get("masks", []))
            continue
        cfg = BankConfig(
            id=data["id"],
            display_name=data["display_name"],
            names=_tuple(data.get("names")),
            short_names=_tuple(data.get("short_names")),
            ifsc_prefixes=tuple(p.upper() for p in data.get("ifsc_prefixes", [])),
            domains=tuple(x.lower() for x in data.get("domains", [])),
            strong_phrases=tuple(x.lower() for x in data.get("strong_phrases", [])),
            statement_phrases=tuple(x.lower() for x in data.get("statement_phrases", [])),
            processor_key=data.get("processor_key"),
            corpus_folder=data.get("corpus_folder"),
        )
        banks[cfg.id] = cfg
    return BankRegistry(banks=banks, masks=masks)


@lru_cache(maxsize=1)
def default_registry() -> BankRegistry:
    return load_registry()
