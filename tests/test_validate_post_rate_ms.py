"""Tests for _validate_post_rate_ms."""

from unittest.mock import MagicMock

from src.hyxi_cloud_api.api import HyxiApiClient


def test_validate_post_rate_ms_valid():
    """Test valid post rates."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    assert api._validate_post_rate_ms(5000) is True
    assert api._validate_post_rate_ms(60000) is True
    assert api._validate_post_rate_ms(3600000) is True


def test_validate_post_rate_ms_too_low():
    """Test post rate below 5000ms."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    assert api._validate_post_rate_ms(4999) is False
    assert api._validate_post_rate_ms(0) is False
    assert api._validate_post_rate_ms(-1000) is False
