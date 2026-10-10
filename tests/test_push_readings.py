"""Tests for which pushed readings process_push_data uses, and when."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from hyxi_cloud_api import HyxiApiClient
from hyxi_cloud_api import api as api_module

SN = "INV123"

# When HYXI delivered the captured reading below.
ARRIVAL = datetime(2026, 10, 10, 16, 33, 16, tzinfo=UTC)

# A flat reading as HYXI pushed it (trimmed): its collectTime reads
# 08:31:30Z, eight hours behind its arrival, and ph1p..ph3p repeat the
# backup port's ph1peps..ph3peps.
CAPTURED_READING = {
    "deviceSn": SN,
    "collectTime": 1791621090000,
    "createTime": "2026-10-11T00:31:42.947836",
    "acP": 9994.0,
    "gridP": None,
    "batSoc": 89,
    "ph1p": 1,
    "ph2p": 3,
    "ph3p": 2,
    "ph1peps": 1,
    "ph2peps": 3,
    "ph3peps": 2,
    "ph1Loadp": 546,
    "ph2Loadp": 2791,
    "ph3Loadp": 57,
}

# The captured reading's corrected time.
READING_TIME = "2026-10-10T16:31:30+00:00"


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return ARRIVAL.astimezone(tz)


@pytest.fixture
def api():
    """A client that knows the device, at the captured reading's arrival."""
    client = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    client._discovery_cache["device_info"] = {
        SN: {"model": "HYX-H10K-HT", "device_type_code": "HYBRID_INVERTER"}
    }
    with patch.object(api_module, "datetime", _FrozenDatetime):
        yield client


def _reading(**changes) -> dict:
    return {**CAPTURED_READING, **changes}


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp() * 1000)


def test_a_reading_hours_off_is_corrected_to_utc(api):
    """A collectTime that is a time zone's whole hours off from its arrival
    is moved back to UTC."""
    results = api.process_push_data({"dataList": [_reading()]})

    assert results[SN]["metrics"]["last_seen"] == READING_TIME


@pytest.mark.parametrize(
    ("collect_time", "last_seen"),
    [
        ("2026-10-10T16:20:00+00:00", "2026-10-10T16:20:00+00:00"),
        ("2026-10-10T16:40:00+00:00", "2026-10-10T16:33:16+00:00"),
        ("2026-10-11T00:31:30+00:00", "2026-10-10T16:31:30+00:00"),
        ("2026-10-10T15:48:16+00:00", "2026-10-10T15:48:16+00:00"),
        ("2026-10-09T16:00:00+00:00", "2026-10-09T16:00:00+00:00"),
    ],
    ids=["utc", "slightly-ahead", "hours-ahead", "45-minutes-late", "a-day-old"],
)
def test_reading_times_close_to_arrival_or_beyond_a_time_zone_are_kept(
    api, collect_time, last_seen
):
    """A reading time within half an hour of its arrival is kept, but never
    placed after the arrival; one less than a whole hour late, or more than
    a time zone away, is not shifted."""
    results = api.process_push_data(
        {"dataList": [_reading(collectTime=_ms(collect_time))]}
    )

    assert results[SN]["metrics"]["last_seen"] == last_seen


def test_the_newest_of_several_readings_is_used(api):
    """A push with several readings of a device, out of order, uses the
    newest one."""
    newest = _reading()
    older = _reading(collectTime=CAPTURED_READING["collectTime"] - 60_000, batSoc=88)

    results = api.process_push_data({"dataList": [newest, older]})

    metrics = results[SN]["metrics"]
    assert metrics["batSoc"] == 89
    assert metrics["last_seen"] == READING_TIME


@pytest.mark.parametrize(
    "held_last_seen",
    [READING_TIME, "2026-10-10T16:32:00+00:00", "2026-10-10T16:32:00"],
    ids=["same-reading", "newer-poll", "naive-time"],
)
def test_a_reading_not_newer_than_the_held_one_is_left_out(api, held_last_seen):
    """A reading HYXI sends again, or one older than what a poll already
    returned, does not replace the held metrics."""
    existing = {SN: {"batSoc": 90, "last_seen": held_last_seen}}

    assert api.process_push_data({"dataList": [_reading()]}, existing) == {}


@pytest.mark.parametrize(
    "held_last_seen", ["2026-10-10T16:30:00+00:00", None, "not-a-time"]
)
def test_a_reading_newer_than_the_held_one_is_used(api, held_last_seen):
    """A newer reading, or one for a device without a usable held time,
    updates the metrics."""
    existing = {SN: {"batSoc": 90, "last_seen": held_last_seen}}

    results = api.process_push_data({"dataList": [_reading()]}, existing)

    assert results[SN]["metrics"]["batSoc"] == 89
    assert results[SN]["metrics"]["last_seen"] == READING_TIME


def test_backup_port_phase_powers_keep_the_polled_ones(api):
    """Pushed ph1p..ph3p that repeat the backup port's powers do not replace
    the inverter's phase powers a poll returned."""
    existing = {
        SN: {
            "ph1p": 1201.0,
            "ph2p": 1189.0,
            "ph3p": 1195.0,
            "last_seen": "2026-10-10T16:30:00+00:00",
        }
    }

    metrics = api.process_push_data({"dataList": [_reading()]}, existing)[SN]["metrics"]

    assert (metrics["ph1p"], metrics["ph2p"], metrics["ph3p"]) == (
        1201.0,
        1189.0,
        1195.0,
    )
    assert metrics["ph1peps"] == 1
    assert metrics["ph2Loadp"] == 2791


def test_phase_powers_that_differ_from_the_backup_port_are_used(api):
    """Pushed phase powers that are not the backup port's are kept."""
    metrics = api.process_push_data(
        {"dataList": [_reading(ph1p=1201.0, ph2p=None, ph3p=1195.0)]}
    )[SN]["metrics"]

    assert metrics["ph1p"] == 1201.0
    assert "ph2p" not in metrics
    assert metrics["ph3p"] == 1195.0


def test_nested_phase_powers_are_kept(api):
    """Phase powers from a nested push's phases section are the inverter's,
    so they are kept even when they equal the backup port's."""
    nested = {
        "record": {"deviceSn": SN, "collectTime": 1791621090000},
        "ph1peps": 1,
        "phases": {"ph1": {"powerW": 1}},
    }

    metrics = api.process_push_data({"dataList": [nested]})[SN]["metrics"]

    assert metrics["ph1p"] == 1
