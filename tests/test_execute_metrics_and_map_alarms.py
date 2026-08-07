import sys
from unittest.mock import MagicMock

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
mock_aiohttp = sys.modules["aiohttp"]


import pytest

from src.hyxi_cloud_api.api import FetchState, HyxiApiClient


@pytest.mark.asyncio
async def test_execute_metrics_and_map_alarms():
    """Test correctly mapping parsed alarms onto metric results."""
    plant_alarms = [
        {"deviceSn": "SN1", "alarmId": "A1"},
        {"deviceSn": "SN1", "alarmId": "A2"},
        {"deviceSn": "SN2", "alarmId": "A3"},
    ]

    state = FetchState(now="2023-10-27")

    state.metric_tasks = [
        ("SN1", {"data": 1}, "TYPE"),
        ("SN2", {"data": 2}, "TYPE"),
        ("SN3", {"data": 3}, "TYPE"),  # No alarms
        (None, {"data": 4}, "TYPE"),  # None SN
    ]

    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    async def mock_fetch(sn, entry, t):
        return (sn, entry)

    api._fetch_all_for_device = mock_fetch
    await api._execute_metrics_and_map_alarms(plant_alarms, state)

    assert state.results["SN1"]["data"] == 1
    assert len(state.results["SN1"]["alarms"]) == 2
    assert {"deviceSn": "SN1", "alarmId": "A1"} in state.results["SN1"]["alarms"]
    assert {"deviceSn": "SN1", "alarmId": "A2"} in state.results["SN1"]["alarms"]

    assert state.results["SN2"]["data"] == 2
    assert len(state.results["SN2"]["alarms"]) == 1
    assert {"deviceSn": "SN2", "alarmId": "A3"} in state.results["SN2"]["alarms"]

    assert state.results["SN3"]["data"] == 3
    assert len(state.results["SN3"]["alarms"]) == 0

    assert None not in state.results


@pytest.mark.asyncio
async def test_execute_metrics_and_map_alarms_alarm_without_device_sn():
    """A malformed alarm entry with no 'deviceSn' is skipped while building
    the alarm map, instead of crashing or being attributed to a device."""
    plant_alarms = [
        {"alarmId": "ORPHAN"},  # no deviceSn
        {"deviceSn": "SN1", "alarmId": "A1"},
    ]
    state = FetchState(now="2023-10-27")
    state.metric_tasks = [("SN1", {"data": 1}, "TYPE")]

    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    async def mock_fetch(sn, entry, t):
        return (sn, entry)

    api._fetch_all_for_device = mock_fetch
    await api._execute_metrics_and_map_alarms(plant_alarms, state)

    assert len(state.results["SN1"]["alarms"]) == 1
    assert state.results["SN1"]["alarms"][0]["alarmId"] == "A1"


@pytest.mark.asyncio
async def test_execute_metrics_and_map_alarms_no_metric_tasks():
    """With no metric tasks (e.g. a plant that only reported alarms), the
    method must not call asyncio.gather on an empty list and should simply
    leave state.results empty."""
    plant_alarms = [{"deviceSn": "SN1", "alarmId": "A1"}]
    state = FetchState(now="2023-10-27")
    state.metric_tasks = []

    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._fetch_all_for_device = MagicMock(
        side_effect=AssertionError("should not be called")
    )

    await api._execute_metrics_and_map_alarms(plant_alarms, state)

    assert not state.results
