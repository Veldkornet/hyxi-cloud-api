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
                "grid": {
                    "powerW": -1500.0,
                    "frequencyHz": 50.02,
                    "powerFactor": 0.98,
                    "energyInKwh": 1023.4,
                    "energyOutKwh": 504.2,
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
    assert metrics["gridP"] == -1.5
    assert metrics["gridF"] == 50.02
    assert metrics["gridPfd"] == 0.98
    assert metrics["totalEnt"] == 1023.4
    assert metrics["totalEpt"] == 504.2
    assert metrics["grid_import"] == 1500.0
    assert metrics["grid_export"] == 0.0


def test_process_push_data_nested_format_ems_device_grid_unaffected():
    """Nested-format EMS/Micro ESS push payloads must NOT be double-corrected
    by _normalize_micro_ess_gridp (GitHub issue #654).

    The nested push format's grid.powerW is real Watts and is already
    converted to kW by _flatten_nested_push_device regardless of device
    type, so _compute_grid_metrics must keep applying its normal kW->W
    multiplier here even for an EMS-classified device.
    """
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    api._discovery_cache["device_info"] = {
        "HALO123": {
            "model": "Halo",
            "device_type_code": "MICRO_STORAGE_ALL_IN_ONE",
            "device_name": "My Halo",
        }
    }

    nested_payload = {
        "dataList": [
            {
                "record": {"deviceSn": "HALO123", "collectTime": 1717764875000},
                "grid": {"powerW": -811.0},
            }
        ]
    }

    results = api.process_push_data(nested_payload)
    metrics = results["HALO123"]["metrics"]

    assert metrics["gridP"] == -0.811
    assert metrics["grid_import"] == 811.0
    assert metrics["grid_export"] == 0.0


def test_process_push_data_flat_format_ems_device_gridp_watts_normalized():
    """Flat-format EMS/Micro ESS push payloads carry gridP unconverted (no
    nested "grid" object to catch it), so they need the same Watts->kW
    normalization as the REST poll path -- otherwise this reproduces the
    exact GitHub issue #654 bug via push instead of REST.
    """
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    api._discovery_cache["device_info"] = {
        "HALO123": {
            "model": "Halo",
            "device_type_code": "MICRO_STORAGE_ALL_IN_ONE",
            "device_name": "My Halo",
        }
    }

    flat_payload = {
        "dataList": [
            {
                "deviceSn": "HALO123",
                "collectTime": 1717764875,
                "gridP": "811.0",
                "gridQ": "26.0",
                "batP": "878",
            }
        ]
    }

    results = api.process_push_data(flat_payload)
    metrics = results["HALO123"]["metrics"]

    assert metrics["gridP"] == 0.811
    assert metrics["grid_import"] == 0.0
    assert metrics["grid_export"] == 811.0


def test_process_push_data_nested_grid_without_powerw_still_normalized():
    """A nested "grid" object without a usable "powerW" (e.g. only
    frequencyHz) must NOT be mistaken for "gridP was already converted" --
    a stray flat gridP in the same payload still needs normalizing.

    Regression test for a review finding on the fix for GitHub issue #654:
    the original check (isinstance(device.get("grid"), dict)) treated any
    nested grid object as proof of conversion, even when that object never
    actually populated gridP.
    """
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    api._discovery_cache["device_info"] = {
        "HALO123": {
            "model": "Halo",
            "device_type_code": "MICRO_STORAGE_ALL_IN_ONE",
            "device_name": "My Halo",
        }
    }

    payload = {
        "dataList": [
            {
                "deviceSn": "HALO123",
                "collectTime": 1717764875,
                "gridP": "811.0",
                "grid": {"frequencyHz": 50.0},  # no "powerW"
            }
        ]
    }

    results = api.process_push_data(payload)
    metrics = results["HALO123"]["metrics"]

    assert metrics["gridP"] == 0.811
    assert metrics["grid_export"] == 811.0


def test_process_push_data_cell_voltages_normalized_from_millivolts():
    """A flat push payload with batVch/batVcl in millivolts is scaled to
    volts, the same as the REST poll path.
    """
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

    api._discovery_cache["device_info"] = {
        "INV123": {
            "model": "HYX-H10K-HT",
            "device_type_code": "HYBRID_INVERTER",
            "device_name": "My Inverter",
        }
    }

    payload = {
        "dataList": [
            {
                "deviceSn": "INV123",
                "collectTime": 1717764875,
                "batVch": "3203.0",
                "batVcl": "3.19",
            }
        ]
    }

    metrics = api.process_push_data(payload)["INV123"]["metrics"]

    assert metrics["batVch"] == 3.203
    assert metrics["batVcl"] == 3.19


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


def test_process_push_data_invalid_time_formats():
    """Test process_push_data correctly handles ValueError and TypeError when parsing timestamps."""

    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._discovery_cache["device_info"] = {
        "TEST_DEV": {
            "model": "TEST",
            "device_type_code": "TEST_TYPE",
            "device_name": "Test Device",
        }
    }

    # Test invalid collectTime (ValueError)
    payload_invalid_collect_time = {
        "dataList": [
            {
                "deviceSn": "TEST_DEV",
                "collectTime": "invalid-time",
            }
        ]
    }

    # Test invalid collectTime (TypeError)
    payload_type_err_collect_time = {
        "dataList": [
            {
                "deviceSn": "TEST_DEV",
                "collectTime": {"a": "b"},
            }
        ]
    }

    # Test invalid reportTimestamp (ValueError)
    payload_invalid_report_ts = {
        "dataList": [
            {
                "deviceSn": "TEST_DEV",
                "reportTimestamp": "invalid-time",
            }
        ]
    }

    # Test invalid reportTimestamp (TypeError)
    payload_type_err_report_ts = {
        "dataList": [
            {
                "deviceSn": "TEST_DEV",
                "reportTimestamp": {"a": "b"},
            }
        ]
    }

    res1 = api.process_push_data(payload_invalid_collect_time)
    res2 = api.process_push_data(payload_type_err_collect_time)
    res3 = api.process_push_data(payload_invalid_report_ts)
    res4 = api.process_push_data(payload_type_err_report_ts)

    # Check that last_seen was not updated to a specific time, but fell back to now_utc
    # In api.process_push_data, if it fails, last_seen = now_utc
    assert "last_seen" in res1["TEST_DEV"]["metrics"]
    assert "last_seen" in res2["TEST_DEV"]["metrics"]
    assert "last_seen" in res3["TEST_DEV"]["metrics"]
    assert "last_seen" in res4["TEST_DEV"]["metrics"]
