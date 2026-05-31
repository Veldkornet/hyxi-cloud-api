"""Tests for process_alarm_push_data in hyxi-cloud-api."""

from unittest.mock import MagicMock

from src.hyxi_cloud_api.api import HyxiApiClient


def test_process_alarm_push_data_invalid():
    """Invalid/malformed payloads return empty dict."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    assert not api.process_alarm_push_data([])
    assert not api.process_alarm_push_data({"no_data_list": True})
    assert not api.process_alarm_push_data({"dataList": "not-a-list"})


def test_process_alarm_push_data_success():
    """Valid alarm payload is parsed into per-device alarm lists."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    payload = {
        "dataList": [
            {
                "deviceSn": "SN001",
                "alarmCode": "769",
                "alarmName": "Over temperature alarm",
                "alarmState": "1",
                "alarmTime": 1712728593000,
                "endTime": None,
            },
            {
                "deviceSn": "SN001",
                "alarmCode": "768",
                "alarmName": "Overvoltage alarm",
                "alarmState": "0",
                "alarmTime": 1712728590000,
                "endTime": 1712729000000,
            },
        ]
    }

    result = api.process_alarm_push_data(payload)
    assert "SN001" in result
    alarms = result["SN001"]
    assert len(alarms) == 2
    codes = {a["alarmCode"] for a in alarms}
    assert codes == {"769", "768"}


def test_process_alarm_push_data_fallback_name():
    """When alarmName is absent the ALARM_CODE_MAP provides the description."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    payload = {
        "dataList": [
            {
                "deviceSn": "SN002",
                "alarmCode": "769",
                # alarmName deliberately omitted
                "alarmState": "1",
            }
        ]
    }
    result = api.process_alarm_push_data(payload)
    assert result["SN002"][0]["alarmName"] == "Over temperature alarm"


def test_process_alarm_push_data_alternate_field_names():
    """happenTime and happenState field aliases are normalised."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    payload = {
        "dataList": [
            {
                "deviceSn": "SN003",
                "alarmCode": "832",
                "happenState": "2",
                "happenTime": 1712728593000,
            }
        ]
    }
    result = api.process_alarm_push_data(payload)
    rec = result["SN003"][0]
    assert rec["alarmState"] == "2"
    assert rec["alarmTime"] == 1712728593000


def test_process_alarm_push_data_multiple_devices():
    """Records for different devices are grouped by SN."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    payload = {
        "dataList": [
            {"deviceSn": "A", "alarmCode": "768", "alarmState": "1"},
            {"deviceSn": "B", "alarmCode": "769", "alarmState": "2"},
            {"deviceSn": "A", "alarmCode": "832", "alarmState": "1"},
        ]
    }
    result = api.process_alarm_push_data(payload)
    assert len(result["A"]) == 2
    assert len(result["B"]) == 1
