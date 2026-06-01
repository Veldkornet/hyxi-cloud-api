"""Tests for the _compute_load_metrics helper function in api.py."""

from src.hyxi_cloud_api.api import _compute_load_metrics


class TestComputeLoadMetrics:
    """Tests for _compute_load_metrics."""

    def test_compute_load_metrics_basic(self):
        """Test load_power_w is fetched from loadPower."""
        m_raw = {"loadPower": 150.5}
        derived: dict[str, float] = {}
        _compute_load_metrics(m_raw, derived)
        assert derived["load_power_w"] == 150.5

    def test_compute_load_metrics_fallback_total_pac(self):
        """Test load_power_w falls back to totalPac when 0 and status is 1."""
        m_raw = {
            "loadPower": 0.0,
            "status": 1,
            "totalPac": 500.0,
        }
        derived: dict[str, float] = {}
        _compute_load_metrics(m_raw, derived)
        assert derived["load_power_w"] == 500.0

    def test_compute_load_metrics_no_fallback_wrong_status(self):
        """Test fallback does not occur if status is not 1."""
        m_raw = {
            "loadPower": 0.0,
            "status": 0,
            "totalPac": 500.0,
        }
        derived: dict[str, float] = {}
        _compute_load_metrics(m_raw, derived)
        assert derived["load_power_w"] == 0.0

    def test_compute_load_metrics_no_fallback_no_total_pac(self):
        """Test fallback does not occur if totalPac is missing."""
        m_raw = {
            "loadPower": 0.0,
            "status": 1,
        }
        derived: dict[str, float] = {}
        _compute_load_metrics(m_raw, derived)
        assert derived["load_power_w"] == 0.0

    def test_compute_load_metrics_invalid_load_power(self):
        """Test invalid loadPower is treated as 0.0 and fallback works."""
        m_raw = {
            "loadPower": "invalid",
            "status": 1,
            "totalPac": 400.0,
        }
        derived: dict[str, float] = {}
        _compute_load_metrics(m_raw, derived)
        assert derived["load_power_w"] == 400.0

    def test_compute_load_metrics_missing_keys(self):
        """Test missing keys do not add ghost sensors."""
        m_raw = {}
        derived: dict[str, float] = {}
        _compute_load_metrics(m_raw, derived)
        assert "load_power_w" not in derived
