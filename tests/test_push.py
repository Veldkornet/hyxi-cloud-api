"""Tests for processing webhook push data in hyxi-cloud-api."""

from unittest.mock import MagicMock

from src.hyxi_cloud_api.api import HyxiApiClient


def test_process_push_data_invalid():
    """Test process_push_data handles invalid/malformed payloads gracefully."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    # Non-dictionary payload
    assert not api.process_push_data([])

    # Missing dataList
    assert not api.process_push_data({"foo": "bar"})

    # dataList is not a list
    assert not api.process_push_data({"dataList": "not-a-list"})


def test_process_push_data_success():
    """Test process_push_data correctly parses and computes metrics."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    # Populate discovery cache for an inverter and a collector
    api._discovery_cache["device_info"] = {
        "INV123": {
            "model": "H5K-HT",
            "device_type_code": "HYBRID_INVERTER",
            "device_name": "My Inverter",
        },
        "COLL456": {
            "model": "STICK-1",
            "device_type_code": "COLLECTOR",
            "device_name": "My Stick",
        },
    }

    payload = {
        "dataList": [
            {
                "deviceSn": "INV123",
                "collectTime": 1717764875,
                "acP": "1000.0",
                "ppv": "2000.0",
                "pv2p": "500.0",
                "batSoc": "80",
                "gridP": "-0.5",  # Importing 0.5kW (500W)
            },
            {
                "deviceSn": "COLL456",
                "reportTimestamp": 1717764875000,
                "acP": "1000.0",  # Should be filtered out for collector
                "batSoc": "80",  # Should be filtered out for collector
                "signalVal": "-65",  # Should be kept
            },
        ]
    }

    results = api.process_push_data(payload)

    # Assert INV123
    assert "INV123" in results
    inv_data = results["INV123"]
    assert inv_data["sn"] == "INV123"
    assert inv_data["model"] == "H5K-HT"
    assert inv_data["device_type_code"] == "HYBRID_INVERTER"

    metrics = inv_data["metrics"]
    assert metrics["acP"] == "1000.0"
    assert metrics["batSoc"] == "80"
    assert metrics["last_seen"] == "2024-06-07T12:54:35+00:00"

    # Derived metrics verification
    assert metrics["pv1p"] == 1500.0  # ppv (2000) - pv2p (500)
    assert metrics["grid_import"] == 500.00
    assert metrics["grid_export"] == 0.0

    # Assert COLL456
    assert "COLL456" in results
    coll_data = results["COLL456"]
    assert coll_data["sn"] == "COLL456"
    assert coll_data["model"] == "STICK-1"
    assert coll_data["device_type_code"] == "COLLECTOR"

    coll_metrics = coll_data["metrics"]
    assert coll_metrics["last_seen"] == "2024-06-07T12:54:35+00:00"
    assert coll_metrics["signalVal"] == "-65"
    assert coll_metrics["acP"] == "1000.0"  # Not filtered by keywords
    assert "batSoc" not in coll_metrics  # Filtered (contains 'bat')
