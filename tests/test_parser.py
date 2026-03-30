from hyxi_cloud_api.api import _compute_derived_metrics


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
