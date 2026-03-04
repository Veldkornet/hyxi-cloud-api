# hyxi-cloud-api

An asynchronous Python client for interacting with the HYXi Cloud API. 

This library was primarily built to power the [HYXi Cloud Home Assistant Integration](LINK_TO_YOUR_HA_REPO_HERE), but it can be used in any Python 3.11+ project to fetch telemetry data from HYXi solar inverters and battery systems.

## 📦 Installation

You can install the package directly from PyPI:

```bash
pip install hyxi-cloud-api
```

## 🚀 Quick Start

This library uses `aiohttp` for non-blocking network requests. You will need to provide your HYXi Cloud Access Key and Secret Key, along with an active `aiohttp.ClientSession`.

```python
import asyncio
import aiohttp
from hyxi_cloud_api import HyxiApiClient

async def main():
    # Replace with your actual HYXi Cloud credentials
    ACCESS_KEY = "your_access_key"
    SECRET_KEY = "your_secret_key"
    BASE_URL = "[https://open.hyxicloud.com](https://open.hyxicloud.com)"

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
* `aiohttp` >= 3.8.0

## ⚠️ Disclaimer
This is an unofficial, community-driven project. It is not affiliated with, endorsed by, or connected to HYXiPower in any official capacity. Use this software at your own risk.
