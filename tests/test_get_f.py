"""Tests for the _get_f utility function in api.py."""

from src.hyxi_cloud_api.api import _get_f

def test_get_f_valid_float_string():
    """Test extracting a valid float string."""
    data = {"key": "123.456"}
    assert _get_f("key", data) == 123.46

def test_get_f_valid_integer_string():
    """Test extracting a valid integer string."""
    data = {"key": "123"}
    assert _get_f("key", data) == 123.0

def test_get_f_with_multiplier():
    """Test applying a multiplier to the extracted value."""
    data = {"key": "1.5"}
    assert _get_f("key", data, mult=1000.0) == 1500.0

def test_get_f_missing_key():
    """Test when the key is not in the data map."""
    data = {"other_key": "123.45"}
    assert _get_f("key", data) == 0.0

def test_get_f_none_value():
    """Test when the value for the key is None."""
    data = {"key": None}
    assert _get_f("key", data) == 0.0

def test_get_f_empty_string():
    """Test when the value for the key is an empty string."""
    data = {"key": ""}
    assert _get_f("key", data) == 0.0

def test_get_f_invalid_string():
    """Test when the value cannot be parsed to a float."""
    data = {"key": "abc"}
    assert _get_f("key", data) == 0.0

def test_get_f_inappropriate_type():
    """Test when the value is an inappropriate type (e.g. list, dict)."""
    data1 = {"key": [1, 2, 3]}
    assert _get_f("key", data1) == 0.0
    data2 = {"key": {"a": 1}}
    assert _get_f("key", data2) == 0.0

def test_get_f_integer_type():
    """Test when the value is actually an int type, not a string."""
    data = {"key": 100}
    assert _get_f("key", data) == 100.0

def test_get_f_float_type():
    """Test when the value is actually a float type, not a string."""
    data = {"key": 100.123}
    assert _get_f("key", data) == 100.12

def test_get_f_rounding():
    """Test that the value is always correctly rounded to 2 decimal places."""
    data1 = {"key": "1.234"}
    assert _get_f("key", data1) == 1.23
    data2 = {"key": "1.235"}
    assert _get_f("key", data2) == 1.24
    data3 = {"key": "-1.234"}
    assert _get_f("key", data3) == -1.23
    data4 = {"key": "-1.235"}
    assert _get_f("key", data4) == -1.24
