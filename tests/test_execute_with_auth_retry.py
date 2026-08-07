"""Tests for _execute_with_auth_retry's re-authentication retry logic."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from hyxi_cloud_api.api import HyxiApiClient, TokenRejectedError


class DummyError(Exception):
    """A dummy exception class for testing."""


@pytest.fixture
def api_client():
    """Fixture for HyxiApiClient."""
    session = MagicMock()
    return HyxiApiClient("access_key", "secret_key", "https://api.example.com", session)


@pytest.mark.asyncio
async def test_execute_with_auth_retry_retries_after_token_rejection(
    api_client, caplog
):
    """A TokenRejectedError raised mid-request triggers exactly one forced
    re-authentication and one retry of the original request, and the retried
    response is returned as if nothing happened."""
    caplog.set_level(logging.DEBUG)
    api_client._ensure_authenticated = AsyncMock()
    api_client._request = AsyncMock(
        side_effect=[
            TokenRejectedError("Server rejected token"),
            (200, {"success": True, "data": {"ok": True}}),
        ]
    )

    result = await api_client._execute_with_auth_retry(
        "POST", "/api/some/path", DummyError, json={"a": 1}
    )

    assert result == {"success": True, "data": {"ok": True}}
    assert api_client._request.await_count == 2
    assert api_client._ensure_authenticated.await_count == 2
    assert (
        "Token rejected, forcing re-authentication and retrying request to "
        "/api/some/path" in caplog.text
    )


@pytest.mark.asyncio
async def test_execute_with_auth_retry_second_rejection_propagates(api_client):
    """If the retried request is ALSO rejected, the TokenRejectedError from the
    retry is not caught a second time -- it propagates to the caller instead
    of retrying forever."""
    api_client._ensure_authenticated = AsyncMock()
    api_client._request = AsyncMock(side_effect=TokenRejectedError("still rejected"))

    with pytest.raises(TokenRejectedError, match="still rejected"):
        await api_client._execute_with_auth_retry(
            "POST", "/api/some/path", DummyError, json={}
        )

    assert api_client._request.await_count == 2
