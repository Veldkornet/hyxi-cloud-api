"""Tests for the _sanitize_dict function in hyxi_cloud_api.api."""

from unittest.mock import patch
from src.hyxi_cloud_api.api import _sanitize_dict


def test_sanitize_dict_plant_address():
    """Test that plantAddress is redacted correctly."""
    raw = {"plantAddress": "123 Main St"}
    result = _sanitize_dict(raw)
    assert result["plantAddress"] == "[REDACTED]"

    raw = {"plantAddress": ""}
    result = _sanitize_dict(raw)
    assert result["plantAddress"] == "[REDACTED]"


@patch("src.hyxi_cloud_api.api._mask_id", return_value="MASKED")
def test_sanitize_dict_sensitive_keys(mock_mask_id):
    """Test that keys matching _SENSITIVE_KEYS are correctly masked."""
    raw = {
        "deviceSn": "123456789",
        "parentSn": "short",
        "plantId": None,  # falsy value
    }
    with patch(
        "src.hyxi_cloud_api.api._SENSITIVE_KEYS", {"deviceSn", "parentSn", "plantId"}
    ):
        result = _sanitize_dict(raw)

    assert result["deviceSn"] == "MASKED"
    assert result["parentSn"] == "MASKED"
    assert result["plantId"] is None

    assert mock_mask_id.call_count == 2
    mock_mask_id.assert_any_call("123456789")
    mock_mask_id.assert_any_call("short")


def test_sanitize_dict_alarmname():
    """Test that alarmName is correctly masked."""
    raw = {
        "alarmName": "Low Battery Warning",
        "normalKey": "value",
    }
    result = _sanitize_dict(raw)
    assert result["alarmName"] != "Low Battery Warning"
    assert result["normalKey"] == "value"


def test_sanitize_dict_alarmstate_passthrough():
    """Test that alarmstate (non-sensitive) is properly passed through."""
    raw = {
        "alarmstate": "active",
        "alarmState": "inactive",
    }
    result = _sanitize_dict(raw)
    assert result["alarmstate"] == "active"
    assert result["alarmState"] == "inactive"


@patch("src.hyxi_cloud_api.api._mask_id", return_value="MASKED")
def test_sanitize_dict_auth_keys(mock_mask_id):
    """Test that authentication keys are correctly masked."""
    raw = {
        "token": "secret_token_123",
        "access_token": "secret_access_token",
        "refresh_token": "secret_refresh_token",
        "password": "super_secret_password",
    }
    with patch(
        "src.hyxi_cloud_api.api._SENSITIVE_KEYS",
        {"token", "access_token", "refresh_token", "password"},
    ):
        result = _sanitize_dict(raw)

    assert result["token"] == "MASKED"
    assert result["access_token"] == "MASKED"
    assert result["refresh_token"] == "MASKED"
    assert result["password"] == "MASKED"

    assert mock_mask_id.call_count == 4
    mock_mask_id.assert_any_call("secret_token_123")
    mock_mask_id.assert_any_call("secret_access_token")
    mock_mask_id.assert_any_call("secret_refresh_token")
    mock_mask_id.assert_any_call("super_secret_password")


def test_sanitize_dict_other_keys():
    """Test that non-sensitive, normal keys are not altered."""
    raw = {
        "normalKey": "value",
        "otherKey": 123,
    }
    result = _sanitize_dict(raw)
    assert result["normalKey"] == "value"
    assert result["otherKey"] == 123


def test_sanitize_dict_no_mutation():
    """Test that _sanitize_dict does not mutate the original dictionary."""
    raw = {"deviceSn": "10602251600016", "other": "val"}
    original = raw.copy()
    result = _sanitize_dict(raw)
    assert raw == original
    assert result != original
