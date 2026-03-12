import pytest
import time
from unittest.mock import AsyncMock
from src.hyxi_cloud_api.api import HyxiApiClient


@pytest.mark.asyncio
async def test_refresh_token_success():
    session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "http://api.com", session)

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "success": True,
        "data": {"token": "fake_token", "expiresIn": 3600},
    }
    session.post.return_value.__aenter__.return_value = mock_response

    result = await api._refresh_token()
    assert result is True
    assert api.token == "Bearer fake_token"
    assert api.token_expires_at > time.time()


@pytest.mark.asyncio
async def test_refresh_token_401():
    session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "http://api.com", session)

    mock_response = AsyncMock()
    mock_response.status = 401
    session.post.return_value.__aenter__.return_value = mock_response

    result = await api._refresh_token()
    assert result == "auth_failed"


@pytest.mark.asyncio
async def test_refresh_token_api_failure_401():
    session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "http://api.com", session)

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "success": False,
        "code": "401",
        "message": "Unauthorized",
    }
    session.post.return_value.__aenter__.return_value = mock_response

    result = await api._refresh_token()
    assert result == "auth_failed"


@pytest.mark.asyncio
async def test_refresh_token_api_failure_generic():
    session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "http://api.com", session)

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "success": False,
        "code": "500",
        "message": "Server Error",
    }
    session.post.return_value.__aenter__.return_value = mock_response

    result = await api._refresh_token()
    assert result is False


@pytest.mark.asyncio
async def test_refresh_token_missing_token():
    session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "http://api.com", session)

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {"success": True, "data": {}}
    session.post.return_value.__aenter__.return_value = mock_response

    result = await api._refresh_token()
    assert result is False


@pytest.mark.asyncio
async def test_refresh_token_already_valid():
    session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "http://api.com", session)
    api.token = "Bearer existing"
    api.token_expires_at = time.time() + 1000

    result = await api._refresh_token()
    assert result is True
    assert session.post.call_count == 0
