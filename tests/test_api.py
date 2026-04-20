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

"""Tests for the HYXI Cloud API client."""

import logging
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from src.hyxi_cloud_api.api import HyxiApiClient, _parse_ems_kv


# --- TEST 1: Basic Initialization ---
def test_api_initialization():
    """Test that the API class stores credentials and URL correctly."""

    # We create a fake aiohttp session to pass into the client
    fake_session = MagicMock()

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

    fake_session = MagicMock()
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


@pytest.mark.asyncio
async def test_get_all_device_data_retry_exhaustion(monkeypatch):
    """Test that get_all_device_data exhausts retries and returns None."""
    fake_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", fake_session)

    # Mock _execute_fetch_all to consistently raise ClientError
    api._execute_fetch_all = AsyncMock(side_effect=aiohttp.ClientError("Network error"))

    # Mock asyncio.sleep to prevent actual delays
    mock_sleep = AsyncMock()
    monkeypatch.setattr("asyncio.sleep", mock_sleep)

    # Run the method
    result = await api.get_all_device_data()

    # Verify the result is None
    assert result is None

    # Verify _execute_fetch_all was called MAX_RETRIES times (3)
    assert api._execute_fetch_all.call_count == 3

    # Verify asyncio.sleep was called MAX_RETRIES - 1 times (2)
    assert mock_sleep.call_count == 2


# --- TEST 3: Header Generation and Hashes ---
def test_generate_headers():
    """Verify that _generate_headers constructs the dictionary and signature properly."""
    fake_session = MagicMock()
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


# --- TEST 4: EMS Data Parsing ---
def test_parse_ems_kv():
    """Verify that _parse_ems_kv correctly flattens the nested Field KV structure."""
    fake_data = [
        {
            "filedKv": [
                {"prop": "softWareVer", "value": "V1.2.3"},
                {"prop": "duiSoc", "value": "88.5"},
            ],
            "modeName": "BMS_OVER_VIEW",
        },
        {
            "filedKv": [
                {"prop": "cuVolt", "value": "450.2"},
                {"prop": "cuCurr", "value": "-5.1"},
            ],
            "modeName": "BATTERY_CLUSTER",
        },
    ]

    result = _parse_ems_kv(fake_data)
    assert result["softwarever"] == "V1.2.3"
    assert result["duisoc"] == "88.5"
    assert result["cuvolt"] == "450.2"
    assert result["cucurr"] == "-5.1"


@pytest.mark.asyncio
async def test_query_ems_basic_details_success():
    """Test successful EMS basic data retrieval."""
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)
    api.token = "Bearer fake_token"

    ems_sn = "EMS123"

    # Mock the response context manager
    mock_response = MagicMock()
    mock_response.__aenter__.return_value.raise_for_status = MagicMock()
    mock_response.__aenter__.return_value.status = 200
    mock_response.__aenter__.return_value.json = AsyncMock(
        return_value={
            "code": "0",
            "data": [
                {
                    "filedKv": [
                        {"prop": "duiSoc", "value": "92.0"},
                        {"prop": "cuVolt", "value": "480"},
                    ]
                }
            ],
        }
    )
    mock_response.__aenter__.return_value.raise_for_status = MagicMock()

    api.session.get = MagicMock(return_value=mock_response)

    result = await api.query_ems_basic_details(ems_sn)
    assert result["duisoc"] == "92.0"
    assert result["cuvolt"] == "480"


@pytest.mark.asyncio
async def test_fetch_ems_basic_data_success(caplog):
    """Test _fetch_ems_basic_data when basic details are returned."""
    caplog.set_level(logging.DEBUG)

    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)
    api.query_ems_basic_details = AsyncMock(return_value={"new_metric": "new_value"})

    ems_sn = "10602251600016"
    entry = {"device_type_code": "EMS", "metrics": {"existing_metric": "value"}}

    await api._fetch_ems_basic_data(ems_sn, entry)

    # Assert query_ems_basic_details was called
    api.query_ems_basic_details.assert_called_once_with(ems_sn)

    # Assert entry['metrics'] is updated
    assert entry["metrics"] == {"existing_metric": "value", "new_metric": "new_value"}

    # Assert the correct debug log was emitted
    assert (
        "HYXI Raw METRICS for fefbfd75 (EMS) [EMS]: {'new_metric': 'new_value'}"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_fetch_ems_basic_data_no_data(caplog):
    """Test _fetch_ems_basic_data when no basic details are returned."""
    caplog.set_level(logging.DEBUG)

    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)
    api.query_ems_basic_details = AsyncMock(return_value={})

    ems_sn = "EMS123"
    entry = {"device_type_code": "EMS", "metrics": {"existing_metric": "value"}}

    await api._fetch_ems_basic_data(ems_sn, entry)

    # Assert query_ems_basic_details was called
    api.query_ems_basic_details.assert_called_once_with("EMS123")

    # Assert entry['metrics'] is unchanged
    assert entry["metrics"] == {"existing_metric": "value"}

    # Assert the correct debug log was emitted
    assert "HYXI EMS telemetry probe returned no data for " in caplog.text


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
    # It must return an awaitable AND add an awaitable to state.metric_tasks
    async def mock_fetch_devices(plant_id, state):
        async def mock_metric_task():
            return (f"SN_{plant_id}", {"device_name": f"Device {plant_id}"})

        state.metric_tasks.append(mock_metric_task())
        return None

    api._fetch_devices_for_plant = MagicMock(side_effect=mock_fetch_devices)

    # Configure the mock response to simulate aiohttp's async context manager.
    mock_response = MagicMock()
    mock_response.__aenter__.return_value.json.return_value = fake_plants_response
    mock_response.__aenter__.return_value.raise_for_status = MagicMock()
    mock_response.__aenter__.return_value.status = 200
    mock_response.__aenter__.return_value.raise_for_status = MagicMock()

    api.session.post = MagicMock(return_value=mock_response)

    results = await api._execute_fetch_all()
    # Verify both plants were called
    assert api._fetch_devices_for_plant.call_count == 2
    # Verify the results are parsed properly (our dummy tuples are keys/values)
    assert "SN_plant_1" in results
    assert "SN_plant_2" in results


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

    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)
    api.token = None

    # Mock the response context manager correctly
    mock_response = MagicMock()
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.raise_for_status = MagicMock()
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
    mock_session = MagicMock()
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
    caplog.set_level(logging.DEBUG)

    # Use a MagicMock for the session to handle context managers
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    mock_response = MagicMock()
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.raise_for_status = MagicMock()
    yielded_response.json = AsyncMock(
        return_value={
            "success": True,
            "data": {
                "pageData": [
                    {
                        "deviceSn": "10602251600016",
                        "alarmName": "Fault 1",
                        "plantId": "12345678",
                    },
                    {"deviceSn": "60701251900927", "alarmName": "Fault 2"},
                ]
            },
        }
    )
    yielded_response.raise_for_status = MagicMock()
    yielded_response.status = 200

    # Mock session.post to return the mock_response context manager
    mock_session.post.return_value = mock_response

    alarms = await api._fetch_alarms_for_plant("12345678")

    assert len(alarms) == 2
    assert alarms[0]["deviceSn"] == "10602251600016"  # Ensure return value is intact

    log_text = caplog.text

    # Assert logs do NOT contain sensitive IDs in plain text
    assert "10602251600016" not in log_text
    assert "60701251900927" not in log_text

    # Assert logs contain the masked versions
    assert "fefbfd75" in log_text
    assert "5a9bda67" in log_text

    # Ensure plant ID itself is masked
    assert "ef797c81" in log_text


@pytest.mark.asyncio
async def test_fetch_all_for_device_collector():
    """Test _fetch_all_for_device when dev_type is COLLECTOR."""
    api = HyxiApiClient("key", "secret", "url", session=MagicMock())

    async def dummy_info(*args, **kwargs):
        pass

    async def dummy_metrics(*args, **kwargs):
        pass

    api._fetch_device_info = MagicMock(side_effect=dummy_info)
    api._fetch_device_metrics = MagicMock(side_effect=dummy_metrics)
    api._fetch_ems_basic_data = AsyncMock()

    sn = "SN_123"
    entry = {"initial": "state"}
    dev_type = "COLLECTOR"

    result_sn, result_entry = await api._fetch_all_for_device(sn, entry, dev_type)

    assert result_sn == sn
    assert result_entry == entry

    api._fetch_device_info.assert_called_once_with(sn, entry)
    api._fetch_device_metrics.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_all_for_device_non_collector():
    """Test _fetch_all_for_device when dev_type is not COLLECTOR."""
    api = HyxiApiClient("key", "secret", "url", session=MagicMock())

    async def dummy_info(*args, **kwargs):
        pass

    async def dummy_metrics(*args, **kwargs):
        pass

    api._fetch_device_info = MagicMock(side_effect=dummy_info)
    api._fetch_device_metrics = MagicMock(side_effect=dummy_metrics)
    api._fetch_ems_basic_data = AsyncMock()

    sn = "SN_456"
    entry = {"initial": "state2"}
    dev_type = "INVERTER"

    result_sn, result_entry = await api._fetch_all_for_device(sn, entry, dev_type)

    assert result_sn == sn
    assert result_entry == entry

    api._fetch_device_info.assert_called_once_with(sn, entry)
    api._fetch_device_metrics.assert_called_once_with(sn, entry)


# --- TEST 6: Empty Data Response (The "Halo ESS" Scenario) ---
@pytest.mark.asyncio
async def test_execute_fetch_all_empty_plants():
    """Verify that _execute_fetch_all returns empty dict (not None) for successful but empty plant list."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)

    # Mock response for /api/plant/v1/page: success=True, but data is an empty list or null
    mock_response = MagicMock()
    # Scenario: success=True, data is empty
    mock_response.__aenter__.return_value.json = AsyncMock(
        return_value={
            "success": True,
            "data": {"list": []},
        }
    )
    mock_response.__aenter__.return_value.raise_for_status = MagicMock()
    mock_response.__aenter__.return_value.status = 200
    mock_response.__aenter__.return_value.raise_for_status = MagicMock()

    api.session.post = MagicMock(return_value=mock_response)

    results = await api._execute_fetch_all()

    # Should return {} (indicating no devices found), NOT None (which would trigger retries)
    assert isinstance(results, dict)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_execute_fetch_all_null_data():
    """Verify robustness when the 'data' field itself is null."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)

    mock_response = MagicMock()
    # Scenario: success=True, data is null (None)
    mock_response.__aenter__.return_value.json = AsyncMock(
        return_value={
            "success": True,
            "data": None,
        }
    )
    mock_response.__aenter__.return_value.raise_for_status = MagicMock()
    mock_response.__aenter__.return_value.status = 200
    mock_response.__aenter__.return_value.raise_for_status = MagicMock()

    api.session.post = MagicMock(return_value=mock_response)

    results = await api._execute_fetch_all()

    assert isinstance(results, dict)
    assert len(results) == 0
