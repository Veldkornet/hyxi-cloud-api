"""Tests for the HYXI subscription API methods."""

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

if "aiohttp" not in sys.modules or not hasattr(sys.modules["aiohttp"], "ClientError"):
    m = MagicMock()
    m.ClientError = Exception
    m.ClientResponseError = type("ClientResponseError", (Exception,), {})
    m.ContentTypeError = type("ContentTypeError", (Exception,), {})
    sys.modules["aiohttp"] = m

from src.hyxi_cloud_api.api import HyxiApiClient


def _client() -> HyxiApiClient:
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(
        return_value=(
            200,
            {
                "code": "0",
                "msg": "Success",
                "data": {"subscribeCode": "sub-code"},
                "success": True,
            },
        )
    )
    return api


@pytest.mark.asyncio
async def test_subscribe_real_time_data():
    """Test real-time data subscription payload."""
    api = _client()

    result = await api.subscribe_real_time_data(
        "https://example.com/hyxi",
        ["SN1", "SN2"],
        60000,
        data_code_list=["pv1p"],
    )

    assert result["data"]["subscribeCode"] == "sub-code"
    api._request.assert_called_once()
    call_args = api._request.call_args
    assert call_args.args[:2] == ("POST", "/api/subscribe/v1/realTimeData")
    body = call_args.kwargs["json"]
    assert body == {
        "callBackUrl": "https://example.com/hyxi",
        "deviceSnList": ["SN1", "SN2"],
        "postRate": 60000,
        "dataCodeList": ["pv1p"],
    }


@pytest.mark.asyncio
async def test_subscribe_alarm():
    """Test alarm subscription payload."""
    api = _client()

    await api.subscribe_alarm(
        "https://example.com/hyxi",
        ["SN1"],
        5000,
        alarm_code_list=["704"],
    )

    call_args = api._request.call_args
    assert call_args.args[:2] == ("POST", "/api/subscribe/v1/alarm")
    body = call_args.kwargs["json"]
    assert body == {
        "callBackUrl": "https://example.com/hyxi",
        "deviceSnList": ["SN1"],
        "postRate": 5000,
        "alarmCodeList": ["704"],
    }


@pytest.mark.asyncio
async def test_subscribe_fm_real_time_data():
    """Test FCAS real-time data subscription payload."""
    api = _client()

    await api.subscribe_fm_real_time_data("https://example.com/hyxi", ["SN1"], 1)

    call_args = api._request.call_args
    assert call_args.args[:2] == ("POST", "/api/subscribe/v1/FMRealTimeData")
    body = call_args.kwargs["json"]
    assert body == {
        "callBackUrl": "https://example.com/hyxi",
        "deviceSnList": ["SN1"],
        "postRate": 1,
    }


@pytest.mark.asyncio
async def test_cancel_subscription():
    """Test subscription cancellation payload."""
    api = _client()

    await api.cancel_subscription(" sub-code ")

    call_args = api._request.call_args
    assert call_args.args[:2] == ("POST", "/api/subscribe/v1/cancel")
    assert call_args.kwargs["json"] == {"subscribeCode": "sub-code"}


@pytest.mark.asyncio
async def test_subscription_error_on_auth_failed():
    """Test SubscriptionError is raised when authentication fails."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value="auth_failed")

    with pytest.raises(api.SubscriptionError, match="Authentication failed"):
        await api.subscribe_alarm("https://example.com/hyxi", ["SN1"], 60000)


@pytest.mark.asyncio
async def test_subscription_error_on_api_failure():
    """Test SubscriptionError is raised when API returns success=False."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(
        return_value=(
            200,
            {"success": False, "code": "C000001", "msg": "Parameter error"},
        )
    )

    with pytest.raises(api.SubscriptionError, match="subscription request failed"):
        await api.subscribe_real_time_data("https://example.com/hyxi", ["SN1"], 60000)


@pytest.mark.asyncio
async def test_subscription_validation():
    """Test subscription input validation."""
    api = _client()

    with pytest.raises(ValueError, match="callback_url must be a non-empty string"):
        await api.subscribe_alarm("", ["SN1"], 60000)

    with pytest.raises(ValueError, match="at least one device SN"):
        await api.subscribe_alarm("https://example.com/hyxi", [], 60000)

    with pytest.raises(ValueError, match="more than 1000"):
        await api.subscribe_alarm(
            "https://example.com/hyxi",
            [f"SN{i}" for i in range(1001)],
            60000,
        )

    with pytest.raises(ValueError, match="between 5000 and 3600000 milliseconds"):
        await api.subscribe_real_time_data("https://example.com/hyxi", ["SN1"], 4999)

    with pytest.raises(ValueError, match="between 1 and 6 hours"):
        await api.subscribe_fm_real_time_data("https://example.com/hyxi", ["SN1"], 7)

    with pytest.raises(ValueError, match="subscribe_code must be a non-empty string"):
        await api.cancel_subscription(" ")


@pytest.mark.asyncio
async def test_post_subscription_success_direct():
    """Test _post_subscription success path."""
    api = _client()
    api._request = AsyncMock(
        return_value=(200, {"success": True, "code": "0", "data": "test"})
    )
    res = await api._post_subscription("/test/path", {"key": "value"})
    assert res == {"success": True, "code": "0", "data": "test"}
    api._request.assert_called_once_with("POST", "/test/path", json={"key": "value"})


@pytest.mark.asyncio
async def test_post_subscription_none_response():
    """Test _post_subscription when response is None."""
    api = _client()
    api._request = AsyncMock(return_value=(200, None))
    with pytest.raises(api.SubscriptionError, match=r"code=no_response"):
        await api._post_subscription("/test/path", {"key": "value"})


@pytest.mark.asyncio
async def test_post_subscription_success_false():
    """Test _post_subscription when response has success=False."""
    api = _client()
    api._request = AsyncMock(
        return_value=(200, {"success": False, "code": "400", "msg": "Bad Request"})
    )
    with pytest.raises(api.SubscriptionError, match=r"code=400.*Bad Request"):
        await api._post_subscription("/test/path", {"key": "value"})
