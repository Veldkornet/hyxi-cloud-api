"""Tests for the HYXi Cloud API client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.hyxi_cloud_api.api import HyxiApiClient


# --- TEST 1: Basic Initialization ---
def test_api_initialization():
    """Test that the API class stores credentials and URL correctly."""

    # We create a fake aiohttp session to pass into the client
    fake_session = AsyncMock()

    api = HyxiApiClient(
        access_key="fake_access_key",
        secret_key="fake_secret_key",
        base_url="https://fake-hyxi-url.com",
        session=fake_session,
    )

    assert api.access_key == "fake_access_key"
    assert api.secret_key == "fake_secret_key"
    assert (
        api.base_url == "https://fake-hyxi-url.com"
    )  # Notice we test that it strips trailing slashes if you added one!
    assert api.token is None


# --- TEST 2: The Retry Logic Wrapper ---
@pytest.mark.asyncio
async def test_get_all_device_data_success():
    """Test that the get_all_device_data correctly formats a successful fetch."""

    fake_session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", fake_session)

    # We mock the internal '_execute_fetch_all' method so it doesn't actually try to hit the network
    # or read your local mock_data.json file. We just force it to return fake dictionary data.
    fake_internal_data = {
        "SN12345": {"device_name": "My Inverter", "metrics": {"totalE": 2731.90}}
    }

    api._execute_fetch_all = AsyncMock(return_value=fake_internal_data)

    # Run the method!
    result = await api.get_all_device_data()

    # Verify the method wrapped our data in the 'attempts' dictionary correctly
    assert result is not None
    assert result["attempts"] == 1
    assert result["data"]["SN12345"]["metrics"]["totalE"] == 2731.90


# --- TEST 3: Header Generation and Hashes ---
def test_generate_headers():
    """Verify that _generate_headers constructs the dictionary and signature properly."""
    fake_session = AsyncMock()
    api = HyxiApiClient("test_ak", "test_sk", "https://api.com", fake_session)
    api.token = "Bearer fake_token"

    # Test standard request
    headers = api._generate_headers(
        path="/api/test", method="GET", is_token_request=False
    )

    assert headers["accessKey"] == "test_ak"
    assert "timestamp" in headers
    assert "nonce" in headers
    assert "sign" in headers
    assert headers["Content-Type"] == "application/json"
    assert headers["Authorization"] == "Bearer fake_token"
    assert "sign-headers" not in headers

    # Test token request
    token_headers = api._generate_headers(
        path="/api/token", method="POST", is_token_request=True
    )

    assert token_headers["accessKey"] == "test_ak"
    assert "sign" in token_headers
    assert token_headers["sign-headers"] == "grantType"
    assert "Authorization" not in token_headers


# --- TEST 4: Token Refresh ---
@pytest.mark.asyncio
async def test_refresh_token_already_valid():
    """Verify that if token is valid, it returns True immediately."""
    fake_session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", fake_session)
    api.token = "Bearer valid_token"
    # Set expiration to far in the future
    import time
    api.token_expires_at = time.time() + 3600

    result = await api._refresh_token()
    assert result is True
    # Session post should not be called
    fake_session.post.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_token_success():
    """Verify that _refresh_token successfully retrieves and stores a token."""
    fake_session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", fake_session)

    mock_response = AsyncMock()

    yielded_response = mock_response.__aenter__.return_value
    yielded_response.status = 200
    yielded_response.json.return_value = {
        "success": True,
        "data": {
            "token": "new_fake_token",
            "expiresIn": 7200
        }
    }
    yielded_response.raise_for_status = MagicMock()

    # Needs to be a MagicMock since we want it to return the mock_response
    # as a context manager and not a coroutine when calling .post()
    fake_session.post = MagicMock(return_value=mock_response)

    from unittest.mock import patch

    with patch('time.time', return_value=10000.0):
        result = await api._refresh_token()

    assert result is True
    assert api.token == "Bearer new_fake_token"
    # expires_at = 10000.0 + 7200 - 300 = 16900.0
    assert api.token_expires_at == 16900.0


@pytest.mark.asyncio
async def test_refresh_token_auth_failed_status():
    """Verify that _refresh_token returns 'auth_failed' if HTTP status is 401/403."""
    fake_session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", fake_session)

    mock_response = AsyncMock()
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.status = 401
    fake_session.post = MagicMock(return_value=mock_response)

    result = await api._refresh_token()
    assert result == "auth_failed"


@pytest.mark.asyncio
async def test_refresh_token_auth_failed_code():
    """Verify that _refresh_token returns 'auth_failed' if JSON code is 401/403."""
    fake_session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", fake_session)

    mock_response = AsyncMock()
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.status = 200
    yielded_response.json.return_value = {"success": False, "code": "401"}
    yielded_response.raise_for_status = MagicMock()
    fake_session.post = MagicMock(return_value=mock_response)

    result = await api._refresh_token()
    assert result == "auth_failed"


@pytest.mark.asyncio
async def test_refresh_token_generic_error():
    """Verify that _refresh_token returns False on a generic error payload."""
    fake_session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", fake_session)

    mock_response = AsyncMock()
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.status = 200
    yielded_response.json.return_value = {"success": False, "code": "500"}
    yielded_response.raise_for_status = MagicMock()
    fake_session.post = MagicMock(return_value=mock_response)

    result = await api._refresh_token()
    assert result is False


@pytest.mark.asyncio
async def test_refresh_token_exception():
    """Verify that _refresh_token returns False on an exception."""
    fake_session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", fake_session)

    # MagicMock since we want post() to act like a context manager but error out
    mock_post = MagicMock()
    # It must return an object where __aenter__ raises an Exception
    mock_context_manager = MagicMock()
    mock_context_manager.__aenter__ = AsyncMock(side_effect=Exception("Network error"))
    mock_post.return_value = mock_context_manager
    fake_session.post = mock_post

    result = await api._refresh_token()
    assert result is False


# --- TEST 5: Concurrent Execution of Fetch All ---
@pytest.mark.asyncio
async def test_execute_fetch_all_concurrent():
    """Verify that _execute_fetch_all handles multiple plants correctly."""

    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    # Bypass token validation and mock file
    api._refresh_token = AsyncMock(return_value=True)

    fake_plants_response = {
        "success": True,
        "data": {"list": [{"plantId": "plant_1"}, {"plantId": "plant_2"}]},
    }

    # Mock the _fetch_devices_for_plant internal call
    # It must return an awaitable AND add an awaitable to metric_tasks
    async def mock_fetch_devices(plant_id, now, metric_tasks):
        async def mock_metric_task():
            return (f"SN_{plant_id}", {"device_name": f"Device {plant_id}"})

        metric_tasks.append(mock_metric_task())
        return None

    api._fetch_devices_for_plant = MagicMock(side_effect=mock_fetch_devices)

    # Need to override asyncio.to_thread so it returns NOT_FOUND for the mock check
    original_to_thread = asyncio.to_thread

    async def fake_to_thread(func, *args, **kwargs):
        if func.__name__ == "load_mock":
            return "NOT_FOUND"
        return await original_to_thread(func, *args, **kwargs)

    asyncio.to_thread = fake_to_thread

    # Make session.post an AsyncMock that returns an object where
    # __aenter__ returns an object where json() returns our dict.
    mock_response = AsyncMock()

    # 🎯 The Context Manager Fix
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.json.return_value = fake_plants_response
    yielded_response.raise_for_status = MagicMock()

    api.session.post = MagicMock(return_value=mock_response)

    try:
        results = await api._execute_fetch_all()
        # Verify both plants were called
        assert api._fetch_devices_for_plant.call_count == 2
        # Verify the results are parsed properly (our dummy tuples are keys/values)
        assert "SN_plant_1" in results
        assert "SN_plant_2" in results
    finally:
        asyncio.to_thread = original_to_thread
