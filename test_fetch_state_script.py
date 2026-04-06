from src.hyxi_cloud_api.api import FetchState
from dataclasses import asdict

state = FetchState(now="2023-10-27T10:00:00Z")
print(f"State: {asdict(state)}")
