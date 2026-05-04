from src.hyxi_cloud_api.api import HyxiApiClient


def test_extract_battery_info_basic():
    """Test basic extraction of battery info."""
    i_raw = {
        "batCap": "10.5",
        "packNum": "2",
        "maxChargePower": "5.0",
        "maxDischargePower": "4.5",
    }

    result = HyxiApiClient._extract_battery_info(i_raw)

    assert result == {
        "batCap": 10.5,
        "packNum": 2,
        "maxChargePower": 5.0,
        "maxDischargePower": 4.5,
    }


def test_extract_battery_info_fallbacks():
    """Test extraction with fallbacks and missing values."""
    i_raw = {
        "batCap": "",
        # missing packNum entirely
        "maxChargingDischargingPower": "7.5",
        # missing maxChargePower and maxDischargePower entirely
    }

    result = HyxiApiClient._extract_battery_info(i_raw)

    assert result == {
        "batCap": 0.0,
        "packNum": 1,
        "maxChargePower": 7.5,
        "maxDischargePower": 7.5,
    }


def test_extract_battery_info_none():
    """Test extraction with None values."""
    i_raw = {
        "batCap": None,
        "packNum": None,
        "maxChargePower": None,
        "maxDischargePower": None,
        "maxChargingDischargingPower": None,
    }

    result = HyxiApiClient._extract_battery_info(i_raw)

    assert result == {
        "batCap": 0.0,
        "packNum": 1,
        "maxChargePower": 0.0,
        "maxDischargePower": 0.0,
    }
