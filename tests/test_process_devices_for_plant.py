"""Tests for the _process_devices_for_plant method."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Handle missing aiohttp gracefully as seen in other files
if "aiohttp" not in sys.modules or not hasattr(sys.modules["aiohttp"], "ClientError"):
    m = MagicMock()

    class MockExp(Exception):
        pass

    m.ClientError = MockExp
    sys.modules["aiohttp"] = m

from src.hyxi_cloud_api.api import FetchState, HyxiApiClient


@pytest.fixture
def mock_api():
    """Fixture for a mock API client."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._update_discovery_cache = MagicMock()
    api._fetch_all_for_device = AsyncMock()
    api._fetch_sub_devices = MagicMock(return_value="fetch_sub_device_task")
    return api


@pytest.fixture
def mock_state():
    """Fixture for a mock FetchState object."""
    return FetchState(now="2024-01-01T00:00:00Z")


@pytest.mark.asyncio
async def test_process_devices_for_plant_missing_sn_edge_cases(mock_api, mock_state):
    """Test with devices having missing, None, or empty string serial numbers."""
    devices = [
        {"deviceType": "INVERTER"},
        {"deviceSn": None, "deviceType": "INVERTER"},
        {"deviceSn": "", "deviceType": "INVERTER"},
    ]
    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
        await mock_api._process_devices_for_plant(devices, mock_state)
        mock_gather.assert_not_called()
        assert len(mock_state.discovered_sns) == 0
        assert len(mock_state.metric_tasks) == 0


@pytest.mark.asyncio
async def test_process_devices_for_plant_empty(mock_api, mock_state):
    """Test with an empty list of devices."""
    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
        await mock_api._process_devices_for_plant([], mock_state)
        mock_gather.assert_not_called()
        assert len(mock_state.discovered_sns) == 0
        assert len(mock_state.metric_tasks) == 0


@pytest.mark.asyncio
async def test_process_devices_for_plant_no_sn(mock_api, mock_state):
    """Test with devices missing a serial number."""
    devices = [{"deviceType": "INVERTER"}, {"deviceName": "No SN"}]
    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
        await mock_api._process_devices_for_plant(devices, mock_state)
        mock_gather.assert_not_called()
        assert len(mock_state.discovered_sns) == 0
        assert len(mock_state.metric_tasks) == 0


@pytest.mark.asyncio
async def test_process_devices_for_plant_normal_devices(mock_api, mock_state):
    """Test with normal devices that do not trigger sub-device fetching."""
    devices = [
        {"deviceSn": "SN_NORMAL_1", "deviceType": "NORMAL_1"},
        {"deviceSn": "SN_NORMAL_2", "deviceType": "NORMAL_2"},
    ]
    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
        await mock_api._process_devices_for_plant(devices, mock_state)

        mock_gather.assert_not_called()
        assert "SN_NORMAL_1" in mock_state.discovered_sns
        assert "SN_NORMAL_2" in mock_state.discovered_sns
        assert mock_api._update_discovery_cache.call_count == 2
        assert len(mock_state.metric_tasks) == 2
        assert len(mock_state.metric_tasks) == 2


@pytest.mark.asyncio
async def test_process_devices_for_plant_parent_devices(mock_api, mock_state):
    """Test with parent devices that trigger sub-device fetching."""
    # "COLLECTOR", "DMU", "INVERTER" are matched by _PARENT_DEVICE_REGEX
    devices = [
        {"deviceSn": "SN_COLLECTOR", "deviceType": "COLLECTOR"},
        {"deviceSn": "SN_DMU", "deviceType": "DMU"},
        {"deviceSn": "SN_INVERTER", "deviceType": "INVERTER"},
    ]
    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
        await mock_api._process_devices_for_plant(devices, mock_state)

        mock_gather.assert_called_once_with(
            "fetch_sub_device_task", "fetch_sub_device_task", "fetch_sub_device_task"
        )
        assert mock_api._fetch_sub_devices.call_count == 3
        mock_api._fetch_sub_devices.assert_any_call("SN_COLLECTOR", mock_state)
        mock_api._fetch_sub_devices.assert_any_call("SN_DMU", mock_state)
        mock_api._fetch_sub_devices.assert_any_call("SN_INVERTER", mock_state)

        assert "SN_COLLECTOR" in mock_state.discovered_sns
        assert "SN_DMU" in mock_state.discovered_sns
        assert "SN_INVERTER" in mock_state.discovered_sns


@pytest.mark.asyncio
async def test_process_devices_for_plant_mixed_devices(mock_api, mock_state):
    """Test with a mix of normal devices, parent devices, and invalid devices."""
    devices = [
        {"deviceSn": "SN_COLLECTOR", "deviceType": "COLLECTOR"},
        {"deviceType": "UNKNOWN"},  # Missing SN
        {"deviceSn": "SN_NORMAL", "deviceType": "METER"},
    ]
    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
        await mock_api._process_devices_for_plant(devices, mock_state)

        mock_gather.assert_called_once_with("fetch_sub_device_task")
        mock_api._fetch_sub_devices.assert_called_once_with("SN_COLLECTOR", mock_state)

        assert "SN_COLLECTOR" in mock_state.discovered_sns
        assert "SN_NORMAL" in mock_state.discovered_sns
        assert len(mock_state.discovered_sns) == 2
        assert len(mock_state.metric_tasks) == 2
