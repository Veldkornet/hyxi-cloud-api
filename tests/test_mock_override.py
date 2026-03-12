import asyncio
from unittest.mock import AsyncMock, patch, mock_open
import pytest
from src.hyxi_cloud_api.api import HyxiApiClient
import json

@pytest.mark.asyncio
async def test_check_mock_override_invalid_json():
    fake_session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", fake_session)

    with patch("src.hyxi_cloud_api.api.pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data="{this_is_not_json}")):
            result = await api._check_mock_override()
            assert result is None

@pytest.mark.asyncio
async def test_check_mock_override_unexpected_error():
    fake_session = AsyncMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", fake_session)

    with patch("src.hyxi_cloud_api.api.pathlib.Path.exists", return_value=True):
        with patch("builtins.open", side_effect=Exception("Generic error")):
            result = await api._check_mock_override()
            assert result is None
