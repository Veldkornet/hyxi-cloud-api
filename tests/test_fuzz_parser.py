from hypothesis import given, strategies as st
from hyxi_cloud_api.parser import parse_inverter_data

@given(st.recursive(st.none() | st.booleans() | st.floats() | st.text(),
                    lambda children: st.lists(children) | st.dictionaries(st.text(), children)))
def test_parse_never_crashes(data):
    """Ensure the parser handles ANY JSON-like structure without a crash."""
    try:
        parse_inverter_data(data)
    except Exception as e:
        # We only care about unhandled crashes (AttributeError, TypeError, etc.)
        # Logic errors (ValueError) are expected and safe.
        assert isinstance(e, (ValueError, KeyError))
