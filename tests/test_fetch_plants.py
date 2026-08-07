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

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hyxi_cloud_api.api import HyxiApiClient, TokenRejectedError


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


@pytest.mark.asyncio
async def test_fetch_plants_success_debug_logging(caplog):
    """Verify that when DEBUG logging is enabled, a non-empty plant list is
    logged with masked plant IDs."""
    caplog.set_level(logging.DEBUG)
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
    assert "HYXI Discovered Plants:" in caplog.text
    # Plant IDs are masked in the log output, not logged in the clear.
    assert "Pl123" not in caplog.text
    assert "Pl456" not in caplog.text


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

    with patch("hyxi_cloud_api.api._LOGGER") as mock_logger:
        plants = await api._fetch_plants()
        assert plants == []
        mock_logger.warning.assert_called_once_with(
            "HYXI API: No plants found associated with this account. "
            "If your developer email differs from your app email, you must share "
            "your Plant from the app to the developer email first."
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("error_code", ["A000002", "A000005", "C000006"])
async def test_request_token_rejection_errors_are_raised(error_code):
    """
    When the HYXI backend rejects a token with a known error code, _request
    should raise TokenRejectedError.
    """
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api.token = "Bearer good_token"
    api.token_expires_at = 9999999999.0

    mocked_response = {
        "success": False,
        "code": error_code,
        "msg": "Server rejected token",
    }

    # Mock the aiohttp client session post method
    mock_post = MagicMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mocked_response)
    mock_post.return_value.__aenter__.return_value = mock_response
    api.session.post = mock_post

    with pytest.raises(TokenRejectedError) as exc_info:
        await api._request("POST", "/api/plant/v1/page", json={})

    assert "Server rejected token" in str(exc_info.value)
    # Ensure token is cleared
    assert api.token is None
    assert api.token_expires_at == 0
