"""In-memory layout registry and header-based layout detection. The PostgreSQL-backed registry (slice 3C) will serve
the same LayoutSpec objects; the engine only ever sees specs."""
from __future__ import annotations

from typing import Dict, List, Sequence

from .anchors import find_header
from .layout_spec import LayoutSpec
from .rows import Page
from .words import group_lines

_DETECT_PAGES = 3


class LayoutRegistry:
    def __init__(self, specs: Sequence[LayoutSpec] = ()):
        self._specs: Dict[str, LayoutSpec] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: LayoutSpec) -> None:
        spec.validate()
        if spec.layout_id in self._specs:
            raise ValueError(f"layout already registered: {spec.layout_id}")
        self._specs[spec.layout_id] = spec

    def get(self, layout_id: str) -> LayoutSpec:
        return self._specs[layout_id]

    def specs(self) -> List[LayoutSpec]:
        return list(self._specs.values())

    def for_bank(self, bank_key: str) -> List[LayoutSpec]:
        return [s for s in self._specs.values() if s.bank_key == bank_key]

    def detect(self, pages: Sequence[Page], bank_key: str = "") -> List[LayoutSpec]:
        """Specs whose table header is found on the first pages; several matches mean an ambiguous layout."""
        candidates = self.for_bank(bank_key) if bank_key else self.specs()
        hits: List[LayoutSpec] = []
        for spec in candidates:
            for page in pages[:_DETECT_PAGES]:
                if find_header(group_lines(page.words), spec):
                    hits.append(spec)
                    break
        return hits
