"""Tests for the recursive device discovery and sensor extraction logic."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from src.hyxi_cloud_api.api import HyxiApiClient


def _setup_mock_api():
    """Helper to set up a mock API client for discovery tests."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._fetch_plants = AsyncMock(return_value=[{"plantId": "Pl123"}])

    mock_response = MagicMock()
    mock_response.__aenter__.return_value.status = 200
    mock_response.__aenter__.return_value.json = AsyncMock(
        side_effect=[
            {
                "success": True,
                "data": {
                    "deviceList": [
                        {
                            "deviceSn": "COLL_001",
                            "deviceType": "COLLECTOR",
                            "deviceName": "My Collector",
                        }
                    ]
                },
            },
            {
                "success": True,
                "data": {
                    "childDevice": [
                        {
                            "deviceSn": "INV_001",
                            "deviceType": "1",  # Hybrid Inverter
                            "deviceName": "My Inverter",
                        }
                    ]
                },
            },
        ]
    )

    api.session.post = MagicMock(return_value=mock_response)
    api.session.get = MagicMock(return_value=mock_response)
    api._fetch_device_info = AsyncMock()
    api._fetch_device_metrics = AsyncMock()
    api._fetch_alarms_for_plant = AsyncMock(return_value=[])

    return api


@pytest.mark.asyncio
async def test_collector_discovery_only():
    """Verify that a Collector is discovered correctly."""
    api = _setup_mock_api()
    results = {}

    await api._process_plants_data(
        [{"plantId": "Pl123"}], "2024-01-01", results, allow_back_discovery=True
    )

    assert "COLL_001" in results
    assert results["COLL_001"]["device_type_code"] == "COLLECTOR"


@pytest.mark.asyncio
async def test_sub_device_discovery_triggered_by_collector():
    """Verify that discovering a Collector triggers discovery of its sub-devices."""
    api = _setup_mock_api()
    results = {}

    await api._process_plants_data(
        [{"plantId": "Pl123"}], "2024-01-01", results, allow_back_discovery=True
    )

    assert "INV_001" in results
    assert results["INV_001"]["model"] == "Hybrid Inverter"
    assert results["INV_001"]["device_type_code"] == "1"


@pytest.mark.asyncio
async def test_back_discovery_and_recursive_probe():
    """Verify that a device found ONLY in alarms triggers a recursive probe."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)

    # 1. No devices in the main list
    api._fetch_devices_for_plant = AsyncMock()

    # 2. Alarm list has a "hidden" Collector
    alarm = {
        "deviceSn": "HIDDEN_COLL",
        "deviceType": "COLLECTOR",
        "deviceName": "Hidden Collector",
    }
    api._fetch_alarms_for_plant = AsyncMock(return_value=[alarm])

    # 3. Mock the sub-device probe for the hidden collector
    mock_sub_response = MagicMock()
    mock_sub_response.__aenter__.return_value.status = 200
    mock_sub_response.__aenter__.return_value.json = AsyncMock(
        return_value={
            "success": True,
            "data": {
                "childDevice": [
                    {
                        "deviceSn": "HIDDEN_INV",
                        "deviceType": "1",
                        "deviceName": "Hidden Inverter",
                    }
                ]
            },
        }
    )
    api.session.post = MagicMock(return_value=mock_sub_response)
    api.session.get = MagicMock(return_value=mock_sub_response)

    # Mock metric/info tasks by replacing the underlying methods
    async def mock_fetch_all(sn, entry, dev_type):
        return (sn, entry)

    api._fetch_all_for_device = MagicMock(side_effect=mock_fetch_all)

    results = {}
    await api._process_plants_data(
        [{"plantId": "Pl123"}], "2024-01-01", results, allow_back_discovery=True
    )

    # Check both were found!
    assert "HIDDEN_COLL" in results
    assert "HIDDEN_INV" in results


@pytest.mark.asyncio
async def test_verified_sensor_extraction():
    """Verify that packNum and batCap are extracted correctly from the info block."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    # Mock the response structure matching user logs: a flat dictionary!
    mock_info_resp = {
        "success": True,
        "data": {"packNum": "5", "batCap": "22.074", "swVerSys": "v1.2.3"},
    }

    # Mock the aiohttp call inside _fetch_device_info
    mock_response = MagicMock()
    mock_response.__aenter__.return_value.status = 200
    mock_response.__aenter__.return_value.json = AsyncMock(return_value=mock_info_resp)
    api.session.get = MagicMock(return_value=mock_response)

    entry = {"metrics": {}, "device_type_code": "1"}  # Hybrid Inverter
    # Device type must be one that allows battery info
    await api._fetch_device_info("SN123", entry)

    # Check extraction
    assert entry["metrics"]["packNum"] == 5
    assert entry["metrics"]["batCap"] == 22.07
    assert entry["sw_version"] == "v1.2.3"


@pytest.mark.asyncio
async def test_metric_sanitization_for_collector():
    """Verify that battery metrics are NOT associated with a COLLECTOR."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    # Mock a metrics response that INCLUDES battery data (which shouldn't be there)
    mock_metrics_resp = {
        "success": True,
        "data": [
            {"dataKey": "signalVal", "dataValue": "4"},
            {"dataKey": "pbat", "dataValue": "1500"},  # A battery metric
            {"dataKey": "batsoc", "dataValue": "80"},  # Another battery metric
        ],
    }

    mock_response = MagicMock()
    mock_response.__aenter__.return_value.status = 200
    mock_response.__aenter__.return_value.json = AsyncMock(
        return_value=mock_metrics_resp
    )
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


@pytest.mark.asyncio
async def test_fetch_sub_devices_rejected():
    """Verify that a rejected sub-device fetch logs an error and returns gracefully."""
    api = HyxiApiClient("ak", "sk", "https://api.com", AsyncMock())

    mock_response = AsyncMock()
    mock_response.__aenter__.return_value.status = 200
    mock_response.__aenter__.return_value.json.return_value = {
        "success": False,
        "msg": "Invalid parent SN",
    }

    api.session.post = MagicMock(return_value=mock_response)

    metric_tasks = []
    discovered_sns = set()

    with pytest.MonkeyPatch.context() as m:
        mock_logger = MagicMock()
        m.setattr("src.hyxi_cloud_api.api._LOGGER", mock_logger)

        await api._fetch_sub_devices("BAD_SN", "Plant123", metric_tasks, discovered_sns)

        assert len(metric_tasks) == 0
        assert len(discovered_sns) == 0

        # Verify the logger was called with the correct error message
        mock_logger.error.assert_called_once()
        args, _ = mock_logger.error.call_args
        assert "HYXI API Sub-Device Fetch Rejected" in args[0]


@pytest.mark.asyncio
async def test_fetch_sub_devices_exception():
    """Verify that an exception during sub-device fetch is caught and logged."""
    api = HyxiApiClient("ak", "sk", "https://api.com", AsyncMock())

    # Force an exception during the request
    api.session.post = MagicMock(side_effect=Exception("Network Timeout"))

    metric_tasks = []
    discovered_sns = set()

    with pytest.MonkeyPatch.context() as m:
        mock_logger = MagicMock()
        m.setattr("src.hyxi_cloud_api.api._LOGGER", mock_logger)

        await api._fetch_sub_devices(
            "SOME_SN", "Plant123", metric_tasks, discovered_sns
        )

        assert len(metric_tasks) == 0
        assert len(discovered_sns) == 0

        # Verify the logger caught the exception
        mock_logger.error.assert_called_once()
        args, _ = mock_logger.error.call_args

@pytest.mark.asyncio
async def test_get_all_device_data_discovery_toggle():
    """Verify that get_all_device_data respects the allow_back_discovery toggle."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._fetch_plants = AsyncMock(return_value=[{"plantId": "Pl123"}])
    
    # 1. Mock empty device list
    api._fetch_devices_for_plant = AsyncMock()
    
    # 2. Mock alarm with a new device
    alarm = {"deviceSn": "NEW_DEVICE_SN", "deviceType": "1", "deviceName": "New Device"}
    api._fetch_alarms_for_plant = AsyncMock(return_value=[alarm])
    api._fetch_all_for_device = AsyncMock(return_value=("NEW_DEVICE_SN", {}))
    
    # CASE A: Toggle OFF (Default) -> Should NOT discover
    res_off = await api.get_all_device_data(allow_back_discovery=False)
    assert "NEW_DEVICE_SN" not in res_off["data"]
    
    # CASE B: Toggle ON -> Should discover
    res_on = await api.get_all_device_data(allow_back_discovery=True)
    assert "NEW_DEVICE_SN" in res_on["data"]

@pytest.mark.asyncio
async def test_back_discovery_sn_validation():
    """Verify that back-discovery rejects malformed or short serial numbers."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._fetch_plants = AsyncMock(return_value=[{"plantId": "Pl123"}])
    api._fetch_devices_for_plant = AsyncMock()
    
    # Alarm with a "ghost" SN (too short)
    alarm = {"deviceSn": "123", "deviceType": "1", "deviceName": "Ghost"}
    api._fetch_alarms_for_plant = AsyncMock(return_value=[alarm])
    api._fetch_all_for_device = AsyncMock()
    
    # Toggle ON -> Should still reject due to length validation
    res = await api.get_all_device_data(allow_back_discovery=True)
    assert "123" not in res["data"]
    api._fetch_all_for_device.assert_not_called()
