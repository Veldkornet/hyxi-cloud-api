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
