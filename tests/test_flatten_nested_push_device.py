"""Tests for _flatten_nested_push_device error handling."""

from hyxi_cloud_api.api import _flatten_nested_push_device


def test_flatten_nested_push_device_record_collecttime_valueerror():
    """Test ValueError is handled when collectTime in record is an invalid string."""
    device = {"record": {"collectTime": "invalid_time"}}
    flat = _flatten_nested_push_device(device)
    assert flat["collectTime"] == "invalid_time"


def test_flatten_nested_push_device_record_collecttime_typeerror():
    """Test TypeError is handled when collectTime in record is of an invalid type."""
    device = {"record": {"collectTime": {"nested": "dict"}}}
    flat = _flatten_nested_push_device(device)
    assert flat["collectTime"] == {"nested": "dict"}


def test_flatten_nested_push_device_root_collecttime_valueerror():
    """Test ValueError is handled when collectTime in root is an invalid string."""
    device = {"collectTime": "invalid_time"}
    flat = _flatten_nested_push_device(device)
    assert flat["collectTime"] == "invalid_time"


def test_flatten_nested_push_device_root_collecttime_typeerror():
    """Test TypeError is handled when collectTime in root is of an invalid type."""
    device = {"collectTime": ["invalid", "type"]}
    flat = _flatten_nested_push_device(device)
    assert flat["collectTime"] == ["invalid", "type"]


def test_flatten_nested_push_device_root_collecttime_valid_large():
    """Test large valid collectTime in root."""
    device = {"collectTime": 20000000000}
    flat = _flatten_nested_push_device(device)
    assert flat["collectTime"] == 20000000.0


def test_flatten_nested_push_device_root_collecttime_valid_small():
    """Test small valid collectTime in root."""
    device = {"collectTime": 5000000000}
    flat = _flatten_nested_push_device(device)
    assert flat["collectTime"] == 5000000000


def test_flatten_nested_push_device_root_reporttimestamp():
    """Test reportTimestamp in root."""
    device = {"reportTimestamp": 1234567890}
    flat = _flatten_nested_push_device(device)
    assert flat["reportTimestamp"] == 1234567890


def test_flatten_nested_push_device_system_workmode():
    """Test workMode in system."""
    device = {"system": {"workMode": "test_mode"}}
    flat = _flatten_nested_push_device(device)
    assert flat["workMode"] == "test_mode"


def test_flatten_nested_push_device_record_parentsn():
    """Test parentSn in record is copied through to the flat layout."""
    device = {"record": {"parentSn": "PARENT123"}}
    flat = _flatten_nested_push_device(device)
    assert flat["parentSn"] == "PARENT123"


def test_flatten_nested_push_device_battery_pbatw():
    """Test battery.pbatW is mapped to the flat 'pbat' key."""
    device = {"battery": {"pbatW": 500}}
    flat = _flatten_nested_push_device(device)
    assert flat["pbat"] == 500


def test_flatten_nested_push_device_battery_charge_energy():
    """Test battery.chargeEnergyKwh is mapped to the flat 'batCharge' key."""
    device = {"battery": {"chargeEnergyKwh": 10.5}}
    flat = _flatten_nested_push_device(device)
    assert flat["batCharge"] == 10.5


def test_flatten_nested_push_device_battery_discharge_energy():
    """Test battery.dischargeEnergyKwh is mapped to the flat 'batDisCharge' key."""
    device = {"battery": {"dischargeEnergyKwh": 8.2}}
    flat = _flatten_nested_push_device(device)
    assert flat["batDisCharge"] == 8.2


def test_flatten_nested_push_device_grid_powerw_non_numeric():
    """Test ValueError/TypeError is handled when grid.powerW isn't numeric,
    falling back to the raw value instead of a computed kW figure."""
    device = {"grid": {"powerW": "not_a_number"}}
    flat = _flatten_nested_push_device(device)
    assert flat["gridP"] == "not_a_number"
