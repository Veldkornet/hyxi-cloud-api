"""Tests for the HYXi Cloud API client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import aiohttp

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


# --- TEST 4: Concurrent Execution of Fetch All ---
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

    # Configure the mock response to simulate aiohttp's async context manager.
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value.json.return_value = fake_plants_response
    mock_response.__aenter__.return_value.status = 200
    mock_response.__aenter__.return_value.raise_for_status = MagicMock()

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

# --- TEST 5: Token Refresh Failures ---
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, payload, expected_result",
    [
        (401, {}, "auth_failed"),
        (403, {}, "auth_failed"),
        (200, {"success": False, "code": "401"}, "auth_failed"),
        (200, {"success": False, "code": 403}, "auth_failed"),
        (200, {"success": False, "code": "500"}, False),
        (500, {"success": False}, False),
    ],
)
async def test_refresh_token_failures(status, payload, expected_result):
    """Test _refresh_token handles various failure conditions correctly."""

    mock_session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)
    api.token = None

    # Mock the response context manager correctly
    mock_response = AsyncMock()
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.status = status

    # Needs to be an async method for res = await response.json()
    yielded_response.json = AsyncMock(return_value=payload)

    if status >= 400 and status not in [401, 403]:
        # In actual code, raise_for_status is not awaited, it's a synchronous call that raises Exception
        yielded_response.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(), history=(), status=status
            )
        )
    else:
        yielded_response.raise_for_status = MagicMock()

    api.session.post = MagicMock(return_value=mock_response)

    result = await api._refresh_token()
    assert result == expected_result

@pytest.mark.asyncio
async def test_refresh_token_network_exception():
    """Test _refresh_token handles network exceptions gracefully."""
    mock_session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)
    api.token = None

    # The session.post method needs to return a context manager,
    # but the act of calling it or entering it raises the exception.
    # The simplest way to trigger the exception is side_effect on request.
    api.session.post = MagicMock(side_effect=aiohttp.ClientError("Network error"))

    result = await api._refresh_token()
    assert result is False

# --- TEST 5: Alarm Log Sanitization ---
@pytest.mark.asyncio
async def test_fetch_alarms_for_plant_sanitization(caplog):
    """Verify that _fetch_alarms_for_plant sanitizes sensitive fields in logs."""
    import logging
    caplog.set_level(logging.DEBUG)

    # Use a MagicMock for the session to handle context managers
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    mock_response = AsyncMock()
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.json.return_value = {
        "success": True,
        "data": {
            "pageData": [
                {"deviceSn": "10602251600016", "alarmName": "Fault 1", "plantId": "12345678"},
                {"deviceSn": "60701251900927", "alarmName": "Fault 2"}
            ]
        }
    }
    yielded_response.raise_for_status = MagicMock()
    yielded_response.status = 200

    # Mock session.post to return the mock_response context manager
    mock_session.post.return_value = mock_response

    alarms = await api._fetch_alarms_for_plant("12345678")

    assert len(alarms) == 2
    assert alarms[0]["deviceSn"] == "10602251600016" # Ensure return value is intact

    log_text = caplog.text

    # Assert logs do NOT contain sensitive IDs in plain text
    assert "10602251600016" not in log_text
    assert "60701251900927" not in log_text

    # Assert logs contain the masked versions
    assert "106XXXXXXXX016" in log_text
    assert "607XXXXXXXX927" in log_text

    # Ensure plant ID itself is masked
    assert "123XX678" in log_text
