"""Hypothesis fuzz tests for API component parsing logic."""

import pytest
from hypothesis import given, strategies as st
from src.hyxi_cloud_api.api import HyxiApiClient, _get_f


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

            # Fuzz the specific metric calculation block using the real function
            grid = _get_f("gridP", m_raw, 1000.0)
            pbat = _get_f("pbat", m_raw)

            entry["metrics"].update(
                {
                    "home_load": _get_f("ph1Loadp", m_raw)
                    + _get_f("ph2Loadp", m_raw)
                    + _get_f("ph3Loadp", m_raw),
                    "grid_import": abs(grid) if grid < 0 else 0,
                    "grid_export": grid if grid > 0 else 0,
                    "bat_charging": abs(pbat) if pbat < 0 else 0,
                    "bat_discharging": pbat if pbat > 0 else 0,
                }
            )
    except Exception as e:
        pytest.fail(f"Parser crashed with {type(e).__name__}: {e}")
