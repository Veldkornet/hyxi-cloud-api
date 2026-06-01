"""Tests for the _compute_battery_metrics helper function."""

from src.hyxi_cloud_api.api import _compute_battery_metrics


def test_compute_battery_metrics_all_in_one():
    derived: dict[str, float] = {}
    m_raw = {"batP": 500.0, "pbat": -450.0}
    _compute_battery_metrics(m_raw, derived, "ALL_IN_ONE")
    assert derived["bat_charging"] == 450.0
    assert derived["bat_discharging"] == 0.0
    assert derived["bat_power_dc"] == 500.0


def test_compute_battery_metrics_all_in_one_fallback_to_bat_p():
    derived: dict[str, float] = {}
    m_raw = {"batP": -500.0, "pbat": 0.0}
    _compute_battery_metrics(m_raw, derived, "ALL_IN_ONE")
    assert derived["bat_charging"] == 500.0
    assert derived["bat_discharging"] == 0.0
    assert derived["bat_power_dc"] == -500.0


def test_compute_battery_metrics_other_devices():
    derived: dict[str, float] = {}
    m_raw = {"batP": 600.0, "pbat": 550.0}
    _compute_battery_metrics(m_raw, derived, "OTHER")
    assert derived["bat_charging"] == 0.0
    assert derived["bat_discharging"] == 600.0
    assert derived["bat_power_dc"] == 600.0


def test_compute_battery_metrics_other_devices_fallback_to_pbat():
    derived: dict[str, float] = {}
    m_raw = {"batP": 0.0, "pbat": 400.0}
    _compute_battery_metrics(m_raw, derived, "OTHER")
    assert derived["bat_charging"] == 0.0
    assert derived["bat_discharging"] == 400.0
    assert derived["bat_power_dc"] == 0.0


def test_compute_battery_metrics_ems_device_type_no_keys():
    derived: dict[str, float] = {}
    m_raw: dict = {}
    _compute_battery_metrics(m_raw, derived, "EMS")
    assert derived["bat_charging"] == 0.0
    assert derived["bat_discharging"] == 0.0
    assert derived["bat_power_dc"] == 0.0


def test_compute_battery_metrics_totals():
    derived: dict[str, float] = {}
    m_raw = {"batCharge": 12.5, "batDisCharge": 45.6}
    _compute_battery_metrics(m_raw, derived, "OTHER")
    assert derived["bat_charge_total"] == 12.5
    assert derived["bat_discharge_total"] == 45.6


def test_compute_battery_metrics_empty():
    derived: dict[str, float] = {}
    _compute_battery_metrics({}, derived, "")
    assert not derived


def test_compute_battery_metrics_none_device_type():
    derived: dict[str, float] = {}
    m_raw = {"batP": -100.0}
    _compute_battery_metrics(m_raw, derived, None)  # type: ignore
    assert derived["bat_charging"] == 100.0
    assert derived["bat_power_dc"] == -100.0
