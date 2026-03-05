import pytest
from unittest.mock import AsyncMock, MagicMock
from src.hyxi_cloud_api.api import HyxiApiClient


@pytest.mark.asyncio
async def test_api_parsing():
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
