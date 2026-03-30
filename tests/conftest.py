import sys
from unittest.mock import MagicMock

# Mock aiohttp and other dependencies that might be missing
sys.modules["aiohttp"] = MagicMock()
sys.modules["hypothesis"] = MagicMock()
sys.modules["hypothesis.strategies"] = MagicMock()
sys.modules["pytest_asyncio"] = MagicMock()
