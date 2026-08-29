"""Tests for the `except TokenRejectedError: raise` guards scattered across the
fetch helpers.

Each of these helpers wraps its work in `except TokenRejectedError: raise`
followed by a catch-all `except Exception`. The guard exists so a token
rejection propagates up to the retry/re-auth logic in
`_execute_with_auth_retry` instead of being swallowed and merely logged like
every other error. Without a test, an accidental deletion of one of these
guards would fail silently: the method would keep working, just with the
rejection silently downgraded to a log line.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from hyxi_cloud_api.api import FetchState, HyxiApiClient, TokenRejectedError


@pytest.fixture
def api_client():
    """Fixture for HyxiApiClient."""
    session = MagicMock()
    return HyxiApiClient("access_key", "secret_key", "https://api.example.com", session)


@pytest.mark.asyncio
async def test_fetch_device_metrics_propagates_token_rejection(api_client):
    """_fetch_device_metrics must not swallow TokenRejectedError."""
    api_client._request = AsyncMock(side_effect=TokenRejectedError("rejected"))
    entry = {"metrics": {}, "device_type_code": "INVERTER"}

    with pytest.raises(TokenRejectedError):
        await api_client._fetch_device_metrics("10600000000001", entry)


@pytest.mark.asyncio
async def test_query_ems_basic_details_propagates_token_rejection(api_client):
    """query_ems_basic_details must not swallow TokenRejectedError."""
    api_client._request = AsyncMock(side_effect=TokenRejectedError("rejected"))

    with pytest.raises(TokenRejectedError):
        await api_client.query_ems_basic_details("10600000000001")


@pytest.mark.asyncio
async def test_fetch_device_info_propagates_token_rejection(api_client):
    """_fetch_device_info must not swallow TokenRejectedError."""
    api_client._request = AsyncMock(side_effect=TokenRejectedError("rejected"))
    entry = {"metrics": {}, "device_type_code": "INVERTER"}

    with pytest.raises(TokenRejectedError):
        await api_client._fetch_device_info("10600000000001", entry)


@pytest.mark.asyncio
async def test_fetch_devices_for_plant_propagates_token_rejection(api_client):
    """_fetch_devices_for_plant must not swallow TokenRejectedError."""
    api_client._fetch_device_list_for_plant = AsyncMock(
        side_effect=TokenRejectedError("rejected")
    )
    state = FetchState(now="2024-01-01")

    with pytest.raises(TokenRejectedError):
        await api_client._fetch_devices_for_plant("plant123", state)


@pytest.mark.asyncio
async def test_fetch_sub_device_list_propagates_token_rejection(api_client):
    """_fetch_sub_device_list must not swallow TokenRejectedError."""
    api_client._request = AsyncMock(side_effect=TokenRejectedError("rejected"))

    with pytest.raises(TokenRejectedError):
        await api_client._fetch_sub_device_list("parent123")


@pytest.mark.asyncio
async def test_fetch_sub_devices_propagates_token_rejection(api_client):
    """_fetch_sub_devices must not swallow TokenRejectedError."""
    api_client._fetch_sub_device_list = AsyncMock(
        side_effect=TokenRejectedError("rejected")
    )
    state = FetchState(now="2024-01-01")

    with pytest.raises(TokenRejectedError):
        await api_client._fetch_sub_devices("parent123", state)


@pytest.mark.asyncio
async def test_fetch_alarms_for_plant_propagates_token_rejection(api_client):
    """_fetch_alarms_for_plant must not swallow TokenRejectedError."""
    api_client._request = AsyncMock(side_effect=TokenRejectedError("rejected"))

    with pytest.raises(TokenRejectedError):
        await api_client._fetch_alarms_for_plant("plant123")
