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

"""Tests for exception handling in _fetch_device_metrics."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from hyxi_cloud_api.api import HyxiApiClient


@pytest.mark.asyncio
async def test_fetch_device_metrics_request_error(caplog):
    """Test that _fetch_device_metrics handles errors from _request gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Mock _request to raise an Exception directly
    api._request = AsyncMock(side_effect=Exception("Mock client error"))

    entry = {"metrics": {}, "device_type_code": "INVERTER"}
    # Use a longer SN so it's not fully masked to ****
    await api._fetch_device_metrics("10600000000001", entry)

    assert "Error fetching metrics for " in caplog.text
    assert "Mock client error" in caplog.text
    # Ensure it didn't crash and entry was not updated with metrics
    assert not entry["metrics"]


@pytest.mark.asyncio
async def test_fetch_device_metrics_network_error(caplog):
    """Test that _fetch_device_metrics handles network errors gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Mock session.get to raise a ClientError
    mock_session.get.side_effect = aiohttp.ClientError("Connection reset")

    entry = {"metrics": {}, "device_type_code": "INVERTER"}
    # Use a longer SN so it's not fully masked to ****
    await api._fetch_device_metrics("10600000000001", entry)

    assert "Error fetching metrics for " in caplog.text
    assert "Connection reset" in caplog.text
    # Ensure it didn't crash and entry was not updated with metrics
    assert not entry["metrics"]


@pytest.mark.asyncio
async def test_fetch_device_metrics_invalid_json(caplog):
    """Test that _fetch_device_metrics handles invalid JSON gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    mock_response = MagicMock()
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.raise_for_status = MagicMock()
    yielded_response.json = AsyncMock(
        side_effect=aiohttp.ContentTypeError(
            request_info=MagicMock(),
            history=(),
            message="Attempt to decode JSON with unexpected mimetype",
        )
    )
    yielded_response.raise_for_status = MagicMock()
    yielded_response.status = 200

    mock_session.get.return_value = mock_response

    entry = {"metrics": {}, "device_type_code": "INVERTER"}
    await api._fetch_device_metrics("10600000000001", entry)

    assert "Error fetching metrics for " in caplog.text
    assert not entry["metrics"]


@pytest.mark.asyncio
async def test_fetch_device_metrics_api_error(caplog):
    """Test that _fetch_device_metrics handles API-level errors correctly."""
    caplog.set_level(logging.WARNING)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    mock_response = MagicMock()
    yielded_response = mock_response.__aenter__.return_value
    yielded_response.raise_for_status = MagicMock()
    yielded_response.json = AsyncMock(
        return_value={
            "success": False,
            "message": "Device not found",
        }
    )
    yielded_response.raise_for_status = MagicMock()
    yielded_response.status = 200

    mock_session.get.return_value = mock_response

    entry = {"metrics": {}, "device_type_code": "INVERTER"}
    await api._fetch_device_metrics("10600000000001", entry)

    assert "HYXI API metrics rejected for " in caplog.text
    assert "success" in caplog.text  # _sanitize_dict logs full response dict
    assert not entry["metrics"]


@pytest.mark.asyncio
async def test_query_ems_basic_details_error(caplog):
    """Test that query_ems_basic_details handles exceptions gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Mock _request to raise an Exception to cover the error path in query_ems_basic_details
    api._request = AsyncMock(side_effect=Exception("EMS query failed"))

    result = await api.query_ems_basic_details("10600000000001")

    assert result == {}

    assert "HYXI EMS Basic Data Request Failed for" in caplog.text
    assert "EMS query failed" in caplog.text


@pytest.mark.asyncio
async def test_query_ems_basic_details_network_error(caplog):
    """Test that query_ems_basic_details handles network errors gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Mock _request to raise a ClientError to cover the network error path
    api._request = AsyncMock(side_effect=aiohttp.ClientError("Connection reset"))

    result = await api.query_ems_basic_details("10600000000001")

    assert result == {}

    assert "HYXI EMS Basic Data Request Failed for" in caplog.text
    assert "Connection reset" in caplog.text


@pytest.mark.asyncio
async def test_query_ems_basic_details_non_zero_code(caplog):
    """Test that query_ems_basic_details logs and returns {} when the API returns a non-zero code.

    This covers devices not enrolled in EMS or where the API signals an
    application-level rejection (HTTP 200 but code != '0').
    """
    caplog.set_level(logging.WARNING)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    api._request = AsyncMock(
        return_value=(200, {"code": "1001", "msg": "Device not enrolled"})
    )

    result = await api.query_ems_basic_details("10600000000001")

    assert result == {}
    assert "HYXI EMS Basic Data Request Rejected for " in caplog.text


@pytest.mark.asyncio
async def test_query_ems_basic_details_malformed_response(caplog):
    """Test that query_ems_basic_details handles malformed responses (AttributeError)."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Mock _request to return (200, None) to trigger AttributeError in query_ems_basic_details
    api._request = AsyncMock(return_value=(200, None))

    result = await api.query_ems_basic_details("10600000000001")

    assert result == {}
    assert "HYXI EMS Basic Data Request Failed for " in caplog.text
    assert "object has no attribute 'get'" in caplog.text


@pytest.mark.asyncio
async def test_query_ems_basic_details_parse_error(caplog):
    """Test that query_ems_basic_details handles exceptions during parsing."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Return a response with code 0 but invalid data type to trigger an exception
    api._request = AsyncMock(return_value=(200, {"code": "0", "data": []}))

    with patch(
        "hyxi_cloud_api.api._parse_ems_kv", side_effect=Exception("Parsing error")
    ):
        result = await api.query_ems_basic_details("10600000000001")

    assert result == {}
    assert "HYXI EMS Basic Data Request Failed for" in caplog.text


@pytest.mark.asyncio
async def test_fetch_device_metrics_parsing_error(caplog, monkeypatch):
    """Test that _fetch_device_metrics handles parsing errors gracefully."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # Return a success response so that it enters the 'if res_q.get("success"):' block
    api._request = AsyncMock(
        return_value=(200, {"success": True, "data": [{"key": "bad"}]})
    )

    def mock_parse(*args, **kwargs):
        raise ValueError("Mock parsing error")

    # Mock _parse_data_list to trigger the exception block at line 1234
    import hyxi_cloud_api.api as api_module  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr(api_module, "_parse_data_list", mock_parse)

    entry = {"metrics": {}, "device_type_code": "INVERTER"}
    await api._fetch_device_metrics("10600000000001", entry)

    assert "Error fetching metrics for " in caplog.text
    assert "Mock parsing error" in caplog.text


@pytest.mark.asyncio
async def test_fetch_device_metrics_ems_gridp_watts_normalized_to_kw():
    """EMS/Micro ESS devices (e.g. Halo) report gridP in Watts, not kW.

    Regression test for GitHub issue #654: a Halo's queryDeviceData response
    included gridP=811.0 (Watts, matching gridQ/gridAp/batP in the same
    payload), but _compute_grid_metrics assumes gridP is in kW and derived
    grid_export=811000.0 instead of 811.0. _fetch_device_metrics must
    normalize gridP to kW for EMS device types before it reaches derived
    metrics computation (and before it's merged into entry["metrics"], so
    any later recompute -- e.g. the HA coordinator's merge-time
    compute_derived_metrics() call -- sees the same convention).
    """
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)
    api._request = AsyncMock(
        return_value=(
            200,
            {
                "success": True,
                "data": [
                    {"dataKey": "gridP", "dataValue": "811.0"},
                    {"dataKey": "gridQ", "dataValue": "26.0"},
                    {"dataKey": "batP", "dataValue": "878"},
                ],
            },
        )
    )

    entry = {"metrics": {}, "device_type_code": "15"}  # Micro ESS
    await api._fetch_device_metrics("10600000000001", entry)

    assert entry["metrics"]["gridP"] == 0.811
    assert entry["metrics"]["grid_export"] == 811.0
    assert entry["metrics"]["grid_import"] == 0.0


@pytest.mark.asyncio
async def test_fetch_device_metrics_non_ems_gridp_left_as_kw():
    """Non-EMS device types are unaffected -- gridP stays in kW as-is."""
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)
    api._request = AsyncMock(
        return_value=(
            200,
            {"success": True, "data": [{"dataKey": "gridP", "dataValue": "1.5"}]},
        )
    )

    entry = {"metrics": {}, "device_type_code": "INVERTER"}
    await api._fetch_device_metrics("10600000000001", entry)

    assert entry["metrics"]["gridP"] == "1.5"
    assert entry["metrics"]["grid_export"] == 1500.0


@pytest.mark.asyncio
async def test_fetch_device_metrics_energy_storage_battery_gridp_left_as_kw():
    """ENERGY_STORAGE_BATTERY is grouped with EMS types for unrelated
    battery-fallback/EMS-probe purposes (_EMS_DEVICE_TYPES), but it's a
    distinct standalone-battery-pack category with no evidence of the
    Micro ESS/Halo gridP-in-Watts quirk -- it must stay out of the
    narrower _MICRO_ESS_DEVICE_TYPES fixup set.
    """
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)
    api._request = AsyncMock(
        return_value=(
            200,
            {"success": True, "data": [{"dataKey": "gridP", "dataValue": "1.5"}]},
        )
    )

    entry = {"metrics": {}, "device_type_code": "ENERGY_STORAGE_BATTERY"}
    await api._fetch_device_metrics("10600000000001", entry)

    assert entry["metrics"]["gridP"] == "1.5"
    assert entry["metrics"]["grid_export"] == 1500.0


@pytest.mark.asyncio
@pytest.mark.parametrize("device_type_code", ["16", "EMS", "MICRO_STORAGE_ALL_IN_ONE"])
async def test_fetch_device_metrics_micro_ess_family_gridp_normalized(
    device_type_code,
):
    """Every code in _MICRO_ESS_DEVICE_TYPES gets the Watts->kW fixup, not
    just the "15" used in test_fetch_device_metrics_ems_gridp_watts_normalized_to_kw.
    """
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)
    api._request = AsyncMock(
        return_value=(
            200,
            {"success": True, "data": [{"dataKey": "gridP", "dataValue": "811.0"}]},
        )
    )

    entry = {"metrics": {}, "device_type_code": device_type_code}
    await api._fetch_device_metrics("10600000000001", entry)

    assert entry["metrics"]["gridP"] == 0.811
    assert entry["metrics"]["grid_export"] == 811.0


@pytest.mark.asyncio
async def test_fetch_device_metrics_cell_voltages_normalized_from_millivolts():
    """queryDeviceData batVch/batVcl in millivolts are scaled to volts before
    they land in entry["metrics"] (some firmwares report mV, others volts).
    """
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)
    api._request = AsyncMock(
        return_value=(
            200,
            {
                "success": True,
                "data": [
                    {"dataKey": "batVch", "dataValue": "3203.0"},
                    {"dataKey": "batVcl", "dataValue": "3.19"},
                ],
            },
        )
    )

    entry = {"metrics": {}, "device_type_code": "HYBRID_INVERTER"}
    await api._fetch_device_metrics("10600000000001", entry)

    assert entry["metrics"]["batVch"] == 3.203
    assert entry["metrics"]["batVcl"] == 3.19


@pytest.mark.asyncio
async def test_fetch_device_metrics_cell_temperatures_normalized_from_tenths():
    """queryDeviceData batTch/batTcl in tenths of a degree are scaled to
    degrees before they land in entry["metrics"] (a HALO reports tenths).
    """
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)
    api._request = AsyncMock(
        return_value=(
            200,
            {
                "success": True,
                "data": [
                    {"dataKey": "batTch", "dataValue": "383.0"},
                    {"dataKey": "batTcl", "dataValue": "336.0"},
                ],
            },
        )
    )

    entry = {"metrics": {}, "device_type_code": "MICRO_STORAGE_ALL_IN_ONE"}
    await api._fetch_device_metrics("10600000000001", entry)

    assert entry["metrics"]["batTch"] == 38.3
    assert entry["metrics"]["batTcl"] == 33.6
