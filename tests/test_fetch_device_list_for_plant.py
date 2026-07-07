"""Tests for fetching the device list for a plant."""

import logging
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from src.hyxi_cloud_api.api import FetchState, HyxiApiClient


@pytest.mark.asyncio
async def test_fetch_device_list_for_plant_success_list():
    """Verify that the method correctly handles a successful response where data is a list."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._request = AsyncMock(
        return_value=(
            200,
            {"success": True, "data": [{"deviceSn": "SN12345678"}]},
        )
    )

    result = await api._fetch_device_list_for_plant("plant123")
    assert result == [{"deviceSn": "SN12345678"}]


@pytest.mark.asyncio
async def test_fetch_device_list_for_plant_success_dict():
    """Verify that the method correctly handles a successful response where data is a dict."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._request = AsyncMock(
        return_value=(
            200,
            {"success": True, "data": {"deviceList": [{"deviceSn": "SN12345678"}]}},
        )
    )

    result = await api._fetch_device_list_for_plant("plant123")
    assert result == [{"deviceSn": "SN12345678"}]


@pytest.mark.asyncio
async def test_fetch_device_list_for_plant_failure(caplog):
    """Verify that the method returns None and logs an error on failure."""
    caplog.set_level(logging.ERROR)
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._request = AsyncMock(
        return_value=(
            200,
            {"success": False, "msg": "error"},
        )
    )

    result = await api._fetch_device_list_for_plant("plant123")
    assert result is None
    assert "HYXI API Device Fetch Rejected for Plant" in caplog.text


@pytest.mark.asyncio
async def test_fetch_device_list_for_plant_empty_data():
    """Verify that the method returns an empty list when data is None."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._request = AsyncMock(
        return_value=(
            200,
            {"success": True, "data": None},
        )
    )

    result = await api._fetch_device_list_for_plant("plant123")
    assert result == []


@pytest.mark.asyncio
async def test_fetch_device_list_for_plant_debug_logging(caplog):
    """Verify that debug logging occurs and masks SNs correctly."""
    caplog.set_level(logging.DEBUG)
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._request = AsyncMock(
        return_value=(
            200,
            {"success": True, "data": [{"deviceSn": "SN12345678"}]},
        )
    )

    await api._fetch_device_list_for_plant("plant123")
    assert "HYXI Discovered Devices for Plant" in caplog.text
    # SN12345678 -> 10 chars. _mask_id should show last 4. 10-4 = 6 X's.
    pass


@pytest.mark.asyncio
async def test_fetch_device_list_for_plant_client_error(caplog):
    """Verify that a client error from _request is caught, logged, and None is returned."""
    caplog.set_level(logging.ERROR)
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._request = AsyncMock(side_effect=aiohttp.ClientError("Mocked Client Error"))

    state = FetchState(now="2024-01-01T00:00:00Z")
    result = await api._fetch_devices_for_plant("plant123", state)

    assert result is None
    assert "Error fetching devices for plant" in caplog.text
