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

"""Tests for exception handling in ensure_token."""

import logging
from unittest.mock import AsyncMock

import pytest

import hyxi_cloud_api.api as api_mod
from hyxi_cloud_api.api import (
    HyxiApiClient,
    HyxiAuthError,
    TokenNetworkError,
    TokenRequestError,
)


@pytest.mark.asyncio
async def test_ensure_token_exception_handling(caplog, monkeypatch):
    """A transport-layer exception from _request is logged and re-raised as
    TokenNetworkError, chained to the original error."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Force _LOGGER to use the standard root logger so caplog captures it.
    # monkeypatch restores the original _LOGGER after this test, so the
    # reassignment can't leak into tests that run afterward.
    monkeypatch.setattr(api_mod, "_LOGGER", logging.getLogger("hyxi_cloud_api.api"))

    error = mock_aiohttp.ClientError("Connection reset")
    api._request = AsyncMock(side_effect=error)

    with pytest.raises(TokenNetworkError) as exc_info:
        await api.ensure_token()

    assert exc_info.value.__cause__ is error
    assert (
        "HYXI Token Request Failed (network/connection error): Connection reset"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_ensure_token_success(caplog, monkeypatch):
    """A successful token response is applied as the client's token,
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

    await api.ensure_token()

    assert api.token == "Bearer abc123"
    assert "HYXI token refresh succeeded" in caplog.text


@pytest.mark.asyncio
async def test_ensure_token_success_response_without_token(caplog, monkeypatch):
    """The API can report overall success while the payload itself lacks a
    token/access_token (a malformed-but-200 response). ensure_token must
    raise TokenRequestError without logging a spurious 'refresh succeeded'
    message."""
    caplog.set_level(logging.DEBUG)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    monkeypatch.setattr(api_mod, "_LOGGER", logging.getLogger("hyxi_cloud_api.api"))

    api._request = AsyncMock(return_value=(200, {"success": True, "data": {}}))

    with pytest.raises(TokenRequestError, match="missing token"):
        await api.ensure_token()

    assert api.token is None
    assert "HYXI token refresh succeeded" not in caplog.text


@pytest.mark.asyncio
async def test_ensure_token_unexpected_exception_propagates():
    """A non-transport exception (e.g. a bug, a malformed response tripping
    up response parsing) is NOT swallowed as a network error -- it should
    surface as the real error it is, not get silently relabeled as "the
    network is flaky" forever."""
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    api._request = AsyncMock(side_effect=ValueError("unexpected parsing bug"))

    with pytest.raises(ValueError, match="unexpected parsing bug"):
        await api.ensure_token()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "side_effect, expected",
    [
        (None, True),
        (HyxiAuthError("rejected"), "auth_failed"),
        (TokenNetworkError("network or connection error"), None),
        (TokenRequestError("token request rejected, code 500"), False),
    ],
)
async def test_refresh_token_keeps_status_return_values(side_effect, expected):
    """_refresh_token maps ensure_token's outcome onto its original return
    values, which ha-hyxi-cloud's config flow branches on."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api.ensure_token = AsyncMock(side_effect=side_effect)

    assert await api._refresh_token() == expected
