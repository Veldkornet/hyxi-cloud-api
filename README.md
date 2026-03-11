# hyxi-cloud-api

[![Security Shield](https://img.shields.io/badge/Security-Shield--Audited-green?logo=github&style=flat-square)](https://github.com/Veldkornet/hyxi-cloud-api/actions/workflows/security.yml)
[![PyPI version](https://badge.fury.io/py/hyxi-cloud-api.svg)](https://badge.fury.io/py/hyxi-cloud-api)
[![CI/CD Pipeline](https://github.com/Veldkornet/hyxi-cloud-api/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Veldkornet/hyxi-cloud-api/actions/workflows/ci-cd.yml)
[![Python Versions](https://img.shields.io/pypi/pyversions/hyxi-cloud-api.svg)](https://pypi.org/project/hyxi-cloud-api/)
[![OpenSSF Baseline](https://www.bestpractices.dev/projects/12101/baseline)](https://www.bestpractices.dev/projects/12101)

An asynchronous Python client for interacting with the HYXI Cloud API.

This library was primarily built to power the [HYXI Cloud Home Assistant Integration](https://github.com/Veldkornet/ha-hyxi-cloud), but it can be used in any Python 3.11+ project to fetch telemetry data from HYXI solar inverters and battery systems.

## 📦 Installation

You can install the package directly from PyPI:

```bash
pip install hyxi-cloud-api
```

## 🚀 Quick Start

This library uses `aiohttp` for non-blocking network requests. You will need to provide your HYXI Cloud Access Key and Secret Key, along with an active `aiohttp.ClientSession`.

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

## 🛠️ Requirements
* Python 3.11 or newer
* `aiohttp` >= 3.13.3

## 🔐 Privacy & Debug Logging

When debug logging is enabled, this library automatically masks sensitive identifiers before writing them to the log — no manual redaction needed.

| Field | Behaviour |
| :--- | :--- |
| Serial numbers (`deviceSn`, `parentSn`, `batSn`) | Middle characters replaced with `X` — length preserved for cross-device tracing, e.g. `106XXXXXXXX016` |
| Plant IDs (`plantId`) | Same X-padding format |
| Home/site address (`plantAddress`) | Fully redacted → `[REDACTED]` |
| IMEI (`gprsImei`) | X-padded |

Masking is deterministic, so parent/child device relationships remain traceable across log lines.

## ⚠️ Disclaimer
This is an unofficial, community-driven project. It is not affiliated with, endorsed by, or connected to HYXiPower in any official capacity. Use this software at your own risk.
