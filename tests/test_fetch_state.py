"""Tests for the FetchState dataclass."""

from src.hyxi_cloud_api.api import FetchState


def test_fetch_state_initialization():
    """Verify that FetchState initializes with correct default values."""
    state = FetchState(now="2023-10-27T10:00:00Z")

    assert state.now == "2023-10-27T10:00:00Z"
    assert not state.metric_tasks
    assert not state.discovered_sns
    assert not state.results


def test_fetch_state_isolation():
    """Verify that default factories create isolated objects per instance."""
    state1 = FetchState(now="1")
    state2 = FetchState(now="2")

    # Mutate state1
    state1.metric_tasks.append("task1")
    state1.discovered_sns.add("sn1")
    state1.results["key"] = "value"

    # Verify state2 is unaffected
    assert not state2.metric_tasks
    assert not state2.discovered_sns
    assert not state2.results


def test_fetch_state_custom_initialization():
    """Verify that FetchState can be initialized with custom values."""
    custom_tasks = ["task_a", "task_b"]
    custom_sns = {"sn_a", "sn_b"}
    custom_results = {"res_a": "value_a"}

    state = FetchState(
        now="custom_time",
        metric_tasks=custom_tasks,
        discovered_sns=custom_sns,
        results=custom_results,
    )

    assert state.now == "custom_time"
    assert state.metric_tasks == ["task_a", "task_b"]
    assert state.discovered_sns == {"sn_a", "sn_b"}
    assert state.results == {"res_a": "value_a"}
