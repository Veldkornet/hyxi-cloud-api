"""Tests for the _compute_grid_metrics helper function in api.py."""

from src.hyxi_cloud_api.api import _compute_grid_metrics


class TestComputeGridMetrics:
    """Tests for _compute_grid_metrics."""

    def test_grid_import(self):
        """Test grid_import when gridP is negative."""
        m_raw = {"gridP": -1.5}
        derived: dict[str, float] = {}
        _compute_grid_metrics(m_raw, derived)
        assert derived["grid_import"] == 1500.0
        assert derived["grid_export"] == 0.0

    def test_grid_export(self):
        """Test grid_export when gridP is positive."""
        m_raw = {"gridP": 2.25}
        derived: dict[str, float] = {}
        _compute_grid_metrics(m_raw, derived)
        assert derived["grid_import"] == 0.0
        assert derived["grid_export"] == 2250.0

    def test_grid_zero(self):
        """Test grid import/export when gridP is zero."""
        m_raw = {"gridP": 0.0}
        derived: dict[str, float] = {}
        _compute_grid_metrics(m_raw, derived)
        assert derived["grid_import"] == 0.0
        assert derived["grid_export"] == 0.0

    def test_grid_missing(self):
        """Test missing gridP."""
        m_raw = {}
        derived: dict[str, float] = {}
        _compute_grid_metrics(m_raw, derived)
        assert "grid_import" not in derived
        assert "grid_export" not in derived
