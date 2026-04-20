from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.hyxi_cloud_api.api import FetchState, HyxiApiClient


@pytest.fixture
def api_client():
    """Fixture to provide a configured API client."""
    return HyxiApiClient("ak", "sk", "https://api.com", MagicMock())


@pytest.mark.asyncio
async def test_fetch_and_process_alarms_empty(api_client):
    """Test _fetch_and_process_alarms with empty list."""
    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
        result = await api_client._fetch_and_process_alarms([], FetchState(now="now"))
        assert result == []
        mock_gather.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_and_process_alarms_none(api_client):
    """Test _fetch_and_process_alarms with None."""
    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
        result = await api_client._fetch_and_process_alarms(None, FetchState(now="now"))
        assert result == []
        mock_gather.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_and_process_alarms_with_tasks(api_client):
    """Test _fetch_and_process_alarms with tasks."""
    state = FetchState(now="now")
    task1 = "dummy_task_1"
    task2 = "dummy_task_2"
    tasks = [task1, task2]
    expected_results = ["result_1", "result_2"]

    with patch(
        "asyncio.gather", new_callable=AsyncMock, return_value=expected_results
    ) as mock_gather:
        with patch.object(
            api_client,
            "_process_alarms_and_back_discovery",
            new_callable=AsyncMock,
            return_value=["processed_result"],
        ) as mock_process:
            result = await api_client._fetch_and_process_alarms(
                tasks, state, allow_back_discovery=True
            )

            assert result == ["processed_result"]
            mock_gather.assert_called_once_with(*tasks)
            mock_process.assert_called_once_with(
                expected_results,
                state,
                allow_back_discovery=True,
            )
