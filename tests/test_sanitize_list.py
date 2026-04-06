"""Tests for the _sanitize_list function in hyxi_cloud_api.api."""

from unittest.mock import patch
from src.hyxi_cloud_api.api import _sanitize_list


def test_sanitize_list_empty():
    """Test that an empty list returns an empty list."""
    # pylint: disable=use-implicit-booleaness-not-comparison
    assert _sanitize_list([]) == []


def test_sanitize_list_simple():
    """Test sanitization of a simple list with mixed types."""
    raw = [1, "string", True, None]
    assert _sanitize_list(raw) == [1, "string", True, None]


def test_sanitize_list_empty_strings():
    """Test that empty strings are converted to None."""
    raw = ["", "valid", ""]
    assert _sanitize_list(raw) == [None, "valid", None]


def test_sanitize_list_nested():
    """Test that nested lists are sanitized recursively."""
    raw = [1, ["", 2], ""]
    assert _sanitize_list(raw) == [1, [None, 2], None]


@patch("src.hyxi_cloud_api.api._mask_id", return_value="MASKED")
def test_sanitize_list_with_dicts(mock_mask):
    """Test that dictionaries within a list are sanitized correctly."""
    raw = [{"deviceSn": "123456789"}, ""]
    result = _sanitize_list(raw)
    assert result[1] is None
    assert result[0]["deviceSn"] == "MASKED"
    mock_mask.assert_called_once_with("123456789")


def test_sanitize_list_falsy_values():
    """Test that falsy values other than empty strings are preserved."""
    raw = [0, 0.0, False, (1, "")]
    expected = [0, 0.0, False, (1, "")]
    assert _sanitize_list(raw) == expected


def test_sanitize_list_whitespace_strings():
    """Test that strings with only whitespace are not converted to None."""
    raw = [" ", "  ", "\t", "\n"]
    assert _sanitize_list(raw) == [" ", "  ", "\t", "\n"]


def test_sanitize_list_no_mutation():
    """Test that _sanitize_list does not mutate the original list."""
    raw = ["deviceSn", "123456789", ""]
    original = raw.copy()
    result = _sanitize_list(raw)
    assert raw == original
    assert result != original
