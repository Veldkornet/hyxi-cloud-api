"""Tests for the _normalize_phase_ac_keys helper function in api.py."""

from src.hyxi_cloud_api.api import _normalize_phase_ac_keys


class TestNormalizePhaseAcKeys:
    """/api/device/v2/queryDeviceData reports per-phase AC voltage/current/
    power as ph{n}Ac{v,i,p}, but every sensor and the push-format parser
    expect the un-infixed ph{n}{v,i,p}; _normalize_phase_ac_keys renames
    them in place.
    """

    def test_renames_all_three_phases(self):
        """ph1/ph2/ph3, each of v/i/p, all become their plain equivalents."""
        m_raw = {
            "ph1Acv": "230.0",
            "ph1Aci": "2.13",
            "ph1Acp": "-11.0",
            "ph2Acv": "232.3",
            "ph2Aci": "0.88",
            "ph2Acp": "-101.0",
            "ph3Acv": "228.4",
            "ph3Aci": "0.3",
            "ph3Acp": "0.0",
        }
        _normalize_phase_ac_keys(m_raw)
        assert m_raw == {
            "ph1v": "230.0",
            "ph1i": "2.13",
            "ph1p": "-11.0",
            "ph2v": "232.3",
            "ph2i": "0.88",
            "ph2p": "-101.0",
            "ph3v": "228.4",
            "ph3i": "0.3",
            "ph3p": "0.0",
        }

    def test_the_ac_infixed_key_does_not_leak_through(self):
        """The source key is removed, not merely aliased."""
        m_raw = {"ph1Acv": "230.0"}
        _normalize_phase_ac_keys(m_raw)
        assert "ph1Acv" not in m_raw

    def test_ph_loadp_is_left_alone(self):
        """ph{n}Loadp was never renamed by HYXI; it isn't in the key map."""
        m_raw = {"ph1Loadp": "303.0", "ph2Loadp": "-100.0"}
        _normalize_phase_ac_keys(m_raw)
        assert m_raw == {"ph1Loadp": "303.0", "ph2Loadp": "-100.0"}

    def test_missing_keys_are_a_noop(self):
        """No ph{n}Ac{v,i,p} in the payload: nothing added, nothing changed."""
        m_raw: dict = {"batSoc": "80"}
        _normalize_phase_ac_keys(m_raw)
        assert m_raw == {"batSoc": "80"}

    def test_partial_payload_only_renames_whats_present(self):
        """A payload with only some phases populated renames just those."""
        m_raw = {"ph2Acv": "232.3", "ph2Aci": "0.88", "ph2Acp": "-101.0"}
        _normalize_phase_ac_keys(m_raw)
        assert m_raw == {"ph2v": "232.3", "ph2i": "0.88", "ph2p": "-101.0"}

    def test_does_not_overwrite_an_existing_plain_key(self):
        """If the plain key is already present (defensive; shouldn't happen
        from a single REST poll), it wins over the Ac-infixed source.
        """
        m_raw = {"ph1Acv": "230.0", "ph1v": "999.0"}
        _normalize_phase_ac_keys(m_raw)
        assert m_raw["ph1v"] == "999.0"
        assert "ph1Acv" not in m_raw
