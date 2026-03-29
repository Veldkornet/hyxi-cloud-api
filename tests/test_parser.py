"""Tests for data parser logic in the API."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.hyxi_cloud_api.api import HyxiApiClient


@pytest.mark.asyncio
async def test_api_parsing():
    """Verify that _fetch_device_metrics successfully parses and extracts expected values."""
    # Fake the exact list structure the HYXI cloud actually returns
    fake_json = {
        "success": True,
        "data": [
            {"dataKey": "totalE", "dataValue": "2731.9"},
            {"dataKey": "pbat", "dataValue": "-500"},  # -500 means charging
            {"dataKey": "gridP", "dataValue": "1.5"},  # 1.5 kW exported
        ],
    }

    # Mock the aiohttp response context manager
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value=fake_json)
    mock_response.raise_for_status = MagicMock()  # Pretend we got a 200 OK

    # Use MagicMock so .get() returns a context manager, not a coroutine
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Initialize the API with the fake session
    api = HyxiApiClient(
        access_key="test_ak",
        secret_key="test_sk",
        base_url="https://test.com",
        session=mock_session,
    )

    # Create the dummy dictionary that the code expects to update
    entry = {"metrics": {}, "device_type_code": "1"}  # Inverter

    # Run the actual parsing method
    await api._fetch_device_metrics("SN123", entry)

    # Verify extracted raw value
    assert entry["metrics"]["totalE"] == "2731.9"

    # Verify inline math converter (gridP * 1000)
    assert entry["metrics"]["grid_export"] == 1500.0

    # Verify battery logic correctly assigned the negative number to the 'charging' sensor
    assert entry["metrics"]["bat_charging"] == 500.0
    assert entry["metrics"]["bat_discharging"] == 0


@pytest.mark.asyncio
async def test_api_device_info_parsing():
    """Verify that _fetch_device_info successfully parses and extracts expected static values."""
    fake_json = {
        "success": True,
        "data": [
            {"dataKey": "swVerSys", "dataValue": "v1.2.3"},
            {"dataKey": "signalIntensity", "dataValue": "good"},
            {"dataKey": "maxChargingDischargingPower", "dataValue": "5000"},
            {"dataKey": "batCap", "dataValue": "100"},
        ],
    }

    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value=fake_json)
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response

    api = HyxiApiClient(
        access_key="test_ak",
        secret_key="test_sk",
        base_url="https://test.com",
        session=mock_session,
    )

    entry = {"metrics": {}, "device_type_code": "1"}  # Inverter

    await api._fetch_device_info("SN123", entry)

    # Verify extracted fw version
    assert entry["sw_version"] == "v1.2.3"

    # Verify basic mapping
    assert entry["metrics"]["signalIntensity"] == "good"
    assert entry["metrics"]["batCap"] == 100.0

    # Verify fallback logic
    assert entry["metrics"]["maxChargePower"] == 5000.0
    assert entry["metrics"]["maxDischargePower"] == 5000.0
