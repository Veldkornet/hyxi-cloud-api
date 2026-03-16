import sys
from src.hyxi_cloud_api.api import HyxiApiClient
from unittest.mock import MagicMock, AsyncMock
import unittest


# Mock aiohttp before importing the API client
mock_aiohttp = MagicMock()
sys.modules["aiohttp"] = mock_aiohttp



class TestSecurityFix(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_device_metrics_fixed(self):
        """Verify that _fetch_device_metrics now uses params mapping."""
        fake_session = MagicMock()
        api = HyxiApiClient("ak", "sk", "https://api.com", fake_session)

        sn = "123&extra=param"
        entry = {"metrics": {}}

        mock_response = AsyncMock()
        mock_response.__aenter__.return_value.json.return_value = {"success": True, "data": []}
        mock_response.__aenter__.return_value.status = 200
        mock_response.__aenter__.return_value.raise_for_status = MagicMock()

        fake_session.get.return_value = mock_response

        await api._fetch_device_metrics(sn, entry)

        args, kwargs = fake_session.get.call_args
        # URL should NOT contain the raw unencoded SN with '&'
        self.assertEqual(args[0], "https://api.com/api/device/v1/queryDeviceData")
        self.assertEqual(kwargs["params"], {"deviceSn": sn})

    async def test_fetch_device_info_fixed(self):
        """Verify that _fetch_device_info now uses params mapping."""
        fake_session = MagicMock()
        api = HyxiApiClient("ak", "sk", "https://api.com", fake_session)

        sn = "123#fragment"
        entry = {"metrics": {}}

        mock_response = AsyncMock()
        mock_response.__aenter__.return_value.json.return_value = {"success": True, "data": []}
        mock_response.__aenter__.return_value.status = 200
        mock_response.__aenter__.return_value.raise_for_status = MagicMock()

        fake_session.get.return_value = mock_response

        await api._fetch_device_info(sn, entry)

        args, kwargs = fake_session.get.call_args
        # URL should NOT contain the raw unencoded SN with '#'
        self.assertEqual(args[0], "https://api.com/api/device/v1/queryDeviceInfo")
        self.assertEqual(kwargs["params"], {"deviceSn": sn})

if __name__ == "__main__":
    unittest.main()
