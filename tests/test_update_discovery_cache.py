"""Tests for _update_discovery_cache."""

from unittest.mock import AsyncMock, MagicMock

from hyxi_cloud_api.api import HyxiApiClient


def test_update_discovery_cache_normal_entry():
    """A normal call stores the entry under the device's SN."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    entry = {"model": "H5K-HT", "device_type_code": "HYBRID_INVERTER"}

    api._update_discovery_cache("SN1", entry)

    assert api._discovery_cache["device_info"]["SN1"]["model"] == "H5K-HT"


def test_update_discovery_cache_corrupted_state_is_a_noop():
    """If something external ever replaces _discovery_cache['device_info']
    with a non-dict value, the guard must skip the update rather than raise
    (e.g. AttributeError on a bare 'x[sn] = ...' assignment)."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._discovery_cache["device_info"] = None

    # Must not raise.
    api._update_discovery_cache("SN1", {"model": "H5K-HT"})

    assert api._discovery_cache["device_info"] is None


def test_update_discovery_cache_keeps_enriched_fields():
    """Re-discovering a device of the same type refreshes its listed fields
    without discarding data learned from queryDeviceInfo: the detailed model,
    versions and battery info."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._discovery_cache["device_info"] = {
        "SN1": {
            "model": "Hybrid Inverter",
            "detailed_model": "HYX-H10K-HT",
            "device_type_code": "HYBRID_INVERTER",
            "device_name": "Old name",
            "info_metrics": {"hw_version": "H1"},
        }
    }

    api._update_discovery_cache(
        "SN1", {"model": "Hybrid Inverter", "device_type_code": "HYBRID_INVERTER"}
    )

    assert api._discovery_cache["device_info"]["SN1"] == {
        "model": "Hybrid Inverter",
        "detailed_model": "HYX-H10K-HT",
        "device_type_code": "HYBRID_INVERTER",
        "device_name": None,
        "sw_version": None,
        "hw_version": None,
        "info_metrics": {"hw_version": "H1"},
    }


def test_update_discovery_cache_drops_detailed_model_when_type_changes():
    """A device whose listed type changes loses the detailed model learned
    for its old type, so a stale one does not stick."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._discovery_cache["device_info"] = {
        "SN1": {
            "model": "Unknown",
            "detailed_model": "OLD-MODEL",
            "device_type_code": "UNKNOWN",
        }
    }

    api._update_discovery_cache(
        "SN1", {"model": "Hybrid Inverter", "device_type_code": "HYBRID_INVERTER"}
    )

    assert "detailed_model" not in api._discovery_cache["device_info"]["SN1"]


def test_apply_cached_device_info_without_a_cache_record():
    """With no cache record (e.g. a corrupted cache), the entry is left as
    the device list built it."""
    entry = {"model": "Hybrid Inverter", "metrics": {}}

    assert HyxiApiClient._apply_cached_device_info(entry, None) is False
    assert entry == {"model": "Hybrid Inverter", "metrics": {}}


async def test_device_info_fetch_with_a_corrupted_cache_still_fills_the_entry():
    """With no usable discovery cache, a device-info fetch still fills the
    entry it was given and does not raise."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._request = AsyncMock(
        return_value=(200, {"success": True, "data": {"swVerSys": "V1"}})
    )
    api._discovery_cache["device_info"] = None
    entry = {"model": "Hybrid Inverter", "device_type_code": "1", "metrics": {}}

    await api._fetch_device_info("SN1", entry)

    assert entry["sw_version"] == "V1"
    assert api._discovery_cache["device_info"] is None
