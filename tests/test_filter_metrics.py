import sys
from unittest.mock import MagicMock

if "aiohttp" not in sys.modules or not hasattr(sys.modules["aiohttp"], "ClientError"):
    m = MagicMock()

    class MockExp(Exception):
        def __init__(self, *args, **kwargs):
            super().__init__(*args)
            for k, v in kwargs.items():
                setattr(self, k, v)

    m.ClientError = MockExp
    m.ClientResponseError = type("ClientResponseError", (MockExp,), {})
    m.ContentTypeError = type("ContentTypeError", (MockExp,), {})
    sys.modules["aiohttp"] = m
mock_aiohttp = sys.modules["aiohttp"]

"""Tests for _filter_collector_metrics optimization."""

from src.hyxi_cloud_api.api import (
    _filter_collector_metrics,
    _is_collector_key_allowed,
)


def test_filter_collector_metrics_filtering():
    """Verify that sensitive metrics are filtered out."""
    m_raw = {
        "totalE": "2731.9",
        "pbat": "-500",
        "gridP": "1.5",
        "ph1Loadp": "0.5",
        "ph2Loadp": "0.5",
        "ph3Loadp": "0.5",
        "temp": "40.5",
        "vpv1": "400",
        "vbat": "52",
        "soc": "100",
    }

    filtered = _filter_collector_metrics(m_raw)

    # These should be filtered out
    assert "pbat" not in filtered
    assert "gridP" not in filtered
    assert "ph1Loadp" not in filtered
    assert "ph2Loadp" not in filtered
    assert "ph3Loadp" not in filtered
    assert "vpv1" not in filtered
    assert "vbat" not in filtered

    # These should remain
    assert "totalE" in filtered
    assert "temp" in filtered
    assert "soc" in filtered
    assert filtered["totalE"] == "2731.9"
    assert filtered["temp"] == "40.5"
    assert filtered["soc"] == "100"


def test_filter_collector_metrics_empty():
    """Verify empty dict handling."""
    assert not _filter_collector_metrics({})


def test_filter_collector_metrics_no_match():
    """Verify dict with no matches handling."""
    m_raw = {"abc": "123", "def": "456"}
    assert _filter_collector_metrics(m_raw) == m_raw


def test_filter_collector_metrics_case_insensitivity():
    """Verify case insensitivity of filtering."""
    m_raw = {"BATTERY_TEMP": "25", "PV_VOLTAGE": "200"}
    filtered = _filter_collector_metrics(m_raw)
    assert "BATTERY_TEMP" not in filtered
    assert "PV_VOLTAGE" not in filtered


def test_is_collector_key_allowed_true():
    """Verify that safe keys are allowed."""
    assert _is_collector_key_allowed("totalE") is True
    assert _is_collector_key_allowed("temp") is True
    assert _is_collector_key_allowed("soc") is True
    assert _is_collector_key_allowed("voltage") is True
    assert _is_collector_key_allowed("current") is True
    assert _is_collector_key_allowed("randomKey") is True


def test_is_collector_key_allowed_false():
    """Verify that sensitive keys are not allowed."""
    assert _is_collector_key_allowed("pbat") is False
    assert _is_collector_key_allowed("gridP") is False
    assert _is_collector_key_allowed("ph1Loadp") is False
    assert _is_collector_key_allowed("ph2Loadp") is False
    assert _is_collector_key_allowed("ph3Loadp") is False
    assert _is_collector_key_allowed("vpv1") is False
    assert _is_collector_key_allowed("vbat") is False


def test_is_collector_key_allowed_case_insensitivity():
    """Verify case insensitivity."""
    assert _is_collector_key_allowed("BAT_VOLTAGE") is False
    assert _is_collector_key_allowed("PV_VOLTAGE") is False
    assert _is_collector_key_allowed("GRID_POWER") is False
    assert _is_collector_key_allowed("LOAD_POWER") is False
    assert _is_collector_key_allowed("PH1_LOAD") is False
    assert _is_collector_key_allowed("PH2_LOAD") is False
    assert _is_collector_key_allowed("PH3_LOAD") is False
    assert _is_collector_key_allowed("BaT") is False
    assert _is_collector_key_allowed("pBAt") is False


def test_is_collector_key_allowed_cache():
    """Verify that the lru_cache works and caches results."""
    # Clear cache to ensure clean state
    _is_collector_key_allowed.cache_clear()

    # First call - should be a miss
    res1 = _is_collector_key_allowed("totalE")

    # Second call - should be a hit
    res2 = _is_collector_key_allowed("totalE")

    # Check cache info
    cache_info = _is_collector_key_allowed.cache_info()

    assert res1 is True
    assert res2 is True
    assert cache_info.hits == 1
    assert cache_info.misses == 1
    assert cache_info.currsize == 1
