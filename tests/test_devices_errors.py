"""Tests for exception handling in _fetch_devices_for_plant."""

import logging
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from hyxi_cloud_api.api import HyxiApiClient


@pytest.mark.asyncio
async def test_fetch_devices_for_plant_api_error(caplog):
    """Test that _fetch_devices_for_plant handles API-level errors correctly."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    mock_response = AsyncMock()
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.json.return_value = {
        "success": False,
        "message": "Plant not found",
    }
    yielded_response.raise_for_status = MagicMock()
    yielded_response.status = 200

    mock_session.post.return_value = mock_response

    metric_tasks = []
    discovered_sns = set()
    await api._fetch_devices_for_plant(
        "plant123", "2024-01-01", metric_tasks, discovered_sns
    )

    assert "HYXI API Device Fetch Rejected for Plant" in caplog.text
    assert not metric_tasks
    assert not discovered_sns


@pytest.mark.asyncio
async def test_fetch_devices_for_plant_network_error(caplog):
    """Test that _fetch_devices_for_plant handles network errors gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    mock_session.post.side_effect = aiohttp.ClientError("Connection reset")

    metric_tasks = []
    discovered_sns = set()
    await api._fetch_devices_for_plant(
        "plant123", "2024-01-01", metric_tasks, discovered_sns
    )

    assert "Error fetching devices for plant" in caplog.text
    assert not metric_tasks
    assert not discovered_sns


@pytest.mark.asyncio
async def test_fetch_devices_for_plant_invalid_json(caplog):
    """Test that _fetch_devices_for_plant handles invalid JSON gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    mock_response = AsyncMock()
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.json.side_effect = aiohttp.ContentTypeError(
        request_info=MagicMock(),
        history=(),
        message="Attempt to decode JSON with unexpected mimetype",
    )
    yielded_response.status = 200

    mock_session.post.return_value = mock_response

    metric_tasks = []
    discovered_sns = set()
    await api._fetch_devices_for_plant(
        "plant123", "2024-01-01", metric_tasks, discovered_sns
    )

    assert "Error fetching devices for plant" in caplog.text
    assert not metric_tasks
    assert not discovered_sns
