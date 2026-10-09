"""Tests for the HYXI Cloud discovery caching mechanism."""

import time
from unittest.mock import AsyncMock, patch

import pytest

from hyxi_cloud_api import HyxiApiClient
from hyxi_cloud_api.api import INCOMPLETE_DISCOVERY_RETRY, FetchState


@pytest.mark.asyncio
async def test_discovery_caching_logic():
    """Verify that subsequent calls use the cache and skip discovery endpoints."""
    session = AsyncMock()
    client = HyxiApiClient("key", "secret", "http://api.com", session)

    # Mock token
    client.token = "Bearer test"
    client.token_expires_at = time.time() + 3600

    # Mock responses for full discovery
    plant_resp = {"success": True, "data": {"list": [{"plantId": "P1"}]}}
    device_resp = {
        "success": True,
        "data": {"deviceList": [{"deviceSn": "S1", "deviceType": "HYBRID_INVERTER"}]},
    }
    info_resp = {"success": True, "data": {"swVerSys": "V1", "hwVer": "H1"}}
    metrics_resp = {"success": True, "data": [{"dataKey": "gridP", "dataValue": "100"}]}
    alarms_resp = {"success": True, "data": {"pageData": []}}
    sub_dev_resp = {"success": True, "data": {"childDevice": []}}

    # Setup the sequence of responses for the first (full) call
    # 1. Plants
    # 2. Devices for Plant
    # 3. Sub-devices for Inverter
    # 4. Alarms for Plant
    # 5. Info for Inverter
    # 6. Metrics for Inverter

    with patch.object(client, "_request") as mock_req:
        mock_req.side_effect = [
            (200, plant_resp),
            (200, device_resp),
            (200, sub_dev_resp),
            (200, alarms_resp),
            (200, info_resp),
            (200, metrics_resp),
        ]

        # First call: Full Discovery
        res1 = await client.get_all_device_data()
        assert res1["data"]["S1"]["sw_version"] == "V1"
        assert mock_req.call_count == 6

        # Second call: Should use cache (Fast Poll). Static device info is
        # served from the cache, so only alarms and metrics are requested.
        mock_req.reset_mock()
        mock_req.side_effect = [
            (200, alarms_resp),
            (200, metrics_resp),
        ]

        res2 = await client.get_all_device_data()
        assert res2["data"]["S1"]["sw_version"] == "V1"  # Still there from cache
        assert res2["data"]["S1"]["metrics"]["_sw_ver_sys"] == "V1"
        assert mock_req.call_count == 2

        # Verify specific URL paths for fast poll
        calls = mock_req.call_args_list
        assert calls[0][0][1] == "/api/alarm/v1/plantAlarmPage"
        assert calls[1][0][1] == "/api/device/v2/queryDeviceData"

        # Third call: Force discovery
        mock_req.reset_mock()
        mock_req.side_effect = [
            (200, plant_resp),
            (200, device_resp),
            (200, sub_dev_resp),
            (200, alarms_resp),
            (200, info_resp),
            (200, metrics_resp),
        ]
        await client.get_all_device_data(force_discovery=True)
        assert mock_req.call_count == 6


@pytest.mark.asyncio
async def test_execute_fetch_cached_no_device_info():
    """Verify _execute_fetch_cached handles missing device_info without errors."""
    session = AsyncMock()
    client = HyxiApiClient("key", "secret", "http://api.com", session)

    # Empty cache
    client._discovery_cache = {
        "plants": [{"plantId": "P1"}],
        "device_info": None,
    }

    state = FetchState(now="2023-01-01T00:00:00Z")

    with (
        patch.object(client, "_build_plant_tasks", return_value=([], [])) as mock_build,
        patch.object(
            client, "_fetch_and_process_alarms", return_value={}
        ) as mock_alarms,
        patch.object(
            client, "_execute_metric_tasks", new_callable=AsyncMock
        ) as mock_exec,
    ):
        results = await client._execute_fetch_cached(state, allow_back_discovery=True)

        # Verify it runs without error and executes the next steps
        assert results == {}
        assert len(state.metric_tasks) == 0
        mock_build.assert_called_once()
        mock_alarms.assert_called_once()
        mock_exec.assert_called_once()


@pytest.mark.asyncio
async def test_execute_fetch_cached_empty_cache():
    """Verify _execute_fetch_cached handles fully empty cache without errors."""
    session = AsyncMock()
    client = HyxiApiClient("key", "secret", "http://api.com", session)

    # Fully empty cache
    client._discovery_cache = {}

    state = FetchState(now="2023-01-01T00:00:00Z")

    with (
        patch.object(client, "_build_plant_tasks", return_value=([], [])) as mock_build,
        patch.object(
            client, "_fetch_and_process_alarms", return_value={}
        ) as mock_alarms,
        patch.object(
            client, "_execute_metric_tasks", new_callable=AsyncMock
        ) as mock_exec,
    ):
        results = await client._execute_fetch_cached(state, allow_back_discovery=True)

        # Verify it runs without error and executes the next steps
        assert results == {}
        assert not state.plants
        assert len(state.metric_tasks) == 0
        mock_build.assert_called_once()
        mock_alarms.assert_called_once()
        mock_exec.assert_called_once()


def _discovery_client(device_lists, sub_device_lists=None, device_info=None):
    """A client whose _request answers discovery calls by path.

    device_lists maps plantId -> list of device dicts, an Exception to raise
    for that plant's devicePage call, or "rejected" for a success:false
    answer. sub_device_lists maps parentSn the same way (default: no
    children). device_info maps SN -> queryDeviceInfo data, or an Exception
    to raise (default: empty data). All three are read on every call, so
    tests can change them between polls. Each devicePage call appends the device types cached at that
    moment to client._request.device_types_seen.
    """
    client = HyxiApiClient("key", "secret", "http://api.com", AsyncMock())
    client.token = "Bearer test"
    client.token_expires_at = time.time() + 3600
    sub_device_lists = sub_device_lists or {}
    device_info = {} if device_info is None else device_info
    device_types_seen = []

    def answer(value, key):
        if isinstance(value, Exception):
            raise value
        if value == "rejected":
            return 200, {"success": False, "code": "B000001", "msg": "denied"}
        return 200, {"success": True, "data": {key: value}}

    async def fake_request(method, path, **kwargs):
        body = kwargs.get("json") or {}
        if path == "/api/plant/v1/page":
            plants = [{"plantId": pid} for pid in device_lists]
            return 200, {"success": True, "data": {"list": plants}}
        if path == "/api/plant/v1/devicePage":
            device_types_seen.append(
                {
                    sn: info.get("device_type_code")
                    for sn, info in client._discovery_cache["device_info"].items()
                }
            )
            return answer(device_lists[body["plantId"]], "deviceList")
        if path == "/api/device/v1/getSubDevicePage":
            return answer(sub_device_lists.get(body["parentSn"], []), "childDevice")
        if path == "/api/device/v1/queryDeviceInfo":
            info = device_info.get(kwargs["params"]["deviceSn"], {})
            if isinstance(info, Exception):
                raise info
            return 200, {"success": True, "data": info}
        if path == "/api/alarm/v1/plantAlarmPage":
            return 200, {"success": True, "data": {"pageData": []}}
        return 200, {"success": True, "data": {}}

    client._request = AsyncMock(side_effect=fake_request)
    client._request.device_types_seen = device_types_seen
    return client


def _inverter(sn):
    return {"deviceSn": sn, "deviceType": "HYBRID_INVERTER"}


def _known():
    """A device_info entry as an earlier discovery would have left it."""
    return {"model": "Hybrid Inverter", "device_type_code": "HYBRID_INVERTER"}


def _seconds_until_rediscovery(client):
    return client._discovery_cache_expires_at - time.time()


def _paths(client):
    return [c.args[1] for c in client._request.call_args_list]


@pytest.mark.asyncio
async def test_failed_device_list_falls_back_to_known_devices(monkeypatch):
    """When the device list times out, the same attempt polls the devices an
    earlier discovery found instead of returning nothing, and full discovery
    is retried before the normal TTL."""
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    client = _discovery_client({"P1": TimeoutError()})
    client._discovery_cache["device_info"] = {"S1": _known()}

    result = await client.get_all_device_data()

    assert set(result["data"]) == {"S1"}
    assert result["attempts"] == 1
    assert _paths(client).count("/api/plant/v1/page") == 1
    assert 0 < _seconds_until_rediscovery(client) <= INCOMPLETE_DISCOVERY_RETRY


@pytest.mark.asyncio
async def test_failed_device_list_with_nothing_known_runs_discovery_once(
    monkeypatch,
):
    """With no previously known devices, a failed device list runs full
    discovery once per cycle, not once per retry attempt."""
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    client = _discovery_client({"P1": TimeoutError()})

    result = await client.get_all_device_data()

    assert result["data"] == {}
    assert _paths(client).count("/api/plant/v1/page") == 1
    assert 0 < _seconds_until_rediscovery(client) <= INCOMPLETE_DISCOVERY_RETRY


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "device_lists, sub_device_lists",
    [
        ({"P1": [_inverter("S1")], "P2": TimeoutError()}, None),
        ({"P1": [_inverter("S1")], "P2": "rejected"}, None),
        ({"P1": [_inverter("S1")]}, {"S1": TimeoutError()}),
        ({"P1": [_inverter("S1")]}, {"S1": "rejected"}),
    ],
    ids=[
        "device-list-timeout",
        "device-list-rejected",
        "sub-device-timeout",
        "sub-device-rejected",
    ],
)
async def test_incomplete_discovery_keeps_known_devices(device_lists, sub_device_lists):
    """A device or sub-device list that fails or is rejected keeps devices
    known from earlier discoveries -- still polled and returned this cycle --
    and schedules an early rediscovery."""
    client = _discovery_client(device_lists, sub_device_lists)
    client._discovery_cache["device_info"] = {"OLD": _known()}

    result = await client.get_all_device_data()

    assert set(result["data"]) == {"S1", "OLD"}
    assert _paths(client).count("/api/device/v2/queryDeviceData") == 2
    assert set(client._discovery_cache["device_info"]) == {"S1", "OLD"}
    assert 0 < _seconds_until_rediscovery(client) <= INCOMPLETE_DISCOVERY_RETRY


@pytest.mark.asyncio
async def test_incomplete_discovery_retry_backs_off_and_resets():
    """While discovery stays incomplete the retry delay doubles up to the
    cache TTL; a complete discovery restores the full TTL and the delay."""
    device_lists = {"P1": [_inverter("S1")], "P2": "rejected"}
    client = _discovery_client(device_lists)
    ttl = client._discovery_cache_ttl

    delays = []
    for _ in range(6):
        await client.get_all_device_data(force_discovery=True)
        delays.append(round(_seconds_until_rediscovery(client), -1))

    expected = [min(INCOMPLETE_DISCOVERY_RETRY * 2**i, ttl) for i in range(6)]
    assert delays == expected

    device_lists["P2"] = []
    await client.get_all_device_data(force_discovery=True)

    assert round(_seconds_until_rediscovery(client), -1) == ttl
    assert client._incomplete_discovery_retry == INCOMPLETE_DISCOVERY_RETRY


@pytest.mark.asyncio
async def test_complete_discovery_prunes_unlisted_devices():
    """A complete discovery commits the cache for the full TTL and drops
    devices that are no longer listed."""
    client = _discovery_client({"P1": [_inverter("S1")]})
    client._discovery_cache["device_info"] = {"GONE": _known()}

    await client.get_all_device_data()

    assert _seconds_until_rediscovery(client) > INCOMPLETE_DISCOVERY_RETRY
    assert set(client._discovery_cache["device_info"]) == {"S1"}


@pytest.mark.asyncio
async def test_device_types_stay_available_while_discovery_runs():
    """Full discovery keeps device_info populated while the device lists are
    being fetched, so push processing can still resolve device types."""
    client = _discovery_client({"P1": [_inverter("S1")]})
    client._discovery_cache["device_info"] = {"S1": _known()}

    await client.get_all_device_data()

    assert client._request.device_types_seen == [{"S1": "HYBRID_INVERTER"}]


@pytest.mark.asyncio
async def test_cached_poll_reuses_device_info_only_for_static_devices():
    """After a full discovery, a cached poll reuses device info for a device
    with static info -- keeping its detailed model, versions and battery
    details -- but fetches it again for a collector, a device reporting a
    live Wi-Fi signal, and a device whose info came back empty."""
    client = HyxiApiClient("key", "secret", "http://api.com", AsyncMock())
    client.token = "Bearer test"
    client.token_expires_at = time.time() + 3600
    devices = [
        {"deviceSn": "INV", "deviceType": "HYBRID_INVERTER"},
        {"deviceSn": "WIFI", "deviceType": "MICRO_STORAGE_ALL_IN_ONE"},
        {"deviceSn": "COL", "deviceType": "COLLECTOR"},
        {"deviceSn": "EMPTY", "deviceType": "HYBRID_INVERTER"},
    ]
    device_info = {
        "INV": {"model": "HYX-H10K-HT", "swVerSys": "V1", "batCap": "10"},
        "WIFI": {"swVerSys": "V2", "signalVal": "-60"},
        "COL": {"swVerSys": "W1", "signalIntensity": "3"},
        "EMPTY": None,
    }
    info_requests = []

    async def fake_request(method, path, **kwargs):
        sn = (kwargs.get("params") or {}).get("deviceSn")
        if path == "/api/plant/v1/page":
            return 200, {"success": True, "data": {"list": [{"plantId": "P1"}]}}
        if path == "/api/plant/v1/devicePage":
            return 200, {"success": True, "data": {"deviceList": devices}}
        if path == "/api/device/v1/queryDeviceInfo":
            info_requests.append(sn)
            return 200, {"success": True, "data": device_info[sn]}
        if path == "/api/alarm/v1/plantAlarmPage":
            return 200, {"success": True, "data": {"pageData": []}}
        return 200, {"success": True, "data": {}}

    client._request = AsyncMock(side_effect=fake_request)
    await client.get_all_device_data()
    info_requests.clear()

    result = await client.get_all_device_data()

    assert set(info_requests) == {"WIFI", "COL", "EMPTY"}
    inv = result["data"]["INV"]
    assert inv["model"] == "HYX-H10K-HT"
    assert inv["sw_version"] == "V1"
    assert inv["metrics"]["batCap"] == 10.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data, expect_info_metrics",
    [({"model": "HYX-H10K-HT", "swVerSys": "V1"}, True), (None, False)],
    ids=["with-data", "empty-data"],
)
async def test_device_info_fetch_caches_detailed_model_and_info(
    data, expect_info_metrics
):
    """A device-info fetch stores the detailed model alongside the device
    list's generic one, and stores the info for reuse only when the response
    actually carried data."""
    client = HyxiApiClient("key", "secret", "http://api.com", AsyncMock())
    client._request = AsyncMock(return_value=(200, {"success": True, "data": data}))
    client._discovery_cache["device_info"]["S1"] = {
        "model": "Hybrid Inverter",
        "device_type_code": "HYBRID_INVERTER",
    }
    entry = {
        "model": "Hybrid Inverter",
        "device_type_code": "HYBRID_INVERTER",
        "metrics": {},
    }

    await client._fetch_device_info("S1", entry)

    cached = client._discovery_cache["device_info"]["S1"]
    assert cached["model"] == "Hybrid Inverter"
    assert cached.get("detailed_model") == (data or {}).get("model")
    assert ("info_metrics" in cached) is expect_info_metrics


@pytest.mark.asyncio
async def test_detailed_model_survives_a_failed_info_refresh():
    """If a later full discovery's device-info request fails, that poll and
    the cached polls after it keep the detailed model and versions learned
    earlier instead of falling back to the device list's generic values."""
    device_info = {"INV": {"model": "HYX-H10K-HT", "swVerSys": "V1"}}
    client = _discovery_client({"P1": [_inverter("INV")]}, device_info=device_info)
    await client.get_all_device_data()

    device_info["INV"] = TimeoutError()
    rediscovered = await client.get_all_device_data(force_discovery=True)
    cached_poll = await client.get_all_device_data()

    for poll in (rediscovered, cached_poll):
        assert poll["data"]["INV"]["model"] == "HYX-H10K-HT"
        assert poll["data"]["INV"]["sw_version"] == "V1"
