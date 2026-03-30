import sys
from unittest.mock import MagicMock

# Mock aiohttp
sys.modules['aiohttp'] = MagicMock()

import pytest
from src.hyxi_cloud_api.api import HyxiApiClient

def test_build_device_entry_complete():
    """Verifies standard behavior with all fields present."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    sn = "SN123"
    device_data = {
        "deviceType": "METER",
        "deviceName": "Main Meter",
        "swVer": "v1.0",
        "hwVer": "v2.0"
    }
    now = 1234567890

    entry, dev_type = api._build_device_entry(sn, device_data, now)

    assert dev_type == "METER"
    assert entry["sn"] == sn
    assert entry["device_name"] == "Main Meter"
    assert entry["model"] == "Meter"
    assert entry["device_type_code"] == "METER"
    assert entry["sw_version"] == "v1.0"
    assert entry["hw_version"] == "v2.0"
    assert entry["metrics"]["last_seen"] == now

def test_build_device_entry_alias_fallback():
    """Verifies that alias is used when deviceName is missing."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    sn = "SN123"
    device_data = {
        "deviceType": "METER",
        "alias": "Alias Name"
    }
    now = 1234567890

    entry, _ = api._build_device_entry(sn, device_data, now)
    assert entry["device_name"] == "Alias Name"

def test_build_device_entry_name_autogen():
    """Verifies that a name is automatically generated when names are missing."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    sn = "SN123"
    device_data = {
        "deviceType": "METER"
    }
    now = 1234567890

    entry, _ = api._build_device_entry(sn, device_data, now)
    assert entry["device_name"] == "Meter SN123"

def test_build_device_entry_unknown_type():
    """Verifies that unmapped deviceType codes are formatted into a title-cased model name."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    sn = "SN123"
    device_data = {
        "deviceType": "SOME_NEW_TYPE"
    }
    now = 1234567890

    entry, dev_type = api._build_device_entry(sn, device_data, now)
    assert dev_type == "SOME_NEW_TYPE"
    assert entry["model"] == "Some New Type"
    assert entry["device_name"] == "Some New Type SN123"

def test_build_device_entry_missing_type():
    """Verifies that a missing deviceType defaults to UNKNOWN and Unknown."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    sn = "SN123"
    device_data = {}
    now = 1234567890

    entry, dev_type = api._build_device_entry(sn, device_data, now)
    assert dev_type == "UNKNOWN"
    assert entry["model"] == "Unknown"
    assert entry["device_name"] == "Unknown SN123"
