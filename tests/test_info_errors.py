"""Tests for exception handling in _fetch_device_info."""

import logging
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from hyxi_cloud_api.api import HyxiApiClient

@pytest.mark.asyncio
async def test_fetch_device_info_network_error(caplog):
    """Test that _fetch_device_info handles network errors gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Mock session.get to raise a ClientError
    mock_session.get.side_effect = aiohttp.ClientError("Connection reset")

    entry = {"metrics": {}, "device_type_code": "INVERTER"}
    # Use a longer SN so it's not fully masked to ****
    await api._fetch_device_info("10602251600016", entry)

    assert "Error fetching device info for 106XXXXXXXX016: Connection reset" in caplog.text
    # Ensure it didn't crash and entry was not updated with metrics
    assert "sw_version" not in entry

@pytest.mark.asyncio
async def test_fetch_device_info_invalid_json(caplog):
    """Test that _fetch_device_info handles invalid JSON gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    mock_response = AsyncMock()
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.json.side_effect = aiohttp.ContentTypeError(
        request_info=MagicMock(), history=(), message="Attempt to decode JSON with unexpected mimetype"
    )
    yielded_response.status = 200

    mock_session.get.return_value = mock_response

    entry = {"metrics": {}, "device_type_code": "INVERTER"}
    await api._fetch_device_info("10602251600016", entry)

    assert "Error fetching device info for 106XXXXXXXX016" in caplog.text
    assert "sw_version" not in entry

@pytest.mark.asyncio
async def test_fetch_device_info_api_error(caplog):
    """Test that _fetch_device_info handles API-level errors correctly."""
    caplog.set_level(logging.WARNING)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    mock_response = AsyncMock()
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.json.return_value = {
        "success": False,
        "message": "Device not found"
    }
    yielded_response.status = 200

    mock_session.get.return_value = mock_response

    entry = {"metrics": {}, "device_type_code": "INVERTER"}
    await api._fetch_device_info("10602251600016", entry)

    assert "HYXi INFO API Rejected for 106XXXXXXXX016: Device not found" in caplog.text
    assert "sw_version" not in entry
