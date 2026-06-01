import pytest
from src.hyxi_cloud_api.api import HyxiApiClient

def test_validate_subscription_device_sns_empty_list():
    with pytest.raises(ValueError, match="device_sn_list must contain at least one device SN"):
        HyxiApiClient._validate_subscription_device_sns([])

def test_validate_subscription_device_sns_too_many():
    device_sns = [f"SN{i}" for i in range(1001)]
    with pytest.raises(ValueError, match="device_sn_list cannot contain more than 1000 device SNs"):
        HyxiApiClient._validate_subscription_device_sns(device_sns)

def test_validate_subscription_device_sns_success():
    # Should not raise any exception
    HyxiApiClient._validate_subscription_device_sns(["SN1", "SN2"])
    HyxiApiClient._validate_subscription_device_sns([f"SN{i}" for i in range(1000)])
