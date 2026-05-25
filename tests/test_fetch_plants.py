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

"""Tests for fetching plants from the API."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.hyxi_cloud_api.api import HyxiApiClient


@pytest.mark.asyncio
async def test_fetch_plants_success():
    """Verify that _fetch_plants returns a list of plants on success."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._request = AsyncMock(
        return_value=(
            200,
            {
                "success": True,
                "data": {"list": [{"plantId": "Pl123"}, {"plantId": "Pl456"}]},
            },
        )
    )

    plants = await api._fetch_plants()
    assert len(plants) == 2
    assert plants[0]["plantId"] == "Pl123"
    assert plants[1]["plantId"] == "Pl456"


@pytest.mark.parametrize("error_code", ["A000002", "A000005"])
@pytest.mark.asyncio
async def test_fetch_plants_token_rejection(error_code):
    """Verify that _fetch_plants handles token rejection correctly."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api.token = "Bearer old_token"
    api.token_expires_at = 9999999999.0

    api._request = AsyncMock(
        return_value=(
            200,
            {"success": False, "code": error_code, "message": "Invalid access token"},
        )
    )

    with pytest.raises(aiohttp.ClientError, match="Server rejected token"):
        await api._fetch_plants()

    assert api.token is None
    assert api.token_expires_at == 0


@pytest.mark.asyncio
async def test_fetch_plants_generic_failure():
    """Verify that _fetch_plants returns None on generic failure."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api.token = "Bearer good_token"
    api.token_expires_at = 9999999999.0

    api._request = AsyncMock(
        return_value=(
            200,
            {"success": False, "code": "C000001", "message": "Parameter error"},
        )
    )

    plants = await api._fetch_plants()

    assert plants is None
    assert api.token == "Bearer good_token"
    assert api.token_expires_at == 9999999999.0


@pytest.mark.asyncio
async def test_fetch_plants_empty_list_warning():
    """Verify that _fetch_plants logs a warning when the plant list is empty."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._request = AsyncMock(
        return_value=(
            200,
            {
                "success": True,
                "data": {"list": []},
            },
        )
    )

    with patch("src.hyxi_cloud_api.api._LOGGER") as mock_logger:
        plants = await api._fetch_plants()
        assert plants == []
        mock_logger.warning.assert_called_once_with(
            "HYXI API: No plants found associated with this account. "
            "If your developer email differs from your app email, you must share "
            "your Plant from the app to the developer email first."
        )
