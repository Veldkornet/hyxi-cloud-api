"""Tests for the HYXI Cloud API client token handling."""

# pylint: disable=redefined-outer-name,wrong-import-position,invalid-name

import sys
from unittest.mock import MagicMock

# Mock aiohttp before importing the client to avoid ModuleNotFoundError in environments without it
sys.modules["aiohttp"] = MagicMock()

from unittest.mock import patch

import pytest

from src.hyxi_cloud_api.api import HyxiApiClient


@pytest.fixture
def api_client():
    """Fixture for HyxiApiClient."""
    session = MagicMock()
    return HyxiApiClient("access_key", "secret_key", "https://api.example.com", session)


def test_apply_token_response_token_field(api_client):
    """Verify it correctly picks 'token' from data and prefixes it with 'Bearer '."""
    data = {"token": "test_token_123"}
    assert api_client._apply_token_response(data) is True
    assert api_client.token == "Bearer test_token_123"


def test_apply_token_response_access_token_field(api_client):
    """Verify it correctly picks 'access_token' from data if 'token' is missing."""
    data = {"access_token": "test_access_token_456"}
    assert api_client._apply_token_response(data) is True
    assert api_client.token == "Bearer test_access_token_456"


def test_apply_token_response_no_token(api_client):
    """Verify it returns False if neither 'token' nor 'access_token' is present."""
    data = {"expiresIn": 3600}
    assert api_client._apply_token_response(data) is False
    assert api_client.token is None


@patch("time.time")
def test_apply_token_response_expiresIn_field(mock_time, api_client):
    """Verify it correctly picks 'expiresIn' for expiration calculation."""
    now = 1000000.0
    mock_time.return_value = now

    data = {"token": "xyz", "expiresIn": 3600}
    assert api_client._apply_token_response(data) is True
    # now + 3600 - 300 = 1003300
    assert api_client.token_expires_at == 1003300.0


@patch("time.time")
def test_apply_token_response_expires_in_field(mock_time, api_client):
    """Verify it correctly picks 'expires_in' if 'expiresIn' is missing."""
    now = 1000000.0
    mock_time.return_value = now

    data = {"token": "xyz", "expires_in": 3600}
    assert api_client._apply_token_response(data) is True
    assert api_client.token_expires_at == 1003300.0


@patch("time.time")
def test_apply_token_response_default_expiration(mock_time, api_client):
    """Verify it defaults to 6600 seconds if no expiration field is provided."""
    now = 1000000.0
    mock_time.return_value = now

    data = {"token": "xyz"}
    assert api_client._apply_token_response(data) is True
    # now + 6600 - 300 = 1006300
    assert api_client.token_expires_at == 1006300.0


@patch("time.time")
def test_apply_token_response_string_expiration(mock_time, api_client):
    """Verify it handles expiration values provided as strings (e.g., '7200')."""
    now = 1000000.0
    mock_time.return_value = now

    data = {"token": "xyz", "expiresIn": "7200"}
    assert api_client._apply_token_response(data) is True
    # now + 7200 - 300 = 1006900
    assert api_client.token_expires_at == 1006900.0


@patch("time.time")
def test_apply_token_response_buffer_application(mock_time, api_client):
    """Verify that the 300s safety buffer is correctly subtracted from the current time + expiration."""
    now = 1234567.89
    mock_time.return_value = now

    expires_in = 1000
    buffer_secs = 300
    data = {"token": "xyz", "expiresIn": expires_in}

    api_client._apply_token_response(data)

    expected_expires_at = now + expires_in - buffer_secs
    assert api_client.token_expires_at == expected_expires_at


def test_apply_token_response_both_tokens_present(api_client):
    """Verify that 'token' is prioritized over 'access_token' when both are present."""
    data = {"token": "test_token_123", "access_token": "test_access_token_456"}
    assert api_client._apply_token_response(data) is True
    assert api_client.token == "Bearer test_token_123"


def test_apply_token_response_empty_string_token(api_client):
    """Verify that an empty string '' for token returns False."""
    data = {"token": "", "access_token": ""}
    assert api_client._apply_token_response(data) is False
    assert api_client.token is None


@patch("time.time")
def test_apply_token_response_both_expires_present(mock_time, api_client):
    """Verify that 'expiresIn' is prioritized over 'expires_in' when both are present."""
    now = 1000000.0
    mock_time.return_value = now

    data = {"token": "xyz", "expiresIn": 3600, "expires_in": 7200}
    assert api_client._apply_token_response(data) is True
    # now + 3600 - 300 = 1003300
    assert api_client.token_expires_at == 1003300.0


@patch("time.time")
def test_apply_token_response_zero_expiration(mock_time, api_client):
    """Verify that an explicit 0 for expiration evaluates as falsy and falls back to the default 6600."""
    now = 1000000.0
    mock_time.return_value = now

    data = {"token": "xyz", "expiresIn": 0}
    assert api_client._apply_token_response(data) is True
    # now + 6600 - 300 = 1006300
    assert api_client.token_expires_at == 1006300.0


@patch("time.time")
def test_apply_token_response_empty_string_expiration(mock_time, api_client):
    """Verify that an empty string '' for expiration evaluates as falsy and falls back to 6600."""
    now = 1000000.0
    mock_time.return_value = now

    data = {"token": "xyz", "expiresIn": ""}
    assert api_client._apply_token_response(data) is True
    # now + 6600 - 300 = 1006300
    assert api_client.token_expires_at == 1006300.0
