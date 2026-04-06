"""Tests for exception handling in _refresh_token."""

import logging
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from hyxi_cloud_api.api import HyxiApiClient

@pytest.mark.asyncio
async def test_refresh_token_exception_handling(caplog):
    """Test that _refresh_token handles exceptions from _request gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Force _LOGGER to use the standard root logger so caplog captures it.
    import hyxi_cloud_api.api as api_mod
    api_mod._LOGGER = logging.getLogger("hyxi_cloud_api.api")

    # Mock _request to raise an Exception
    error = Exception("Connection reset")
    api._request = AsyncMock(side_effect=error)

    result = await api._refresh_token()

    assert result is False
    assert "HYXI Token Request Failed: Connection reset" in caplog.text
