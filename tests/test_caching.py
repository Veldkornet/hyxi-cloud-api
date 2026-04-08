import pytest
import time
from unittest.mock import patch, AsyncMock
from hyxi_cloud_api import HyxiApiClient

@pytest.mark.asyncio
async def test_discovery_caching_logic():
    """Verify that subsequent calls use the cache and skip discovery endpoints."""
    session = AsyncMock()
    client = HyxiApiClient("key", "secret", "http://api.com", session)
    
    # Mock token
    client.token = "Bearer test"
    client.token_expires_at = time.time() + 3600

    # Mock responses for full discovery
    plant_resp = {"success": True, "data": {"list": [{"plantId": "P1"}]}}
    device_resp = {"success": True, "data": {"deviceList": [{"deviceSn": "S1", "deviceType": "HYBRID_INVERTER"}]}}
    info_resp = {"success": True, "data": {"swVerSys": "V1", "hwVer": "H1"}}
    metrics_resp = {"success": True, "data": [{"dataKey": "gridP", "dataValue": "100"}]}
    alarms_resp = {"success": True, "data": {"pageData": []}}
    sub_dev_resp = {"success": True, "data": {"childDevice": []}}

    # Setup the sequence of responses for the first (full) call
    # 1. Plants
    # 2. Devices for Plant
    # 3. Sub-devices for Inverter
    # 4. Alarms for Plant
    # 5. Info for Inverter
    # 6. Metrics for Inverter
    # 7. EMS Probe
    
    with patch.object(client, "_request") as mock_req:
        mock_req.side_effect = [
            (200, plant_resp),
            (200, device_resp),
            (200, sub_dev_resp),
            (200, alarms_resp),
            (200, info_resp),
            (200, metrics_resp),
            (200, {}), # EMS
        ]

        # First call: Full Discovery
        res1 = await client.get_all_device_data()
        assert res1["data"]["S1"]["sw_version"] == "V1"
        assert mock_req.call_count == 7

        # Second call: Should use cache (Fast Poll)
        # Sequence expected for Fast Poll:
        # 1. Alarms (for Plant)
        # 2. Info (for SN)
        # 3. Metrics (for SN)
        # 4. EMS Probe
        mock_req.reset_mock()
        mock_req.side_effect = [
            (200, alarms_resp),
            (200, info_resp),
            (200, metrics_resp),
            (200, {}), # EMS
        ]
        
        res2 = await client.get_all_device_data()
        assert res2["data"]["S1"]["sw_version"] == "V1" # Still there from cache
        assert mock_req.call_count == 4
        
        # Verify specific URL paths for fast poll
        calls = mock_req.call_args_list
        assert calls[0][0][1] == "/api/alarm/v1/plantAlarmPage"
        assert calls[1][0][1] == "/api/device/v1/queryDeviceInfo"
        assert calls[2][0][1] == "/api/device/v1/queryDeviceData"

        # Third call: Force discovery
        mock_req.reset_mock()
        mock_req.side_effect = [
            (200, plant_resp),
            (200, device_resp),
            (200, sub_dev_resp),
            (200, alarms_resp),
            (200, info_resp),
            (200, metrics_resp),
            (200, {}), # EMS
        ]
        await client.get_all_device_data(force_discovery=True)
        assert mock_req.call_count == 7
