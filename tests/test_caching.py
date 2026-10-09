"""Tests for the HYXI Cloud discovery caching mechanism."""

import asyncio
import logging
import time
from unittest.mock import AsyncMock, patch

import pytest

from hyxi_cloud_api import HyxiApiClient
from hyxi_cloud_api.api import (
    _FETCH_ALARMS,
    _FETCH_METRICS,
    INCOMPLETE_DISCOVERY_RETRY,
    DiscoveryResult,
    TokenRejectedError,
)


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

    # The first (full) call discovers -- plants, the plant's devices, the
    # inverter's sub-devices and its device info -- then polls alarms and
    # metrics.
    full_cycle = [
        (200, plant_resp),
        (200, device_resp),
        (200, sub_dev_resp),
        (200, info_resp),
        (200, alarms_resp),
        (200, metrics_resp),
    ]

    with patch.object(client, "_request") as mock_req:
        mock_req.side_effect = list(full_cycle)

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
        mock_req.side_effect = list(full_cycle)
        await client.get_all_device_data(force_discovery=True)
        assert mock_req.call_count == 6


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cache",
    [{"plants": [{"plantId": "P1"}], "device_info": None}, {}],
    ids=["no-device-info", "empty-cache"],
)
async def test_poll_devices_without_an_inventory_returns_nothing(cache):
    """Polling with no device inventory returns no devices rather than
    raising, and does not run a discovery itself."""
    client = HyxiApiClient("key", "secret", "http://api.com", AsyncMock())
    client.ensure_token = AsyncMock()
    client._discover = AsyncMock()
    client._fetch_and_process_alarms = AsyncMock(return_value=[])
    client._discovery_cache = cache

    assert await client.poll_devices() == {}
    client._discover.assert_not_awaited()


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


@pytest.mark.asyncio
async def test_complete_discovery_forgets_failures_of_removed_subjects(caplog):
    """A complete discovery drops failure state for devices and plants it no
    longer lists, keeps it for ones still listed and still failing, and a
    removed device that fails again is reported in full."""
    caplog.set_level(logging.DEBUG, logger="hyxi_cloud_api.api")
    client = _discovery_client({"P1": [_inverter("S1")]})
    discovery = client._request.side_effect
    rejected = (200, {"success": False, "code": "X"})

    async def still_failing(method, path, **kwargs):
        if path in ("/api/device/v2/queryDeviceData", "/api/alarm/v1/plantAlarmPage"):
            return rejected
        return await discovery(method, path, **kwargs)

    client._request = AsyncMock(side_effect=still_failing)
    client._failing_fetches = {
        (_FETCH_METRICS, "S1"): "rejected:X",
        (_FETCH_METRICS, "GONE"): "rejected:X",
        (_FETCH_ALARMS, "P1"): "rejected:X",
        (_FETCH_ALARMS, "OLD_PLANT"): "rejected:X",
    }

    await client.get_all_device_data()

    assert set(client._failing_fetches) == {
        (_FETCH_METRICS, "S1"),
        (_FETCH_ALARMS, "P1"),
    }

    caplog.clear()
    await client._fetch_device_metrics("GONE", {"metrics": {}})
    assert [
        r.levelname for r in caplog.records if "rejected for" in r.getMessage()
    ] == ["WARNING"]


@pytest.mark.asyncio
async def test_discover_devices_reports_the_inventory():
    """discover_devices returns each discovered device with its detailed
    model and versions from device info."""
    device_info = {"S1": {"model": "HYX-H10K-HT", "swVerSys": "V1", "hwVer": "H1"}}
    client = _discovery_client({"P1": [_inverter("S1")]}, device_info=device_info)

    result = await client.discover_devices()

    assert result.complete
    assert result.devices == {
        "S1": {
            "sn": "S1",
            "device_name": "Hybrid Inverter S1",
            "model": "HYX-H10K-HT",
            "device_type_code": "HYBRID_INVERTER",
            "sw_version": "V1",
            "hw_version": "H1",
        }
    }


@pytest.mark.asyncio
async def test_incomplete_discover_devices_keeps_known_devices():
    """An incomplete discovery reports complete=False and keeps devices
    that an earlier discovery found."""
    client = _discovery_client({"P1": TimeoutError()})
    client._discovery_cache["device_info"] = {"OLD": _known()}

    result = await client.discover_devices()

    assert not result.complete
    assert set(result.devices) == {"OLD"}


@pytest.mark.asyncio
async def test_discover_devices_with_a_corrupted_cache_reports_no_devices():
    """A device-info cache that is not a dict yields an empty inventory."""
    client = _discovery_client({})
    client._fetch_plants = AsyncMock(return_value=None)
    client._discovery_cache["device_info"] = None

    result = await client.discover_devices()

    assert result == DiscoveryResult(devices={}, complete=False)


@pytest.mark.asyncio
async def test_poll_devices_does_not_rediscover_a_known_inventory():
    """Once devices are known, poll_devices only polls them."""
    client = _discovery_client({"P1": [_inverter("S1")]})
    await client.discover_devices()
    client._request.reset_mock()

    result = await client.poll_devices()

    assert set(result) == {"S1"}
    assert "/api/plant/v1/page" not in _paths(client)
    assert "/api/plant/v1/devicePage" not in _paths(client)


@pytest.mark.asyncio
async def test_discover_devices_keeps_devices_known_only_from_alarms():
    """With back-discovery enabled, a device that appears only in alarms is
    part of the discovered inventory, so discovery does not prune it."""
    client = _discovery_client({"P1": [_inverter("S1")]})
    alarm = {"deviceSn": "HIDDEN1", "deviceType": "HYBRID_INVERTER"}
    discovery = client._request.side_effect

    async def with_alarm(method, path, **kwargs):
        if path == "/api/alarm/v1/plantAlarmPage":
            return 200, {"success": True, "data": {"pageData": [alarm]}}
        return await discovery(method, path, **kwargs)

    client._request = AsyncMock(side_effect=with_alarm)
    client._discovery_cache["device_info"] = {"HIDDEN1": _known()}

    result = await client.discover_devices(allow_back_discovery=True)

    assert set(result.devices) == {"S1", "HIDDEN1"}


@pytest.mark.asyncio
async def test_discover_devices_keeps_versions_of_live_info_devices():
    """A collector's device info is not reusable between polls, but the
    versions it reported are still part of the inventory."""
    collector = {"deviceSn": "COL", "deviceType": "COLLECTOR"}
    device_info = {"COL": {"swVerSys": "W1", "hwVer": "H2", "signalIntensity": "3"}}
    client = _discovery_client({"P1": [collector]}, device_info=device_info)

    result = await client.discover_devices()

    assert result.devices["COL"]["sw_version"] == "W1"
    assert result.devices["COL"]["hw_version"] == "H2"


@pytest.mark.asyncio
async def test_rejected_plant_list_does_not_advance_the_retry_backoff():
    """A rejected plant list leaves the incomplete-discovery backoff alone, so
    the caller's retries do not multiply it."""
    client = _discovery_client({})
    client._fetch_plants = AsyncMock(return_value=None)

    for _ in range(3):
        result = await client.discover_devices()

    assert not result.complete
    assert client._incomplete_discovery_retry == INCOMPLETE_DISCOVERY_RETRY


@pytest.mark.asyncio
async def test_discover_devices_tolerates_a_corrupted_cache_with_plants():
    """A device-info cache that is not a dict does not crash a discovery
    that lists devices."""
    client = _discovery_client({"P1": [_inverter("S1")]})
    client._discovery_cache["device_info"] = None

    result = await client.discover_devices()

    assert result.devices == {}


@pytest.mark.asyncio
async def test_back_discovered_device_is_kept_when_its_info_fetch_fails():
    """A device found only in alarms is part of the inventory even if its
    device-info request fails."""
    alarm = {"deviceSn": "HIDDEN1", "deviceType": "HYBRID_INVERTER"}
    client = _discovery_client(
        {"P1": [_inverter("S1")]}, device_info={"HIDDEN1": TimeoutError()}
    )
    discovery = client._request.side_effect

    async def with_alarm(method, path, **kwargs):
        if path == "/api/alarm/v1/plantAlarmPage":
            return 200, {"success": True, "data": {"pageData": [alarm]}}
        return await discovery(method, path, **kwargs)

    client._request = AsyncMock(side_effect=with_alarm)

    result = await client.discover_devices(allow_back_discovery=True)

    assert set(result.devices) == {"S1", "HIDDEN1"}


@pytest.mark.asyncio
async def test_device_info_fetch_does_not_recreate_a_pruned_device():
    """A device-info fetch for a device discovery no longer knows leaves the
    inventory alone, so a poll cannot bring a pruned device back."""
    client = _discovery_client({"P1": [_inverter("S1")]})
    entry = {"model": "Hybrid Inverter", "device_type_code": "1", "metrics": {}}

    await client._fetch_device_info("GONE", entry)

    assert "GONE" not in client._discovery_cache["device_info"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "later_info", [TimeoutError(), {}], ids=["info-fails", "info-without-versions"]
)
async def test_device_list_version_does_not_replace_device_info_version(later_info):
    """When a later info refresh fails or carries no versions, the inventory
    keeps the version device info reported rather than switching to the
    device list's."""
    device = dict(_inverter("S1"), swVer="1.0")
    device_info = {"S1": {"swVerSys": "1.2"}}
    client = _discovery_client({"P1": [device]}, device_info=device_info)
    await client.discover_devices()

    device_info["S1"] = later_info
    result = await client.discover_devices()

    assert result.devices["S1"]["sw_version"] == "1.2"


@pytest.mark.asyncio
async def test_discover_devices_defers_get_all_device_data_rediscovery():
    """After a public discover_devices(), get_all_device_data only polls."""
    client = _discovery_client({"P1": [_inverter("S1")]})
    await client.discover_devices()
    client._request.reset_mock()

    await client.get_all_device_data()

    assert "/api/plant/v1/page" not in _paths(client)


def test_push_data_reports_the_detailed_model():
    """Push results use the detailed model from device info when known."""
    client = HyxiApiClient("key", "secret", "http://api.com", AsyncMock())
    client._discovery_cache["device_info"] = {
        "S1": {
            "model": "Hybrid Inverter",
            "detailed_model": "HYX-H10K-HT",
            "device_type_code": "HYBRID_INVERTER",
        }
    }

    result = client.process_push_data({"dataList": [{"deviceSn": "S1"}]})

    assert result["S1"]["model"] == "HYX-H10K-HT"


@pytest.mark.asyncio
async def test_device_list_version_is_used_while_device_info_has_none():
    """For a device whose device info reports no versions, a firmware update
    shown in the device list reaches the inventory."""
    device = dict(_inverter("S1"), swVer="1.0")
    client = _discovery_client({"P1": [device]})
    await client.discover_devices()

    device["swVer"] = "1.1"
    result = await client.discover_devices()

    assert result.devices["S1"]["sw_version"] == "1.1"


@pytest.mark.asyncio
async def test_rejected_forced_discovery_rediscovers_on_the_next_call():
    """A forced discovery whose plant list is rejected expires a still-valid
    cache, so the next get_all_device_data() retries the discovery."""
    client = _discovery_client({"P1": [_inverter("S1")]})
    await client.discover_devices()
    client._fetch_plants = AsyncMock(return_value=None)

    await client.get_all_device_data(force_discovery=True)

    assert _seconds_until_rediscovery(client) <= 0


def _reject_token_once(client, path):
    """Make the first request to path reject the token as the server does,
    and answer token requests with a new token."""
    answer = client._request.side_effect
    rejected = False

    async def fake_request(method, request_path, **kwargs):
        nonlocal rejected
        if kwargs.get("is_token_request"):
            return 200, {"success": True, "data": {"token": "new", "expiresIn": 7200}}
        if request_path == path and not rejected:
            rejected = True
            client.token = None
            client.token_expires_at = 0
            raise TokenRejectedError("Server rejected token")
        return await answer(method, request_path, **kwargs)

    client._request = AsyncMock(side_effect=fake_request)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation, path",
    [
        (lambda client: client.discover_devices(), "/api/plant/v1/devicePage"),
        (lambda client: client.poll_devices(), "/api/alarm/v1/plantAlarmPage"),
        (
            lambda client: client.get_all_device_data(),
            "/api/alarm/v1/plantAlarmPage",
        ),
    ],
    ids=["discover", "poll", "get-all"],
)
async def test_token_rejected_mid_operation_reauthenticates_once(operation, path):
    """A token rejected part-way through discovery or polling is replaced by
    a new one and the operation run once more, rather than failing it."""
    client = _discovery_client({"P1": [_inverter("S1")]})
    await client.discover_devices()
    _reject_token_once(client, path)

    result = await operation(client)

    if isinstance(result, DiscoveryResult):
        devices = result.devices
    else:
        devices = result.get("data", result)
    assert set(devices) == {"S1"}
    assert client.token == "Bearer new"


@pytest.mark.asyncio
async def test_token_rejected_twice_fails_the_operation():
    """A token rejected again after re-authenticating is not retried further."""
    client = _discovery_client({"P1": [_inverter("S1")]})
    client._fetch_plants = AsyncMock(side_effect=TokenRejectedError("rejected"))
    client.ensure_token = AsyncMock()

    with pytest.raises(TokenRejectedError):
        await client.discover_devices()
    assert client._fetch_plants.await_count == 2


@pytest.mark.asyncio
async def test_token_retry_cancels_the_failed_attempts_requests():
    """When one request of a discovery rejects the token, the attempt's other
    requests are cancelled before the retry, so none of them can update the
    inventory after the retried discovery has committed it."""
    client = _discovery_client({"P1": [_inverter("S1")], "P2": [_inverter("S2")]})
    answer = client._request.side_effect
    attempt = 0
    stalled = asyncio.Event()
    cancelled = []

    async def fake_request(method, path, **kwargs):
        nonlocal attempt
        if kwargs.get("is_token_request"):
            return 200, {"success": True, "data": {"token": "new", "expiresIn": 7200}}
        if path == "/api/plant/v1/page":
            attempt += 1
        if path == "/api/plant/v1/devicePage" and attempt == 1:
            if kwargs["json"]["plantId"] == "P1":
                try:
                    stalled.set()
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled.append("P1")
                    raise
            await stalled.wait()
            client.token = None
            raise TokenRejectedError("Server rejected token")
        return await answer(method, path, **kwargs)

    client._request = AsyncMock(side_effect=fake_request)

    result = await client.discover_devices()

    assert set(result.devices) == {"S1", "S2"}
    assert cancelled == ["P1"]
