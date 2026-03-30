"""Hypothesis fuzz tests for API component parsing logic."""

import pytest
from hypothesis import given, strategies as st
from hyxi_cloud_api.api import HyxiApiClient, _compute_derived_metrics


@given(
    st.recursive(
        st.none() | st.booleans() | st.floats() | st.text(),
        lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    )
)
def test_metric_parsing_never_crashes(data):
    """
    Test the internal dictionary-to-metrics logic.
    We mock the client to avoid actual network calls.
    """
    # 1. Create a dummy client (we won't actually use the session)
    _client = HyxiApiClient("key", "secret", "http://localhost", None)

    # 2. Create a dummy entry structure like the one in your _execute_fetch_all
    entry = {"metrics": {}, "device_type_code": "INVERTER"}

    # 3. Simulate what happens in _fetch_device_metrics
    # Your code does: m_raw = {item.get("dataKey"): item.get("dataValue") for item in data ...}
    try:
        if isinstance(data, list):
            m_raw = {
                item.get("dataKey"): item.get("dataValue")
                for item in data
                if isinstance(item, dict) and item.get("dataKey")
            }

            # Use the real function so fuzz tests always cover the current implementation.
            # This ensures batP / pbat priority logic is also exercised.
            entry["metrics"].update(_compute_derived_metrics(m_raw))
    except Exception as e:
        pytest.fail(f"Parser crashed with {type(e).__name__}: {e}")
