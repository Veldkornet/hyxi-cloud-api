import asyncio
import time

async def dummy_execute_device_tasks():
    await asyncio.sleep(0.5)

async def dummy_fetch_and_process_alarms():
    await asyncio.sleep(0.5)
    return ["alarm1"]

async def run_sequential():
    start = time.time()
    await dummy_execute_device_tasks()
    plant_alarms = await dummy_fetch_and_process_alarms()
    end = time.time()
    return end - start, plant_alarms

async def run_concurrent():
    start = time.time()
    _, plant_alarms = await asyncio.gather(
        dummy_execute_device_tasks(),
        dummy_fetch_and_process_alarms()
    )
    end = time.time()
    return end - start, plant_alarms

async def main():
    seq_time, _ = await run_sequential()
    con_time, _ = await run_concurrent()
    print(f"Sequential: {seq_time:.4f}s")
    print(f"Concurrent: {con_time:.4f}s")

if __name__ == "__main__":
    asyncio.run(main())
