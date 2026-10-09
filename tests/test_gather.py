"""Tests for _gather, the gather that cancels a failed operation's work."""

import asyncio
import logging

import pytest

from hyxi_cloud_api.api import _gather


@pytest.mark.asyncio
async def test_results_keep_the_order_of_the_awaitables():
    """Results come back in argument order, whatever order they finish in."""

    async def after(delay, value):
        await asyncio.sleep(delay)
        return value

    assert await _gather(after(0.02, "a"), after(0, "b")) == ["a", "b"]


@pytest.mark.asyncio
async def test_a_failure_cancels_the_others_before_propagating(caplog):
    """The first failure propagates as itself, once the other awaitables have
    been cancelled and awaited; another one's own failure is logged."""
    caplog.set_level(logging.DEBUG, logger="hyxi_cloud_api.api")
    stalled = asyncio.Event()
    cancelled = []

    async def stall():
        try:
            stalled.set()
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append("stall")
            raise

    async def fail_on_cancel():
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise ValueError("teardown failed") from None

    async def fail():
        await stalled.wait()
        raise KeyError("first")

    gathering = _gather(stall(), fail_on_cancel(), fail())

    with pytest.raises(KeyError, match="first"):
        await gathering

    assert cancelled == ["stall"]
    assert "teardown failed" in caplog.text
