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

    def test_grid_fallback_phases_positive(self):
        """Test grid fallback to phase active powers when gridP is missing."""
        m_raw = {
            "ph1p": 200.0,
            "ph2p": 150.0,
            "ph3p": 50.0,
        }
        derived: dict[str, float] = {}
        _compute_grid_metrics(m_raw, derived)
        assert derived["gridP"] == 0.4  # (200 + 150 + 50) / 1000 = 0.4 kW
        assert derived["grid_import"] == 0.0
        assert derived["grid_export"] == 400.0

    def test_grid_fallback_phases_negative(self):
        """Test grid fallback to phase active powers when importing (negative)."""
        m_raw = {
            "ph1p": -300.0,
            "ph2p": -200.0,
            "ph3p": -100.0,
        }
        derived: dict[str, float] = {}
        _compute_grid_metrics(m_raw, derived)
        assert derived["gridP"] == -0.6  # -600W / 1000 = -0.6 kW
        assert derived["grid_import"] == 600.0
        assert derived["grid_export"] == 0.0

    def test_grid_priority(self):
        """Test that gridP takes priority over phase fallback if present."""
        m_raw = {
            "gridP": 1.5,
            "ph1p": -300.0,
            "ph2p": -200.0,
            "ph3p": -100.0,
        }
        derived: dict[str, float] = {}
        _compute_grid_metrics(m_raw, derived)
        assert "gridP" not in derived  # gridP was in m_raw, not computed/derived
        assert derived["grid_import"] == 0.0
        assert derived["grid_export"] == 1500.0
