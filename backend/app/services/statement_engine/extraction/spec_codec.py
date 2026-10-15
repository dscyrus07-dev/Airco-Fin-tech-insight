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
        "end_markers": list(spec.end_markers), "date_tail_re": spec.date_tail_re.pattern if spec.date_tail_re else None,
        "summary_expected": spec.summary_expected, "dates_monotonic_expected": spec.dates_monotonic_expected,
        "period_tolerance_days": spec.period_tolerance_days, "side_flip_policy": spec.side_flip_policy,
        "totals_line_re": spec.totals_line_re.pattern if spec.totals_line_re else None, "continuation_start": spec.continuation_start, "summary_position": spec.summary_position, "band_left_pad": dict(spec.band_left_pad), "page_footer_markers": list(spec.page_footer_markers), "merge_drcr_suffix": spec.merge_drcr_suffix, "left_aligned_amounts": spec.left_aligned_amounts, "amount_sign_gap": spec.amount_sign_gap, "opening_row_marker": spec.opening_row_marker, "closing_row_marker": spec.closing_row_marker, "zero_amount_is_empty": spec.zero_amount_is_empty, "single_amount_column": spec.single_amount_column, "side_marker_column": spec.side_marker_column, "continuation_amounts": spec.continuation_amounts, "amount_prefix": spec.amount_prefix, "dated_rows_after_end_ok": spec.dated_rows_after_end_ok, "merge_statements": spec.merge_statements, "year_from_period": spec.year_from_period, "bank_markers": list(spec.bank_markers), "monospace_text": spec.monospace_text, "empty_amount_marker": spec.empty_amount_marker, "totals_accumulate": spec.totals_accumulate, "undated_rows_inherit_date": spec.undated_rows_inherit_date, "totals_credit_first": spec.totals_credit_first, "carry_forward_re": spec.carry_forward_re.pattern if spec.carry_forward_re else None, "opening_row_balance_only": spec.opening_row_balance_only, "page_break_re": spec.page_break_re.pattern if spec.page_break_re else None, "merge_sign_prefix": spec.merge_sign_prefix, "row_order": spec.row_order, "sign_is_decoration": spec.sign_is_decoration, "wrapped_amount_tokens": spec.wrapped_amount_tokens, "drcr_suffix_decoration": spec.drcr_suffix_decoration, "header_only_ok": spec.header_only_ok, "clipped_drcr_suffix": spec.clipped_drcr_suffix,
        "opening_balance_re": spec.opening_balance_re.pattern if spec.opening_balance_re else None,
        "closing_balance_re": spec.closing_balance_re.pattern if spec.closing_balance_re else None,
        "anchor_full": spec.anchor_full, "date_left_pad": spec.date_left_pad, "header_wraps": spec.header_wraps,
        "ignore_line_res": [r.pattern for r in spec.ignore_line_res],
        "implicit_header": list(spec.implicit_header),
        "header_lines": spec.header_lines, "header_merge_tol": spec.header_merge_tol,
        "untitled_date_column": spec.untitled_date_column, "date_join_words": spec.date_join_words,
        "anchor_scan": spec.anchor_scan, "no_running_balance": spec.no_running_balance, "leading_narration": spec.leading_narration, "balance_optional": spec.balance_optional, "leading_amounts": spec.leading_amounts, "chain_reorder_same_date": spec.chain_reorder_same_date,
        "segment_header_re": spec.segment_header_re.pattern if spec.segment_header_re else None,
        "segment_count_re": spec.segment_count_re.pattern if spec.segment_count_re else None,
        "balance_checkpoint_re": spec.balance_checkpoint_re.pattern if spec.balance_checkpoint_re else None,
        "balance_inline_re": spec.balance_inline_re.pattern if spec.balance_inline_re else None,
        "single_amount_default_side": spec.single_amount_default_side,
        "section_date_re": spec.section_date_re.pattern if spec.section_date_re else None,
        "derive_side_from_balance": spec.derive_side_from_balance,
        "doubled_header_glyphs": spec.doubled_header_glyphs,
        "summary_truncated": spec.summary_truncated,
        "period_from_borrows_end_year": spec.period_from_borrows_end_year,
        "totals_sum_tail": spec.totals_sum_tail,
        "doc_counts_re": spec.doc_counts_re.pattern if spec.doc_counts_re else None,
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
            end_markers=tuple(data.get("end_markers") or ()),
            date_tail_re=re.compile(data["date_tail_re"]) if data.get("date_tail_re") else None,
            summary_expected=bool(data.get("summary_expected", True)),
            dates_monotonic_expected=bool(data.get("dates_monotonic_expected", True)),
            period_tolerance_days=int(data.get("period_tolerance_days", 1)),
            side_flip_policy=data.get("side_flip_policy", "fail"),
            totals_line_re=re.compile(data["totals_line_re"]) if data.get("totals_line_re") else None,
            continuation_start=data.get("continuation_start", "marker"),
            summary_position=data.get("summary_position", "after"),
            band_left_pad=dict(data.get("band_left_pad") or {}),
            page_footer_markers=tuple(data.get("page_footer_markers") or ()),
            merge_drcr_suffix=bool(data.get("merge_drcr_suffix", False)), left_aligned_amounts=bool(data.get("left_aligned_amounts", False)), amount_sign_gap=bool(data.get("amount_sign_gap", False)),
            opening_row_marker=data.get("opening_row_marker", ""), closing_row_marker=data.get("closing_row_marker", ""), zero_amount_is_empty=bool(data.get("zero_amount_is_empty", False)), single_amount_column=data.get("single_amount_column", ""), side_marker_column=data.get("side_marker_column", ""), continuation_amounts=bool(data.get("continuation_amounts", False)), amount_prefix=data.get("amount_prefix", ""), dated_rows_after_end_ok=bool(data.get("dated_rows_after_end_ok", False)), merge_statements=bool(data.get("merge_statements", False)), year_from_period=bool(data.get("year_from_period", False)), bank_markers=tuple(data.get("bank_markers", ())), monospace_text=bool(data.get("monospace_text", False)), empty_amount_marker=data.get("empty_amount_marker", ""), totals_accumulate=bool(data.get("totals_accumulate", False)), undated_rows_inherit_date=bool(data.get("undated_rows_inherit_date", False)), totals_credit_first=bool(data.get("totals_credit_first", False)), carry_forward_re=re.compile(data["carry_forward_re"]) if data.get("carry_forward_re") else None, opening_row_balance_only=bool(data.get("opening_row_balance_only", False)), page_break_re=re.compile(data["page_break_re"]) if data.get("page_break_re") else None, merge_sign_prefix=bool(data.get("merge_sign_prefix", False)), row_order=data.get("row_order", "forward"), sign_is_decoration=data.get("sign_is_decoration", False), wrapped_amount_tokens=bool(data.get("wrapped_amount_tokens", False)), drcr_suffix_decoration=bool(data.get("drcr_suffix_decoration", False)), header_only_ok=bool(data.get("header_only_ok", False)), clipped_drcr_suffix=bool(data.get("clipped_drcr_suffix", False)),
            opening_balance_re=re.compile(data["opening_balance_re"]) if data.get("opening_balance_re") else None,
            closing_balance_re=re.compile(data["closing_balance_re"]) if data.get("closing_balance_re") else None,
            anchor_full=bool(data.get("anchor_full", False)), date_left_pad=float(data.get("date_left_pad", 3.0)), header_wraps=bool(data.get("header_wraps", False)),
            ignore_line_res=tuple(re.compile(x) for x in data.get("ignore_line_res") or ()),
            implicit_header=tuple(data.get("implicit_header") or ()),
            header_lines=int(data.get("header_lines", 1)), header_merge_tol=float(data.get("header_merge_tol", 4.0)),
            untitled_date_column=bool(data.get("untitled_date_column", False)),
            date_join_words=bool(data.get("date_join_words", False)),
            anchor_scan=data.get("anchor_scan", "edges"),
            no_running_balance=bool(data.get("no_running_balance", False)),
            leading_narration=bool(data.get("leading_narration", False)),
            balance_optional=bool(data.get("balance_optional", False)),
            leading_amounts=bool(data.get("leading_amounts", False)),
            chain_reorder_same_date=bool(data.get("chain_reorder_same_date", False)),
            segment_header_re=re.compile(data["segment_header_re"]) if data.get("segment_header_re") else None,
            segment_count_re=re.compile(data["segment_count_re"]) if data.get("segment_count_re") else None,
            balance_checkpoint_re=re.compile(data["balance_checkpoint_re"]) if data.get("balance_checkpoint_re") else None,
            balance_inline_re=re.compile(data["balance_inline_re"]) if data.get("balance_inline_re") else None,
            single_amount_default_side=data.get("single_amount_default_side", ""),
            section_date_re=re.compile(data["section_date_re"]) if data.get("section_date_re") else None,
            derive_side_from_balance=bool(data.get("derive_side_from_balance", False)),
            doubled_header_glyphs=bool(data.get("doubled_header_glyphs", False)),
            summary_truncated=bool(data.get("summary_truncated", False)),
            period_from_borrows_end_year=bool(data.get("period_from_borrows_end_year", False)),
            totals_sum_tail=bool(data.get("totals_sum_tail", False)),
            doc_counts_re=re.compile(data["doc_counts_re"]) if data.get("doc_counts_re") else None,
        )
    except (KeyError, re.error, TypeError) as exc:
        raise ValueError(f"invalid layout config: {exc!r}") from exc
    spec.validate()
    return spec
