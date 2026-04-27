with open("tests/test_fetch_device_list_for_plant.py", "r") as f:
    content = f.read()

content = content.replace("    import aiohttp\n", "")
content = content.replace("    \n    api._request", "    api = HyxiApiClient(\"ak\", \"sk\", \"https://api.com\", MagicMock())\n    api._request")

with open("tests/test_fetch_device_list_for_plant.py", "w") as f:
    f.write(content)
