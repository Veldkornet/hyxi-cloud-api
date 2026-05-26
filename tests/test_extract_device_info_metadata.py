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


def test_extract_device_info_metadata_micro_ess():
    """Test extraction of battery-specific metrics and fallbacks for Micro ESS (type 16) devices."""
    entry = {"metrics": {}, "device_type_code": "16"}
    i_raw = {
        "batCap": "15.0",
        "packNum": "1",
        "maxChargePower": "700",
        "maxDischargePower": "700",
        "swVerWifi": "V01.00.00.01",
        "ratedFrequency": "50",
    }

    base_info = HyxiApiClient._extract_device_info_metadata(entry, i_raw)

    assert base_info["batCap"] == 15.0
    assert base_info["packNum"] == 1
    assert base_info["maxChargePower"] == 700.0
    assert base_info["maxDischargePower"] == 700.0
    assert base_info["wifiVer"] == "V01.00.00.01"
    assert base_info["ratedFrequency"] == "50"
    assert "batCap" in entry["metrics"]


def test_extract_device_info_metadata_model():
    """Test that the model field is extracted and updates the entry when changed."""
    entry = {"metrics": {}, "device_type_code": "UNKNOWN", "model": "generic inverter"}
    i_raw = {"model": "H10K-HT"}
    HyxiApiClient._extract_device_info_metadata(entry, i_raw)
    assert entry["model"] == "H10K-HT"

    # Verify model is NOT overwritten if not present in response
    entry2 = {"metrics": {}, "device_type_code": "UNKNOWN", "model": "H10K-HT"}
    i_raw2 = {}
    HyxiApiClient._extract_device_info_metadata(entry2, i_raw2)
    assert entry2["model"] == "H10K-HT"
