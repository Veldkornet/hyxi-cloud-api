"""Tests for _merge_push_metrics."""

from hyxi_cloud_api.api import _merge_push_metrics


def test_merge_push_metrics_skips_none_values():
    """A None value in raw_metrics must not overwrite/seed the merged dict --
    None means 'the push payload didn't report this metric', not 'set it to
    None'."""
    merged = _merge_push_metrics("SN1", {"acP": None, "batSoc": 55}, "INVERTER", None)
    assert "acP" not in merged
    assert merged["batSoc"] == 55


def test_merge_push_metrics_overlays_onto_existing():
    """New metrics are layered on top of a copy of the existing entry for
    that SN, without mutating the caller's existing_metrics dict."""
    existing = {"SN1": {"batSoc": 40, "acP": 100}}
    merged = _merge_push_metrics("SN1", {"acP": 120}, "INVERTER", existing)

    assert merged == {"batSoc": 40, "acP": 120}
    # The caller's dict is untouched.
    assert existing["SN1"] == {"batSoc": 40, "acP": 100}


def test_merge_push_metrics_no_existing_entry_for_sn():
    """A SN with no prior entry in existing_metrics starts from an empty base."""
    existing = {"OTHER_SN": {"batSoc": 40}}
    merged = _merge_push_metrics("SN1", {"acP": 100}, "INVERTER", existing)
    assert merged == {"acP": 100}


def test_merge_push_metrics_filters_battery_keys_for_collector():
    """Collectors strip battery/power keys that shouldn't be present on them."""
    merged = _merge_push_metrics(
        "COLL1", {"batSoc": 55, "totalEnt": 10}, "COLLECTOR", None
    )
    assert "batSoc" not in merged
    assert merged["totalEnt"] == 10
