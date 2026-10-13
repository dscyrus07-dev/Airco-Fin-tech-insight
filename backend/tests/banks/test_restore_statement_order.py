from app.services.banks._shared.base_processor import restore_statement_order


def _k(t):
    return (t["date"], t["description"], t["debit"], t["balance"])


def _row(d, desc, deb, bal, tag=""):
    return {"date": d, "description": desc, "debit": deb, "balance": bal, "tag": tag}


def test_duplicate_keys_do_not_leak_phantom_rows():
    validated = [_row("1", "A", "5", "95"), _row("1", "A", "5", "95"), _row("2", "B", "1", "94")]
    engine = [_row("1", "A", "5", "95", "e1"), _row("1", "A", "5", "95", "e2"), _row("2", "B", "1", "94", "e3")]
    ordered, used = restore_statement_order(validated, engine, _k)
    assert [r["tag"] for r in ordered] == ["e1", "e2", "e3"]
    assert len(used) == 3 and len(ordered) == len(validated)


def test_unmatched_validated_row_is_kept():
    validated = [_row("1", "A", "5", "95"), _row("9", "Z", "1", "1")]
    engine = [_row("1", "A", "5", "95", "e1")]
    ordered, used = restore_statement_order(validated, engine, _k)
    assert ordered[0]["tag"] == "e1" and ordered[1] is validated[1]


def test_order_follows_validated_not_engine():
    validated = [_row("1", "A", "5", "95"), _row("2", "B", "1", "94")]
    engine = [_row("2", "B", "1", "94", "b"), _row("1", "A", "5", "95", "a")]
    ordered, _ = restore_statement_order(validated, engine, _k)
    assert [r["tag"] for r in ordered] == ["a", "b"]
