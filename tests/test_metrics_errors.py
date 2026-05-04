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

"""Tests for exception handling in _fetch_device_metrics."""

import logging
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from hyxi_cloud_api.api import HyxiApiClient


@pytest.mark.asyncio
async def test_fetch_device_metrics_request_error(caplog):
    """Test that _fetch_device_metrics handles errors from _request gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Mock _request to raise an Exception directly
    api._request = AsyncMock(side_effect=Exception("Mock client error"))

    entry = {"metrics": {}, "device_type_code": "INVERTER"}
    # Use a longer SN so it's not fully masked to ****
    await api._fetch_device_metrics("10602251600016", entry)

    assert "Error fetching metrics for fefbfd75: Mock client error" in caplog.text
    # Ensure it didn't crash and entry was not updated with metrics
    assert not entry["metrics"]


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

    assert "Error fetching metrics for fefbfd75: Connection reset" in caplog.text
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

    assert "Error fetching metrics for fefbfd75" in caplog.text
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

    assert "HYXI API metrics rejected for fefbfd75: Device not found" in caplog.text
    assert not entry["metrics"]


@pytest.mark.asyncio
async def test_fetch_ems_basic_data_no_data(caplog):
    """Test that _fetch_ems_basic_data handles empty response gracefully."""
    caplog.set_level(logging.DEBUG)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Mock query_ems_basic_details to return {} (no data — the actual return contract)
    api.query_ems_basic_details = AsyncMock(return_value={})

    entry = {"metrics": {}, "device_type_code": "EMS"}
    await api._fetch_ems_basic_data("10602251600016", entry)

    assert "HYXI EMS telemetry probe returned no data for fefbfd75" in caplog.text
    # Ensure entry was not updated with metrics
    assert not entry["metrics"]


@pytest.mark.asyncio
async def test_fetch_ems_basic_data_error(caplog):
    """Test that _fetch_ems_basic_data handles errors from query_ems_basic_details."""
    caplog.set_level(logging.DEBUG)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Mock _request to raise an Exception to ensure query_ems_basic_details returns {}
    api._request = AsyncMock(side_effect=Exception("EMS data fetch failed"))

    entry = {"metrics": {}, "device_type_code": "EMS"}
    await api._fetch_ems_basic_data("10602251600016", entry)

    # Assert entry['metrics'] is unchanged
    assert not entry["metrics"]

    # Assert the correct debug log was emitted from _fetch_ems_basic_data due to empty return
    assert "HYXI EMS telemetry probe returned no data for fefbfd75" in caplog.text


@pytest.mark.asyncio
async def test_query_ems_basic_details_error(caplog):
    """Test that query_ems_basic_details handles exceptions gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Mock _request to raise an Exception to cover the error path in query_ems_basic_details
    api._request = AsyncMock(side_effect=Exception("EMS query failed"))

    result = await api.query_ems_basic_details("10602251600016")

    assert result == {}

    assert (
        "HYXI EMS Basic Data Request Failed for fefbfd75: EMS query failed"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_query_ems_basic_details_network_error(caplog):
    """Test that query_ems_basic_details handles network errors gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Mock _request to raise a ClientError to cover the network error path
    api._request = AsyncMock(side_effect=aiohttp.ClientError("Connection reset"))

    result = await api.query_ems_basic_details("10602251600016")

    assert result == {}

    assert (
        "HYXI EMS Basic Data Request Failed for fefbfd75: Connection reset"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_query_ems_basic_details_non_zero_code(caplog):
    """Test that query_ems_basic_details logs and returns {} when the API returns a non-zero code.

    This covers devices not enrolled in EMS or where the API signals an
    application-level rejection (HTTP 200 but code != '0').
    """
    caplog.set_level(logging.DEBUG)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    api._request = AsyncMock(
        return_value=(200, {"code": "1001", "msg": "Device not enrolled"})
    )

    result = await api.query_ems_basic_details("10602251600016")

    assert result == {}
    assert "HYXI EMS query returned non-zero code for fefbfd75: 1001" in caplog.text

@pytest.mark.asyncio
async def test_query_ems_basic_details_malformed_response(caplog):
    """Test that query_ems_basic_details handles malformed responses (AttributeError)."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Mock _request to return (200, None) to trigger AttributeError in query_ems_basic_details
    api._request = AsyncMock(return_value=(200, None))

    result = await api.query_ems_basic_details("10602251600016")

    assert result == {}
    assert "HYXI EMS Basic Data Request Failed for fefbfd75" in caplog.text
    assert "object has no attribute 'get'" in caplog.text
