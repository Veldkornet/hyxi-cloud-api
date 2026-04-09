"""Tests for the _compute_derived_metrics helper function in api.py."""

from src.hyxi_cloud_api.api import _compute_derived_metrics


class TestComputeDerivedMetrics:
    """Tests for _compute_derived_metrics."""

    def test_home_load_calculation(self):
        """Test home_load is the sum of phase loads."""
        data = {
            "ph1Loadp": 100.5,
            "ph2Loadp": 200.0,
            "ph3Loadp": 50.25,
        }
        result = _compute_derived_metrics(data)
        assert result["home_load"] == 350.75

    def test_grid_import(self):
        """Test grid_import when gridP is negative."""
        data = {"gridP": -1.5}
        result = _compute_derived_metrics(data)
        assert result["grid_import"] == 1500.0
        assert result["grid_export"] == 0.0

    def test_grid_export(self):
        """Test grid_export when gridP is positive."""
        data = {"gridP": 2.25}
        result = _compute_derived_metrics(data)
        assert result["grid_import"] == 0.0
        assert result["grid_export"] == 2250.0

    def test_grid_zero(self):
        """Test grid import/export when gridP is zero."""
        data = {"gridP": 0.0}
        result = _compute_derived_metrics(data)
        assert result["grid_import"] == 0.0
        assert result["grid_export"] == 0.0

    def test_battery_charging_using_bat_p(self):
        """Test bat_charging when batP is negative."""
        data = {"batP": -500.0, "pbat": -450.0}
        result = _compute_derived_metrics(data)
        assert result["bat_charging"] == 500.0
        assert result["bat_discharging"] == 0.0
        assert result["bat_power_dc"] == -500.0

    def test_battery_discharging_using_bat_p(self):
        """Test bat_discharging when batP is positive."""
        data = {"batP": 600.0, "pbat": 550.0}
        result = _compute_derived_metrics(data)
        assert result["bat_charging"] == 0.0
        assert result["bat_discharging"] == 600.0
        assert result["bat_power_dc"] == 600.0

    def test_battery_charging_fallback_to_pbat(self):
        """Test bat_charging falls back to pbat when batP is 0 or missing."""
        data = {"pbat": -300.0}
        result = _compute_derived_metrics(data)
        assert result["bat_charging"] == 300.0
        assert result["bat_discharging"] == 0.0
        assert result["bat_power_dc"] == 0.0

    def test_battery_discharging_fallback_to_pbat(self):
        """Test bat_discharging falls back to pbat when batP is 0 or missing."""
        data = {"batP": 0.0, "pbat": 400.0}
        result = _compute_derived_metrics(data)
        assert result["bat_charging"] == 0.0
        assert result["bat_discharging"] == 400.0
        assert result["bat_power_dc"] == 0.0

    def test_battery_zero(self):
        """Test battery metrics when power is zero."""
        data = {"batP": 0.0, "pbat": 0.0}
        result = _compute_derived_metrics(data)
        assert result["bat_charging"] == 0.0
        assert result["bat_discharging"] == 0.0
        assert result["bat_power_dc"] == 0.0

    def test_battery_totals(self):
        """Test total charge and discharge values."""
        data = {"batCharge": 12.5, "batDisCharge": 45.6}
        result = _compute_derived_metrics(data)
        assert result["bat_charge_total"] == 12.5
        assert result["bat_discharge_total"] == 45.6

    def test_empty_dict(self):
        """Test empty dict returns all zeros."""
        result = _compute_derived_metrics({})
        assert result == {
            "home_load": 0.0,
            "grid_import": 0.0,
            "grid_export": 0.0,
            "bat_charging": 0.0,
            "bat_discharging": 0.0,
            "bat_power_dc": 0.0,
            "bat_charge_total": 0.0,
            "bat_discharge_total": 0.0,
            "pv1p": 0.0,
            "pv2p": 0.0,
            "pv3p": 0.0,
            "pv4p": 0.0,
        }
