"""Per-bank support state for the UI: derived from the serve configuration plus
a static data table (bank_status.json — reasons and non-servable states only).

States: verified | review_required | legacy | coming_soon | unsupported.
Derivation order and maintenance rules: bank_status.README.md.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger(__name__)

STATUS_PATH = Path(__file__).parent / "bank_status.json"

VERIFIED = "verified"
REVIEW_REQUIRED = "review_required"
LEGACY = "legacy"
COMING_SOON = "coming_soon"
UNSUPPORTED = "unsupported"

# declared states only; verified/legacy are derived, never declared
_DECLARED = {REVIEW_REQUIRED, COMING_SOON, UNSUPPORTED}

_DEFAULT_REASONS = {
    REVIEW_REQUIRED: "This bank's statements cannot be fully verified automatically; every report is marked needs review.",
    COMING_SOON: "Detected and measured on samples; not enabled yet.",
    UNSUPPORTED: "Not supported yet.",
}


@lru_cache
def _table() -> Dict[str, Dict[str, Any]]:
    try:
        raw = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # missing/invalid file: degrade to derivation-only
        log.warning("bank_status.json unreadable (%s); states derive without reasons", type(exc).__name__)
        return {}
    banks = raw.get("banks")
    if not isinstance(banks, dict):
        return {}
    out = {}
    for bid, entry in banks.items():
        if not isinstance(bid, str) or not isinstance(entry, dict):
            continue
        state = entry.get("state")
        reason = entry.get("reason")
        out[bid] = {
            "state": state if state in _DECLARED else None,
            "reason": reason if isinstance(reason, str) and reason.strip() else None,
        }
    return out


def _reason(bid: str, state: str):
    return _table().get(bid, {}).get("reason") or _DEFAULT_REASONS.get(state)


def support_states() -> List[Dict[str, Any]]:
    """Every known bank id -> {id, name, support_state, reason}.

    Known = detector-registry banks (banks/*.json) plus spec banks that have a
    registered layout but no registry config (e.g. spec-only onboarded banks).
    """
    from .registry import default_registry
    from .serve import serve_banks, spec_bank_keys, spec_key_for, v2_mode
    from ..analysis_service import PIPELINE_BANK_NAME
    from .extractors.registry import DEFAULT_REGISTRY as _LREG

    reg = default_registry()
    try:
        mode = v2_mode()
    except Exception:
        mode = "off"
    allow = serve_banks()
    spec_keys = spec_bank_keys()
    names_by_key = {s.bank_key: s.bank_name for s in _LREG._specs.values()}

    # spec keys reachable from a registry id (scb, bob, ...) are the same bank;
    # only orphan spec keys (e.g. apgv: spec, no registry config) extend the set
    ids = set(reg.banks) | (set(spec_keys) - {spec_key_for(b) for b in reg.banks})
    out: List[Dict[str, Any]] = []
    for bid in ids:
        cfg = reg.get(bid)
        name = cfg.display_name if cfg else names_by_key.get(bid, bid)
        spec_key = spec_key_for(bid)
        served = mode == "serve" and spec_key in spec_keys and spec_key in allow
        declared = _table().get(bid, {}).get("state")
        if served:
            state = REVIEW_REQUIRED if declared == REVIEW_REQUIRED else VERIFIED
        elif bid in PIPELINE_BANK_NAME:
            state = LEGACY
        elif declared in (REVIEW_REQUIRED, COMING_SOON) or spec_key in spec_keys:
            state = COMING_SOON
        else:
            state = UNSUPPORTED
        out.append({
            "id": bid,
            "name": name,
            "support_state": state,
            "reason": _reason(bid, state),
        })
    order = {VERIFIED: 0, REVIEW_REQUIRED: 1, LEGACY: 2, COMING_SOON: 3, UNSUPPORTED: 4}
    out.sort(key=lambda b: (order[b["support_state"]], b["name"].lower()))
    return out


def support_state_map() -> Dict[str, str]:
    """bank id -> support_state (for annotating the servable `banks` list)."""
    return {b["id"]: b["support_state"] for b in support_states()}
