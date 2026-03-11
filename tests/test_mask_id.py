"""Tests for the _mask_id log sanitisation helper in api.py."""

from hyxi_cloud_api.api import _mask_id


class TestMaskId:
    """Tests for _mask_id to validate anonymisation and debuggability."""

    # --- Anonymisation ---

    def test_normal_sn_is_masked(self):
        """A typical device serial number should be partially masked."""
        result = _mask_id("HYXABC12345678")
        assert result == "HYX...678"

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
        assert result == "ABC...234"

    def test_empty_string_returns_redacted(self):
        """An empty string input should return the redacted placeholder."""
        assert _mask_id("") == "****"

    def test_none_like_falsy_value(self):
        """None coerced to string would be 'None' (4 chars) — should be redacted."""
        # _mask_id expects a str; guard against accidental None being passed
        assert _mask_id("None") == "****"

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
        assert result == "123...789"

    def test_output_format_contains_ellipsis(self):
        """Masked output must use '...' as the separator for readability."""
        result = _mask_id("HYXABC12345678")
        assert "..." in result
