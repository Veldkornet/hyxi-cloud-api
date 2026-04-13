import asyncio
from unittest.mock import AsyncMock, patch
import pytest

from src.hyxi_cloud_api.api import HyxiApiClient

@pytest.mark.asyncio
async def test_execute_device_tasks_empty():
    """Test _execute_device_tasks with empty list."""
    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
        await HyxiApiClient._execute_device_tasks([])
        mock_gather.assert_not_called()

@pytest.mark.asyncio
async def test_execute_device_tasks_none():
    """Test _execute_device_tasks with None."""
    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
        await HyxiApiClient._execute_device_tasks(None)
        mock_gather.assert_not_called()

@pytest.mark.asyncio
async def test_execute_device_tasks_with_tasks():
    """Test _execute_device_tasks with tasks."""
    task1 = "dummy_task_1"
    task2 = "dummy_task_2"
    tasks = [task1, task2]

    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
        await HyxiApiClient._execute_device_tasks(tasks)
        mock_gather.assert_called_once_with(*tasks)
