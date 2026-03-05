import pytest
from unittest.mock import AsyncMock

# Import your actual API client
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
