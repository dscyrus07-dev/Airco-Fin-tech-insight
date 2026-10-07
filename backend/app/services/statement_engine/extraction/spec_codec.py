"""LayoutSpec <-> JSON-able dict, for the layout registry table (bank_layouts.config_json). Regexes are stored as
pattern strings; nothing executable is stored."""
from __future__ import annotations

import re
from typing import Any, Dict

from .layout_spec import DEFAULT_SUMMARY_FIELDS, LayoutSpec

CONFIG_VERSION = 1
_REGEX_FIELDS = ("date_re", "amount_re", "period_re", "ifsc_re")


def spec_to_dict(spec: LayoutSpec) -> Dict[str, Any]:
    spec.validate()
    return {
        "config_version": CONFIG_VERSION,
        "layout_id": spec.layout_id, "bank_key": spec.bank_key, "bank_name": spec.bank_name,
        "columns": {k: [list(seq) for seq in alts] for k, alts in spec.columns.items()},
        "text_columns": list(spec.text_columns),
        "debit_column": spec.debit_column, "credit_column": spec.credit_column, "balance_column": spec.balance_column,
        "date_re": spec.date_re.pattern, "date_format": spec.date_format, "amount_re": spec.amount_re.pattern,
        "period_re": spec.period_re.pattern, "period_date_format": spec.period_date_format,
        "summary_marker": spec.summary_marker, "summary_label_text": spec.summary_label_text,
        "summary_fields": list(spec.summary_fields),
        "secondary_date_column": spec.secondary_date_column, "header_repeats": spec.header_repeats,
        "ifsc_re": spec.ifsc_re.pattern if spec.ifsc_re else None, "account_label": spec.account_label,
    }


def spec_from_dict(data: Dict[str, Any]) -> LayoutSpec:
    version = data.get("config_version", CONFIG_VERSION)
    if version != CONFIG_VERSION:
        raise ValueError(f"unsupported layout config_version {version}")
    try:
        spec = LayoutSpec(
            layout_id=data["layout_id"], bank_key=data["bank_key"], bank_name=data["bank_name"],
            columns={k: tuple(tuple(seq) for seq in alts) for k, alts in data["columns"].items()},
            text_columns=tuple(data["text_columns"]),
            debit_column=data["debit_column"], credit_column=data["credit_column"], balance_column=data["balance_column"],
            date_re=re.compile(data["date_re"]), date_format=data["date_format"], amount_re=re.compile(data["amount_re"]),
            period_re=re.compile(data["period_re"]), period_date_format=data["period_date_format"],
            summary_marker=data["summary_marker"], summary_label_text=data["summary_label_text"],
            summary_fields=tuple(data.get("summary_fields") or DEFAULT_SUMMARY_FIELDS),
            secondary_date_column=data.get("secondary_date_column"), header_repeats=bool(data.get("header_repeats", False)),
            ifsc_re=re.compile(data["ifsc_re"]) if data.get("ifsc_re") else None, account_label=data.get("account_label", ""),
        )
    except (KeyError, re.error, TypeError) as exc:
        raise ValueError(f"invalid layout config: {exc!r}") from exc
    spec.validate()
    return spec
