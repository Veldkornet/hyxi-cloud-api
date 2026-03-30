"""Fuzz testing for the metrics parser.

Ensures that the parser handles unexpected or malicious data types without
crashing, while verifying that derived metric triggers remain intact.
"""

from hyxi_cloud_api.api import _compute_derived_metrics


def test_parser_fuzz_types():
    """Feed random types into the parser helper to ensure no unhandled exceptions."""
    junk_inputs = [
        None,
        "",
        "   ",
        "NaN",
        "inf",
        "999999999999999999999",
        [],
        {},
        True,
        False,
        "0.0.0",
        "-",
    ]

    for val in junk_inputs:
        # Should not raise
        m_raw = {
            "gridP": val,
            "pbat": val,
            "batP": val,
            "ph1Loadp": val,
            "ph2Loadp": val,
            "ph3Loadp": val,
        }
        res = _compute_derived_metrics(m_raw)
        assert isinstance(res, dict)
        # Ensure fallback to 0.0
        assert isinstance(res["home_load"], float)
        assert isinstance(res["bat_power_dc"], float)


def test_parser_extreme_values():
    """Verify that the round() in parser handles extreme floats gracefully."""
    m_raw = {
        "gridP": "1.23456789",
        "pbat": "99999.99999",
        "batP": "-0.00000001",
    }
    res = _compute_derived_metrics(m_raw)
    assert res["grid_export"] == 1234.57  # gridP * 1000
    assert res["bat_discharging"] == 100000.0  # pbat rounded
    assert res["bat_power_dc"] == -0.0
