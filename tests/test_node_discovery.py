"""Tests for HyxiApiClient.resolve_base_url() — regional node discovery."""

import sys
from unittest.mock import AsyncMock, MagicMock

if "aiohttp" not in sys.modules or not hasattr(sys.modules["aiohttp"], "ClientError"):
    m = MagicMock()

    class _MockExp(Exception):
        def __init__(self, *args, **kwargs):
            super().__init__(*args)
            for k, v in kwargs.items():
                setattr(self, k, v)

    m.ClientError = _MockExp
    m.ClientResponseError = type("ClientResponseError", (_MockExp,), {})
    m.ContentTypeError = type("ContentTypeError", (_MockExp,), {})
    sys.modules["aiohttp"] = m

import aiohttp
import pytest

from src.hyxi_cloud_api.api import HyxiApiClient


def _make_mock_response(json_payload, status=200, raise_on_status=None):
    """Build a mock aiohttp async context manager response."""
    resp = MagicMock()
    inner = resp.__aenter__.return_value
    inner.status = status
    inner.json = AsyncMock(return_value=json_payload)
    if raise_on_status:
        inner.raise_for_status = MagicMock(side_effect=raise_on_status)
    else:
        inner.raise_for_status = MagicMock()
    return resp


def _make_session(response):
    """Build a mock session whose .post() returns the given response."""
    session = MagicMock()
    session.post = MagicMock(return_value=response)
    return session


# ── Happy paths ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_base_url_api_url_key():
    """Returns URL from the 'apiUrl' key in the data dict."""
    payload = {"data": {"apiUrl": "https://or.hyxicloud.com"}}
    session = _make_session(_make_mock_response(payload))

    result = await HyxiApiClient.resolve_base_url("AU", session)

    assert result == "https://or.hyxicloud.com"
    session.post.assert_called_once()
    call_kwargs = session.post.call_args
    # Must POST to the switch URL with the uppercased country code
    assert call_kwargs[0][0] == HyxiApiClient.SWITCH_URL
    assert call_kwargs[1]["json"] == {"countryCode": "AU"}


@pytest.mark.asyncio
async def test_resolve_base_url_base_url_key():
    """Falls back to 'baseUrl' when 'apiUrl' is absent."""
    payload = {"data": {"baseUrl": "https://fra.hyxicloud.com"}}
    session = _make_session(_make_mock_response(payload))

    result = await HyxiApiClient.resolve_base_url("DE", session)

    assert result == "https://fra.hyxicloud.com"


@pytest.mark.asyncio
async def test_resolve_base_url_strips_trailing_slash():
    """Trailing slashes are stripped from the returned URL."""
    payload = {"data": {"apiUrl": "https://or.hyxicloud.com/"}}
    session = _make_session(_make_mock_response(payload))

    result = await HyxiApiClient.resolve_base_url("us", session)

    assert result == "https://or.hyxicloud.com"


@pytest.mark.asyncio
async def test_resolve_base_url_lowercases_country_code_uppercased():
    """Country code is uppercased in the request body regardless of input case."""
    payload = {"data": {"apiUrl": "https://cn.hyxicloud.com"}}
    session = _make_session(_make_mock_response(payload))

    await HyxiApiClient.resolve_base_url("cn", session)

    assert session.post.call_args[1]["json"] == {"countryCode": "CN"}


@pytest.mark.asyncio
async def test_resolve_base_url_data_is_direct_string():
    """Handles the case where 'data' is a plain URL string (older API version)."""
    payload = {"data": "https://or.hyxicloud.com"}
    session = _make_session(_make_mock_response(payload))

    result = await HyxiApiClient.resolve_base_url("AU", session)

    assert result == "https://or.hyxicloud.com"


# ── Graceful failure paths ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_base_url_returns_none_on_missing_url(caplog):
    """Returns None when response contains no usable URL key."""
    payload = {"data": {"someOtherKey": "not a url"}}
    session = _make_session(_make_mock_response(payload))

    result = await HyxiApiClient.resolve_base_url("AU", session)

    assert result is None
    assert "no usable URL" in caplog.text


@pytest.mark.asyncio
async def test_resolve_base_url_returns_none_on_network_error(caplog):
    """Returns None (not raises) on network failure."""
    session = MagicMock()
    session.post = MagicMock(side_effect=aiohttp.ClientError("Connection refused"))

    result = await HyxiApiClient.resolve_base_url("AU", session)

    assert result is None
    assert "node resolution failed" in caplog.text


@pytest.mark.asyncio
async def test_resolve_base_url_returns_none_on_http_error(caplog):
    """Returns None (not raises) on non-2xx HTTP response."""
    resp = _make_mock_response(
        {},
        status=503,
        raise_on_status=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=503
        ),
    )
    session = _make_session(resp)

    result = await HyxiApiClient.resolve_base_url("AU", session)

    assert result is None
    assert "node resolution failed" in caplog.text


@pytest.mark.asyncio
async def test_resolve_base_url_returns_none_on_empty_data(caplog):
    """Returns None when 'data' is None or empty."""
    payload = {"data": None}
    session = _make_session(_make_mock_response(payload))

    result = await HyxiApiClient.resolve_base_url("AU", session)

    assert result is None


# ── Class constants ───────────────────────────────────────────────────────────


def test_switch_url_constant():
    """SWITCH_URL and DEFAULT_BASE_URL are defined on the class."""
    assert (
        HyxiApiClient.SWITCH_URL
        == "https://switch.hyxicloud.com/switchApi/fe/clientActive"
    )
    assert HyxiApiClient.DEFAULT_BASE_URL == "https://open.hyxicloud.com"
