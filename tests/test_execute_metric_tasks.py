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


@pytest.mark.asyncio
async def test_execute_metric_tasks_with_tasks():
    """Test _execute_metric_tasks when metric tasks are present."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    state = FetchState(plants=[{"id": 1}], now="2024-01-01T00:00:00Z")
    state.metric_tasks = [("SN", {}, "TYPE")]
    api._execute_metrics_and_map_alarms = AsyncMock()
    plant_alarms = {}

    api._fetch_all_for_device = AsyncMock()
    with patch("asyncio.gather", new_callable=AsyncMock):
        await api._execute_metric_tasks(plant_alarms, state)
        api._execute_metrics_and_map_alarms.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_metric_tasks_without_tasks():
    """Test _execute_metric_tasks when metric tasks are absent."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    state = FetchState(plants=[{"id": 1}], now="2024-01-01T00:00:00Z")
    state.metric_tasks = []
    plant_alarms = {}
    api._execute_metrics_and_map_alarms = AsyncMock()

    with patch("asyncio.gather", new_callable=AsyncMock):
        await api._execute_metric_tasks(plant_alarms, state)
        api._execute_metrics_and_map_alarms.assert_not_awaited()
