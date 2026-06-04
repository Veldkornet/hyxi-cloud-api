"""Initialization module for HYXi Cloud API."""

from .api import HyxiApiClient

# Module-level alias so callers can do: from hyxi_cloud_api import VPP_ACTIVE_MODES
VPP_ACTIVE_MODES: frozenset[str] = HyxiApiClient.VPP_ACTIVE_MODES

__version__ = "1.3.5"
__all__ = ["VPP_ACTIVE_MODES", "HyxiApiClient"]
