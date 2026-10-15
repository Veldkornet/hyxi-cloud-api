"""Initialization module for HYXi Cloud API."""

from .api import (
    AuthorizationType,
    DiscoveryResult,
    HyxiApiClient,
    HyxiAuthError,
    SubscribeResult,
    Subscription,
    SubscriptionType,
    TokenNetworkError,
    TokenRequestError,
)

# Module-level alias so callers can do: from hyxi_cloud_api import VPP_ACTIVE_MODES
VPP_ACTIVE_MODES: frozenset[str] = HyxiApiClient.VPP_ACTIVE_MODES

__version__ = "1.4.9"
__all__ = [
    "VPP_ACTIVE_MODES",
    "AuthorizationType",
    "DiscoveryResult",
    "HyxiApiClient",
    "HyxiAuthError",
    "SubscribeResult",
    "Subscription",
    "SubscriptionType",
    "TokenNetworkError",
    "TokenRequestError",
]
