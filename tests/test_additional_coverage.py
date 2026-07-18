import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.hyxi_cloud_api.api import FetchState, HyxiApiClient


@pytest.mark.asyncio
async def test_fetch_sub_devices_coverage(caplog):
    """Test _fetch_sub_devices debug logging, duplicates, and exceptions."""
    caplog.set_level(logging.DEBUG)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # 1. Test successful sub-device discovery with debug logging
    state = FetchState(now="2026-06-02T08:00:00")
    state.discovered_sns.add("DUPLICATE_SN")

    children_data = [
        {"deviceSn": "NEW_SN", "deviceType": "INVERTER"},
        {
            "deviceSn": "DUPLICATE_SN",
            "deviceType": "INVERTER",
        },  # should be skipped (duplicate)
        {"deviceSn": "", "deviceType": "INVERTER"},  # should be skipped (missing SN)
    ]
    api._fetch_sub_device_list = AsyncMock(return_value=children_data)
    api._fetch_all_for_device = AsyncMock()

    await api._fetch_sub_devices("PARENT_SN", state)

    # Verify debug log was hit (line 1243)
    # PARENT_SN is masked to ca7b0e8c
    assert "HYXI Found 3 sub-devices under " in caplog.text
    # Verify duplicate/empty check worked (line 1253)
    assert len(state.metric_tasks) == 1
    assert state.metric_tasks[0] == (
        "NEW_SN",
        {
            "sn": "NEW_SN",
            "device_name": "Inverter NEW_SN",
            "model": "Inverter",
            "device_type_code": "INVERTER",
            "sw_version": None,
            "hw_version": None,
            "metrics": {"last_seen": "2026-06-02T08:00:00"},
        },
        "INVERTER",
    )

    # 2. Test exception logging in _fetch_sub_devices (lines 1265-1266)
    caplog.clear()
    api._fetch_sub_device_list = AsyncMock(side_effect=Exception("Database failure"))
    await api._fetch_sub_devices("PARENT_SN", state)
    # PARENT_SN is masked to ca7b0e8c
    assert "Error fetching sub-devices for " in caplog.text
    assert "Database failure" in caplog.text


@pytest.mark.asyncio
async def test_fetch_alarms_for_plant_coverage(caplog):
    """Test _fetch_alarms_for_plant rejection and alarm name mapping."""
    caplog.set_level(logging.ERROR)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # 1. Rejection logging (lines 1281-1286)
    api._request = AsyncMock(
        return_value=(200, {"success": False, "msg": "Limit exceeded"})
    )
    res = await api._fetch_alarms_for_plant("PLANT_123")
    assert res == []
    # PLANT_123 is masked to b7a0873d
    assert "HYXI API Alarm Fetch Rejected for Plant " in caplog.text

    # 2. Alarm Name Mapping (line 1295)
    api._request = AsyncMock(
        return_value=(
            200,
            {
                "success": True,
                "data": {
                    "pageData": [
                        {
                            "alarmCode": "704",
                            "alarmState": "1",
                        }  # "704" is mapped in ALARM_CODE_MAP
                    ]
                },
            },
        )
    )
    res = await api._fetch_alarms_for_plant("PLANT_123")
    assert len(res) == 1
    assert (
        res[0]["alarmName"] == "The ambient temperature is too high"
    )  # ALARM_CODE_MAP["704"]


@pytest.mark.asyncio
async def test_execute_fetch_all_errors():
    """Test _execute_fetch_all authentication fail paths (lines 1530, 1532)."""
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # 1. auth_failed path (line 1530)
    api._refresh_token = AsyncMock(return_value="auth_failed")
    res = await api._execute_fetch_all()
    assert res == "auth_failed"

    # 2. False token status path (line 1532)
    api._refresh_token = AsyncMock(return_value=False)
    res = await api._execute_fetch_all()
    assert res is None


@pytest.mark.asyncio
async def test_execute_fetch_full_discovery_error():
    """Test _execute_fetch_full_discovery returns None if fetch_plants fails (line 1588)."""
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)
    state = FetchState(now="now")

    api._fetch_plants = AsyncMock(return_value=None)
    res = await api._execute_fetch_full_discovery(state, allow_back_discovery=False)
    assert res is None


@pytest.mark.asyncio
async def test_alter_alarm_token_errors():
    """Test alter_alarm raises ControlError on token failure (line 1911)."""
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # 1. auth_failed
    api._refresh_token = AsyncMock(return_value="auth_failed")
    with pytest.raises(HyxiApiClient.ControlError, match="Authentication failed"):
        await api.alter_alarm([123])

    # 2. False status (line 1911)
    api._refresh_token = AsyncMock(return_value=False)
    with pytest.raises(HyxiApiClient.ControlError, match="Could not obtain API token"):
        await api.alter_alarm([123])


def test_compute_derived_metrics_classmethod():
    """Test compute_derived_metrics proxy call (line 1937)."""
    res = HyxiApiClient.compute_derived_metrics({"gridP": 100}, "INVERTER")
    assert isinstance(res, dict)
    assert "grid_import" in res


def test_process_push_data_edge_cases(caplog):
    """Test process_push_data ignores invalid items and dates (lines 1973, 1977, 2001-2002, 2008-2009)."""
    caplog.set_level(logging.WARNING)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    # dataList contains invalid elements (non-dict, missing SN, invalid dates)
    payload = {
        "dataList": [
            123,  # not a dict (line 1973)
            {"reportTimestamp": 1712728593000},  # missing SN (line 1977)
            {
                "deviceSn": "SN123",
                "collectTime": "invalid_date_type",  # invalid date type (line 2001-2002)
                "reportTimestamp": "invalid_ts_type",  # invalid timestamp type (line 2008-2009)
            },
        ]
    }

    res = api.process_push_data(payload)
    assert "SN123" in res
    assert res["SN123"]["metrics"]["last_seen"].startswith("2")  # starts with year 202x


def test_process_alarm_push_data_edge_cases(caplog):
    """Test process_alarm_push_data handles invalid elements (lines 2078, 2082)."""
    caplog.set_level(logging.WARNING)
    mock_session = MagicMock()
    api = HyxiApiClient("ak", "sk", "https://api.com", mock_session)

    payload = {
        "dataList": [
            123,  # not a dict (line 2078)
            {"alarmCode": "12"},  # missing SN (line 2082)
            {"deviceSn": "SN123", "alarmCode": "12", "alarmState": "1"},  # valid
        ]
    }

    res = api.process_alarm_push_data(payload)
    assert "SN123" in res
    assert len(res["SN123"]) == 1
    assert res["SN123"][0]["alarmCode"] == "12"
