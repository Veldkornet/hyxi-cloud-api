"""Tests for ALL_IN_ONE device support."""

from src.hyxi_cloud_api.api import _compute_derived_metrics


class TestAllInOneBatteryPreference:
    """Test that pbat is preferred over batP for ALL_IN_ONE devices.

    ALL_IN_ONE devices can report batP with an inverted sign convention,
    while pbat is consistently negative-for-charging / positive-for-discharging.
    """

    def test_pbat_preferred_when_batp_sign_inverted(self):
        """ALL_IN_ONE: batP has inverted sign, pbat is correct."""
        data = {"batP": 500.0, "pbat": -450.0}  # batP says discharging, pbat says charging
        result = _compute_derived_metrics(data, device_type="ALL_IN_ONE")
        assert result["bat_charging"] == 450.0
        assert result["bat_discharging"] == 0.0

    def test_pbat_preferred_discharging(self):
        """ALL_IN_ONE: pbat positive = discharging."""
        data = {"batP": -600.0, "pbat": 550.0}  # batP inverted, pbat correct
        result = _compute_derived_metrics(data, device_type="ALL_IN_ONE")
        assert result["bat_charging"] == 0.0
        assert result["bat_discharging"] == 550.0

    def test_fallback_to_batp_when_pbat_zero(self):
        """ALL_IN_ONE: when pbat is zero, fall back to batP."""
        data = {"batP": -300.0, "pbat": 0.0}
        result = _compute_derived_metrics(data, device_type="ALL_IN_ONE")
        assert result["bat_charging"] == 300.0
        assert result["bat_discharging"] == 0.0
        assert result["bat_power_dc"] == -300.0


class TestAllInOnePv1pDerivation:
    """Test pv1p derivation for ALL_IN_ONE devices.

    ALL_IN_ONE devices may only report ppv (total) and pv2p (string 2),
    without reporting pv1p directly. In that case pv1p = ppv - pv2p.
    """

    def test_pv1p_derived_from_ppv_minus_pv2p(self):
        """pv1p is derived when only ppv and pv2 data are present."""
        data = {"ppv": 3000.0, "pv2v": 400.0, "pv2i": 5.0}
        result = _compute_derived_metrics(data)
        assert result["pv2p"] == 2000.0
        assert result["pv1p"] == 1000.0  # 3000 - 2000

    def test_pv1p_not_negative(self):
        """pv1p derivation clamps to zero (never negative)."""
        data = {"ppv": 1000.0, "pv2v": 400.0, "pv2i": 5.0}  # pv2p=2000 > ppv
        result = _compute_derived_metrics(data)
        assert result["pv2p"] == 2000.0
        assert result["pv1p"] == 0.0

    def test_pv1p_not_derived_when_reported_directly(self):
        """pv1p is NOT derived when pv1 data is already reported."""
        data = {"ppv": 3000.0, "pv1v": 300.0, "pv1i": 3.0, "pv2v": 400.0, "pv2i": 5.0}
        result = _compute_derived_metrics(data)
        assert result["pv1p"] == 900.0  # from pv1v * pv1i, not ppv - pv2p
        assert result["pv2p"] == 2000.0

    def test_pv1p_not_derived_without_ppv(self):
        """pv1p is NOT derived when ppv is missing."""
        data = {"pv2v": 400.0, "pv2i": 5.0}
        result = _compute_derived_metrics(data)
        assert result["pv2p"] == 2000.0
        assert "pv1p" not in result

    def test_pv1p_not_derived_without_pv2(self):
        """pv1p is NOT derived when pv2 data is missing."""
        data = {"ppv": 3000.0}
        result = _compute_derived_metrics(data)
        assert "pv1p" not in result
