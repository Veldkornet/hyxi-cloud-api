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

import asyncio

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

    async def mock_metric_task(sn, result):
        return (sn, result)

    state.metric_tasks = [
        asyncio.create_task(mock_metric_task("SN1", {"data": 1})),
        asyncio.create_task(mock_metric_task("SN2", {"data": 2})),
        asyncio.create_task(mock_metric_task("SN3", {"data": 3})),  # No alarms
        asyncio.create_task(mock_metric_task(None, {"data": 4})),  # None SN
    ]

    await HyxiApiClient._execute_metrics_and_map_alarms(plant_alarms, state)

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
