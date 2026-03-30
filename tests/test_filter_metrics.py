"""Tests for _filter_collector_metrics optimization."""

import pytest
from src.hyxi_cloud_api.api import _filter_collector_metrics


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
