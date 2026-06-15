"""Tests for the _compute_battery_metrics helper function."""

from src.hyxi_cloud_api.api import _compute_battery_metrics


def test_compute_battery_metrics_all_in_one():
    """Test ALL_IN_ONE device specific logic where pbat is preferred."""
    derived: dict[str, float] = {}
    m_raw = {"batP": 500.0, "pbat": -450.0}
    _compute_battery_metrics(m_raw, derived, "ALL_IN_ONE")
    assert derived["bat_charging"] == 450.0
    assert derived["bat_discharging"] == 0.0
    assert derived["bat_power_dc"] == 500.0


def test_compute_battery_metrics_all_in_one_fallback_to_bat_p():
    """Test ALL_IN_ONE fallback logic when pbat is zero."""
    derived: dict[str, float] = {}
    m_raw = {"batP": -500.0, "pbat": 0.0}
    _compute_battery_metrics(m_raw, derived, "ALL_IN_ONE")
    assert derived["bat_charging"] == 500.0
    assert derived["bat_discharging"] == 0.0
    assert derived["bat_power_dc"] == -500.0


def test_compute_battery_metrics_other_devices():
    """Test standard device logic where batP is preferred."""
    derived: dict[str, float] = {}
    m_raw = {"batP": 600.0, "pbat": 550.0}
    _compute_battery_metrics(m_raw, derived, "OTHER")
    assert derived["bat_charging"] == 0.0
    assert derived["bat_discharging"] == 600.0
    assert derived["bat_power_dc"] == 600.0


def test_compute_battery_metrics_other_devices_fallback_to_pbat():
    """Test standard device fallback logic when batP is zero."""
    derived: dict[str, float] = {}
    m_raw = {"batP": 0.0, "pbat": 400.0}
    _compute_battery_metrics(m_raw, derived, "OTHER")
    assert derived["bat_charging"] == 0.0
    assert derived["bat_discharging"] == 400.0
    assert derived["bat_power_dc"] == 0.0


def test_compute_battery_metrics_ems_device_type_no_keys():
    """Test EMS device type logic handles empty input keys."""
    derived: dict[str, float] = {}
    m_raw: dict = {}
    _compute_battery_metrics(m_raw, derived, "EMS")
    assert derived["bat_charging"] == 0.0
    assert derived["bat_discharging"] == 0.0
    assert derived["bat_power_dc"] == 0.0


def test_compute_battery_metrics_totals():
    """Test handling of total charging and discharging statistics."""
    derived: dict[str, float] = {}
    m_raw = {"batCharge": 12.5, "batDisCharge": 45.6}
    _compute_battery_metrics(m_raw, derived, "OTHER")
    assert derived["bat_charge_total"] == 12.5
    assert derived["bat_discharge_total"] == 45.6
    assert derived["totalEchg"] == 12.5
    assert derived["totalEdchg"] == 45.6
    assert derived["batCharge"] == 12.5
    assert derived["batDisCharge"] == 45.6


def test_compute_battery_metrics_polling_keys():
    """Test fallback and synchronization when only polling keys are present."""
    derived: dict[str, float] = {}
    m_raw = {"totalEchg": 100.5, "totalEdchg": 200.2}
    _compute_battery_metrics(m_raw, derived, "OTHER")
    assert derived["bat_charge_total"] == 100.5
    assert derived["bat_discharge_total"] == 200.2
    assert derived["totalEchg"] == 100.5
    assert derived["totalEdchg"] == 200.2
    assert derived["batCharge"] == 100.5
    assert derived["batDisCharge"] == 200.2


def test_compute_battery_metrics_null_and_empty_handling():
    """Verify that null-equivalent and empty values do not pollute derived metrics."""
    derived: dict[str, float] = {}
    m_raw = {
        "batCharge": 150.0,
        "totalEchg": "null",
        "batDisCharge": "None",
        "totalEdchg": 250.0,
    }
    _compute_battery_metrics(m_raw, derived, "OTHER")
    assert derived["bat_charge_total"] == 150.0
    assert derived["bat_discharge_total"] == 250.0


def test_compute_battery_metrics_empty():
    """Test graceful handling of empty inputs."""
    derived: dict[str, float] = {}
    _compute_battery_metrics({}, derived, "")
    assert not derived


def test_compute_battery_metrics_none_device_type():
    """Test graceful handling of missing device_type."""
    derived: dict[str, float] = {}
    m_raw = {"batP": -100.0}
    _compute_battery_metrics(m_raw, derived, None)  # type: ignore
    assert derived["bat_charging"] == 100.0
    assert derived["bat_power_dc"] == -100.0
