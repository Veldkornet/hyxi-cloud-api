import sys
import asyncio
import os
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock

# 🚨 CRITICAL: Mock aiohttp before importing HyxiApiClient because
# api.py has a top-level 'import aiohttp' and it is not installed
# in this environment. Using sys.modules to prevent ImportError.
if "aiohttp" not in sys.modules:
    sys.modules["aiohttp"] = MagicMock()

# Add src to path so we can import hyxi_cloud_api directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from hyxi_cloud_api.api import HyxiApiClient

class TestFetchConcurrency(IsolatedAsyncioTestCase):
    """
    Test suite for verifying concurrent task spawning in HyxiApiClient.
    Specifically tests that _fetch_all_for_device correctly decides which
    tasks to spawn based on the device type.
    """

    async def test_fetch_all_for_device_inverter(self):
        """Test that both info and metrics are fetched for non-COLLECTOR devices."""
        api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

        # We need these to return real coroutines because asyncio.create_task
        # is strict and doesn't accept AsyncMock objects directly.
        async def mock_info(sn, entry):
            pass
        async def mock_metrics(sn, entry):
            pass

        api._fetch_device_info = MagicMock(side_effect=mock_info)
        api._fetch_device_metrics = MagicMock(side_effect=mock_metrics)

        sn = "SN123"
        entry = {"metrics": {}}
        dev_type = "INVERTER"

        # _fetch_all_for_device returns (sn, entry)
        result_sn, result_entry = await api._fetch_all_for_device(sn, entry, dev_type)

        self.assertEqual(result_sn, sn)
        self.assertEqual(result_entry, entry)
        api._fetch_device_info.assert_called_once_with(sn, entry)
        api._fetch_device_metrics.assert_called_once_with(sn, entry)

    async def test_fetch_all_for_device_collector(self):
        """Test that only info is fetched for COLLECTOR devices."""
        api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())

        async def mock_info(sn, entry):
            pass
        async def mock_metrics(sn, entry):
            pass

        api._fetch_device_info = MagicMock(side_effect=mock_info)
        api._fetch_device_metrics = MagicMock(side_effect=mock_metrics)

        sn = "SN456"
        entry = {"metrics": {}}
        dev_type = "COLLECTOR"

        result_sn, result_entry = await api._fetch_all_for_device(sn, entry, dev_type)

        self.assertEqual(result_sn, sn)
        self.assertEqual(result_entry, entry)
        api._fetch_device_info.assert_called_once_with(sn, entry)
        api._fetch_device_metrics.assert_not_called()
