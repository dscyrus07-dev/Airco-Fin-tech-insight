"""Regression: every bank advertised via PIPELINE_BANK_NAME must route to a
real processor, and look-alike names must not misroute to a different bank."""
import pytest

from app.services.analysis_service import PIPELINE_BANK_NAME
from app.services.pipeline_orchestrator import _normalize_bank_name, _get_bank_processor


@pytest.mark.parametrize("name,key", [
    ("Bank of India", "bank_of_india"),
    ("Indian Bank", "indian_bank"),
    ("Bank of Baroda", "bank_of_baroda"),
    ("HDFC Bank", "hdfc"),
    ("State Bank of India", "sbi"),
    ("Union Bank of India", "union"),
])
def test_advertised_banks_resolve(name, key):
    assert _normalize_bank_name(name) == key
    assert _get_bank_processor(key) is not None


def test_every_pipeline_bank_name_routes():
    for bank_id, display in PIPELINE_BANK_NAME.items():
        assert _get_bank_processor(_normalize_bank_name(display)) is not None, bank_id


def test_south_indian_bank_not_misrouted():
    assert _get_bank_processor(_normalize_bank_name("South Indian Bank")) is None
