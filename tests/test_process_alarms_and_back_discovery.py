"""Tests for the _process_alarms_and_back_discovery method."""
# pylint: disable=protected-access, redefined-outer-name

import sys
from unittest.mock import AsyncMock, MagicMock, patch

if "aiohttp" not in sys.modules or not hasattr(sys.modules["aiohttp"], "ClientError"):
    m = MagicMock()

    class MockExp(Exception):
        def __init__(self, *args, **kwargs):
            super().__init__(*args)
            for k, v in kwargs.items():
                setattr(self, k, v)

    m.ClientError = MockExp
    m.ClientResponseError = type("ClientResponseError", (MockExp,), {})
    m.ContentTypeError = type("ContentTypeError", (MockExp,), {})
    sys.modules["aiohttp"] = m


import pytest

from src.hyxi_cloud_api.api import FetchState, HyxiApiClient


@pytest.fixture
def mock_api():
    """Fixture for a mock HYXi API client."""
    return HyxiApiClient("ak", "sk", "https://api.com", MagicMock())


@pytest.fixture
def mock_state():
    """Fixture for a mock FetchState object."""
    state = FetchState(now="2024-01-01T00:00:00Z")
    state.plants = [{"plantId": "plant1"}, {"plantId": "plant2"}, {"plantId": "plant3"}]
    return state


@pytest.mark.asyncio
async def test_process_alarms_allow_back_discovery_false(mock_api, mock_state):
    """Test extracting alarms when back-discovery is disabled."""
    mock_api._handle_back_discovery_alarm = MagicMock()
    alarm_results = [
        [{"id": "a1", "deviceSn": "sn1"}],
        [{"id": "a2", "deviceSn": "sn2"}],
        [{"id": "a3", "deviceSn": "sn3"}],
    ]

    result = await mock_api._process_alarms_and_back_discovery(
        alarm_results, mock_state, allow_back_discovery=False
    )

    assert len(result) == 3
    assert result[0]["id"] == "a1"
    assert result[1]["id"] == "a2"
    assert result[2]["id"] == "a3"
    mock_api._handle_back_discovery_alarm.assert_not_called()


@pytest.mark.asyncio
async def test_process_alarms_allow_back_discovery_true(mock_api, mock_state):
    """Test processing alarms when back-discovery is enabled."""
    mock_api._handle_back_discovery_alarm = MagicMock()
    alarm_results = [
        [{"id": "a1", "deviceSn": "sn1"}],
        [{"id": "a2", "deviceSn": "sn2"}],
        [{"id": "a3", "deviceSn": "sn3"}],
    ]

    result = await mock_api._process_alarms_and_back_discovery(
        alarm_results, mock_state, allow_back_discovery=True
    )

    assert len(result) == 3
    assert mock_api._handle_back_discovery_alarm.call_count == 3

    # Check that _handle_back_discovery_alarm was called with the correct plant_id
    calls = mock_api._handle_back_discovery_alarm.call_args_list
    assert calls[0][0][0] == {"id": "a1", "deviceSn": "sn1"}
    assert calls[0][0][1] == "plant1"
    assert calls[1][0][0] == {"id": "a2", "deviceSn": "sn2"}
    assert calls[1][0][1] == "plant2"
    assert calls[2][0][0] == {"id": "a3", "deviceSn": "sn3"}
    assert calls[2][0][1] == "plant3"


@pytest.mark.asyncio
async def test_process_alarms_with_non_list_results(mock_api, mock_state):
    """Test that non-list alarm results are skipped."""
    mock_api._handle_back_discovery_alarm = MagicMock()
    alarm_results = [
        [{"id": "a1"}],
        {"error": "something went wrong"},  # Not a list, should be skipped
        [{"id": "a3"}],
    ]

    result = await mock_api._process_alarms_and_back_discovery(
        alarm_results, mock_state, allow_back_discovery=True
    )

    assert len(result) == 2
    assert result[0]["id"] == "a1"
    assert result[1]["id"] == "a3"
    assert mock_api._handle_back_discovery_alarm.call_count == 2


@pytest.mark.asyncio
@patch("src.hyxi_cloud_api.api.asyncio.gather", new_callable=AsyncMock)
async def test_process_alarms_gathers_sub_device_tasks(
    mock_gather, mock_api, mock_state
):
    """Test that sub-device tasks created during back-discovery are awaited."""

    def side_effect(a, plant_id, state, sub_device_tasks):
        sub_device_tasks.append(("sn", state))

    mock_api._handle_back_discovery_alarm = MagicMock(side_effect=side_effect)
    alarm_results = [[{"id": "a1"}]]

    await mock_api._process_alarms_and_back_discovery(
        alarm_results, mock_state, allow_back_discovery=True
    )

    mock_gather.assert_called_once()
