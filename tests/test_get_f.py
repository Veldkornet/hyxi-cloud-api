"""Tests for the _get_f helper function in api.py."""

import pytest
from hyxi_cloud_api.api import _get_f


@pytest.mark.parametrize(
    "key, data_map, mult, expected",
    [
        # Happy paths
        ("val", {"val": "10.5"}, 1.0, 10.5),
        ("val", {"val": "10.5"}, 2.0, 21.0),
        ("val", {"val": "10.556"}, 1.0, 10.56),  # Rounding check
        ("val", {"val": "10.554"}, 1.0, 10.55),  # Rounding check
        ("val", {"val": 10}, 1.5, 15.0),  # Int input
        ("val", {"val": 10.5}, 1.0, 10.5),  # Float input
        # Edge cases: None, empty, missing
        ("val", {"val": None}, 1.0, 0.0),
        ("val", {"val": ""}, 1.0, 0.0),
        ("missing", {"val": "10.5"}, 1.0, 0.0),
        ("val", {}, 1.0, 0.0),
        # Error conditions: Invalid strings
        ("val", {"val": "not-a-number"}, 1.0, 0.0),
        ("val", {"val": "10.5.5"}, 1.0, 0.0),
        # Multiplier variations
        ("val", {"val": "100"}, 0.1, 10.0),
        ("val", {"val": "100"}, 0.0, 0.0),
        ("val", {"val": "100"}, -1.0, -100.0),
    ],
)
def test_get_f_parameterized(key, data_map, mult, expected):
    """Test _get_f with various inputs to ensure safety and correctness."""
    assert _get_f(key, data_map, mult) == expected


def test_get_f_default_multiplier():
    """Test _get_f uses default multiplier of 1.0."""
    assert _get_f("val", {"val": "42.0"}) == 42.0
