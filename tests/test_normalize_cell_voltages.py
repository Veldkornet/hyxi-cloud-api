"""Tests for the _normalize_cell_voltages helper function in api.py."""

from src.hyxi_cloud_api.api import _normalize_cell_voltages


class TestNormalizeCellVoltages:
    """batVch/batVcl arrive in millivolts from some firmwares and volts from
    others; _normalize_cell_voltages converts the millivolt form and returns
    both as floats.
    """

    def test_converts_millivolts_to_volts(self):
        """A HYX-H10K-HT sends batVch in millivolts."""
        m_raw = {"batVch": "3203.0", "batVcl": "3190.0"}
        _normalize_cell_voltages(m_raw)
        assert m_raw["batVch"] == 3.203
        assert m_raw["batVcl"] == 3.19

    def test_leaves_volts_untouched_but_floats_them(self):
        """A HALO already sends volts; magnitude is kept, type is float."""
        m_raw = {"batVch": "3.308", "batVcl": "3.299"}
        _normalize_cell_voltages(m_raw)
        assert m_raw["batVch"] == 3.308
        assert m_raw["batVcl"] == 3.299

    def test_mixed_units_in_one_payload_end_up_consistent(self):
        """batVch in millivolts, batVcl in volts (seen together in one poll)
        -- both come out as volts, both as float.
        """
        m_raw = {"batVch": "3203.0", "batVcl": "3.19"}
        _normalize_cell_voltages(m_raw)
        assert m_raw["batVch"] == 3.203
        assert m_raw["batVcl"] == 3.19

    def test_out_of_range_value_keeps_magnitude(self):
        """A 65535 'no data' sentinel is not a plausible millivolt cell
        reading, so it is left at its magnitude (as a float).
        """
        m_raw = {"batVch": "65535"}
        _normalize_cell_voltages(m_raw)
        assert m_raw["batVch"] == 65535.0

    def test_missing_keys_are_a_noop(self):
        """No batVch/batVcl in the payload: nothing added, nothing changed."""
        m_raw: dict = {"batSoc": "80"}
        _normalize_cell_voltages(m_raw)
        assert m_raw == {"batSoc": "80"}

    def test_unparsable_value_left_untouched(self):
        """A non-numeric value is left exactly as-is."""
        m_raw = {"batVch": "not-a-number"}
        _normalize_cell_voltages(m_raw)
        assert m_raw["batVch"] == "not-a-number"

    def test_none_value_left_untouched(self):
        """A None value is left exactly as-is."""
        m_raw = {"batVch": None}
        _normalize_cell_voltages(m_raw)
        assert m_raw["batVch"] is None

    def test_threshold_boundaries_are_treated_as_volts(self):
        """10 and 10000 exactly are outside the millivolt band, so their
        magnitude is kept.
        """
        m_raw = {"batVch": 10.0, "batVcl": 10000.0}
        _normalize_cell_voltages(m_raw)
        assert m_raw["batVch"] == 10.0
        assert m_raw["batVcl"] == 10000.0
