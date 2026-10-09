"""Tests for the client's cap on concurrent HTTP requests."""

import asyncio
from unittest.mock import MagicMock

import pytest

from hyxi_cloud_api.api import HyxiApiClient


class _Tracker:
    """Counts how many stand-in responses are open at once."""

    def __init__(self):
        self.in_flight = 0
        self.peak = 0

    def response(self, *args, **kwargs):
        """Return a stand-in aiohttp response bound to this tracker."""
        return _TrackingResponse(self)


class _TrackingResponse:
    """Async context manager standing in for an aiohttp response."""

    status = 200

    def __init__(self, tracker):
        self._tracker = tracker

    async def __aenter__(self):
        self._tracker.in_flight += 1
        self._tracker.peak = max(self._tracker.peak, self._tracker.in_flight)
        await asyncio.sleep(0.01)
        return self

    async def __aexit__(self, *exc):
        self._tracker.in_flight -= 1

    def raise_for_status(self):
        """Never raises: every stand-in response is a 200."""

    async def json(self):
        """Return a minimal successful API body."""
        return {"success": True}


def _client(tracker, limit):
    session = MagicMock()
    session.get = MagicMock(side_effect=tracker.response)
    session.post = MagicMock(side_effect=tracker.response)
    return HyxiApiClient("ak", "sk", "https://api.com", session, limit), session


@pytest.mark.asyncio
async def test_request_concurrency_is_capped():
    """No more than max_concurrent_requests requests run at the same time."""
    tracker = _Tracker()
    client, session = _client(tracker, 3)

    await asyncio.gather(*(client._request("GET", "/x") for _ in range(10)))

    assert tracker.peak == 3
    assert session.get.call_count == 10


@pytest.mark.asyncio
async def test_token_request_bypasses_concurrency_cap():
    """A token request runs even while every request slot is taken."""
    tracker = _Tracker()
    client, _ = _client(tracker, 1)

    await asyncio.gather(
        client._request("GET", "/x"),
        client._request("POST", "/token", is_token_request=True),
    )

    assert tracker.peak == 2


def test_max_concurrent_requests_must_be_positive():
    """A cap below 1 is rejected rather than deadlocking every request."""
    with pytest.raises(ValueError, match="at least 1"):
        HyxiApiClient("ak", "sk", "https://api.com", MagicMock(), 0)
