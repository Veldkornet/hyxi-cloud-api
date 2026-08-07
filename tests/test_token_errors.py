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

"""Tests for exception handling in _refresh_token."""

import logging
from unittest.mock import AsyncMock

import pytest

import hyxi_cloud_api.api as api_mod
from hyxi_cloud_api.api import HyxiApiClient


@pytest.mark.asyncio
async def test_refresh_token_exception_handling(caplog, monkeypatch):
    """A transport-layer exception from _request is caught and reported as
    a network failure (falsy, distinguishable via `is None`)."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Force _LOGGER to use the standard root logger so caplog captures it.
    # monkeypatch restores the original _LOGGER after this test, so the
    # reassignment can't leak into tests that run afterward.
    monkeypatch.setattr(api_mod, "_LOGGER", logging.getLogger("hyxi_cloud_api.api"))

    error = mock_aiohttp.ClientError("Connection reset")
    api._request = AsyncMock(side_effect=error)

    result = await api._refresh_token()

    assert result is None
    assert (
        "HYXI Token Request Failed (network/connection error): Connection reset"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_refresh_token_success(caplog, monkeypatch):
    """A successful token response is applied and the refresh reports success,
    logging that the refresh succeeded (the happy path every failure test in
    this file is implicitly contrasted against)."""
    caplog.set_level(logging.DEBUG)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Force _LOGGER to use the standard root logger so caplog captures it.
    monkeypatch.setattr(api_mod, "_LOGGER", logging.getLogger("hyxi_cloud_api.api"))

    api._request = AsyncMock(
        return_value=(
            200,
            {"success": True, "data": {"token": "abc123", "expiresIn": 3600}},
        )
    )

    result = await api._refresh_token()

    assert result is True
    assert api.token == "Bearer abc123"
    assert "HYXI token refresh succeeded" in caplog.text


@pytest.mark.asyncio
async def test_refresh_token_success_response_without_token(caplog, monkeypatch):
    """The API can report overall success while the payload itself lacks a
    token/access_token (a malformed-but-200 response). _apply_token_response
    returns False in that case, and _refresh_token must propagate that False
    without logging a spurious 'refresh succeeded' message."""
    caplog.set_level(logging.DEBUG)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    monkeypatch.setattr(api_mod, "_LOGGER", logging.getLogger("hyxi_cloud_api.api"))

    api._request = AsyncMock(return_value=(200, {"success": True, "data": {}}))

    result = await api._refresh_token()

    assert result is False
    assert api.token is None
    assert "HYXI token refresh succeeded" not in caplog.text


@pytest.mark.asyncio
async def test_refresh_token_unexpected_exception_propagates():
    """A non-transport exception (e.g. a bug, a malformed response tripping
    up response parsing) is NOT swallowed as a network error -- it should
    surface as the real error it is, not get silently relabeled as "the
    network is flaky" forever."""
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    api._request = AsyncMock(side_effect=ValueError("unexpected parsing bug"))

    with pytest.raises(ValueError, match="unexpected parsing bug"):
        await api._refresh_token()
