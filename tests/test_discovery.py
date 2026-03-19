"""Tests for the recursive device discovery and sensor extraction logic."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from src.hyxi_cloud_api.api import HyxiApiClient

@pytest.mark.asyncio
async def test_sub_device_recursive_discovery():
    """Verify that discovering a Collector triggers discovery of its sub-devices."""
    api = HyxiApiClient("ak", "sk", "https://api.com", AsyncMock())
    api._refresh_token = AsyncMock(return_value=True)

    # 1. Mock _fetch_plants
    api._fetch_plants = AsyncMock(return_value=[{"plantId": "Pl123"}])

    # 2. Mock response
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value.status = 200
    mock_response.__aenter__.return_value.json.side_effect = [
        {
            "success": True,
            "data": {
                "deviceList": [
                    {
                        "deviceSn": "COLL_001",
                        "deviceType": "COLLECTOR",
                        "deviceName": "My Collector"
                    }
                ]
            }
        },
        {
            "success": True,
            "data": {
                "childDevice": [
                    {
                        "deviceSn": "INV_001",
                        "deviceType": "1", # Hybrid Inverter
                        "deviceName": "My Inverter"
                    }
                ]
            }
        }
    ]
    
    # Inverters and Collectors need both POST (for sub-discovery) and GET (for info/metrics)
    api.session.post = MagicMock(return_value=mock_response)
    api.session.get = MagicMock(return_value=mock_response)

    # We need to mock _fetch_device_info/metrics to avoid more network calls
    api._fetch_device_info = AsyncMock()
    api._fetch_device_metrics = AsyncMock()
    # Mock alarm fetch to return empty list
    api._fetch_alarms_for_plant = AsyncMock(return_value=[])

    results = {}
    await api._process_plants_data([{"plantId": "Pl123"}], "2024-01-01", results)

    # Verify both Collector and Inverter were discovered
    assert "COLL_001" in results
    assert "INV_001" in results
    assert results["INV_001"]["model"] == "Hybrid Inverter"

@pytest.mark.asyncio
async def test_back_discovery_and_recursive_probe():
    """Verify that a device found ONLY in alarms triggers a recursive probe."""
    api = HyxiApiClient("ak", "sk", "https://api.com", AsyncMock())
    api._refresh_token = AsyncMock(return_value=True)

    # 1. No devices in the main list
    api._fetch_devices_for_plant = AsyncMock()

    # 2. Alarm list has a "hidden" Collector
    alarm = {
        "deviceSn": "HIDDEN_COLL",
        "deviceType": "COLLECTOR",
        "deviceName": "Hidden Collector"
    }
    api._fetch_alarms_for_plant = AsyncMock(return_value=[alarm])

    # 3. Mock the sub-device probe for the hidden collector
    mock_sub_response = AsyncMock()
    mock_sub_response.__aenter__.return_value.status = 200
    mock_sub_response.__aenter__.return_value.json.return_value = {
        "success": True,
        "data": {
            "childDevice": [
                {"deviceSn": "HIDDEN_INV", "deviceType": "1", "deviceName": "Hidden Inverter"}
            ]
        }
    }
    api.session.post = MagicMock(return_value=mock_sub_response)
    api.session.get = MagicMock(return_value=mock_sub_response)

    # Mock metric/info tasks by replacing the underlying methods
    async def mock_fetch_all(sn, entry, dev_type):
        return (sn, entry)
    api._fetch_all_for_device = MagicMock(side_effect=mock_fetch_all)

    results = {}
    await api._process_plants_data([{"plantId": "Pl123"}], "2024-01-01", results)

    # Check both were found!
    assert "HIDDEN_COLL" in results
    assert "HIDDEN_INV" in results

@pytest.mark.asyncio
async def test_verified_sensor_extraction():
    """Verify that packNum and batCap are extracted correctly from the info block."""
    api = HyxiApiClient("ak", "sk", "https://api.com", AsyncMock())
    
    # Mock the response structure matching user logs: a flat dictionary!
    mock_info_resp = {
        "success": True,
        "data": {
            "packNum": "5",
            "batCap": "22.074",
            "swVerSys": "v1.2.3"
        }
    }
    
    # Mock the aiohttp call inside _fetch_device_info
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value.status = 200
    mock_response.__aenter__.return_value.json.return_value = mock_info_resp
    api.session.get = MagicMock(return_value=mock_response)

    entry = {"metrics": {}, "device_type_code": "1"} # Hybrid Inverter
    # Device type must be one that allows battery info
    await api._fetch_device_info("SN123", entry)
    
    # Check extraction
    assert entry["metrics"]["packNum"] == 5
    assert entry["metrics"]["batCap"] == 22.07
    assert entry["sw_version"] == "v1.2.3"

@pytest.mark.asyncio
async def test_metric_sanitization_for_collector():
    """Verify that battery metrics are NOT associated with a COLLECTOR."""
    api = HyxiApiClient("ak", "sk", "https://api.com", AsyncMock())
    
    # Mock a metrics response that INCLUDES battery data (which shouldn't be there)
    mock_metrics_resp = {
        "success": True,
        "data": [
            {"dataKey": "signalVal", "dataValue": "4"},
            {"dataKey": "pbat", "dataValue": "1500"}, # A battery metric
            {"dataKey": "batsoc", "dataValue": "80"}  # Another battery metric
        ]
    }
    
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value.status = 200
    mock_response.__aenter__.return_value.json.return_value = mock_metrics_resp
    api.session.get = MagicMock(return_value=mock_response)

    # 1. Test with COLLECTOR - Should be sanitized
    entry_coll = {"metrics": {}, "device_type_code": "COLLECTOR"}
    await api._fetch_device_metrics("SN_COLL", entry_coll)
    assert "signalVal" in entry_coll["metrics"]
    assert "pbat" not in entry_coll["metrics"]
    assert "batsoc" not in entry_coll["metrics"]

    # 2. Test with INVERTER - Should NOT be sanitized
    entry_inv = {"metrics": {}, "device_type_code": "1"}
    await api._fetch_device_metrics("SN_INV", entry_inv)
    assert "pbat" in entry_inv["metrics"]
    assert "batsoc" in entry_inv["metrics"]
