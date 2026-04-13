"""Tests for security sanitization and path management."""

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.hyxi_cloud_api.api import HyxiApiClient, _sanitize_dict

# Mock aiohttp before importing the API client
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


def test_sanitize_dict_recursive():
    """Verify that _sanitize_dict masks sensitive keys in nested dicts and lists."""
    raw = {
        "plantAddress": "123 Secret St",
        "deviceSn": "SN123456789",
        "normalKey": "normalValue",
        "data": [
            {
                "deviceSn": "SN987654321",
                "nested": {"plantId": "PID123", "normal": "value"},
            },
            "not a dict",
        ],
        "nestedDict": {"batSn": "BAT12345"},
        "nestedList": [[{"deviceSn": "SN0000"}]],
    }

    sanitized = _sanitize_dict(raw)

    assert sanitized["plantAddress"] == "[REDACTED]"
    assert sanitized["deviceSn"] == "XXXXXXX6789"
    assert sanitized["normalKey"] == "normalValue"

    # Check nested list of dicts
    assert sanitized["data"][0]["deviceSn"] == "XXXXXXX4321"
    assert sanitized["data"][0]["nested"]["plantId"] == "****"
    assert sanitized["data"][0]["nested"]["normal"] == "value"
    assert sanitized["data"][1] == "not a dict"

    # Check nested dict
    assert sanitized["nestedDict"]["batSn"] == "XXXX2345"

    # Check nested list
    assert sanitized["nestedList"][0][0]["deviceSn"] == "****"


@pytest.mark.asyncio
async def test_fetch_device_metrics_fixed():
    """Verify that _fetch_device_metrics now uses params mapping."""
    fake_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", fake_session)

    sn = "123&extra=param"
    entry = {"metrics": {}}

    mock_response = MagicMock()
    mock_response.__aenter__.return_value.json = AsyncMock(
        return_value={
            "success": True,
            "data": [],
        }
    )
    mock_response.__aenter__.return_value.raise_for_status = MagicMock()
    mock_response.__aenter__.return_value.status = 200

    fake_session.get.return_value = mock_response

    await api._fetch_device_metrics(sn, entry)

    args, kwargs = fake_session.get.call_args
    # URL should NOT contain the raw unencoded SN with '&'
    assert args[0] == "https://api.com/api/device/v1/queryDeviceData"
    assert kwargs["params"] == {"deviceSn": sn}


@pytest.mark.asyncio
async def test_fetch_device_info_fixed():
    """Verify that _fetch_device_info now uses params mapping."""
    fake_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", fake_session)

    sn = "123#fragment"
    entry = {"metrics": {}}

    mock_response = MagicMock()
    mock_response.__aenter__.return_value.json = AsyncMock(
        return_value={
            "success": True,
            "data": [],
        }
    )
    mock_response.__aenter__.return_value.raise_for_status = MagicMock()
    mock_response.__aenter__.return_value.status = 200

    fake_session.get.return_value = mock_response

    await api._fetch_device_info(sn, entry)

    args, kwargs = fake_session.get.call_args
    # URL should NOT contain the raw unencoded SN with '#'
    assert args[0] == "https://api.com/api/device/v1/queryDeviceInfo"
    assert kwargs["params"] == {"deviceSn": sn}
