import asyncio
import time
from unittest.mock import MagicMock, AsyncMock
from src.hyxi_cloud_api.api import HyxiApiClient, FetchState

async def mock_fetch_sub_devices(sn, state):
    await asyncio.sleep(0.1) # Simulate network delay

async def mock_fetch_all_for_device(sn, entry, dev_type):
    return (sn, entry)

async def run_benchmark():
    client = HyxiApiClient("test", "test", "http://test", MagicMock())
    client._fetch_sub_devices = mock_fetch_sub_devices
    client._fetch_all_for_device = mock_fetch_all_for_device

    state = FetchState(now=time.time())

    # 5 plants, each with 5 parent devices -> 25 devices
    plants = [{"plantId": f"p{i}"} for i in range(5)]
    alarm_results = [
        [
            {"deviceSn": f"sn_{i}_{j}", "deviceType": "COLLECTOR"}
            for j in range(5)
        ] for i in range(5)
    ]

    start_time = time.time()
    await client._process_alarms_and_back_discovery(
        alarm_results, plants, state, allow_back_discovery=True
    )

    # Need to await tasks so they don't produce warnings
    for task in state.metric_tasks:
        await task

    end_time = time.time()
    print(f"Time taken: {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
