"""Tests for the _compute_pv_metrics helper function in api.py."""

from src.hyxi_cloud_api.api import _compute_pv_metrics


class TestComputePvMetrics:
    """Tests for _compute_pv_metrics."""

    def test_compute_pv_metrics_with_direct_power(self):
        """Test PV power uses direct power when provided."""
        m_raw = {"pv1v": 100.0, "pv1i": 5.0, "pv1p": 600.0}
        derived: dict[str, float] = {}
        _compute_pv_metrics(m_raw, derived)
        assert derived["pv1p"] == 600.0

    def test_compute_pv_metrics_with_voltage_current(self):
        """Test PV power calculates voltage * current when direct power is missing."""
        m_raw = {"pv1v": 100.0, "pv1i": 5.5}
        derived: dict[str, float] = {}
        _compute_pv_metrics(m_raw, derived)
        assert derived["pv1p"] == 550.0

    def test_compute_pv_metrics_empty_dict(self):
        """Test empty input results in empty derived metrics."""
        m_raw = {}
        derived: dict[str, float] = {}
        _compute_pv_metrics(m_raw, derived)
        assert derived == {}

    def test_compute_pv_metrics_pv1_fallback_normal(self):
        """Test pv1p fallback is calculated correctly from ppv and pv2p."""
        m_raw = {"ppv": 1000.0}
        derived: dict[str, float] = {"pv2p": 400.0}
        _compute_pv_metrics(m_raw, derived)
        assert derived["pv1p"] == 600.0
        assert derived["pv2p"] == 400.0

    def test_compute_pv_metrics_pv1_fallback_negative(self):
        """Test pv1p fallback bounds negative results to 0.0."""
        m_raw = {"ppv": 300.0}
        derived: dict[str, float] = {"pv2p": 400.0}
        _compute_pv_metrics(m_raw, derived)
        assert derived["pv1p"] == 0.0

    def test_compute_pv_metrics_zero_direct_power_with_vi(self):
        """Test PV power falls back to calculated value if direct power is exactly 0.0."""
        m_raw = {"pv1v": 100.0, "pv1i": 5.0, "pv1p": 0.0}
        derived: dict[str, float] = {}
        _compute_pv_metrics(m_raw, derived)
        assert derived["pv1p"] == 500.0
