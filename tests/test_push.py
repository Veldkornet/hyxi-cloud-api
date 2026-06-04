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


def test_process_push_data_with_existing_metrics():
    """Test process_push_data merges new updates with existing metrics before computing derived metrics."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    api._discovery_cache["device_info"] = {
        "INV123": {
            "model": "H5K-HT",
            "device_type_code": "HYBRID_INVERTER",
            "device_name": "My Inverter",
        }
    }

    # Historical metrics in coordinator: phase 2 and 3 load power, and grid power
    existing_metrics = {
        "INV123": {
            "ph2Loadp": 300.0,
            "ph3Loadp": 200.0,
            "gridP": "-1.0",
        }
    }

    # Incoming push notification: only phase 1 load power updated
    payload = {
        "dataList": [
            {
                "deviceSn": "INV123",
                "collectTime": 1717764875,
                "ph1Loadp": "500.0",
            }
        ]
    }

    results = api.process_push_data(payload, existing_metrics=existing_metrics)

    assert "INV123" in results
    metrics = results["INV123"]["metrics"]

    # Incoming push value updated
    assert metrics["ph1Loadp"] == "500.0"
    # Existing metrics preserved
    assert metrics["ph2Loadp"] == 300.0
    assert metrics["ph3Loadp"] == 200.0
    assert metrics["gridP"] == "-1.0"

    # Derived metrics calculated on the fully merged metrics map:
    # home_load = ph1Loadp + ph2Loadp + ph3Loadp = 500 + 300 + 200 = 1000.0
    assert metrics["home_load"] == 1000.0
    assert metrics["grid_import"] == 1000.0
    assert metrics["grid_export"] == 0.0


def test_process_push_data_nested_format():
    """Test process_push_data correctly flattens and parses nested push telemetry payload."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    api._discovery_cache["device_info"] = {
        "INV123": {
            "model": "H5K-HT",
            "device_type_code": "HYBRID_INVERTER",
            "device_name": "My Inverter",
        }
    }

    nested_payload = {
        "dataList": [
            {
                "record": {
                    "deviceSn": "INV123",
                    "collectTime": 1717764875000,
                    "deviceState": 1,
                },
                "system": {
                    "workMode": "16",
                },
                "ac": {
                    "frequencyHz": 50.04,
                    "powerW": 644.0,
                    "energyKwh": 6.7,
                },
                "pv": {
                    "totalPowerW": 1298.88,
                    "pv1": {
                        "voltageV": 331.1,
                        "currentA": 1.75,
                        "powerW": 579.8,
                    },
                    "pv2": {
                        "voltageV": 336.8,
                        "currentA": 2.13,
                        "powerW": 719.0,
                    },
                },
                "battery": {
                    "serialNumber": "bat_sn_123",
                    "capacityKwh": 15.0,
                    "socPercent": 41,
                    "sohPercent": 100,
                    "powerW": -541,
                    "voltageV": 318.7,
                    "currentA": -1.7,
                    "temperature": {
                        "chargeTempC": 19.0,
                        "cellLowTempC": 17.0,
                    },
                    "limits": {
                        "maxChargePowerW": 9000.0,
                        "maxDischargePowerW": 9000.0,
                    },
                    "cellVoltage": {
                        "cellVoltageLowV": 3.32,
                        "cellVoltageHighV": 3.33,
                    },
                },
                "dcBus": {
                    "vbus": 783.4,
                },
                "temperatures": {
                    "inverterTempC": 36,
                },
                "phases": {
                    "ph1": {
                        "voltageV": 242.8,
                        "currentA": 1.88,
                        "powerW": 450.0,
                        "epsPowerW": 269.0,
                    }
                },
            }
        ]
    }

    results = api.process_push_data(nested_payload)
    assert "INV123" in results
    metrics = results["INV123"]["metrics"]

    assert metrics["last_seen"] == "2024-06-07T12:54:35+00:00"  # 1717764875 epoch
    assert metrics["workMode"] == "16"
    assert metrics["f"] == 50.04
    assert metrics["acP"] == 644.0
    assert metrics["acE"] == 6.7
    assert metrics["ppv"] == 1298.88
    assert metrics["pv1v"] == 331.1
    assert metrics["pv1i"] == 1.75
    assert metrics["pv1p"] == 579.8
    assert metrics["pv2v"] == 336.8
    assert metrics["pv2i"] == 2.13
    assert metrics["pv2p"] == 719.0
    assert metrics["batSn"] == "bat_sn_123"
    assert metrics["batCap"] == 15.0
    assert metrics["batSoc"] == 41
    assert metrics["batSoh"] == 100
    assert metrics["batP"] == -541
    assert metrics["batV"] == 318.7
    assert metrics["batI"] == -1.7
    assert metrics["batTch"] == 19.0
    assert metrics["batTcl"] == 17.0
    assert metrics["maxChargePower"] == 9000.0
    assert metrics["maxDischargePower"] == 9000.0
    assert metrics["batVcl"] == 3.32
    assert metrics["batVch"] == 3.33
    assert metrics["vbus"] == 783.4
    assert metrics["tinv"] == 36
    assert metrics["ph1v"] == 242.8
    assert metrics["ph1i"] == 1.88
    assert metrics["ph1p"] == 450.0
    assert metrics["ph1Loadp"] == 269.0


def test_process_push_data_flat_ms_collect_time():
    """Test process_push_data correctly parses flat telemetry with millisecond collectTime."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    api._discovery_cache["device_info"] = {
        "INV123": {
            "model": "H5K-HT",
            "device_type_code": "HYBRID_INVERTER",
            "device_name": "My Inverter",
        }
    }

    flat_payload = {
        "dataList": [
            {
                "deviceSn": "INV123",
                "collectTime": 1717764875000,
                "pv1v": 119.0,
                "pv1i": 1.2,
                "pv1p": 142.8,
            }
        ]
    }

    results = api.process_push_data(flat_payload)
    assert "INV123" in results
    metrics = results["INV123"]["metrics"]

    assert metrics["last_seen"] == "2024-06-07T12:54:35+00:00"
    assert metrics["pv1v"] == 119.0
    assert metrics["pv1i"] == 1.2
    assert metrics["pv1p"] == 142.8
