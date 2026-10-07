"""In-memory layout registry and header-based layout detection. The PostgreSQL-backed registry (slice 3C) will serve
the same LayoutSpec objects; the engine only ever sees specs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .anchors import _find_sequence, _tokens, find_header
from .layout_spec import LayoutSpec
from .rows import Page
from .words import group_lines

_DETECT_PAGES = 3


@dataclass
class Resolution:
    """Outcome of layout resolution. spec is None when no layout may be used; status says why."""
    spec: Optional[LayoutSpec]
    status: str                                  # "resolved" | "no_layout" | "foreign_bank" | "ambiguous"
    candidates: List[str] = field(default_factory=list)      # layout ids that matched the header
    rejected: List[str] = field(default_factory=list)        # ids refused because the page names another bank
    notes: List[str] = field(default_factory=list)


def _header_region_text(pages: Sequence[Page], spec_hits: Sequence[LayoutSpec]) -> str:
    """Whitespace-free UPPER-CASE text of page 1 above the first table header any candidate found there (all of page 1's
    first lines when no header sits on page 1)."""
    if not pages:
        return ""
    lines = group_lines(pages[0].words)
    cut = len(lines)
    for spec in spec_hits:
        found = find_header(lines, spec)
        if found:
            cut = min(cut, found[0])
    if cut == len(lines):
        cut = min(len(lines), 20)
    return "".join("".join(w.text for w in ln) for ln in lines[:cut]).replace(" ", "").upper()


def _spelling_penalty(pages: Sequence[Page], spec: LayoutSpec) -> int:
    """Sum, over columns, of the position of the title spelling that matched in the spec's list of alternatives (0 = the
    primary spelling): a header that fits one spec's primary titles and another's fallbacks belongs to the first."""
    for pg in pages[:_DETECT_PAGES]:
        lines = group_lines(pg.words)
        found = find_header(lines, spec)
        if found:
            toks = _tokens(lines[found[0]])
            return sum(next((i for i, seq in enumerate(alts) if _find_sequence(toks, seq)), len(alts)) for alts in spec.columns.values())
    return 10 ** 6


def _rank(pages: Sequence[Page], spec: LayoutSpec, own: bool):
    return (own, -_spelling_penalty(pages, spec), _date_hits(pages, spec), len(spec.columns))


def _date_hits(pages: Sequence[Page], spec: LayoutSpec) -> int:
    return sum(1 for pg in pages[:_DETECT_PAGES] for w in pg.words if spec.date_re.match(w.text.strip()))


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

    def resolve(self, pages: Sequence[Page], bank_key: str = "") -> Resolution:
        """Pick the layout for a file, or say why none may be used.

        1. header match (detect). 2. bank anchoring: a candidate is refused when the text above the table names another
           registered bank and not its own (a header shared verbatim by two banks must not be accepted under the wrong
           one); a page that names no bank at all is not refused. 3. rank: own bank named, then header titles closest to the layout's
           primary spellings, then more date cells in its own date shape, then more columns. 4. equal rank across different banks is ambiguous: no layout.
        """
        hits = self.detect(pages, bank_key)
        if not hits:
            return Resolution(None, "no_layout")
        region = _header_region_text(pages, hits)
        known = {m for sp in self._specs.values() for m in sp.bank_markers}
        accepted: List[LayoutSpec] = []
        rejected: List[str] = []
        own_hit: Dict[str, bool] = {}
        for spec in hits:
            own = any(m in region for m in spec.bank_markers)
            foreign = any(m in region for m in known if m not in spec.bank_markers)
            own_hit[spec.layout_id] = own
            if foreign and not own:
                rejected.append(spec.layout_id)
            else:
                accepted.append(spec)
        ids = [s.layout_id for s in hits]
        if not accepted:
            return Resolution(None, "foreign_bank", ids, rejected)
        ranked = sorted(accepted, key=lambda s: _rank(pages, s, own_hit[s.layout_id]), reverse=True)
        top = ranked[0]
        key = _rank(pages, top, own_hit[top.layout_id])
        ties = [s for s in ranked[1:] if _rank(pages, s, own_hit[s.layout_id]) == key]
        if any(t.bank_key != top.bank_key for t in ties):
            return Resolution(None, "ambiguous", ids, rejected, [f"tie:{top.layout_id},{','.join(t.layout_id for t in ties)}"])
        notes = [f"multiple_layouts_matched:{len(accepted)}"] if len(accepted) > 1 else []
        return Resolution(top, "resolved", ids, rejected, notes)
