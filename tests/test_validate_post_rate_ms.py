"""Tests for _validate_post_rate_ms."""

import pytest

from src.hyxi_cloud_api.api import HyxiApiClient

def test_validate_post_rate_ms_valid():
    """Test valid post rates."""
    HyxiApiClient._validate_post_rate_ms(5000)
    HyxiApiClient._validate_post_rate_ms(60000)
    HyxiApiClient._validate_post_rate_ms(3600000)

def test_validate_post_rate_ms_too_low():
    """Test post rate below 5000ms."""
    with pytest.raises(
        ValueError, match="post_rate must be between 5000 and 3600000 milliseconds"
    ):
        HyxiApiClient._validate_post_rate_ms(4999)

    with pytest.raises(
        ValueError, match="post_rate must be between 5000 and 3600000 milliseconds"
    ):
        HyxiApiClient._validate_post_rate_ms(0)

    with pytest.raises(
        ValueError, match="post_rate must be between 5000 and 3600000 milliseconds"
    ):
        HyxiApiClient._validate_post_rate_ms(-1000)

def test_validate_post_rate_ms_too_high():
    """Test post rate above 3600000ms."""
    with pytest.raises(
        ValueError, match="post_rate must be between 5000 and 3600000 milliseconds"
    ):
        HyxiApiClient._validate_post_rate_ms(3600001)

    with pytest.raises(
        ValueError, match="post_rate must be between 5000 and 3600000 milliseconds"
    ):
        HyxiApiClient._validate_post_rate_ms(5000000)
