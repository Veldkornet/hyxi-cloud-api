"""
HYXI Cloud API Diagnostic Utility
=================================
Calls all status/telemetry endpoints on the live HYXI API and dumps the raw
JSON responses to diagnose device parameters, VPP status, EMS parameters,
and alarm states.

Usage:
    export HYXI_ACCESS_KEY="your_access_key"
    export HYXI_SECRET_KEY="your_secret_key"
    python scratch/api_diagnostic.py
"""

import asyncio
import json
import os

import aiohttp

from hyxi_cloud_api.api import HyxiApiClient

ACCESS_KEY = os.environ.get("HYXI_ACCESS_KEY", "")
SECRET_KEY = os.environ.get("HYXI_SECRET_KEY", "")
BASE_URL = os.environ.get("HYXI_BASE_URL", HyxiApiClient.DEFAULT_BASE_URL)


# pylint: disable=too-many-statements
async def main():
    """Main execution of the diagnostic script."""
    if not ACCESS_KEY or not SECRET_KEY:
        print(
            "❌ Error: HYXI_ACCESS_KEY and HYXI_SECRET_KEY environment variables must be set."
        )
        return

    async with aiohttp.ClientSession() as session:
        client = HyxiApiClient(ACCESS_KEY, SECRET_KEY, BASE_URL, session)

        print("🔑 Authenticating...")
        ok = await client._refresh_token()
        if not ok or ok == "auth_failed":
            print(f"❌ Authentication failed (status={ok!r}).")
            return
        print(f"✅ Authenticated. Token tail: ...{(client.token or '')[-12:]}")

        # 1. Fetch Plants
        print("\n🌱 [POST /api/plant/v1/page] Fetching plants...")
        _, plants_res = await client._request(
            "POST", "/api/plant/v1/page", json={"pageSize": 50, "currentPage": 1}
        )
        print(f"Response:\n{json.dumps(plants_res, indent=2)}")

        if not plants_res.get("success"):
            print("❌ Failed to query plants.")
            return

        plants = plants_res.get("data", {}).get("list", [])
        if not plants:
            print("⚠️ No plants associated with this account.")
            return

        for plant in plants:
            plant_id = plant.get("plantId")
            plant_name = plant.get("plantName", "Unknown")
            print("\n==================================================")
            print(f"🏭 Plant: {plant_name} ({plant_id})")
            print("==================================================")

            # 2. Fetch Plant Alarms
            print("\n🚨 [POST /api/alarm/v1/plantAlarmPage] Querying active alarms...")
            _, alarms_res = await client._request(
                "POST",
                "/api/alarm/v1/plantAlarmPage",
                json={"plantId": plant_id, "pageSize": 100, "currentPage": 1},
            )
            print(f"Response:\n{json.dumps(alarms_res, indent=2)}")

            # 3. Fetch Devices for Plant
            print("\n📟 [POST /api/plant/v1/devicePage] Fetching devices...")
            _, devices_res = await client._request(
                "POST",
                "/api/plant/v1/devicePage",
                json={"plantId": plant_id, "pageSize": 50, "currentPage": 1},
            )
            print(f"Response:\n{json.dumps(devices_res, indent=2)}")

            devices = (
                devices_res.get("data", {}).get("deviceList", [])
                if devices_res.get("success")
                else []
            )
            for device in devices:
                sn = device.get("deviceSn")
                dtype = device.get("deviceType")
                model = device.get("model", "Unknown")
                print("\n  --------------------------------------------------")
                print(f"  📟 Device: {sn} (Type: {dtype} | Model: {model})")
                print("  --------------------------------------------------")

                # 4. Fetch Static Device Info
                print(
                    "  [1] [GET /api/device/v1/queryDeviceInfo] Querying static device metadata..."
                )
                _, info_res = await client._request(
                    "GET", "/api/device/v1/queryDeviceInfo", params={"deviceSn": sn}
                )
                print(f"  Response:\n{json.dumps(info_res, indent=4)}")

                # 5. Fetch Raw Device Telemetry
                print(
                    "  [2] [GET /api/device/v1/queryDeviceData] Querying raw telemetry..."
                )
                _, tele_res = await client._request(
                    "GET", "/api/device/v1/queryDeviceData", params={"deviceSn": sn}
                )
                print(f"  Response:\n{json.dumps(tele_res, indent=4)}")

                # 6. Fetch Sub-devices (linked child devices)
                print(
                    "  [3] [POST /api/device/v1/getSubDevicePage] Querying sub-devices..."
                )
                _, sub_res = await client._request(
                    "POST",
                    "/api/device/v1/getSubDevicePage",
                    json={"parentSn": sn, "pageSize": 50, "currentPage": 1},
                )
                print(f"  Response:\n{json.dumps(sub_res, indent=4)}")

                # 7. Fetch EMS Basic Details (for Inverters / Energy Storage units)
                print(
                    "  [4] [GET /api/ems/v1/queryBasicDetails] Querying EMS details..."
                )
                _, ems_res = await client._request(
                    "GET", "/api/ems/v1/queryBasicDetails", params={"emsSn": sn}
                )
                print(f"  Response:\n{json.dumps(ems_res, indent=4)}")

                # 8. Fetch VPP Settings
                print(
                    "  [5] [POST /hyx-plant/deviceInstruct/v1/getVppModeSetting] Querying VPP settings..."
                )
                try:
                    _, vpp_res = await client._request(
                        "POST",
                        "/hyx-plant/deviceInstruct/v1/getVppModeSetting",
                        json={"sn": sn},
                    )
                    print(f"  Response:\n{json.dumps(vpp_res, indent=4)}")
                except Exception as e:
                    print(f"  ⚠️ Request failed: {e}")

    print("\n✅ Diagnostic complete.")


if __name__ == "__main__":
    asyncio.run(main())
