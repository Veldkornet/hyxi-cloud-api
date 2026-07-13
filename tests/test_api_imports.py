"""Tests for import fallbacks in the API client module."""

import builtins
import sys
import unittest.mock


def test_utc_import_fallback():
    """Test the ImportError fallback for datetime.UTC at line 27."""
    original_import = builtins.__import__

    def mocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        # Trigger ImportError when trying to import UTC from datetime
        if name == "datetime" and fromlist and "UTC" in fromlist:
            raise ImportError("mocked ImportError for UTC")
        return original_import(name, globals, locals, fromlist, level)

    # Force a reload of the api module by removing it from sys.modules
    for module_name in list(sys.modules.keys()):
        if module_name.startswith("src.hyxi_cloud_api"):
            del sys.modules[module_name]

    with unittest.mock.patch("builtins.__import__", side_effect=mocked_import):
        import src.hyxi_cloud_api.api as api  # pylint: disable=import-outside-toplevel

        assert api.UTC is not None
        assert api.UTC.tzname(None) == "UTC"
