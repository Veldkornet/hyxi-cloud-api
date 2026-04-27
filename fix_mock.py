import re

with open("tests/test_discovery.py", "r") as f:
    content = f.read()

# Instead of side_effect returning limited results, just return a single default dict
new_mock = """    mock_response.__aenter__.return_value.json = AsyncMock(
        return_value={
            "success": True,
            "data": {
                "deviceList": [
                    {
                        "deviceSn": "COLL_001",
                        "deviceType": "COLLECTOR",
                        "deviceName": "My Collector",
                    }
                ],
                "childDevice": [
                    {
                        "deviceSn": "INV_001",
                        "deviceType": "1",
                        "deviceName": "My Inverter",
                    }
                ]
            },
        }
    )"""

content = re.sub(r'    mock_response.__aenter__.return_value.json = AsyncMock\(\n        side_effect=\[\n.*?\n        \]\n    \)', new_mock, content, flags=re.DOTALL)

with open("tests/test_discovery.py", "w") as f:
    f.write(content)
