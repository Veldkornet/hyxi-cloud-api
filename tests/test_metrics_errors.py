"""Tests for exception handling in _fetch_device_metrics."""

import logging
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from hyxi_cloud_api.api import HyxiApiClient


@pytest.mark.asyncio
async def test_fetch_device_metrics_network_error(caplog):
    """Test that _fetch_device_metrics handles network errors gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Mock session.get to raise a ClientError
    mock_session.get.side_effect = aiohttp.ClientError("Connection reset")

    entry = {"metrics": {}, "device_type_code": "INVERTER"}
    # Use a longer SN so it's not fully masked to ****
    await api._fetch_device_metrics("10602251600016", entry)

    assert "Error fetching metrics for 106XXXXXXXX016: Connection reset" in caplog.text
    # Ensure it didn't crash and entry was not updated with metrics
    assert not entry["metrics"]


@pytest.mark.asyncio
async def test_fetch_device_metrics_invalid_json(caplog):
    """Test that _fetch_device_metrics handles invalid JSON gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    mock_response = MagicMock()
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.raise_for_status = MagicMock()
    yielded_response.json = AsyncMock(
        side_effect=aiohttp.ContentTypeError(
            request_info=MagicMock(),
            history=(),
            message="Attempt to decode JSON with unexpected mimetype",
        )
    )
    yielded_response.raise_for_status = MagicMock()
    yielded_response.status = 200

    mock_session.get.return_value = mock_response

    entry = {"metrics": {}, "device_type_code": "INVERTER"}
    await api._fetch_device_metrics("10602251600016", entry)

    assert "Error fetching metrics for 106XXXXXXXX016" in caplog.text
    assert not entry["metrics"]


@pytest.mark.asyncio
async def test_fetch_device_metrics_api_error(caplog):
    """Test that _fetch_device_metrics handles API-level errors correctly."""
    caplog.set_level(logging.WARNING)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    mock_response = MagicMock()
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.raise_for_status = MagicMock()
    yielded_response.json = AsyncMock(
        return_value={
            "success": False,
            "message": "Device not found",
        }
    )
    yielded_response.raise_for_status = MagicMock()
    yielded_response.status = 200

    mock_session.get.return_value = mock_response

    entry = {"metrics": {}, "device_type_code": "INVERTER"}
    await api._fetch_device_metrics("10602251600016", entry)

    assert (
        "HYXI API metrics rejected for 106XXXXXXXX016: Device not found" in caplog.text
    )
    assert not entry["metrics"]


@pytest.mark.asyncio
async def test_fetch_ems_basic_data_no_data(caplog):
    """Test that _fetch_ems_basic_data handles empty response gracefully."""
    caplog.set_level(logging.DEBUG)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Mock query_ems_basic_details to return None (no data)
    api.query_ems_basic_details = AsyncMock(return_value=None)

    # Inject mock directly into the module resolving all patch issues
    import hyxi_cloud_api.api as api_mod  # pylint: disable=import-outside-toplevel

    mock_logger = MagicMock()
    api_mod._LOGGER = mock_logger

    entry = {"metrics": {}, "device_type_code": "EMS"}
    await api._fetch_ems_basic_data("10602251600016", entry)

    mock_logger.debug.assert_called_with(
        "HYXI EMS telemetry probe returned no data for %s", "106XXXXXXXX016"
    )
    # Ensure entry was not updated with metrics
    assert not entry["metrics"]


@pytest.mark.asyncio
async def test_fetch_ems_basic_data_error(caplog):
    """Test that _fetch_ems_basic_data propagates errors from query_ems_basic_details."""
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Mock query_ems_basic_details to raise an Exception
    api.query_ems_basic_details = AsyncMock(
        side_effect=Exception("EMS data fetch failed")
    )

    entry = {"metrics": {}, "device_type_code": "EMS"}

    with pytest.raises(Exception, match="EMS data fetch failed"):
        await api._fetch_ems_basic_data("10602251600016", entry)


@pytest.mark.asyncio
async def test_query_ems_basic_details_error(caplog):
    """Test that query_ems_basic_details handles exceptions gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Inject mock directly into the module resolving all patch issues
    import hyxi_cloud_api.api as api_mod  # pylint: disable=import-outside-toplevel

    mock_logger = MagicMock()
    api_mod._LOGGER = mock_logger

    # Mock _request to raise an Exception to cover the error path in query_ems_basic_details
    api._request = AsyncMock(side_effect=Exception("EMS query failed"))

    result = await api.query_ems_basic_details("10602251600016")

    assert result == {}

    # Verify the mock logger was called instead of using caplog directly (like other tests here)
    mock_logger.error.assert_called_with(
        "HYXI EMS Basic Data Request Failed for %s: %s",
        "106XXXXXXXX016",
        api._request.side_effect,
    )
