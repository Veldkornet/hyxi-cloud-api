import asyncio
import time
from unittest.mock import MagicMock

class MockState:
    pass

class MockAPI:
    @staticmethod
    async def _execute_device_tasks(tasks):
        if tasks:
            await asyncio.gather(*tasks)

    async def _fetch_and_process_alarms(self, tasks, state, allow_back_discovery=False):
        if tasks:
            await asyncio.gather(*tasks)
        return ["alarms"]

    async def _execute_metric_tasks(self, plant_alarms, state):
        pass

    async def _build_plant_tasks(self, state):
        async def mock_device_task():
            await asyncio.sleep(0.5)

        async def mock_alarm_task():
            await asyncio.sleep(0.5)

        return [mock_device_task()], [mock_alarm_task()]

    async def _process_plants_data_sequential(self, state, allow_back_discovery=False):
        device_fetch_tasks, alarm_fetch_tasks = await self._build_plant_tasks(state)

        await self._execute_device_tasks(device_fetch_tasks)

        plant_alarms = await self._fetch_and_process_alarms(
            alarm_fetch_tasks,
            state,
            allow_back_discovery=allow_back_discovery,
        )

        await self._execute_metric_tasks(plant_alarms, state)
        return plant_alarms

    async def _process_plants_data_concurrent(self, state, allow_back_discovery=False):
        device_fetch_tasks, alarm_fetch_tasks = await self._build_plant_tasks(state)

        _, plant_alarms = await asyncio.gather(
            self._execute_device_tasks(device_fetch_tasks),
            self._fetch_and_process_alarms(
                alarm_fetch_tasks,
                state,
                allow_back_discovery=allow_back_discovery,
            ),
        )

        await self._execute_metric_tasks(plant_alarms, state)
        return plant_alarms

async def main():
    api = MockAPI()
    state = MockState()

    start = time.time()
    await api._process_plants_data_sequential(state)
    end = time.time()
    print(f"Sequential: {end - start:.4f}s")

    start = time.time()
    await api._process_plants_data_concurrent(state)
    end = time.time()
    print(f"Concurrent: {end - start:.4f}s")

if __name__ == "__main__":
    asyncio.run(main())
