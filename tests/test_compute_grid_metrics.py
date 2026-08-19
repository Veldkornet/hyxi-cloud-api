"""Tests for the _compute_grid_metrics helper function in api.py."""

import pytest

from src.hyxi_cloud_api.api import _compute_grid_metrics, _normalize_micro_ess_gridp


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


class TestNormalizeMicroEssGridp:
    """Tests for _normalize_micro_ess_gridp (GitHub issue #654).

    Micro ESS/Halo devices report gridP in Watts wherever the raw API value
    passes through unconverted; _compute_grid_metrics always expects gridP
    in kW, so this normalizes it in place before that happens.
    """

    @pytest.mark.parametrize(
        "device_type", ["15", "16", "EMS", "MICRO_STORAGE_ALL_IN_ONE"]
    )
    def test_normalizes_watts_to_kw_for_micro_ess_family(self, device_type):
        """Test that every code in _MICRO_ESS_DEVICE_TYPES gets the fixup."""
        m_raw = {"gridP": "811.0"}
        _normalize_micro_ess_gridp(m_raw, device_type)
        assert m_raw["gridP"] == 0.811

    def test_leaves_non_micro_ess_device_untouched(self):
        """Test that non-Micro-ESS device types are left as-is."""
        m_raw = {"gridP": "1.5"}
        _normalize_micro_ess_gridp(m_raw, "HYBRID_INVERTER")
        assert m_raw["gridP"] == "1.5"

    def test_leaves_energy_storage_battery_untouched(self):
        """ENERGY_STORAGE_BATTERY shares _EMS_DEVICE_TYPES with the Micro ESS
        family for unrelated purposes, but has no evidence of this quirk.
        """
        m_raw = {"gridP": "1.5"}
        _normalize_micro_ess_gridp(m_raw, "ENERGY_STORAGE_BATTERY")
        assert m_raw["gridP"] == "1.5"

    def test_missing_gridp_is_a_noop(self):
        """Test that a missing gridP key doesn't raise or add one."""
        m_raw: dict = {}
        _normalize_micro_ess_gridp(m_raw, "15")
        assert "gridP" not in m_raw

    def test_unparsable_gridp_left_untouched(self):
        """Test that an unparsable gridP value is left as-is."""
        m_raw = {"gridP": "not-a-number"}
        _normalize_micro_ess_gridp(m_raw, "15")
        assert m_raw["gridP"] == "not-a-number"

    def test_none_device_type_is_a_noop(self):
        """Test that a None device_type is treated as non-Micro-ESS."""
        m_raw = {"gridP": "811.0"}
        _normalize_micro_ess_gridp(m_raw, None)
        assert m_raw["gridP"] == "811.0"
