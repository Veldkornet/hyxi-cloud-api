"""Tests for the _handle_back_discovery_alarm method in the HYXi Cloud API client."""
# pylint: disable=redefined-outer-name

import sys
from unittest.mock import AsyncMock, MagicMock

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

import pytest

from src.hyxi_cloud_api.api import FetchState, HyxiApiClient


@pytest.fixture
def mock_api():
    """Fixture for a mock HYXi API client."""
    return HyxiApiClient("ak", "sk", "https://api.com", MagicMock())


@pytest.fixture
def mock_state():
    """Fixture for a mock FetchState object."""
    return FetchState(now="2024-01-01T00:00:00Z")


def test_handle_back_discovery_alarm_missing_sn(mock_api, mock_state):
    """Test short-circuiting when deviceSn is missing."""
    sub_device_tasks = []
    mock_api._handle_back_discovery_alarm({}, "plant1", mock_state, sub_device_tasks)
    assert not mock_state.discovered_sns
    assert not mock_state.metric_tasks
    assert not sub_device_tasks


def test_handle_back_discovery_alarm_short_sn(mock_api, mock_state):
    """Test short-circuiting when deviceSn is too short."""
    sub_device_tasks = []
    mock_api._handle_back_discovery_alarm(
        {"deviceSn": "123"}, "plant1", mock_state, sub_device_tasks
    )
    assert not mock_state.discovered_sns
    mock_api._handle_back_discovery_alarm(
        {"deviceSn": 1234}, "plant1", mock_state, sub_device_tasks
    )
    assert not mock_state.discovered_sns


def test_handle_back_discovery_alarm_already_discovered(mock_api, mock_state):
    """Test short-circuiting when deviceSn is already discovered."""
    sub_device_tasks = []
    mock_state.discovered_sns.add("SN12345")
    mock_api._handle_back_discovery_alarm(
        {"deviceSn": "SN12345"}, "plant1", mock_state, sub_device_tasks
    )
    assert len(mock_state.discovered_sns) == 1
    assert not mock_state.metric_tasks


def test_handle_back_discovery_alarm_success_non_parent(mock_api, mock_state):
    """Test successful discovery of a non-parent device."""
    sub_device_tasks = []
    alarm = {"deviceSn": "SN12345", "deviceType": "METER", "deviceName": "My Meter"}
    mock_api._fetch_all_for_device = AsyncMock()

    mock_api._handle_back_discovery_alarm(alarm, "plant1", mock_state, sub_device_tasks)

    assert "SN12345" in mock_state.discovered_sns
    assert len(mock_state.metric_tasks) == 1
    assert mock_state.metric_tasks[0][0] == "SN12345"
    assert not sub_device_tasks

    args = mock_state.metric_tasks[0]
    assert args[0] == "SN12345"
    assert args[1]["sn"] == "SN12345"
    assert args[1]["device_name"] == "My Meter"
    assert args[1]["model"] == "Meter"
    assert args[2] == "METER"


def test_handle_back_discovery_alarm_success_parent(mock_api, mock_state):
    """Test successful discovery of a parent device."""
    sub_device_tasks = []
    alarm = {"deviceSn": "SN_COLL_1", "deviceType": "COLLECTOR"}
    mock_api._fetch_all_for_device = AsyncMock()

    mock_api._handle_back_discovery_alarm(alarm, "plant1", mock_state, sub_device_tasks)

    assert "SN_COLL_1" in mock_state.discovered_sns
    assert len(mock_state.metric_tasks) == 1
    assert len(sub_device_tasks) == 1


def test_handle_back_discovery_alarm_fallback_name(mock_api, mock_state):
    """Test fallback naming logic when deviceName is missing."""
    sub_device_tasks = []
    alarm = {"deviceSn": "SN_INV_1", "deviceType": "1"}  # Hybrid Inverter
    mock_api._fetch_all_for_device = MagicMock()

    mock_api._handle_back_discovery_alarm(alarm, "plant1", mock_state, sub_device_tasks)

    args = mock_state.metric_tasks[0]
    assert args[1]["device_name"] == "Hybrid Inverter SN_INV_1"
    assert args[1]["model"] == "Hybrid Inverter"


def test_handle_back_discovery_alarm_unknown_type(mock_api, mock_state):
    """Test discovery with an unknown device type."""
    sub_device_tasks = []
    alarm = {"deviceSn": "SN_UNKNOWN", "deviceType": "UNKNOWN_TYPE"}
    mock_api._fetch_all_for_device = MagicMock()

    mock_api._handle_back_discovery_alarm(alarm, "plant1", mock_state, sub_device_tasks)

    args = mock_state.metric_tasks[0]
    assert args[1]["model"] == "Unknown Type"
    assert args[1]["device_name"] == "Unknown Type SN_UNKNOWN"
