"""Tests for the set_log_salt function in api.py."""

import pytest

import hyxi_cloud_api.api as api
from hyxi_cloud_api.api import _mask_id, set_log_salt


@pytest.fixture(autouse=True)
def restore_log_salt():
    """Fixture to ensure the original _LOG_SALT is restored after each test."""
    original_salt = api._LOG_SALT
    yield
    api._LOG_SALT = original_salt
    _mask_id.cache_clear()


def test_set_log_salt_with_string():
    """Test that setting log salt with a string correctly encodes it to bytes and clears cache."""
    # Given an initial salt
    set_log_salt(b"initial_salt_123")

    # Pre-populate cache for a specific ID
    test_id = "test_sn_123"
    initial_masked = _mask_id(test_id)

    # Act
    set_log_salt("new_string_salt")

    # Assert
    assert api._LOG_SALT == b"new_string_salt"

    # Verify the cache was cleared and new salt is used
    new_masked = _mask_id(test_id)
    assert new_masked != initial_masked


def test_set_log_salt_with_bytes():
    """Test that setting log salt with bytes correctly assigns it and clears cache."""
    # Given an initial salt
    set_log_salt("initial_salt_123")

    # Pre-populate cache for a specific ID
    test_id = "test_sn_123"
    initial_masked = _mask_id(test_id)

    # Act
    set_log_salt(b"new_bytes_salt")

    # Assert
    assert api._LOG_SALT == b"new_bytes_salt"

    # Verify the cache was cleared and new salt is used
    new_masked = _mask_id(test_id)
    assert new_masked != initial_masked


def test_set_log_salt_clears_mask_id_cache():
    """Test that setting the log salt explicitly clears the _mask_id cache."""
    # Ensure cache is initially populated
    _mask_id("dummy_id_for_cache_test")

    # Check cache info directly (if cache info is accessible)
    cache_info = _mask_id.cache_info()
    assert cache_info.currsize > 0

    # Act
    set_log_salt("another_salt")

    # Assert cache size is 0
    cache_info_after = _mask_id.cache_info()
    assert cache_info_after.currsize == 0
