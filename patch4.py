with open("src/hyxi_cloud_api/api.py", "r") as f:
    content = f.read()

search = """    async def _process_alarms_and_back_discovery(
        self, alarm_results, plants, discovered_sns, now, metric_tasks
    ):"""

# In order to avoid the pylint "too-many-arguments" (which allows 5, we have 6 including self),
# we can group some arguments or just use a pylint disable for this specific method.
# Wait, metric_tasks, discovered_sns, now are just passed down.
# Can we disable the pylint rule locally?
# R0913: Too many arguments (6/5)
# R0917: Too many positional arguments (6/5)

replace = """    # pylint: disable=too-many-arguments,too-many-positional-arguments
    async def _process_alarms_and_back_discovery(
        self, alarm_results, plants, discovered_sns, now, metric_tasks
    ):"""

content = content.replace(search, replace)
with open("src/hyxi_cloud_api/api.py", "w") as f:
    f.write(content)
print("done")
