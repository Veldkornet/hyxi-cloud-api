"""Tests for the _mask_id and _sanitize_dict log sanitisation helpers in api.py."""

from src.hyxi_cloud_api.api import _mask_id, _sanitize_dict


class TestMaskId:
    """Tests for _mask_id to validate anonymisation and debuggability."""

    # --- Anonymisation ---

    def test_normal_sn_is_masked_with_x_padding(self):
        """A typical device SN should be masked using X characters, preserving length."""
        result = _mask_id("HYXABC12345678")
        assert result == "HYXXXXXXXXX678"  # HYX + 8 X's + 678 = 14 chars
        assert len(result) == len("HYXABC12345678")

    def test_normal_sn_does_not_expose_full_value(self):
        """The full serial number must not appear in the output."""
        sn = "HYXABC12345678"
        result = _mask_id(sn)
        assert result != sn

    def test_short_id_is_fully_redacted(self):
        """IDs shorter than 8 characters must be fully hidden to prevent exposure."""
        assert _mask_id("12345") == "****"
        assert _mask_id("1234567") == "****"

    def test_exactly_8_chars_is_masked(self):
        """An 8-character ID sits on the threshold and should be partially masked."""
        result = _mask_id("ABCD1234")
        assert result == "ABCXX234"  # ABC + 2 X's + 234 = 8 chars
        assert len(result) == 8

    def test_empty_string_returns_redacted(self):
        """An empty string input should return the redacted placeholder."""
        assert _mask_id("") == "****"

    def test_none_like_falsy_value(self):
        """'None' as a string (4 chars) — should be redacted."""
        assert _mask_id("None") == "****"

    def test_length_is_always_preserved(self):
        """Masked output must always be the same length as the original ID."""
        for sn in ["HYXABC12345678", "10602251600016", "60701251900927"]:
            assert len(_mask_id(sn)) == len(sn)

    # --- Debuggability / cross-device correlation ---

    def test_same_id_always_produces_same_output(self):
        """Masking is deterministic: same SN yields same masked value every time.
        This ensures cross-device log correlation is preserved."""
        sn = "HYXABC12345678"
        assert _mask_id(sn) == _mask_id(sn)

    def test_different_ids_with_different_suffixes_are_distinguishable(self):
        """Two devices with different SNs should produce different masked values."""
        result_a = _mask_id("HYXABC00000001")
        result_b = _mask_id("HYXABC00000099")
        assert result_a != result_b

    def test_numeric_plant_id_long_enough_is_masked(self):
        """A long numeric plant ID (e.g. 8+ digits) should be partially masked."""
        result = _mask_id("123456789")
        assert result == "123XXX789"
        assert len(result) == 9

    def test_output_uses_x_characters(self):
        """Masked output must use 'X' as the padding character."""
        result = _mask_id("HYXABC12345678")
        middle = result[3:-3]
        assert all(c == "X" for c in middle)


class TestSanitizeDict:
    """Tests for _sanitize_dict to verify PII is scrubbed from raw API payloads."""

    def test_device_sn_is_masked(self):
        """Device serial numbers in raw API payloads must be masked."""
        raw = {"deviceSn": "10602251600016", "ratedPower": "10000"}
        result = _sanitize_dict(raw)
        assert result["deviceSn"] != "10602251600016"
        assert "X" in result["deviceSn"]
        assert result["ratedPower"] == "10000"  # Non-sensitive key unchanged

    def test_parent_sn_is_masked(self):
        """Parent device serial numbers must be masked (they link devices to each other)."""
        raw = {"parentSn": "60701251900927", "model": "HYX-H10K-HT"}
        result = _sanitize_dict(raw)
        assert result["parentSn"] != "60701251900927"
        assert "X" in result["parentSn"]

    def test_bat_sn_is_masked(self):
        """Battery serial numbers must be masked."""
        raw = {"batSn": "15023250300001", "batSoc": "91"}
        result = _sanitize_dict(raw)
        assert result["batSn"] != "15023250300001"
        assert "X" in result["batSn"]

    def test_plant_id_is_masked(self):
        """Plant IDs must be masked as they identify a user's cloud account."""
        raw = {"plantId": "Pl1970106681857806336", "plantName": "My Plant"}
        result = _sanitize_dict(raw)
        assert result["plantId"] != "Pl1970106681857806336"
        assert "X" in result["plantId"]

    def test_plant_address_is_fully_redacted(self):
        """Home address must be completely hidden, not partially masked."""
        raw = {"plantAddress": "2, Bonenakker, Zoetermeer, Netherlands"}
        result = _sanitize_dict(raw)
        assert result["plantAddress"] == "[REDACTED]"

    def test_gprs_imei_is_masked(self):
        """GPRS IMEI numbers are sensitive device identifiers and must be masked."""
        raw = {"gprsImei": "123456789012345"}
        result = _sanitize_dict(raw)
        assert result["gprsImei"] != "123456789012345"

    def test_non_sensitive_keys_are_unchanged(self):
        """Keys not in the sensitive list must pass through unmodified."""
        raw = {"ratedPower": "10000", "hwVer": "V00.00.01", "model": "HYX-H10K-HT"}
        result = _sanitize_dict(raw)
        assert result == raw

    def test_original_dict_is_not_mutated(self):
        """_sanitize_dict must return a copy, never modifying the original."""
        raw = {"deviceSn": "10602251600016", "ratedPower": "10000"}
        _ = _sanitize_dict(raw)
        assert raw["deviceSn"] == "10602251600016"

    def test_empty_sensitive_value_stays_empty(self):
        """An empty string for a sensitive key should not be masked (nothing to hide)."""
        raw = {"gprsImei": "", "model": "HYX-DCS-WL"}
        result = _sanitize_dict(raw)
        assert result["gprsImei"] == ""
