import sys
from unittest.mock import MagicMock

if "aiohttp" not in sys.modules or not hasattr(sys.modules["aiohttp"], "ClientError"):
    m = MagicMock()

    class MockExp(Exception):
        def __init__(self, *args, **kwargs):
            super().__init__(*args)
            for k, v in kwargs.items():
                setattr(self, k, v)

    m.ClientError = MockExp
    m.ClientResponseError = type("ClientResponseError", (MockExp,), {})
    m.ContentTypeError = type("ContentTypeError", (MockExp,), {})
    sys.modules["aiohttp"] = m
mock_aiohttp = sys.modules["aiohttp"]

"""Tests for the _get_f helper function in api.py."""

from src.hyxi_cloud_api.api import _get_f


class TestGetF:
    """Tests for _get_f to validate data extraction and type conversion."""

    def test_valid_integer(self):
        """Valid integer value should be converted to float."""
        data = {"key": 100}
        assert _get_f("key", data) == 100.0

    def test_valid_float(self):
        """Valid float value should be returned as float."""
        data = {"key": 123.45}
        assert _get_f("key", data) == 123.45

    def test_valid_string_number(self):
        """Valid string representation of a number should be converted."""
        data = {"key": "456.78"}
        assert _get_f("key", data) == 456.78

    def test_valid_number_with_multiplier(self):
        """Multiplier should be applied correctly."""
        data = {"key": "10.5"}
        assert _get_f("key", data, mult=2.0) == 21.0

    def test_rounding_to_two_decimals(self):
        """Result should be rounded to 2 decimal places."""
        data = {"key": "1.23456"}
        assert _get_f("key", data) == 1.23

        data2 = {"key": "1.236"}
        assert _get_f("key", data2) == 1.24

    def test_missing_key(self):
        """Missing key should return 0.0."""
        data = {"other_key": 100}
        assert _get_f("missing_key", data) == 0.0

    def test_value_is_none(self):
        """None value should return 0.0."""
        data = {"key": None}
        assert _get_f("key", data) == 0.0

    def test_value_is_empty_string(self):
        """Empty string value should return 0.0."""
        data = {"key": ""}
        assert _get_f("key", data) == 0.0

    def test_value_is_invalid_string(self):
        """Non-numeric string should return 0.0 due to ValueError."""
        data = {"key": "invalid_number"}
        assert _get_f("key", data) == 0.0

    def test_value_is_invalid_type_list(self):
        """Invalid type (list) should return 0.0 due to TypeError."""
        data = {"key": [1, 2, 3]}
        assert _get_f("key", data) == 0.0

    def test_value_is_invalid_type_dict(self):
        """Invalid type (dict) should return 0.0 due to TypeError."""
        data = {"key": {"nested": "value"}}
        assert _get_f("key", data) == 0.0

    def test_value_error_triggered(self):
        """Test a condition that triggers a ValueError and returns 0.0."""
        data = {"key": "not-a-number"}
        assert _get_f("key", data) == 0.0

    def test_get_f_explicit_type_error(self):
        """Test specific condition triggering TypeError at line 567."""
        data = {"key": []}
        assert _get_f("key", data) == 0.0
