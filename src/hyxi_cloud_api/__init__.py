"""Initialization module for HYXi Cloud API."""

from .api import HyxiApiClient as HyxiApiClient  # pylint: disable=useless-import-alias

__version__ = "1.1.3"
__all__ = ["HyxiApiClient"]
