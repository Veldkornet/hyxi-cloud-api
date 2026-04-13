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

"""Tests for exception handling in _refresh_token."""

import logging
from unittest.mock import AsyncMock

import pytest

import hyxi_cloud_api.api as api_mod
from hyxi_cloud_api.api import HyxiApiClient


@pytest.mark.asyncio
async def test_refresh_token_exception_handling(caplog):
    """Test that _refresh_token handles exceptions from _request gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Force _LOGGER to use the standard root logger so caplog captures it.
    api_mod._LOGGER = logging.getLogger("hyxi_cloud_api.api")

    # Mock _request to raise an Exception
    error = Exception("Connection reset")
    api._request = AsyncMock(side_effect=error)

    result = await api._refresh_token()

    assert result is False
    assert "HYXI Token Request Failed: Connection reset" in caplog.text
