"""Tests for _update_discovery_cache."""

from unittest.mock import MagicMock

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
