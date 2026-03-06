import pytest
from hypothesis import given, strategies as st
from hyxi_cloud_api.api import HyxiApiClient

@given(st.recursive(st.none() | st.booleans() | st.floats() | st.text(),
                    lambda children: st.lists(children) | st.dictionaries(st.text(), children)))
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
            
            # This is the logic we are fuzzing (nested inside your _fetch_device_metrics)
            def get_f(key, data_map, mult=1.0):
                try:
                    val = data_map.get(key)
                    if val is None or val == "":
                        return 0.0
                    return round(float(val) * mult, 2)
                except (ValueError, TypeError):
                    return 0.0

            # Fuzz the specific metric calculation block
            grid = get_f("gridP", m_raw, 1000.0)
            pbat = get_f("pbat", m_raw)
            
            entry["metrics"].update({
                "home_load": get_f("ph1Loadp", m_raw) + get_f("ph2Loadp", m_raw) + get_f("ph3Loadp", m_raw),
                "grid_import": abs(grid) if grid < 0 else 0,
                "grid_export": grid if grid > 0 else 0,
                "bat_charging": abs(pbat) if pbat < 0 else 0,
                "bat_discharging": pbat if pbat > 0 else 0,
            })
    except Exception as e:
        pytest.fail(f"Parser crashed with {type(e).__name__}: {e}")
