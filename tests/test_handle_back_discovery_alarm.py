import sys
from unittest.mock import MagicMock, ANY

# Mock aiohttp before importing the API to bypass ModuleNotFoundError in restricted environments
mock_aiohttp = MagicMock()
sys.modules["aiohttp"] = mock_aiohttp

import pytest
from src.hyxi_cloud_api.api import HyxiApiClient, FetchState

@pytest.fixture
def api():
    return HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

@pytest.fixture
def state():
    return FetchState(now="2024-01-01T00:00:00Z")

def test_handle_back_discovery_alarm_missing_sn(api, state):
    sub_device_tasks = []
    api._handle_back_discovery_alarm({}, "plant1", state, sub_device_tasks)
    assert not state.discovered_sns
    assert not state.metric_tasks
    assert not sub_device_tasks

def test_handle_back_discovery_alarm_short_sn(api, state):
    sub_device_tasks = []
    api._handle_back_discovery_alarm({"deviceSn": "123"}, "plant1", state, sub_device_tasks)
    assert not state.discovered_sns
    api._handle_back_discovery_alarm({"deviceSn": 1234}, "plant1", state, sub_device_tasks)
    assert not state.discovered_sns

def test_handle_back_discovery_alarm_already_discovered(api, state):
    sub_device_tasks = []
    state.discovered_sns.add("SN12345")
    api._handle_back_discovery_alarm({"deviceSn": "SN12345"}, "plant1", state, sub_device_tasks)
    assert len(state.discovered_sns) == 1
    assert not state.metric_tasks

def test_handle_back_discovery_alarm_success_non_parent(api, state):
    sub_device_tasks = []
    alarm = {
        "deviceSn": "SN12345",
        "deviceType": "METER",
        "deviceName": "My Meter"
    }
    api._fetch_all_for_device = MagicMock(return_value="mock_task")

    api._handle_back_discovery_alarm(alarm, "plant1", state, sub_device_tasks)

    assert "SN12345" in state.discovered_sns
    assert len(state.metric_tasks) == 1
    assert state.metric_tasks[0] == "mock_task"
    assert not sub_device_tasks

    api._fetch_all_for_device.assert_called_once()
    args, _ = api._fetch_all_for_device.call_args
    assert args[0] == "SN12345"
    assert args[1]["sn"] == "SN12345"
    assert args[1]["device_name"] == "My Meter"
    assert args[1]["model"] == "Meter"
    assert args[2] == "METER"

def test_handle_back_discovery_alarm_success_parent(api, state):
    sub_device_tasks = []
    alarm = {
        "deviceSn": "SN_COLL_1",
        "deviceType": "COLLECTOR"
    }
    api._fetch_all_for_device = MagicMock(return_value="metric_task")
    api._fetch_sub_devices = MagicMock(return_value="sub_task")

    api._handle_back_discovery_alarm(alarm, "plant1", state, sub_device_tasks)

    assert "SN_COLL_1" in state.discovered_sns
    assert state.metric_tasks == ["metric_task"]
    assert sub_device_tasks == ["sub_task"]

    api._fetch_all_for_device.assert_called_with("SN_COLL_1", ANY, "COLLECTOR")
    api._fetch_sub_devices.assert_called_with("SN_COLL_1", state)

def test_handle_back_discovery_alarm_fallback_name(api, state):
    sub_device_tasks = []
    alarm = {
        "deviceSn": "SN_INV_1",
        "deviceType": "1" # Hybrid Inverter
    }
    api._fetch_all_for_device = MagicMock()

    api._handle_back_discovery_alarm(alarm, "plant1", state, sub_device_tasks)

    args, _ = api._fetch_all_for_device.call_args
    assert args[1]["device_name"] == "Hybrid Inverter SN_INV_1"
    assert args[1]["model"] == "Hybrid Inverter"

def test_handle_back_discovery_alarm_unknown_type(api, state):
    sub_device_tasks = []
    alarm = {
        "deviceSn": "SN_UNKNOWN",
        "deviceType": "UNKNOWN_TYPE"
    }
    api._fetch_all_for_device = MagicMock()

    api._handle_back_discovery_alarm(alarm, "plant1", state, sub_device_tasks)

    args, _ = api._fetch_all_for_device.call_args
    assert args[1]["model"] == "Unknown Type"
    assert args[1]["device_name"] == "Unknown Type SN_UNKNOWN"
