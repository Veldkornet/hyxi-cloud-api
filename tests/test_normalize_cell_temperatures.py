"""Tests for the _normalize_cell_temperatures helper function in api.py."""

import pytest

from src.hyxi_cloud_api.api import _normalize_cell_temperatures


class TestNormalizeCellTemperatures:
    """Micro ESS/Halo devices report batTch/batTcl in tenths of a degree;
    _normalize_cell_temperatures scales them to degrees for that family only.
    """

    @pytest.mark.parametrize(
        "device_type", ["15", "16", "EMS", "MICRO_STORAGE_ALL_IN_ONE"]
    )
    def test_scales_tenths_for_micro_ess_family(self, device_type):
        """A HALO sends cell temps in tenths of a degree."""
        m_raw = {"batTch": "383.0", "batTcl": "336.0"}
        _normalize_cell_temperatures(m_raw, device_type)
        assert m_raw["batTch"] == 38.3
        assert m_raw["batTcl"] == 33.6

    def test_leaves_other_device_types_untouched(self):
        """A hybrid inverter already sends whole degrees."""
        m_raw = {"batTch": "25.0", "batTcl": "22.0"}
        _normalize_cell_temperatures(m_raw, "HYBRID_INVERTER")
        assert m_raw["batTch"] == "25.0"
        assert m_raw["batTcl"] == "22.0"

    def test_none_device_type_is_a_noop(self):
        """A None device_type is treated as non-Micro-ESS."""
        m_raw = {"batTch": "383.0"}
        _normalize_cell_temperatures(m_raw, None)
        assert m_raw["batTch"] == "383.0"

    def test_missing_keys_are_a_noop(self):
        """No batTch/batTcl in the payload: nothing added, nothing changed."""
        m_raw: dict = {"batSoc": "80"}
        _normalize_cell_temperatures(m_raw, "15")
        assert m_raw == {"batSoc": "80"}

    def test_unparsable_value_left_untouched(self):
        """A non-numeric value is left exactly as-is."""
        m_raw = {"batTch": "not-a-number"}
        _normalize_cell_temperatures(m_raw, "15")
        assert m_raw["batTch"] == "not-a-number"

    def test_negative_tenths_scaled(self):
        """A sub-zero cell in tenths (a HALO in a cold space) scales too."""
        m_raw = {"batTcl": "-55.0"}
        _normalize_cell_temperatures(m_raw, "16")
        assert m_raw["batTcl"] == -5.5
