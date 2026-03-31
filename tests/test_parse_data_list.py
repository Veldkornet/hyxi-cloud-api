"""Tests for the _parse_data_list helper function in api.py."""

from src.hyxi_cloud_api.api import _parse_data_list


def test_parse_data_list_happy_path():
    """Test that valid list of dicts is parsed correctly."""
    data = [
        {"dataKey": "key1", "dataValue": "value1"},
        {"dataKey": "key2", "dataValue": "value2"},
    ]
    assert _parse_data_list(data) == {"key1": "value1", "key2": "value2"}


def test_parse_data_list_empty_list():
    """Test that an empty list returns an empty dict."""
    assert _parse_data_list([]) == {}


def test_parse_data_list_invalid_items():
    """Test that invalid items are ignored."""
    data = [
        {"dataKey": "key1", "dataValue": "value1"},
        "invalid",
        {"key2": "value2"},
        None,
    ]
    assert _parse_data_list(data) == {"key1": "value1"}


def test_parse_data_list_missing_value():
    """Test that items missing dataValue return None."""
    data = [{"dataKey": "key1"}]
    assert _parse_data_list(data) == {"key1": None}


def test_parse_data_list_missing_key():
    """Test that items missing dataKey are ignored."""
    data = [{"dataValue": "value1"}]
    assert _parse_data_list(data) == {}
