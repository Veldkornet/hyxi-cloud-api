"""Tests for the Device Control API methods."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.hyxi_cloud_api.api import HyxiApiClient


@pytest.mark.asyncio
async def test_set_mode_idle():
    """Test set_mode_idle sends controlId 1062."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    result = await api.set_mode_idle("SN123")

    assert result["success"] is True
    api._request.assert_called_once()
    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["1062"] == ""


@pytest.mark.asyncio
async def test_set_mode_charge():
    """Test set_mode_charge sends controlId 1063 with wattage."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    result = await api.set_mode_charge("SN123", watts=3000)

    assert result["success"] is True
    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["1063"] == "3000"


@pytest.mark.asyncio
async def test_set_mode_discharge():
    """Test set_mode_discharge sends controlId 1064 with wattage."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    result = await api.set_mode_discharge("SN123", watts=2500)

    assert result["success"] is True
    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["1064"] == "2500"


@pytest.mark.asyncio
async def test_set_mode_self_consume():
    """Test set_mode_self_consume sends controlId 1065."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    result = await api.set_mode_self_consume("SN123")

    assert result["success"] is True
    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["1065"] == ""


@pytest.mark.asyncio
async def test_set_peak_shaving():
    """Test set_peak_shaving sends controlId 1021 with mapped value."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    await api.set_peak_shaving("SN123", action="charge")

    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["1021"] == "1"


@pytest.mark.asyncio
async def test_set_peak_shaving_invalid_action():
    """Test set_peak_shaving raises ValueError for invalid action."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)

    with pytest.raises(ValueError, match="Invalid peak shaving action"):
        await api.set_peak_shaving("SN123", action="invalid")


@pytest.mark.asyncio
async def test_set_frequency_control():
    """Test set_frequency_control correctly sets parameters."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api.set_device_control = AsyncMock(return_value={"success": True})

    # Test enabled=True
    result = await api.set_frequency_control("SN123", enabled=True)
    assert result == {"success": True}

    call_args = api.set_device_control.call_args
    if "param_code" in call_args.kwargs or (len(call_args.args) == 0 and "device_sn" in call_args.kwargs):
        api.set_device_control.assert_any_call(
            device_sn="SN123",
            param_code="pfEn",
            value=1,
            extra_params={"pfSys": 1}
        )
    else:
        api.set_device_control.assert_any_call("SN123", {1020: "1"})

    api.set_device_control.reset_mock()

    # Test enabled=False
    result = await api.set_frequency_control("SN123", enabled=False)
    assert result == {"success": True}

    call_args = api.set_device_control.call_args
    if "param_code" in call_args.kwargs or (len(call_args.args) == 0 and "device_sn" in call_args.kwargs):
        api.set_device_control.assert_any_call(
            device_sn="SN123",
            param_code="pfEn",
            value=0,
            extra_params={}
        )
    else:
        api.set_device_control.assert_any_call("SN123", {1020: "0"})






@pytest.mark.asyncio
async def test_control_error_on_auth_failed():
    """Test ControlError is raised when authentication fails."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value="auth_failed")

    with pytest.raises(api.ControlError, match="Authentication failed"):
        await api.set_mode_idle("SN123")


@pytest.mark.asyncio
async def test_control_error_on_no_token():
    """Test ControlError is raised when token cannot be obtained."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=False)

    with pytest.raises(api.ControlError, match="Could not obtain API token"):
        await api.set_mode_idle("SN123")


@pytest.mark.asyncio
async def test_control_error_on_api_failure():
    """Test ControlError is raised when API returns success=False."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(
        return_value=(
            200,
            {"success": False, "code": "C000001", "msg": "Parameter error"},
        )
    )

    with pytest.raises(api.ControlError, match="controlMap write failed"):
        await api.set_mode_charge("SN123", watts=3000)


@pytest.mark.asyncio
async def test_set_mode_charge_invalid_watts():
    """Test set_mode_charge raises ValueError for zero/negative watts."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)

    with pytest.raises(ValueError, match="watts must be a positive integer"):
        await api.set_mode_charge("SN123", watts=0)

    with pytest.raises(ValueError, match="watts must be a positive integer"):
        await api.set_mode_charge("SN123", watts=-100)


@pytest.mark.asyncio
async def test_set_mode_discharge_invalid_watts():
    """Test set_mode_discharge raises ValueError for zero/negative watts."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)

    with pytest.raises(ValueError, match="watts must be a positive integer"):
        await api.set_mode_discharge("SN123", watts=0)

    with pytest.raises(ValueError, match="watts must be a positive integer"):
        await api.set_mode_discharge("SN123", watts=-100)


@pytest.mark.asyncio
async def test_set_micro_power():
    """Test set_micro_power sends controlId 3011 with value '1' or '0'."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    await api.set_micro_power("SN123", power_on=True)
    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["3011"] == "1"

    api._request.reset_mock()
    await api.set_micro_power("SN123", power_on=False)
    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["3011"] == "0"


@pytest.mark.asyncio
async def test_set_micro_power_limit():
    """Test set_micro_power_limit sends controlId 3012 with percentage string."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    await api.set_micro_power_limit("SN123", percentage=80)

    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["3012"] == "80"


@pytest.mark.asyncio
async def test_set_micro_power_limit_invalid_percentage():
    """Test set_micro_power_limit raises ValueError for out-of-range percentage."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)

    with pytest.raises(ValueError, match="percentage must be between 0 and 100"):
        await api.set_micro_power_limit("SN123", percentage=101)

    with pytest.raises(ValueError, match="percentage must be between 0 and 100"):
        await api.set_micro_power_limit("SN123", percentage=-1)


@pytest.mark.asyncio
async def test_restart_device():
    """Test restart_device sends controlId 3013 with value '1'."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = MagicMock()
    # Handle async response for _request
    async_mock = AsyncMock(return_value=(200, {"success": True}))
    api._request.side_effect = async_mock

    await api.restart_device("SN123")

    api._request.assert_called_once()
    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"]["3013"] == "1"


@pytest.mark.asyncio
async def test_alter_alarm():
    """Test alter_alarm sends correct POST request payload."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    result = await api.alter_alarm([10086, 10087])

    assert result["success"] is True
    api._request.assert_called_once()
    call_args, call_kwargs = api._request.call_args
    assert call_args[0] == "POST"
    assert call_args[1] == "/api/alarm/v1/alterAlarm"
    body = call_kwargs.get("json")
    assert body == {"ids": [10086, 10087], "state": 1}


@pytest.mark.asyncio
async def test_alter_alarm_auth_failed():
    """Test alter_alarm raises ControlError when authentication fails."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value="auth_failed")

    with pytest.raises(api.ControlError, match="Authentication failed"):
        await api.alter_alarm([10086])


@pytest.mark.asyncio
async def test_alter_alarm_api_failure():
    """Test alter_alarm raises ControlError when API returns success=False."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(
        return_value=(
            200,
            {"success": False, "code": "C000002", "msg": "Internal error"},
        )
    )

    with pytest.raises(api.ControlError, match="alarm alteration failed"):
        await api.alter_alarm([10086])


@pytest.mark.asyncio
async def test_set_device_control_success():
    """Test set_device_control sends correct control map and handles success."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    result = await api.set_device_control("SN123", {"1062": "1"})

    assert result["success"] is True
    api._request.assert_called_once()
    call_args, call_kwargs = api._request.call_args
    assert call_args[0] == "POST"
    assert call_args[1] == "/api/device/v2/control"
    body = call_kwargs.get("json")
    assert body == {"deviceControlMap": {"SN123": {"1062": "1"}}}


@pytest.mark.asyncio
async def test_set_device_control_key_conversion():
    """Test set_device_control correctly converts integer keys to strings."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, {"success": True}))

    result = await api.set_device_control("SN123", {1062: "1", "1063": "3000"})

    assert result["success"] is True
    call_kwargs = api._request.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert body["deviceControlMap"]["SN123"] == {"1062": "1", "1063": "3000"}


@pytest.mark.asyncio
async def test_set_device_control_no_response():
    """Test set_device_control raises ControlError when no response is returned."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(return_value=(200, None))

    with pytest.raises(
        api.ControlError, match="controlMap write failed \\(code=no_response\\):"
    ):
        await api.set_device_control("SN123", {"1062": "1"})


@pytest.mark.asyncio
async def test_set_device_control_api_failure():
    """Test set_device_control raises ControlError when API returns success=False."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock(
        return_value=(200, {"success": False, "code": "E123", "msg": "API Error"})
    )

    with pytest.raises(
        api.ControlError, match="controlMap write failed \\(code=E123\\): API Error"
    ):
        await api.set_device_control("SN123", {"1062": "1"})


@pytest.mark.asyncio
async def test_set_device_control_empty_settings():
    """Test set_device_control handles empty settings gracefully, warning and returning empty dict."""
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._refresh_token = AsyncMock(return_value=True)
    api._request = AsyncMock()

    result = await api.set_device_control("SN123", {})

    assert result == {}
    api._request.assert_not_called()
