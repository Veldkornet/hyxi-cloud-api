import sys
from unittest.mock import MagicMock, AsyncMock, patch

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

@pytest.mark.asyncio
async def test_execute_metric_tasks_with_tasks():
    state = FetchState(plants=[{"id": 1}], now="2024-01-01T00:00:00Z")
    state.metric_tasks = [AsyncMock()]
    plant_alarms = []

    with patch.object(
        HyxiApiClient,
        "_execute_metrics_and_map_alarms",
        new_callable=AsyncMock
    ) as mock_execute:
        await HyxiApiClient._execute_metric_tasks(plant_alarms, state)
        mock_execute.assert_awaited_once_with(plant_alarms, state)

@pytest.mark.asyncio
async def test_execute_metric_tasks_without_tasks():
    state = FetchState(plants=[{"id": 1}], now="2024-01-01T00:00:00Z")
    state.metric_tasks = []
    plant_alarms = []

    with patch.object(
        HyxiApiClient,
        "_execute_metrics_and_map_alarms",
        new_callable=AsyncMock
    ) as mock_execute:
        await HyxiApiClient._execute_metric_tasks(plant_alarms, state)
        mock_execute.assert_not_awaited()
