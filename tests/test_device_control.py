"""Tests for the Device Control API methods."""

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

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.hyxi_cloud_api.api import HyxiApiClient


@pytest.mark.asyncio
async def test_set_mode_idle():
    """Test set_mode_idle sends controlId 1062."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    result = await api.set_mode_idle("SN123")

    assert result["success"] is True
    api._request.assert_called_once()
    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["1062"] == ""


@pytest.mark.asyncio
async def test_set_mode_charge():
    """Test set_mode_charge sends controlId 1063 with wattage."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    result = await api.set_mode_charge("SN123", watts=3000)

    assert result["success"] is True
    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["1063"] == "3000"


@pytest.mark.asyncio
async def test_set_mode_discharge():
    """Test set_mode_discharge sends controlId 1064 with wattage."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    result = await api.set_mode_discharge("SN123", watts=2500)

    assert result["success"] is True
    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["1064"] == "2500"


@pytest.mark.asyncio
async def test_set_mode_self_consume():
    """Test set_mode_self_consume sends controlId 1065."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    result = await api.set_mode_self_consume("SN123")

    assert result["success"] is True
    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["1065"] == ""


@pytest.mark.asyncio
async def test_set_peak_shaving():
    """Test set_peak_shaving sends controlId 1021 with mapped value."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    await api.set_peak_shaving("SN123", action="charge")

    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["1021"] == "1"


@pytest.mark.asyncio
async def test_set_peak_shaving_invalid_action():
    """Test set_peak_shaving raises ValueError for invalid action."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)

    with pytest.raises(ValueError, match="Invalid peak shaving action"):
        await api.set_peak_shaving("SN123", action="invalid")


@pytest.mark.asyncio
async def test_set_frequency_control():
    """Test set_frequency_control sends controlId 1020."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    await api.set_frequency_control("SN123", enabled=True)

    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["1020"] == "1"

    api._request.reset_mock()
    await api.set_frequency_control("SN123", enabled=False)

    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["1020"] == "0"


@pytest.mark.asyncio
async def test_control_error_on_auth_failed():
    """Test ControlError is raised when authentication fails."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value="auth_failed")

    with pytest.raises(api.ControlError, match="Authentication failed"):
        await api.set_mode_idle("SN123")


@pytest.mark.asyncio
async def test_control_error_on_no_token():
    """Test ControlError is raised when token cannot be obtained."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=False)

    with pytest.raises(api.ControlError, match="Could not obtain API token"):
        await api.set_mode_idle("SN123")


@pytest.mark.asyncio
async def test_control_error_on_api_failure():
    """Test ControlError is raised when API returns success=False."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(
        return_value=(200, {"success": False, "code": "C000001", "msg": "Parameter error"})
    )

    with pytest.raises(api.ControlError, match="controlMap write failed"):
        await api.set_mode_charge("SN123", watts=3000)
