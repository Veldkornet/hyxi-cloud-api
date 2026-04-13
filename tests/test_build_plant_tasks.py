import sys
from unittest.mock import MagicMock

if "aiohttp" not in sys.modules or not hasattr(sys.modules["aiohttp"], "ClientError"):
    m = MagicMock()

    class MockExp(Exception):
        def __init__(self, *args, **kwargs):
            super().__init__(*args)
            for k, v in kwargs.items():
                setattr(self, k, v)

    m.ClientError = MockExp
    m.ClientResponseError = type("ClientResponseError", (MockExp,), {})
    m.ContentTypeError = type("ContentTypeError", (MockExp,), {})
    sys.modules["aiohttp"] = m
mock_aiohttp = sys.modules["aiohttp"]

from src.hyxi_cloud_api.api import FetchState, HyxiApiClient


def _setup_mock_api():
    """Helper to set up a mock API client for testing _build_plant_tasks."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._fetch_devices_for_plant = MagicMock(
        side_effect=lambda pid, state: f"device_task_{pid}"
    )
    api._fetch_alarms_for_plant = MagicMock(side_effect=lambda pid: f"alarm_task_{pid}")
    return api


def test_build_plant_tasks_with_devices():
    """Test building tasks when including devices."""
    api = _setup_mock_api()
    state = FetchState(now="now")
    state.plants = [{"plantId": "p1"}, {"plantId": "p2"}]

    device_tasks, alarm_tasks = api._build_plant_tasks(state, include_devices=True)

    assert device_tasks == ["device_task_p1", "device_task_p2"]
    assert alarm_tasks == ["alarm_task_p1", "alarm_task_p2"]
    api._fetch_devices_for_plant.assert_any_call("p1", state)
    api._fetch_devices_for_plant.assert_any_call("p2", state)
    api._fetch_alarms_for_plant.assert_any_call("p1")
    api._fetch_alarms_for_plant.assert_any_call("p2")


def test_build_plant_tasks_without_devices():
    """Test building tasks without including devices."""
    api = _setup_mock_api()
    state = FetchState(now="now")
    state.plants = [{"plantId": "p1"}]

    device_tasks, alarm_tasks = api._build_plant_tasks(state, include_devices=False)

    assert not device_tasks
    assert alarm_tasks == ["alarm_task_p1"]
    api._fetch_devices_for_plant.assert_not_called()
    api._fetch_alarms_for_plant.assert_called_once_with("p1")


def test_build_plant_tasks_missing_plant_id():
    """Test handling plants that are missing a plantId."""
    api = _setup_mock_api()
    state = FetchState(now="now")
    state.plants = [{"name": "Missing ID Plant"}, {"plantId": "p1"}]

    device_tasks, alarm_tasks = api._build_plant_tasks(state, include_devices=True)

    assert device_tasks == ["device_task_p1"]
    assert alarm_tasks == ["alarm_task_p1"]
    assert api._fetch_devices_for_plant.call_count == 1
    assert api._fetch_alarms_for_plant.call_count == 1


def test_build_plant_tasks_empty_plants():
    """Test handling an empty list of plants."""
    api = _setup_mock_api()
    state = FetchState(now="now")
    state.plants = []

    device_tasks, alarm_tasks = api._build_plant_tasks(state, include_devices=True)

    assert not device_tasks
    assert not alarm_tasks
    api._fetch_devices_for_plant.assert_not_called()
    api._fetch_alarms_for_plant.assert_not_called()
