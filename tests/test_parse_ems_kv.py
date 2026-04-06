"""Tests for the _parse_ems_kv helper function in api.py."""

from src.hyxi_cloud_api.api import _parse_ems_kv

def test_parse_ems_kv_happy_path():
    """Test that a valid list of modules with filedKv is parsed correctly."""
    data = [
        {
            "moduleName": "System",
            "filedKv": [
                {"prop": "GridVoltage", "value": "230.0"},
                {"prop": "Frequency", "value": "50.0"}
            ]
        },
        {
            "moduleName": "Battery",
            "filedKv": [
                {"prop": "SOC", "value": "100"}
            ]
        }
    ]
    expected = {
        "gridvoltage": "230.0",
        "frequency": "50.0",
        "soc": "100"
    }
    assert _parse_ems_kv(data) == expected

def test_parse_ems_kv_empty_list():
    """Test that an empty list returns an empty dict."""
    assert _parse_ems_kv([]) == {}

def test_parse_ems_kv_invalid_input_type():
    """Test that passing a non-list input returns an empty dict."""
    assert _parse_ems_kv(None) == {}
    assert _parse_ems_kv({}) == {}
    assert _parse_ems_kv("invalid string") == {}

def test_parse_ems_kv_invalid_module_type():
    """Test that invalid modules within the list are ignored."""
    data = [
        "invalid module",
        None,
        {
            "moduleName": "ValidModule",
            "filedKv": [
                {"prop": "ValidProp", "value": "10"}
            ]
        }
    ]
    expected = {"validprop": "10"}
    assert _parse_ems_kv(data) == expected

def test_parse_ems_kv_missing_filedkv():
    """Test that modules missing filedKv are ignored."""
    data = [
        {"moduleName": "NoFiledKv"}
    ]
    assert _parse_ems_kv(data) == {}

def test_parse_ems_kv_invalid_filedkv_items():
    """Test that invalid items within filedKv are handled correctly."""
    data = [
        {
            "filedKv": [
                "invalid item",
                None,
                {"value": "10"}, # missing prop
                {"prop": "ValidProp", "value": "10"}
            ]
        }
    ]
    expected = {"validprop": "10"}
    assert _parse_ems_kv(data) == expected
