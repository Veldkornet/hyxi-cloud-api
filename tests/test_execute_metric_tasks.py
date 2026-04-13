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
    state = FetchState(plants=[{"id": 1}], now="2024-01-01T00:00:00Z")
    state.metric_tasks = [AsyncMock()]
    plant_alarms = {}

    with patch(
        "asyncio.gather",
        new_callable=AsyncMock
    ) as mock_gather:
        await HyxiApiClient._execute_metric_tasks(plant_alarms, state)
        mock_gather.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_metric_tasks_without_tasks():
    """Test _execute_metric_tasks when metric tasks are absent."""
    state = FetchState(plants=[{"id": 1}], now="2024-01-01T00:00:00Z")
    state.metric_tasks = []
    plant_alarms = {}

    with patch(
        "asyncio.gather",
        new_callable=AsyncMock
    ) as mock_gather:
        await HyxiApiClient._execute_metric_tasks(plant_alarms, state)
        mock_gather.assert_not_awaited()
