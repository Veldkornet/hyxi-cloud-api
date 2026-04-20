"""Tests for fetching the sub-device list for a parent SN."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.hyxi_cloud_api.api import HyxiApiClient


@pytest.mark.asyncio
async def test_fetch_sub_device_list_success():
    """Verify that the method correctly handles a successful response containing child devices."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._request = AsyncMock(
        return_value=(
            200,
            {
                "success": True,
                "data": {"childDevice": [{"deviceSn": "CHILD123"}]},
            },
        )
    )

    result = await api._fetch_sub_device_list("parent123")
    assert result == [{"deviceSn": "CHILD123"}]
    api._request.assert_awaited_once_with(
        "POST",
        "/api/device/v1/getSubDevicePage",
        json={"parentSn": "parent123", "pageSize": 50, "currentPage": 1},
    )


@pytest.mark.asyncio
async def test_fetch_sub_device_list_failure(caplog):
    """Verify that the method returns an empty list and logs an error on failure."""
    caplog.set_level(logging.ERROR)
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._request = AsyncMock(
        return_value=(
            200,
            {"success": False, "msg": "error"},
        )
    )

    result = await api._fetch_sub_device_list("parent123")
    assert result == []
    api._request.assert_awaited_once_with(
        "POST",
        "/api/device/v1/getSubDevicePage",
        json={"parentSn": "parent123", "pageSize": 50, "currentPage": 1},
    )
    assert "HYXI API Sub-Device Fetch Rejected for" in caplog.text
    api._request.assert_awaited_once_with(
        "POST",
        "/api/device/v1/getSubDevicePage",
        json={"parentSn": "parent123", "pageSize": 50, "currentPage": 1},
    )


@pytest.mark.asyncio
async def test_fetch_sub_device_list_data_not_dict():
    """Verify that the method returns an empty list when data is not a dict."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._request = AsyncMock(
        return_value=(
            200,
            {"success": True, "data": [{"deviceSn": "CHILD123"}]},
        )
    )

    result = await api._fetch_sub_device_list("parent123")
    assert result == []
    api._request.assert_awaited_once_with(
        "POST",
        "/api/device/v1/getSubDevicePage",
        json={"parentSn": "parent123", "pageSize": 50, "currentPage": 1},
    )


@pytest.mark.asyncio
async def test_fetch_sub_device_list_missing_child_device():
    """Verify that the method returns an empty list when childDevice is missing."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._request = AsyncMock(
        return_value=(
            200,
            {"success": True, "data": {"otherKey": "value"}},
        )
    )

    result = await api._fetch_sub_device_list("parent123")
    assert result == []
