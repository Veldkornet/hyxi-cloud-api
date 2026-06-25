"""Tests for _flatten_nested_push_device error handling."""

from src.hyxi_cloud_api.api import _flatten_nested_push_device


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
