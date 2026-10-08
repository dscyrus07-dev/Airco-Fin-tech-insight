"""Database-backed layout registry (slice 3C): the tables in database/migrations/version_003_layout_registry.sql hold one
serialised LayoutSpec per layout. This module converts between a LayoutRegistry and rows, and renders an idempotent seed
script. It has no database dependency: callers pass rows in (fetch) or take rows out (seed), so the same code serves
Postgres, tests and a JSON dump. Loaded specs go through spec_codec, so the engine only ever sees LayoutSpec objects."""
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Mapping

from .layout_spec import LayoutSpec
from .registry import OTHER_BANK_MARKERS, LayoutRegistry
from .spec_codec import spec_from_dict, spec_to_dict


def family_code(spec: LayoutSpec) -> str:
    """Structural family of a layout: how money is printed and which columns exist. Layouts of different banks that share
    this shape are one reusable family; the per-layout details live in the configuration."""
    shape = "single_amount" if spec.single_amount_column else "split_drcr"
    roles = "-".join(r for r in spec.columns if r not in ("debit", "credit", "balance"))
    flags = "".join(f"+{f}" for f, on in (("monospace", spec.monospace_text), ("reverse", spec.row_order != "forward")) if on)
    return f"{shape}:{roles}{flags}"


def registry_to_rows(registry: LayoutRegistry) -> List[Dict[str, Any]]:
    """One row per layout in registration order (priority = position * 10, lower wins)."""
    rows = []
    for i, spec in enumerate(registry.specs()):
        rows.append({"bank_code": spec.bank_key, "bank_name": spec.bank_name, "family_code": family_code(spec),
                     "layout_id": spec.layout_id, "priority": (i + 1) * 10, "config_json": spec_to_dict(spec), "active": True})
    return rows


def registry_from_rows(rows: Iterable[Mapping[str, Any]], foreign_markers=OTHER_BANK_MARKERS) -> LayoutRegistry:
    """Build a registry from active rows, ordered by priority. config_json may be a dict or a JSON string."""
    chosen = sorted((r for r in rows if r.get("active", True)), key=lambda r: (r.get("priority", 100), r["layout_id"]))
    specs = []
    for r in chosen:
        cfg = r["config_json"]
        spec = spec_from_dict(json.loads(cfg) if isinstance(cfg, (str, bytes)) else dict(cfg))
        if spec.layout_id != r["layout_id"]:
            raise ValueError(f"row layout_id {r['layout_id']!r} does not match its configuration {spec.layout_id!r}")
        specs.append(spec)
    return LayoutRegistry(specs, foreign_markers)


def _q(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def seed_sql(registry: LayoutRegistry) -> str:
    """Idempotent upsert script for banks, layout_families and bank_layouts (safe to re-run; never deletes)."""
    out = ["BEGIN;"]
    rows = registry_to_rows(registry)
    for code, name in sorted({(r["bank_code"], r["bank_name"]) for r in rows}):
        out.append(f"INSERT INTO public.banks (code, name) VALUES ({_q(code)}, {_q(name)}) ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name;")
    for fam in sorted({r["family_code"] for r in rows}):
        out.append(f"INSERT INTO public.layout_families (code, name) VALUES ({_q(fam)}, {_q(fam)}) ON CONFLICT (code) DO NOTHING;")
    for r in rows:
        cfg = json.dumps(r["config_json"], sort_keys=True)
        out.append(
            "INSERT INTO public.bank_layouts (bank_id, layout_family_id, layout_id, priority, config_json) "
            f"SELECT b.id, f.id, {_q(r['layout_id'])}, {r['priority']}, {_q(cfg)}::jsonb "
            f"FROM public.banks b, public.layout_families f WHERE b.code = {_q(r['bank_code'])} AND f.code = {_q(r['family_code'])} "
            "ON CONFLICT (layout_id) DO UPDATE SET config_json = EXCLUDED.config_json, priority = EXCLUDED.priority, "
            "layout_family_id = EXCLUDED.layout_family_id, config_version = public.bank_layouts.config_version + 1, updated_at = now() "
            "WHERE public.bank_layouts.config_json IS DISTINCT FROM EXCLUDED.config_json "
            "OR public.bank_layouts.priority IS DISTINCT FROM EXCLUDED.priority "
            "OR public.bank_layouts.layout_family_id IS DISTINCT FROM EXCLUDED.layout_family_id;")
    out.append("COMMIT;")
    return "\n".join(out) + "\n"


FETCH_SQL = (
    "SELECT b.code AS bank_code, b.name AS bank_name, f.code AS family_code, l.layout_id, l.priority, l.config_json, l.active "
    "FROM public.bank_layouts l JOIN public.banks b ON b.id = l.bank_id JOIN public.layout_families f ON f.id = l.layout_family_id "
    "WHERE l.active AND b.active AND f.active ORDER BY l.priority, l.layout_id"
)
