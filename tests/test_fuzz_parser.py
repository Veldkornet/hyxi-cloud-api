from hypothesis import given, strategies as st
from hyxi_cloud_api.parser import parse_inverter_data
import pytest

@given(st.recursive(st.none() | st.booleans() | st.floats() | st.text(),
                    lambda children: st.lists(children) | st.dictionaries(st.text(), children)))
def test_parse_never_crashes(data):
    """Ensure the parser handles ANY JSON-like structure without a crash."""
    try:
        parse_inverter_data(data)
    except (ValueError, KeyError):
        # These are "graceful" failures. The parser recognized the data was 
        # bad and handled it correctly.
        pass
    except Exception as e:
        # If we hit an AttributeError, TypeError, or ZeroDivisionError, 
        # that's a real bug! We want pytest to report the exact exception.
        pytest.fail(f"Parser crashed with unexpected {type(e).__name__}: {e}")
