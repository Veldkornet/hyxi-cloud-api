"""
HYXI Control-Result Latency Probe
==================================
Issues one real control command against a live device and polls
/api/device/v1/obtain (query_control_result) until it resolves to a
terminal result ("3" success / "6" failure) or a timeout elapses,
printing a timestamped log of every observed state.

Exists to answer a real, unmeasured question: how long does it actually
take HYXI's cloud to reflect the device's real response to a control
write? ha-hyxi-cloud's control_verify.py currently assumes a ~15 second
round trip (a 5s initial delay plus up to two 5s retries) -- explicitly
flagged in its own comment as "unconfirmed against live timing". This
script measures the real number so that budget can be corrected.

CAUTION: this issues a real command against a real device. "idle" safely
stops charge/discharge and is the default for that reason, but nothing
here restores whatever mode the device was in beforehand -- HYXI's own
telemetry poll doesn't report the currently-active mode (nothing to
reliably restore to), so plan to manually set your preferred mode again
once the test finishes.

Also tests a hypothesis for why a mode command might be accepted by HYXI's
cloud yet never visibly applied by the device: ha-hyxi-cloud's Modbus
client writes register 4146 ("vpp_enable" / dispatch mode 2) before every
mode write, since the device's own firmware ignores the mode register
(4147) unless dispatch is armed first -- and nothing in the Cloud control
path sends an equivalent "arm" instruction. controlId 1020 ("Frequency
Control Enable") is the one documented candidate for a Cloud-side
equivalent, though HYXI's docs scope it to single-phase devices. Set
HYXI_ARM_DISPATCH_FIRST=1 to send it before the mode command and see
whether that's what was missing.

Usage:
    export HYXI_ACCESS_KEY="your_access_key"
    export HYXI_SECRET_KEY="your_secret_key"
    export HYXI_TEST_DEVICE_SN="the device SN to test against"
    export HYXI_ARM_DISPATCH_FIRST=1  # optional, see above
    python scratch/measure_control_latency.py [mode] [max_minutes]

    mode: idle or self_consume (default: idle). charge/discharge are
          deliberately not offered here -- they need a wattage this
          script doesn't prompt for, and are a less neutral default to
          fire blind against a live device.
    max_minutes: how long to keep polling before giving up (default: 20).
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

import aiohttp

from hyxi_cloud_api import HyxiApiClient

ACCESS_KEY = os.environ.get("HYXI_ACCESS_KEY", "")
SECRET_KEY = os.environ.get("HYXI_SECRET_KEY", "")
DEVICE_SN = os.environ.get("HYXI_TEST_DEVICE_SN", "")
BASE_URL = os.environ.get("HYXI_BASE_URL", HyxiApiClient.DEFAULT_BASE_URL)
ARM_DISPATCH_FIRST = os.environ.get("HYXI_ARM_DISPATCH_FIRST", "").lower() in (
    "1",
    "true",
    "yes",
)

_ARM_SETTLE_DELAY_S = 3.0  # give the enable a moment to land before the mode write

_FAST_POLL_WINDOW_S = 120.0  # poll tightly for the first 2 minutes...
_FAST_POLL_INTERVAL_S = 10.0
_SLOW_POLL_INTERVAL_S = 60.0  # ...then back off, in case this takes a while.


def _next_poll_delay(elapsed_s: float) -> float:
    """Poll every 10s for the first 2 minutes (fine resolution in case
    the answer comes back fast), then every 60s after that (coarser, so
    a slow answer doesn't cost dozens of needless requests).
    """
    return (
        _FAST_POLL_INTERVAL_S
        if elapsed_s < _FAST_POLL_WINDOW_S
        else _SLOW_POLL_INTERVAL_S
    )


async def _arm_dispatch_first(client: HyxiApiClient, device_sn: str) -> None:
    """Send controlId 1020 (Frequency Control Enable) and wait for it to
    settle, per the HYXI_ARM_DISPATCH_FIRST hypothesis (see module docstring).
    """
    print("🔓 Sending Frequency Control Enable (controlId 1020) to arm dispatch...")
    try:
        arm_response = await client.set_frequency_control(device_sn, True)
        print(f"Arm response: {arm_response}")
    except HyxiApiClient.ControlError as err:
        print(f"⚠️  Arm step rejected outright: {err} (continuing anyway)")
    print(f"⏳ Waiting {_ARM_SETTLE_DELAY_S:.0f}s before the mode write...")
    await asyncio.sleep(_ARM_SETTLE_DELAY_S)


async def main() -> None:
    """Issue one control command and poll its result until resolved or timed out."""
    if not ACCESS_KEY or not SECRET_KEY or not DEVICE_SN:
        print(
            "Set HYXI_ACCESS_KEY, HYXI_SECRET_KEY, and HYXI_TEST_DEVICE_SN "
            "before running this."
        )
        return

    mode = sys.argv[1] if len(sys.argv) > 1 else "idle"
    max_minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
    if mode not in ("idle", "self_consume"):
        print(f"Unsupported mode {mode!r}; use idle or self_consume.")
        return

    async with aiohttp.ClientSession() as session:
        client = HyxiApiClient(ACCESS_KEY, SECRET_KEY, BASE_URL, session)

        print("🔑 Authenticating...")
        ok = await client._refresh_token()  # pylint: disable=protected-access
        if not ok or ok == "auth_failed":
            print(f"❌ Authentication failed (status={ok!r}).")
            return

        masked_sn = f"...{DEVICE_SN[-6:]}" if len(DEVICE_SN) > 6 else DEVICE_SN

        if ARM_DISPATCH_FIRST:
            await _arm_dispatch_first(client, DEVICE_SN)

        print(f"📤 Issuing mode '{mode}' to device {masked_sn}")
        send_fn = (
            client.set_mode_idle if mode == "idle" else client.set_mode_self_consume
        )
        try:
            response = await send_fn(DEVICE_SN)
        except HyxiApiClient.ControlError as err:
            print(f"❌ Control write rejected outright: {err}")
            return
        print(f"Control response: {response}")

        data = response.get("data")
        trace_id = None
        if isinstance(data, list) and data and isinstance(data[0], dict):
            trace_id = data[0].get("traceId")
        if not trace_id:
            print("❌ No traceId in the response -- can't poll a result. Aborting.")
            return
        if not str(trace_id).strip().isdigit():
            print(
                f"⚠️  traceId is {trace_id!r} -- not a real, numeric trace ID. "
                "Every genuine HYXI traceId is purely numeric; a non-numeric "
                'value (e.g. the literal string "SKIPPED", observed live '
                "against a device under active third-party/energy-provider "
                "control) means HYXI never generated a trackable result for "
                "this write, and query_control_result would just return "
                "data: None forever. Aborting rather than polling for "
                f"{max_minutes:.0f} minutes for nothing."
            )
            return

        print(f"🔎 traceId: {trace_id}")
        print(
            f"⏱️  Polling every {_FAST_POLL_INTERVAL_S:.0f}s for the first "
            f"{_FAST_POLL_WINDOW_S / 60:.0f} min, then every "
            f"{_SLOW_POLL_INTERVAL_S:.0f}s, up to {max_minutes:.0f} min total.\n"
        )

        t0 = time.monotonic()
        deadline = t0 + max_minutes * 60

        while True:
            elapsed = time.monotonic() - t0
            try:
                result_response = await client.query_control_result(trace_id)
            except Exception as err:  # pylint: disable=broad-exception-caught
                print(f"[t+{elapsed:6.1f}s] query_control_result error: {err}")
            else:
                result_data = result_response.get("data") or {}
                result = result_data.get("result")
                print(f"[t+{elapsed:6.1f}s] result={result!r} raw={result_response}")
                if result in ("3", "6"):
                    outcome = "SUCCESS" if result == "3" else "FAILURE"
                    print(
                        f"\n✅ Resolved as {outcome} after {elapsed:.1f}s "
                        f"({elapsed / 60:.2f} min)."
                    )
                    return

            if time.monotonic() >= deadline:
                print(
                    f"\n⏹️  Gave up after {max_minutes:.0f} minutes without a "
                    "terminal result."
                )
                return

            await asyncio.sleep(_next_poll_delay(elapsed))


if __name__ == "__main__":
    asyncio.run(main())
