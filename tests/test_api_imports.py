"""Tests for import fallbacks in the API client module."""

import builtins
import sys
import unittest.mock


def test_utc_import_fallback():
    """Test the ImportError fallback for datetime.UTC at line 27."""
    original_import = builtins.__import__

    def mocked_import(name, global_vars=None, local_vars=None, fromlist=(), level=0):
        # Trigger ImportError when trying to import UTC from datetime
        if name == "datetime" and fromlist and "UTC" in fromlist:
            raise ImportError("mocked ImportError for UTC")
        return original_import(name, global_vars, local_vars, fromlist, level)

    original_api = sys.modules.get("hyxi_cloud_api.api")
    if "hyxi_cloud_api.api" in sys.modules:
        del sys.modules["hyxi_cloud_api.api"]

    try:
        with unittest.mock.patch("builtins.__import__", side_effect=mocked_import):
            from hyxi_cloud_api import api  # pylint: disable=import-outside-toplevel

            assert api.UTC is not None
            assert api.UTC.tzname(None) == "UTC"
    finally:
        # Restore normal module state
        if "hyxi_cloud_api.api" in sys.modules:
            del sys.modules["hyxi_cloud_api.api"]
        if original_api is not None:
            sys.modules["hyxi_cloud_api.api"] = original_api
