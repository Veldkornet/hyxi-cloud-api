"""Tests for data parser logic in the API."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.hyxi_cloud_api.api import HyxiApiClient, _compute_derived_metrics


@pytest.mark.asyncio
async def test_api_parsing():
    """Verify that _fetch_device_metrics successfully parses and extracts expected values."""
    # Fake the exact list structure the HYXI cloud actually returns
    fake_json = {
        "success": True,
        "data": [
            {"dataKey": "totalE", "dataValue": "2731.9"},
            {"dataKey": "pbat", "dataValue": "-500"},  # -500W AC-reported power (charging)
            {"dataKey": "batP", "dataValue": "-469"},  # -469W raw DC power (V×I) — preferred
            {"dataKey": "gridP", "dataValue": "1.5"},  # 1.5 kW exported
        ],
    }

    # Mock the aiohttp response context manager
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value=fake_json)
    mock_response.raise_for_status = MagicMock()  # Pretend we got a 200 OK

    # Use MagicMock so .get() returns a context manager, not a coroutine
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Initialize the API with the fake session
    api = HyxiApiClient(
        access_key="test_ak",
        secret_key="test_sk",
        base_url="https://test.com",
        session=mock_session,
    )

    # Create the dummy dictionary that the code expects to update
    entry = {"metrics": {}, "device_type_code": "1"}  # Inverter

    # Run the actual parsing method
    await api._fetch_device_metrics("SN123", entry)

    # Verify extracted raw value
    assert entry["metrics"]["totalE"] == "2731.9"

    # Verify inline math converter (gridP * 1000)
    assert entry["metrics"]["grid_export"] == 1500.0

    # batP takes priority over pbat for the derived sensors (raw DC power is more accurate)
    assert entry["metrics"]["bat_charging"] == 469.0
    assert entry["metrics"]["bat_discharging"] == 0.0

    # bat_power_dc is directly exposed as the raw DC value
    assert entry["metrics"]["bat_power_dc"] == -469.0


@pytest.mark.asyncio
async def test_api_parsing_batp_only():
    """Verify derived metrics are computed when only batP is present (no pbat/gridP)."""
    # Real-world scenario: inverter reporting batP but no pbat or gridP
    fake_json = {
        "success": True,
        "data": [
            {"dataKey": "batV", "dataValue": "521.5"},
            {"dataKey": "batI", "dataValue": "0.9"},
            {"dataKey": "batP", "dataValue": "469"},  # Discharging
        ],
    }

    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value=fake_json)
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response

    api = HyxiApiClient(
        access_key="test_ak",
        secret_key="test_sk",
        base_url="https://test.com",
        session=mock_session,
    )

    entry = {"metrics": {}, "device_type_code": "1"}  # Inverter
    await api._fetch_device_metrics("SN123", entry)

    # Derived metrics should still fire when only batP is present
    assert entry["metrics"]["bat_discharging"] == 469.0
    assert entry["metrics"]["bat_charging"] == 0.0
    assert entry["metrics"]["bat_power_dc"] == 469.0


@pytest.mark.asyncio
async def test_api_device_info_parsing():
    """Verify that _fetch_device_info successfully parses and extracts expected static values."""
    fake_json = {
        "success": True,
        "data": [
            {"dataKey": "swVerSys", "dataValue": "v1.2.3"},
            {"dataKey": "signalIntensity", "dataValue": "good"},
            {"dataKey": "maxChargingDischargingPower", "dataValue": "5000"},
            {"dataKey": "batCap", "dataValue": "100"},
        ],
    }

    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value=fake_json)
    mock_response.raise_for_status = MagicMock()

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_response

    api = HyxiApiClient(
        access_key="test_ak",
        secret_key="test_sk",
        base_url="https://test.com",
        session=mock_session,
    )

    entry = {"metrics": {}, "device_type_code": "1"}  # Inverter

    await api._fetch_device_info("SN123", entry)

    # Verify extracted fw version
    assert entry["sw_version"] == "v1.2.3"

    # Verify basic mapping
    assert entry["metrics"]["signalIntensity"] == "good"
    assert entry["metrics"]["batCap"] == 100.0

    # Verify fallback logic
    assert entry["metrics"]["maxChargePower"] == 5000.0
    assert entry["metrics"]["maxDischargePower"] == 5000.0


def test_compute_derived_metrics_basic():
    """Test standard derived metric calculation with charging battery."""
    m_raw = {
        "gridP": "-0.5",  # -500W (Import)
        "pbat": "-100.0",  # -100W (Charging)
        "ph1Loadp": "200.0",
        "ph2Loadp": "150.0",
        "ph3Loadp": "50.0",
        "batCharge": "1000.0",
        "batDisCharge": "500.0",
    }
    res = _compute_derived_metrics(m_raw)

    assert res["home_load"] == 400.0
    assert res["grid_import"] == 500.0
    assert res["grid_export"] == 0.0
    assert res["bat_charging"] == 100.0
    assert res["bat_discharging"] == 0.0
    assert res["bat_charge_total"] == 1000.0
    assert res["bat_discharge_total"] == 500.0


def test_compute_derived_metrics_discharging():
    """Test standard derived metric calculation with discharging battery."""
    m_raw = {
        "gridP": "0.2",  # 200W (Export)
        "pbat": "300.0",  # 300W (Discharging)
        "ph1Loadp": "100.0",
        "ph2Loadp": "0.0",
        "ph3Loadp": "0.0",
    }
    res = _compute_derived_metrics(m_raw)
    assert res["grid_import"] == 0.0
    assert res["grid_export"] == 200.0
    assert res["bat_charging"] == 0.0
    assert res["bat_discharging"] == 300.0


def test_batp_priority():
    """Verify that batP (DC) is preferred over pbat (AC estimate)."""
    # Case 1: Both present, batP takes precedence
    m_raw = {
        "pbat": "100.0",  # AC estimate
        "batP": "115.5",  # DC reality (the truthful value)
    }
    res = _compute_derived_metrics(m_raw)
    assert res["bat_discharging"] == 115.5
    assert res["bat_power_dc"] == 115.5

    # Case 2: batP missing, fall back to pbat
    m_raw = {"pbat": "200.0"}
    res = _compute_derived_metrics(m_raw)
    assert res["bat_discharging"] == 200.0
    assert res["bat_power_dc"] == 0.0

    # Case 3: Charging (negative values)
    m_raw = {"pbat": "-100.0", "batP": "-110.0"}
    res = _compute_derived_metrics(m_raw)
    assert res["bat_charging"] == 110.0
    assert res["bat_power_dc"] == -110.0


def test_batp_trigger_logic():
    """Verify that metrics are computed even if ONLY batP is present."""
    m_raw = {"batP": "500.0"}
    res = _compute_derived_metrics(m_raw)
    assert res["bat_discharging"] == 500.0
    assert res["bat_power_dc"] == 500.0


def test_compute_derived_metrics_empty():
    """Test robustness with missing keys."""
    res = _compute_derived_metrics({})
    assert res["home_load"] == 0.0
    assert res["grid_import"] == 0.0
    assert res["bat_charging"] == 0.0


def test_compute_derived_metrics_invalid():
    """Test robustness with non-numeric garbage."""
    m_raw = {"gridP": "GHOST", "pbat": None, "ph1Loadp": ""}
    res = _compute_derived_metrics(m_raw)
    assert res["grid_import"] == 0.0
    assert res["bat_discharging"] == 0.0
    assert res["home_load"] == 0.0
