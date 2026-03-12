"""Tests for data parser logic in the API."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.hyxi_cloud_api.api import HyxiApiClient


@pytest.mark.asyncio
async def test_api_parsing():
    """Verify that _fetch_device_metrics successfully parses and extracts expected values."""
    # 1. Fake the exact list structure the HYXi cloud actually returns
    fake_json = {
        "success": True,
        "data": [
            {"dataKey": "totalE", "dataValue": "2731.9"},
            {"dataKey": "pbat", "dataValue": "-500"},  # -500 means charging
            {"dataKey": "gridP", "dataValue": "1.5"},  # 1.5 kW exported
        ],
    }

    # 2. We mock the aiohttp response context manager
    mock_response = AsyncMock()
    mock_response.json.return_value = fake_json
    mock_response.raise_for_status = MagicMock()  # Pretend we got a 200 OK

    # 👇 THE FIX: Use MagicMock here so .get() returns a context manager, not a coroutine!
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # 3. Initialize your API with the fake session
    api = HyxiApiClient(
        access_key="test_ak",
        secret_key="test_sk",
        base_url="https://test.com",
        session=mock_session,
    )

    # 4. Create the dummy dictionary that your code expects to update
    entry = {"metrics": {}}

    # 5. EXECUTE: Run your actual parsing method!
    await api._fetch_device_metrics("SN123", entry)

    # --- 6. THE VERIFICATION ---

    # Did it extract the raw value?
    assert entry["metrics"]["totalE"] == "2731.9"

    # Did your inline math converter work? (gridP * 1000)
    assert entry["metrics"]["grid_export"] == 1500.0

    # Did your battery logic correctly assign the negative number to the 'charging' sensor?
    assert entry["metrics"]["bat_charging"] == 500.0
    assert entry["metrics"]["bat_discharging"] == 0


@pytest.mark.asyncio
async def test_api_info_parsing():
    """Verify that _fetch_device_info successfully parses and extracts static device info."""
    fake_json = {
        "success": True,
        "data": [
            {"dataKey": "swVerSys", "dataValue": "V1.0.0"},
            {"dataKey": "signalIntensity", "dataValue": "Good"},
            {"dataKey": "signalVal", "dataValue": "4"},
            {"dataKey": "wifiVer", "dataValue": "W1.2.3"},
            {"dataKey": "comMode", "dataValue": "WiFi"},
            {"dataKey": "batCap", "dataValue": "100.0"},
            {"dataKey": "maxChargePower", "dataValue": "5000"},
            {"dataKey": "maxDischargePower", "dataValue": "6000"},
        ],
    }

    mock_response = AsyncMock()
    mock_response.json.return_value = fake_json
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response

    api = HyxiApiClient(
        access_key="test_ak",
        secret_key="test_sk",
        base_url="https://test.com",
        session=mock_session,
    )

    entry = {"metrics": {}}

    await api._fetch_device_info("SN123", entry)

    assert entry.get("sw_version") == "V1.0.0"
    assert entry["metrics"]["signalIntensity"] == "Good"
    assert entry["metrics"]["signalVal"] == "4"
    assert entry["metrics"]["wifiVer"] == "W1.2.3"
    assert entry["metrics"]["comMode"] == "WiFi"
    assert entry["metrics"]["batCap"] == "100.0"
    assert entry["metrics"]["maxChargePower"] == "5000"
    assert entry["metrics"]["maxDischargePower"] == "6000"


@pytest.mark.asyncio
async def test_api_info_parsing_fallbacks():
    """Verify that _fetch_device_info correctly uses fallback keys for device info."""
    fake_json = {
        "success": True,
        "data": [
            # swVerSys is absent, but swVerMaster is present
            {"dataKey": "swVerMaster", "dataValue": "V2.0.0"},
            # maxChargePower and maxDischargePower are absent
            {"dataKey": "maxChargingDischargingPower", "dataValue": "4500"},
        ],
    }

    mock_response = AsyncMock()
    mock_response.json.return_value = fake_json
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response

    api = HyxiApiClient(
        access_key="test_ak",
        secret_key="test_sk",
        base_url="https://test.com",
        session=mock_session,
    )

    entry = {"metrics": {}}

    await api._fetch_device_info("SN123", entry)

    # Verify fallback for sw_version
    assert entry.get("sw_version") == "V2.0.0"

    # Verify fallback for power limits
    assert entry["metrics"]["maxChargePower"] == "4500"
    assert entry["metrics"]["maxDischargePower"] == "4500"
