"""Tests for _ensure_authenticated."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from hyxi_cloud_api.api import HyxiApiClient


class DummyError(Exception):
    """A dummy exception class for testing."""


@pytest.fixture
def api_client():
    """Fixture for HyxiApiClient."""
    session = MagicMock()
    return HyxiApiClient("access_key", "secret_key", "https://api.example.com", session)


@pytest.mark.asyncio
async def test_ensure_authenticated_success(api_client):
    """Test _ensure_authenticated succeeds without raising when token refresh is successful."""
    api_client._refresh_token = AsyncMock(return_value=True)
    await api_client._ensure_authenticated(DummyError)
    api_client._refresh_token.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_authenticated_auth_failed(api_client):
    """Test _ensure_authenticated raises error_cls with specific message on auth_failed."""
    api_client._refresh_token = AsyncMock(return_value="auth_failed")
    with pytest.raises(DummyError, match="Authentication failed"):
        await api_client._ensure_authenticated(DummyError)


@pytest.mark.asyncio
async def test_ensure_authenticated_no_token(api_client):
    """Test _ensure_authenticated raises error_cls when token cannot be obtained."""
    api_client._refresh_token = AsyncMock(return_value=False)
    with pytest.raises(DummyError, match="Could not obtain API token"):
        await api_client._ensure_authenticated(DummyError)

    api_client._refresh_token = AsyncMock(return_value=None)
    with pytest.raises(DummyError, match="Could not obtain API token"):
        await api_client._ensure_authenticated(DummyError)
