"""Tests for security sanitization and path management."""

import importlib
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.hyxi_cloud_api import api as api_module
from src.hyxi_cloud_api.api import HyxiApiClient, _mask_id, _sanitize_dict

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
    assert sanitized["deviceSn"] == _mask_id("SN123456789")
    assert sanitized["normalKey"] == "normalValue"

    # Check nested list of dicts
    assert sanitized["data"][0]["deviceSn"] == _mask_id("SN987654321")
    assert sanitized["data"][0]["nested"]["plantId"] == _mask_id("PID123")
    assert sanitized["data"][0]["nested"]["normal"] == "value"
    assert sanitized["data"][1] == "not a dict"

    # Check nested dict
    assert sanitized["nestedDict"]["batSn"] == _mask_id("BAT12345")

    # Check nested list
    assert sanitized["nestedList"][0][0]["deviceSn"] == _mask_id("SN0000")


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


@pytest.fixture
def real_aiohttp():
    """The genuine aiohttp module, bypassing this suite's mock in sys.modules."""
    backup = sys.modules.pop("aiohttp", None)
    module = importlib.import_module("aiohttp")
    sys.modules.pop("aiohttp", None)
    sys.modules["aiohttp"] = backup or module
    return module


def test_sanitize_response_error_strips_query_params(monkeypatch, real_aiohttp):
    """_sanitize_response_error must genuinely strip deviceSn/plantId from the
    URL, using aiohttp's real RequestInfo/ClientResponseError classes.

    The rest of this suite mocks aiohttp with a bare-bones stand-in, so it
    can't catch a masking bug in code that depends on real aiohttp's own
    URL/exception behaviour -- swap in the genuine module for this one test.
    """
    # pylint: disable=import-outside-toplevel
    from aiohttp.client_reqrep import RequestInfo
    from multidict import CIMultiDict, CIMultiDictProxy
    from yarl import URL

    # pylint: enable=import-outside-toplevel

    monkeypatch.setattr(api_module, "aiohttp", real_aiohttp)

    url = URL(
        "https://api.com/api/device/v1/queryDeviceData"
        "?deviceSn=SECRETSN&plantId=SECRETPLANT"
    )
    request_info = RequestInfo(
        url=url, method="GET", headers=CIMultiDictProxy(CIMultiDict()), real_url=url
    )
    original = real_aiohttp.ClientResponseError(
        request_info, (), status=401, message="Unauthorized", headers=None
    )

    sanitized = api_module._sanitize_response_error(original)

    assert "SECRETSN" not in str(sanitized)
    assert "SECRETPLANT" not in str(sanitized)
    assert "queryDeviceData" in str(sanitized)
    assert sanitized.status == 401
    assert sanitized.message == "Unauthorized"
