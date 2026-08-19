# hyxi-cloud-api

[![Security Shield](https://img.shields.io/badge/Security-Shield--Audited-green?logo=github&style=flat-square)](https://github.com/Veldkornet/hyxi-cloud-api/actions/workflows/security.yml)
[![PyPI version](https://badge.fury.io/py/hyxi-cloud-api.svg)](https://badge.fury.io/py/hyxi-cloud-api)
[![CI/CD Pipeline](https://github.com/Veldkornet/hyxi-cloud-api/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Veldkornet/hyxi-cloud-api/actions/workflows/ci-cd.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/Veldkornet/hyxi-cloud-api/main.svg)](https://results.pre-commit.ci/latest/github/Veldkornet/hyxi-cloud-api/main)
[![Python Versions](https://img.shields.io/pypi/pyversions/hyxi-cloud-api.svg)](https://pypi.org/project/hyxi-cloud-api/)
[![OpenSSF Baseline](https://www.bestpractices.dev/projects/12101/baseline)](https://www.bestpractices.dev/projects/12101)

An asynchronous Python client for interacting with the HYXI Cloud API.

This library was primarily built to power the [HYXI Cloud Home Assistant Integration](https://github.com/Veldkornet/ha-hyxi-cloud), but it can be used in any Python 3.14+ project to fetch telemetry data from HYXI solar inverters and battery systems.

## 📦 Installation

You can install the package directly from PyPI:

```bash
pip install hyxi-cloud-api
```

## 🚀 Quick Start

This library uses `aiohttp` for non-blocking network requests. You will need to provide your **Developer API credentials (AK/SK)**, along with an active `aiohttp.ClientSession`.

> [!NOTE]
> The HYXI Open API requires a separate developer account registered at [open.hyxicloud.com](https://open.hyxicloud.com). If your developer email is different from your main HYXI app account, you must **Share your Plant** from the app to your developer email address to access your data.

```python
import asyncio
import aiohttp
from hyxi_cloud_api import HyxiApiClient

async def main():
    # Replace with your actual HYXi Cloud credentials
    ACCESS_KEY = "your_access_key"
    SECRET_KEY = "your_secret_key"
    BASE_URL = "https://open.hyxicloud.com"

    async with aiohttp.ClientSession() as session:
        # 1. Initialize the client
        client = HyxiApiClient(
            access_key=ACCESS_KEY,
            secret_key=SECRET_KEY,
            base_url=BASE_URL,
            session=session
        )

        # 2. Fetch device data
        try:
            device_data = await client.get_all_device_data()
            print("Successfully fetched HYXi data:")
            print(device_data)
        except Exception as e:
            print(f"Error communicating with HYXi Cloud: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

HYXI Open API base URLs vary by region. The examples in this README use the
Europe endpoint by default.

| Node | Request Address |
| :--- | :--- |
| China | `https://open-cn.hyxicloud.com` |
| Europe (default) | `https://open.hyxicloud.com` |
| North America | `https://open-or.hyxicloud.com` |

## 🔧 Device Control

You can control inverter operating modes directly through the API. This requires a device serial number, which you can obtain from the device data response above.

```python
async def control_example(client, device_sn):
    # Set operating mode
    await client.set_mode_self_consume(device_sn)
    await client.set_mode_charge(device_sn, watts=3000)
    await client.set_mode_discharge(device_sn, watts=2500)
    await client.set_mode_idle(device_sn)

    # Peak shaving (close, charge, discharge, stop, hold)
    await client.set_peak_shaving(device_sn, action="charge")

    # Frequency control
    await client.set_frequency_control(device_sn, enabled=True)
```

Control failures raise `HyxiApiClient.ControlError`:

```python
try:
    await client.set_mode_charge(device_sn, watts=3000)
except client.ControlError as e:
    print(f"Control command failed: {e}")
```

## 🔔 Subscriptions

You can subscribe a callback URL to HYXI push notifications for real-time data,
alarms, and FCAS/frequency-modulation real-time data.

```python
async def subscription_example(client):
    callback_url = "https://your-public-callback-host/hyxi/callback"
    device_sns = ["60700000000001", "60700000000002"]

    real_time = await client.subscribe_real_time_data(
        callback_url,
        device_sns,
        post_rate=60000,  # milliseconds, 5000-3600000
    )

    alarm = await client.subscribe_alarm(
        callback_url,
        device_sns,
        post_rate=60000,  # milliseconds, 5000-3600000
    )

    fcas = await client.subscribe_fm_real_time_data(
        callback_url,
        device_sns,
        post_rate=1,  # hours, 1-6
    )

    await client.cancel_subscription(real_time["data"]["subscribeCode"])
```

Subscription failures raise `HyxiApiClient.SubscriptionError`.

## 🛠️ Requirements
* Python 3.14 or newer
* `aiohttp` >= 3.13.3

## 🔐 Privacy & Debug Logging

When debug logging is enabled, this library automatically masks sensitive identifiers before writing them to the log — no manual redaction needed.

| Field | Behaviour |
| :--- | :--- |
| Serial numbers (`deviceSn`, `parentSn`, `batSn`) | Hashed securely using SHA-256 (first 8 chars shown) to enable deterministic cross-device tracing without exposing the original identifier, e.g. `e3b0c442` |
| Plant IDs (`plantId`) | Same SHA-256 hashing format |
| Home/site address (`plantAddress`) | Fully redacted → `[REDACTED]` |
| IMEI (`gprsImei`) | Same SHA-256 hashing format |

Masking is deterministic, so parent/child device relationships remain traceable across log lines.

## ⚠️ Disclaimer
This is an unofficial, community-driven project. It is not affiliated with, endorsed by, or connected to HYXiPower in any official capacity. Use this software at your own risk.
