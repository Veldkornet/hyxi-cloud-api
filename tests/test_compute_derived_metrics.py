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
        """Test empty dict returns empty dict (no ghost sensors)."""
        result = _compute_derived_metrics({})
        assert not result

    def test_missing_pv_power_derived(self):
        """Test PV power is derived when missing but voltage and current are present."""
        data = {"pv1v": 100.0, "pv1i": 5.0}
        result = _compute_derived_metrics(data)
        assert "pv1p" in result
        assert result["pv1p"] == 500.0

    def test_provided_pv_power_takes_precedence(self):
        """Test provided PV power takes precedence over derived power."""
        data = {"pv1v": 100.0, "pv1i": 5.0, "pv1p": 600.0}
        result = _compute_derived_metrics(data)
        assert "pv1p" in result
        assert result["pv1p"] == 600.0

    def test_partial_pv_data(self):
        """Test PV power derivation with partial data (e.g. only voltage)."""
        data = {"pv1v": 100.0}
        result = _compute_derived_metrics(data)
        assert "pv1p" in result
        assert result["pv1p"] == 0.0

    def test_selective_pv_strings(self):
        """Test that only PV strings present in input are present in output."""
        data = {"pv1v": 100, "pv1i": 5}  # PV1 only
        result = _compute_derived_metrics(data)
        assert "pv1p" in result
        assert result["pv1p"] == 500.0
        assert "pv2p" not in result
        assert "pv3p" not in result
        assert "pv4p" not in result

    def test_selective_load(self):
        """Test that home_load is only present if phase loads exist."""
        result = _compute_derived_metrics({"gridP": 1.0})
        assert "home_load" not in result

        result = _compute_derived_metrics({"ph1Loadp": 100.0})
        assert "home_load" in result
        assert result["home_load"] == 100.0
