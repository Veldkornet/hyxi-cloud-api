from src.hyxi_cloud_api.api import HyxiApiClient


def test_extract_device_info_metadata_basic():
    """Test basic metadata extraction and non-battery metrics exclusion."""
    entry = {"metrics": {}, "device_type_code": "UNKNOWN"}
    i_raw = {
        "swVer": "v1.0",
        "hwVer": "h1.0",
        "signalIntensity": "Strong",
        "signalVal": 100,
        "wifiVer": "w1.0",
        "comMode": "WiFi",
        "swVerMaster": "m1.0",
        "swVerSlave": "s1.0",
    }

    base_info = HyxiApiClient._extract_device_info_metadata(entry, i_raw)

    assert entry["sw_version"] == "m1.0"
    assert entry["hw_version"] == "h1.0"
    assert base_info["_sw_ver_sys"] == "m1.0"
    assert base_info["hw_version"] == "h1.0"
    assert base_info["signalIntensity"] == "Strong"
    assert base_info["signalVal"] == 100
    assert base_info["wifiVer"] == "w1.0"
    assert base_info["comMode"] == "WiFi"
    assert base_info["swVerMaster"] == "m1.0"
    assert base_info["swVerSlave"] == "s1.0"

    # Verify battery metrics are not included
    assert "batCap" not in base_info


def test_extract_device_info_metadata_sw_ver_fallback():
    """Test software version fallbacks prioritizing swVerSys > swVerMaster > swVer."""
    # Only swVer present
    entry = {"metrics": {}}
    i_raw = {"swVer": "v1.0"}
    HyxiApiClient._extract_device_info_metadata(entry, i_raw)
    assert entry["sw_version"] == "v1.0"

    # swVerMaster takes precedence over swVer
    entry = {"metrics": {}}
    i_raw = {"swVer": "v1.0", "swVerMaster": "m1.0"}
    HyxiApiClient._extract_device_info_metadata(entry, i_raw)
    assert entry["sw_version"] == "m1.0"

    # swVerSys takes precedence over swVerMaster
    entry = {"metrics": {}}
    i_raw = {"swVer": "v1.0", "swVerMaster": "m1.0", "swVerSys": "sys1.0"}
    HyxiApiClient._extract_device_info_metadata(entry, i_raw)
    assert entry["sw_version"] == "sys1.0"
    assert entry.get("hw_version") is None


def test_extract_device_info_metadata_battery_device():
    """Test extraction of battery-specific metrics for battery devices."""
    entry = {"metrics": {}, "device_type_code": "INVERTER"}
    i_raw = {
        "batCap": "100.5",
        "packNum": "2",
        "maxChargePower": "50.0",
        "maxDischargePower": "40.0",
    }

    base_info = HyxiApiClient._extract_device_info_metadata(entry, i_raw)

    assert base_info["batCap"] == 100.5
    assert base_info["packNum"] == 2
    assert base_info["maxChargePower"] == 50.0
    assert base_info["maxDischargePower"] == 40.0
    assert "batCap" in entry["metrics"]


def test_extract_device_info_metadata_battery_fallbacks():
    """Test fallbacks for missing battery-specific metrics."""
    entry = {"metrics": {}, "device_type_code": "ESS"}
    i_raw = {
        "maxChargingDischargingPower": "30.0"
        # packNum is missing, should default to 1
        # maxChargePower and maxDischargePower missing, fallback to maxChargingDischargingPower
    }

    base_info = HyxiApiClient._extract_device_info_metadata(entry, i_raw)

    assert base_info["packNum"] == 1
    assert base_info["maxChargePower"] == 30.0
    assert base_info["maxDischargePower"] == 30.0
