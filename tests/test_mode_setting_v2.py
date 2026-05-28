"""Tests for HyxiApiClient.get_mode_setting_v2() and its integration into _fetch_all_for_device."""

import sys
from unittest.mock import AsyncMock, MagicMock

if "aiohttp" not in sys.modules or not hasattr(sys.modules["aiohttp"], "ClientError"):
    m = MagicMock()

    class _MockExp(Exception):
        def __init__(self, *args, **kwargs):
            super().__init__(*args)
            for k, v in kwargs.items():
                setattr(self, k, v)

    m.ClientError = _MockExp
    m.ClientResponseError = type("ClientResponseError", (_MockExp,), {"status": 0})
    m.ContentTypeError = type("ContentTypeError", (_MockExp,), {})
    sys.modules["aiohttp"] = m

import aiohttp
import pytest

from src.hyxi_cloud_api.api import HyxiApiClient


def _make_client():
    return HyxiApiClient("ak", "sk", "https://api.com", MagicMock())


# ── get_mode_setting_v2 unit tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_mode_setting_v2_success():
    """Returns the data dict on a successful v2 response."""
    api = _make_client()
    api._request = AsyncMock(
        return_value=(
            200,
            {
                "success": True,
                "data": {"workMode": "self_consumption", "scheduleEnabled": True},
            },
        )
    )

    result = await api.get_mode_setting_v2("SN123")

    assert result == {"workMode": "self_consumption", "scheduleEnabled": True}
    api._request.assert_called_once_with(
        "GET",
        "/hyx-plant/selfDevice/v1/getModeSettingV2",
        params={"deviceSn": "SN123"},
    )


@pytest.mark.asyncio
async def test_get_mode_setting_v2_api_rejection():
    """Returns {} when the API responds success=False (device doesn't support v2)."""
    api = _make_client()
    api._request = AsyncMock(return_value=(200, {"success": False, "code": "A000010"}))

    result = await api.get_mode_setting_v2("SN123")

    assert result == {}


@pytest.mark.asyncio
async def test_get_mode_setting_v2_404():
    """Returns {} on a 404 without logging a warning (expected for older devices)."""
    api = _make_client()
    err = aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=404)
    api._request = AsyncMock(side_effect=err)

    result = await api.get_mode_setting_v2("SN123")

    assert result == {}


@pytest.mark.asyncio
async def test_get_mode_setting_v2_http_error_non_404(caplog):
    """Returns {} but logs a warning on unexpected HTTP errors."""
    api = _make_client()
    err = aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=500)
    api._request = AsyncMock(side_effect=err)

    result = await api.get_mode_setting_v2("SN123")

    assert result == {}
    assert "getModeSettingV2 HTTP error" in caplog.text


@pytest.mark.asyncio
async def test_get_mode_setting_v2_network_error():
    """Returns {} on a general network exception."""
    api = _make_client()
    api._request = AsyncMock(side_effect=aiohttp.ClientError("timeout"))

    result = await api.get_mode_setting_v2("SN123")

    assert result == {}


@pytest.mark.asyncio
async def test_get_mode_setting_v2_empty_data():
    """Returns {} when the 'data' field is None or empty."""
    api = _make_client()
    api._request = AsyncMock(return_value=(200, {"success": True, "data": None}))

    result = await api.get_mode_setting_v2("SN123")

    assert result == {}


@pytest.mark.asyncio
async def test_get_mode_setting_v2_non_dict_data():
    """Returns {} when 'data' is a list instead of a dict (unexpected shape)."""
    api = _make_client()
    api._request = AsyncMock(
        return_value=(200, {"success": True, "data": ["unexpected", "list"]})
    )

    result = await api.get_mode_setting_v2("SN123")

    assert result == {}


# ── Integration: _fetch_all_for_device ───────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_all_for_device_inverter_runs_mode_v2():
    """For INVERTER types, get_mode_setting_v2 is run concurrently and merged."""
    api = _make_client()
    api._fetch_device_info = AsyncMock()
    api._fetch_device_metrics = AsyncMock()
    api.query_ems_basic_details = AsyncMock(return_value={})
    api.get_mode_setting_v2 = AsyncMock(
        return_value={"workMode": "charge", "scheduleEnabled": False}
    )

    sn = "SN_INV"
    entry = {"metrics": {}}
    await api._fetch_all_for_device(sn, entry, "INVERTER")

    api.get_mode_setting_v2.assert_called_once_with(sn)
    # Keys must be prefixed with "mode_v2_"
    assert entry["metrics"]["mode_v2_workMode"] == "charge"
    assert entry["metrics"]["mode_v2_scheduleEnabled"] is False


@pytest.mark.asyncio
async def test_fetch_all_for_device_inverter_mode_v2_empty():
    """When get_mode_setting_v2 returns {}, no keys are added to metrics."""
    api = _make_client()
    api._fetch_device_info = AsyncMock()
    api._fetch_device_metrics = AsyncMock()
    api.query_ems_basic_details = AsyncMock(return_value={})
    api.get_mode_setting_v2 = AsyncMock(return_value={})

    sn = "SN_INV"
    entry = {"metrics": {"existing": "value"}}
    await api._fetch_all_for_device(sn, entry, "INVERTER")

    # No mode_v2_ keys added, existing keys untouched
    assert "mode_v2_workMode" not in entry["metrics"]
    assert entry["metrics"]["existing"] == "value"


@pytest.mark.asyncio
async def test_fetch_all_for_device_collector_skips_mode_v2():
    """COLLECTOR types must not trigger get_mode_setting_v2."""
    api = _make_client()
    api._fetch_device_info = AsyncMock()
    api._fetch_device_metrics = AsyncMock()
    api.query_ems_basic_details = AsyncMock(return_value={})
    api.get_mode_setting_v2 = AsyncMock(return_value={})

    entry = {"metrics": {}}
    await api._fetch_all_for_device("SN_COL", entry, "COLLECTOR")

    api.get_mode_setting_v2.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_all_for_device_hybrid_inverter_runs_mode_v2():
    """HYBRID_INVERTER type also triggers the v2 probe."""
    api = _make_client()
    api._fetch_device_info = AsyncMock()
    api._fetch_device_metrics = AsyncMock()
    api.query_ems_basic_details = AsyncMock(return_value={})
    api.get_mode_setting_v2 = AsyncMock(return_value={"hybridMode": "grid_tie"})

    entry = {"metrics": {}}
    await api._fetch_all_for_device("SN_HYB", entry, "HYBRID_INVERTER")

    api.get_mode_setting_v2.assert_called_once_with("SN_HYB")
    assert entry["metrics"]["mode_v2_hybridMode"] == "grid_tie"
