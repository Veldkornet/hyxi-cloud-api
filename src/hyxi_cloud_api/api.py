"""HYXI Cloud API Client for retrieving inverter and battery data.

This module is intentionally large: it includes the full ALARM_CODE_MAP,
INTERNAL_ERROR_MAP, and DEVICE_TYPE_MAP reference tables to avoid external
dependencies. Suppress the module-size warning accordingly.
"""  # pylint: disable=too-many-lines

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

try:
    from datetime import UTC, datetime
except ImportError:
    from datetime import datetime

    # pylint: disable=W0127,E0601
    UTC = UTC

import aiohttp


@dataclass
class FetchState:
    """State object to hold shared data during a device fetch cycle."""

    now: str
    metric_tasks: list = field(default_factory=list)
    discovered_sns: set = field(default_factory=set)
    results: dict = field(default_factory=dict)
    plants: list = field(default_factory=list)


_LOGGER = logging.getLogger(__name__)
_battery_device_types = ("INVERTER", "ESS", "HALO", "1", "15")
_BATTERY_DEVICE_REGEX = re.compile("|".join(_battery_device_types))
_parent_device_types = ("COLLECTOR", "DMU", "INVERTER")
_PARENT_DEVICE_REGEX = re.compile("|".join(_parent_device_types))
_COLLECTOR_FILTER_KEYWORDS = (
    "bat",
    "pv",
    "grid",
    "load",
    "ph1",
    "ph2",
    "ph3",
)

_COLLECTOR_FILTER_REGEX = re.compile("|".join(_COLLECTOR_FILTER_KEYWORDS))

# Official HYXI Alarm Code Reference Table
ALARM_CODE_MAP = {
    "704": "The ambient temperature is too high",
    "705": "Low ambient temperature",
    "706": "Inv radiator temperature overheating",
    "768": "Overvoltage alarm",
    "769": "Over temperature alarm",
    "770": "Low temperature alarm",
    "832": "Abnormal alarm of environmental temperature sensor",
    "833": "Inverter temperature sensor abnormal alarm",
    "1088": "AC voltage overvoltage",
    "1089": "Transient Overvoltage in Power Grid",
    "1090": "Power grid overvoltage lasting for 10 minutes",
    "1091": "AC voltage undervoltage",
    "1092": "AC voltage over frequency",
    "1093": "AC voltage underfrequency",
    "1094": "Power grid failure",
    "1095": "Communication overcurrent",
    "1096": "AC instantaneous overcurrent",
    "1097": "Permanent fault of inverter overcurrent",
    "1098": "Inverter output with wave by wave current limiting",
    "1099": "The power grid overvoltage Ctf",
    "1100": "Grid undervoltage Ctf",
    "1101": "Power grid overfrequency Ctf",
    "1102": "Grid underfrequency Ctf",
    "1103": "If a fault occurs, reconnect the Ctf",
    "1104": "10min Power grid overvoltage Cft",
    "1105": "LN short circuit",
    "1106": "AC instantaneous overvoltage",
    "1107": "CBC shutdown",
    "1108": "Grid connected certification: Overvoltage fault in the power grid",
    "1109": "Grid connected certification for under voltage faults in the power grid",
    "1110": "Grid certification: Over frequency fault in the power grid",
    "1111": "Grid connected certification: Underfrequency fault in the power grid",
    "1112": "Continuous grid connection failure fault",
    "1152": "PV1 reverse connection fault",
    "1153": "PV2 reverse connection fault",
    "1154": "PV3 reverse connection fault",
    "1155": "PV4 reverse connection fault",
    "1156": "PV5 reverse connection fault",
    "1157": "PV6 reverse connection fault",
    "1158": "PV7 reverse connection fault",
    "1159": "PV8 reverse connection fault",
    "1160": "PV9 reverse connection fault",
    "1161": "PV10 reverse connection fault",
    "1162": "Reserve 50 routes",
    "1163": "PV1 overcurrent fault",
    "1164": "PV2 overcurrent fault",
    "1165": "PV3 overcurrent fault",
    "1166": "PV4 overcurrent fault",
    "1167": "PV5 overcurrent fault",
    "1168": "PV6 overcurrent fault",
    "1169": "PV7 overcurrent fault",
    "1170": "PV8 overcurrent fault",
    "1171": "PV9 overcurrent fault",
    "1172": "PV10 overcurrent fault",
    "1173": "Reserve 50 routes",
    "1174": "DC busbar voltage overvoltage",
    "1175": "DC instantaneous overvoltage",
    "1176": "DC bus undervoltage",
    "1177": "BDC current instantaneous overcurrent",
    "1178": "Battery charging and discharging overcurrent",
    "1179": "Battery voltage undervoltage",
    "1180": "Battery voltage overvoltage",
    "1181": "PV1 overvoltage",
    "1183": "PV2 overvoltage",
    "1185": "The PV reverse connection is faulty",
    "1186": "PV1 transient overvoltage",
    "1187": "Instantaneous overvoltage of PV2",
    "1188": "PV1 transient overflow",
    "1189": "The PV2 transient overflow",
    "1190": "PV instantaneous overcurrent",
    "1191": "PV3 instantaneous overvoltage",
    "1192": "PV3 instantaneous overcurrent",
    "1193": "PV3 overvoltage",
    "1194": "PV overvoltage level 1 fault",
    "1216": "Leakage current fault",
    "1217": "Insulation impedance fault",
    "1218": "Grounding fault",
    "1219": "High DC component of inverter voltage",
    "1220": "High DC component of inverter current",
    "1222": "AFCI failure",
    "1223": "The BMS communication is faulty",
    "1224": "Battery connection exception",
    "1225": "Ac transient overcurrent",
    "1226": "Fan malfunction",
    "1227": "Grid connected relay fault",
    "1228": "Bypass relay fault",
    "1229": "Off grid port relay fault",
    "1230": "BDC soft start relay fault",
    "1231": "SDSP detects power grid faults",
    "1235": "BDC hardware overcurrent",
    "1236": "Inverter self-test fault",
    "1237": "Leakage current sensor fault",
    "1238": "Synchronization Failure",
    "1239": "12V power supply abnormality",
    "1240": "Continuous startup fault",
    "1241": "AD zero drift correction value error",
    "1242": "Software forced shutdown",
    "1302": "Battery reverse connection fault",
    "1344": "AFCI self-test alarm",
    "1345": "Electricity meter/CT reverse connection alarm",
    "1346": "Electricity meter communication abnormal alarm",
    "1347": "Communication abnormality between main and auxiliary DSP",
    "1348": "Fan alarm",
    "1349": "BDC temperature sensor abnormal alarm",
    "1350": "Boost temperature sensor abnormal alarm",
    "1351": "Inverter over temperature alarm",
    "1352": "Boost over temperature alarm",
    "1355": "Boost under temperature alarm",
    "1356": "DSP under temperature alarm",
    "1357": "ARM communication abnormality",
    "1358": "Inverter over temperature and load drop alarm",
    "1359": "PV voltage overvoltage alarm",
    "1360": "Off grid voltage low alarm",
    "1361": "PVcmd latch alarm",
    "1408": "Communication with the electricity meter",
    "1409": "Communication with batteries",
    "1410": "Overload fault",
    "1411": "Product type error",
    "1412": "AFCI communication failure",
    "1413": "Power level mismatch",
    "1414": "AFCI arc fault",
    "1415": "Insufficient off grid energy supply",
    "1416": "Battery sleep mode",
    "1417": "Battery emergency stop fault",
    "1418": "Optimizer communication failure",
    "1419": "Load point table malfunction",
    "1420": "Off grid overload fault",
    "1421": "Grid overload fault",
    "1422": "Battery not connected to high voltage",
    "1423": "Insufficient Off Grid SOC",
    "1424": "Battery Strong Charging Request",
    "1425": "Continuous overload fault",
    "1426": "Battery over discharge protection alarm",
    "1427": "High voltage protection warning under battery",
    "1428": "Abnormal diesel generator power",
    "1429": "Diesel generator not starting up properly",
    "1430": "Abnormal shutdown of diesel generator",
    "4800": "High ambient temperature",
    "4801": "Low ambient temperature",
    "4864": "Overvoltage alarm",
    "4865": "Over temperature alarm",
    "4866": "Low temperature alarm",
    "4928": "Abnormal alarm of environmental temperature sensor",
    "4929": "Inverter temperature sensor abnormal alarm",
    "5184": "Grid overvoltage/high voltage",
    "5185": "Transient Overvoltage in Power Grid",
    "5186": "10 minute power grid overvoltage",
    "5187": "Power grid undervoltage/low voltage",
    "5188": "Grid Overfrequency/High Frequency",
    "5189": "Under frequency/low frequency of power grid",
    "5190": "Power grid failure",
    "5191": "Inverter overcurrent fault",
    "5192": "Inverter instantaneous overcurrent fault",
    "5193": "Permanent fault of inverter overcurrent",
    "5194": "Inverter output with wave by wave current limiting",
    "5195": "Grid overvoltage Ctf",
    "5196": "Under voltage Ctf of power grid",
    "5197": "Grid Overfrequency Ctf",
    "5198": "Under frequency Ctf of power grid",
    "5199": "Fault reconnection Ctf",
    "5200": "10 minute power grid overvoltage Cft",
    "5201": "LN short circuit",
    "5202": "AC instantaneous overvoltage",
    "5248": "PV1 reverse connection fault",
    "5249": "PV2 reverse connection fault",
    "5250": "PV3 reverse connection fault",
    "5251": "PV4 reverse connection fault",
    "5252": "PV5 reverse connection fault",
    "5253": "PV6 reverse connection fault",
    "5254": "PV7 reverse connection fault",
    "5255": "PV8 reverse connection fault",
    "5256": "PV9 reverse connection fault",
    "5257": "PV10 reverse connection fault",
    "5258": "Reserve 50 routes",
    "5259": "PV1 overcurrent fault",
    "5260": "PV2 overcurrent fault",
    "5261": "PV3 overcurrent fault",
    "5262": "PV4 overcurrent fault",
    "5263": "PV5 overcurrent fault",
    "5264": "PV6 overcurrent fault",
    "5265": "PV7 overcurrent fault",
    "5266": "PV8 overcurrent fault",
    "5267": "PV9 overcurrent fault",
    "5268": "PV10 overcurrent fault",
    "5269": "Reserve 50 routes",
    "5270": "BUS bus average overvoltage",
    "5271": "BUS bus instantaneous overvoltage",
    "5273": "BDC current instantaneous overcurrent",
    "5274": "BDC average current overcurrent",
    "5275": "Battery average low voltage fault",
    "5277": "PV1 overvoltage",
    "5279": "PV2 overvoltage",
    "5281": "PV reverse connection fault",
    "5282": "PV1 instantaneous overvoltage",
    "5283": "PV2 instantaneous overvoltage",
    "5284": "PV1 instantaneous overcurrent",
    "5285": "PV2 instantaneous overcurrent",
    "5286": "PV instantaneous overcurrent",
    "5287": "PV3 instantaneous overvoltage",
    "5288": "PV3 instantaneous overcurrent",
    "5289": "PV3 overvoltage",
    "5312": "Leakage current exceeds the standard",
    "5313": "Low insulation impedance of the system",
    "5314": "Ground wire fault",
    "5315": "High DC component of inverter voltage",
    "5316": "High DC component of inverter current",
    "5322": "Fan malfunction",
    "5324": "Bypass relay fault",
    "5325": "Off grid port relay fault",
    "5326": "BDC soft start relay fault",
    "5327": "SDSP detects power grid faults",
    "5332": "Inverter self-test fault",
    "5333": "Leakage current sensor fault",
    "5334": "Synchronization Failure",
    "5335": "Abnormal 12V power supply",
    "5337": "AD zero drift correction value error",
    "5440": "AFCI self-test alarm",
    "5441": "Electricity meter/CT reverse connection alarm",
    "5442": "Electricity meter communication abnormal alarm",
    "5444": "Fan alarm",
    "5445": "BDC temperature sensor abnormal alarm",
    "5446": "Boost temperature sensor abnormal alarm",
    "5447": "Inverter over temperature alarm",
    "5448": "Boost over temperature alarm",
    "5454": "Inverter over temperature and load drop alarm",
    "5515": "Load point table malfunction",
    "5516": "Off grid overload fault",
    "5517": "Grid overload fault",
    "5518": "Battery not connected to high voltage",
    "5519": "Insufficient Off Grid SOC",
    "5520": "Battery Strong Charging Request",
    "6848": "High ambient temperature",
    "6849": "Low ambient temperature",
    "6850": "Inverter driven overheating",
    "6851": "PV drive overheating",
    "6852": "Environmental temperature is too high",
    "7232": "Certified first level overvoltage of power grid",
    "7233": "Certified secondary overvoltage of power grid",
    "7234": "Grid overvoltage/high voltage level three",
    "7235": "Transient Overvoltage in Power Grid",
    "7236": "Certified power grid overvoltage for ten minutes",
    "7237": "Certified first level undervoltage in the power grid",
    "7238": "Certified power grid level 2 undervoltage",
    "7239": "Power grid undervoltage/low voltage level three",
    "7240": "Certified power grid level one overclocking",
    "7241": "Certified power grid level 2 overclocking",
    "7242": "Certified power grid level one underfrequency",
    "7243": "Certified power grid level 2 underfrequency",
    "7244": "The grid connection conditions are not met",
    "7245": "Grid reconnection conditions not met",
    "7246": "Power grid failure",
    "7247": "Inverter A-phase overcurrent fault",
    "7248": "Inverter B-phase overcurrent fault",
    "7249": "Inverter C-phase overcurrent fault",
    "7250": "Inverter A-phase instantaneous overcurrent fault",
    "7251": "Inverter B-phase instantaneous overcurrent fault",
    "7252": "Inverter C-phase instantaneous overcurrent fault",
    "7256": "Inverter A-phase wave by wave current limiting",
    "7257": "Inverter B-phase wave by wave current limiting",
    "7258": "Inverter C-phase wave by wave current limiting",
    "7259": "LN short circuit",
    "7268": "Inverter voltage overvoltage",
    "7276": "Buckup load phase A overload fault",
    "7277": "Buckup load B-phase overload fault",
    "7278": "Buckup load C-phase overload fault",
    "7280": "Phase angle offset offset",
    "7296": "PV1 reverse connection",
    "7297": "PV2 reverse connection",
    "7298": "Boost3_SV reverse connection fault",
    "7299": "Boost4_SV reverse connection fault",
    "7300": "Boost5_SV reverse connection fault",
    "7301": "Boost6_SV reverse connection fault",
    "7302": "Boost7_SV reverse connection fault",
    "7303": "Boost8_SV reverse connection fault",
    "7304": "Boost9_SV reverse connection fault",
    "7305": "Boost10_SV reverse connection fault",
    "7306": "Boost11_SV reverse connection fault",
    "7307": "Boost12_SV reverse connection fault",
    "7308": "PV1 current overcurrent",
    "7309": "PV2 current overcurrent",
    "7321": "Bus voltage overvoltage",
    "7322": "Upper half bus voltage overvoltage",
    "7323": "Lower half bus voltage overvoltage",
    "7324": "Bus voltage undervoltage",
    "7325": "Upper half bus voltage undervoltage",
    "7326": "Lower half bus voltage undervoltage",
    "7327": "PV1 voltage overvoltage",
    "7328": "PV1 voltage undervoltage",
    "7329": "PV2 voltage overvoltage",
    "7331": "Boost3_SV overvoltage",
    "7333": "Boost4_SV overvoltage",
    "7335": "Boost5_SV overvoltage",
    "7337": "Boost6_SV overvoltage",
    "7338": "Boost6_SV undervoltage",
    "7340": "Boost7_SV undervoltage",
    "7342": "Boost8_SV undervoltage",
    "7344": "Boost9_SV undervoltage",
    "7346": "Boost10_SV undervoltage",
    "7348": "Boost11_SV undervoltage",
    "7359": "Boost7_SV software overcurrent fault",
    "7365": "Leakage current fault",
    "7366": "Insulation impedance fault",
    "7367": "Grounding detection fault",
    "7368": "High DC component of inverter voltage",
    "7369": "Certified DC component first level overcurrent",
    "7371": "AFCI malfunction",
    "7372": "Internal fan malfunction",
    "7374": "Inverter A-phase overcurrent hardware failure",
    "7375": "Inverter B-phase overcurrent hardware failure",
    "7376": "Inverter C-phase overcurrent hardware failure",
    "7377": "Hardware bus voltage overvoltage",
    "7378": "BUS upper half bus overvoltage hardware fault",
    "7379": "BUS lower half bus overvoltage hardware fault",
    "7380": "Hardware PV1 current overcurrent",
    "7381": "Hardware PV2 current overcurrent",
    "7382": "Boost3_SV hardware overcurrent fault",
    "7383": "Boost4_SV hardware overcurrent fault",
    "7384": "Boost5_SV hardware overcurrent fault",
    "7385": "Boost6_SV hardware overcurrent fault",
    "7386": "Boost7_SV hardware overcurrent fault",
    "7387": "Boost8_SV hardware overcurrent fault",
    "7388": "Boost9_SV hardware overcurrent fault",
    "7389": "Boost10_SV hardware overcurrent fault",
    "7390": "Boost11_SV hardware overcurrent fault",
    "7391": "Boost12_SV hardware overcurrent fault",
    "7392": "Inverter self-test fault",
    "7393": "Leakage current sensor fault",
    "7394": "Synchronization Failure",
    "7396": "Continuous startup fault",
    "7397": "AD zero drift correction value error",
    "7399": "Slow start fault",
    "7400": "Authentication Island Trigger",
    "7401": "Overload fault",
    "7411": "Abnormal 1.5V reference voltage",
    "7412": "0.5V reference voltage abnormal",
    "7413": "DSP chip self-test fault",
    "7414": "Real time detection of faults in AC side relay operation",
    "7424": "Bat1 battery overcurrent fault",
    "7425": "Bat1 battery overvoltage fault",
    "7426": "Bat1 battery undervoltage fault",
    "7427": "Bat1 battery hardware overvoltage fault",
    "7428": "Bat1 battery hardware overcurrent fault",
    "7429": "Battery radiator overheating alarm",
    "7430": "Battery radiator under temperature alarm",
    "7431": "Battery relay malfunction",
    "7488": "Communication abnormality between main and auxiliary DSP",
    "7489": "DSP2 communication exception",
    "7491": "Fan alarm",
    "7492": "Inverter over temperature alarm",
    "7493": "Boost over temperature alarm",
    "7494": "DSP over temperature alarm",
    "7495": "Inverter under temperature alarm",
    "7496": "Boost under temperature alarm",
    "7497": "DSP under temperature alarm",
    "7498": "ARM communication abnormality",
    "7499": "Inverter over temperature and load drop alarm",
    "7502": "Temperature alarm",
    "7505": "DC lightning protection",
    "7506": "Communication lightning protection",
    "7552": "Communication with the electricity meter",
    "7553": "Communication with battery",
    "7554": "Overload fault",
    "7555": "Product type error",
    "7556": "AFCI communication failure",
    "7557": "Power level mismatch",
    "7558": "AFCI arc fault",
    "7559": "Insufficient off grid energy supply",
    "7560": "Battery sleep mode",
    "7561": "Battery emergency stop fault",
    "7562": "Optimizer communication failure",
    "7563": "Load point table fault",
    "7564": "Off grid overload fault",
    "7565": "Grid overload fault",
    "7566": "Battery not connected to high voltage",
    "7567": "Insufficient Off Grid SOC",
    "7568": "Battery Strong Charging Request",
    "7570": "Battery overdischarge protection alarm",
    "7581": "ARM slave 2 version mismatch",
    "7582": "ARM slave 3 version mismatch",
    "7583": "ARM Slave 4 Version Mismatch",
    "7584": "ARM slave 5 version mismatch",
    "7585": "ARM Slave 6 Version Mismatch",
    "7586": "ARM slave 7 version mismatch",
    "7596": "Parallel battery parallel failure alarm",
    "7626": "PV1 overload",
    "7660": "Hardware balanced bridge current overcurrent",
    "7662": "Balance bridge overcurrent",
    "8435": "1.5V reference voltage abnormal",
    "8436": "0.5V reference voltage abnormal",
    "8437": "DSP chip self-test fault",
    "8438": "Real time detection of faults in AC side relay operation",
    "9615": "Insufficient Off Grid SOC",
    "9616": "Battery Strong Charging Request",
}

# Official HYXI Authentication & Common Exception Table
INTERNAL_ERROR_MAP = {
    "A000001": "Authentication failed",
    "A000002": "Invalid access token",
    "A000003": "User information does not exist",
    "A000004": "Invalid credentials",
    "A000005": "Signature verification failed",
    "A000006": "Request time differs significantly from server time",
    "A000007": "The length of signature header fields cannot exceed five",
    "A000008": "Refresh token is not supported",
    "A000009": "Invalid refresh_token",
    "A000010": "Token has expired, please obtain a new one",
    "A000011": "Unknown scope, please login again",
    "A000012": "No access permission for this resource",
    "C000001": "Parameter error",
    "C000002": "Request frequency exceeded",
    "C000003": "No HTTP information obtained",
    "C000004": "Request failed, please try again later",
    "C000005": "Unsupported request method",
    "C000006": "User information not found, please re-login or check the token",
    "C000007": "Invalid response data",
    "C000008": "RSA encryption failed",
    "C000009": "RSA decryption failed",
    "C000010": "AES encryption failed",
    "C000011": "AES decryption failed",
    "C999999": "Service exception, please contact the service provide",
}


# Official HYXI Device Type Reference Table
DEVICE_TYPE_MAP = {
    "HYBRID_INVERTER": "Hybrid Inverter",
    "STRING_INVERTER": "String Inverter",
    "MICRO_INVERTER": "Microinverter",
    "OPTIMIZER": "Optimizer",
    "EMS": "Energy Storage System",
    "DMU": "Data Management Unit",
    "COLLECTOR": "Data Communication Stick",
    "METER": "Meter",
    "ENERGY_STORAGE_BATTERY": "Battery",
    "ALL_IN_ONE": "all-in-one machine",
    "AC_BATTERY": "AC Battery",
    # Official Numeric IDs (as seen in getSubDevicePage)
    "1": "Hybrid Inverter",
    "2": "Grid-Connected Inverter",
    "3": "Collector",
    "15": "Micro ESS",
    "16": "Micro ESS",
}

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # Seconds to wait between retries (multiplied by attempt number)

# Precomputed hashes for HMAC signature
_GRANT_TYPE_HASH = hashlib.sha512(b"grantType:1").hexdigest()
_EMPTY_STR_HASH = hashlib.sha512(b"").hexdigest()


def _parse_data_list(data_list: list) -> dict:
    """Extract dataKey and dataValue into a cleaner dictionary."""
    return {
        k: item.get("dataValue")
        for item in data_list
        if isinstance(item, dict) and (k := item.get("dataKey"))
    }


def _parse_ems_kv(data: list) -> dict:
    """Extract prop and value from nested EMS Field KV structure.

    Keys are lowercased to match HA sensor entity key conventions.
    """
    if not isinstance(data, list):
        return {}
    return {
        prop.lower(): item.get("value")
        for module in data
        if isinstance(module, dict)
        for item in module.get("filedKv", ())
        if isinstance(item, dict) and (prop := item.get("prop"))
    }


def _get_f(key: str, data_map: dict, mult: float = 1.0) -> float:
    """Helper to safely extract and multiply float values."""
    try:
        val = data_map.get(key)
        if val is None or val == "":
            return 0.0
        return round(float(val) * mult, 2)
    except ValueError:
        return 0.0
    except TypeError:
        return 0.0


def _filter_collector_metrics(m_raw: dict) -> dict:
    """Remove battery/power metrics that shouldn't be present on Collectors."""
    return {
        k: v for k, v in m_raw.items() if not _COLLECTOR_FILTER_REGEX.search(k.lower())
    }


def _compute_derived_metrics(m_raw: dict) -> dict:
    """Calculate derived metrics from raw metrics map.

    Only keys that have relevant base data in m_raw will be included in the
    resulting dictionary to avoid 'ghost' sensors for unsupported features.
    """
    derived = {}

    # 1. Load Calculation
    if "ph1Loadp" in m_raw or "ph2Loadp" in m_raw or "ph3Loadp" in m_raw:
        derived["home_load"] = (
            _get_f("ph1Loadp", m_raw)
            + _get_f("ph2Loadp", m_raw)
            + _get_f("ph3Loadp", m_raw)
        )

    # 2. Grid Metrics
    if "gridP" in m_raw:
        grid = _get_f("gridP", m_raw, 1000.0)
        derived["grid_import"] = abs(grid) if grid < 0 else 0.0
        derived["grid_export"] = grid if grid > 0 else 0.0

    # 3. Battery Metrics
    # Prefer batP (DC terminals) over pbat (AC equivalent)
    bat_p_dc = _get_f("batP", m_raw)
    pbat = _get_f("pbat", m_raw)

    if "batP" in m_raw or "pbat" in m_raw:
        power_source = bat_p_dc if bat_p_dc != 0.0 else pbat
        derived["bat_charging"] = abs(power_source) if power_source < 0 else 0.0
        derived["bat_discharging"] = power_source if power_source > 0 else 0.0
        derived["bat_power_dc"] = bat_p_dc

    if "batCharge" in m_raw:
        derived["bat_charge_total"] = _get_f("batCharge", m_raw)
    if "batDisCharge" in m_raw:
        derived["bat_discharge_total"] = _get_f("batDisCharge", m_raw)

    # 4. PV String Powers (Derived if missing)
    for i in range(1, 5):
        v_k, i_k, p_k = f"pv{i}v", f"pv{i}i", f"pv{i}p"
        if v_k in m_raw or i_k in m_raw or p_k in m_raw:
            derived[p_k] = _get_f(p_k, m_raw) or round(
                _get_f(v_k, m_raw) * _get_f(i_k, m_raw), 2
            )

    return derived


def _mask_id(value: str) -> str:
    """Mask an identifier (SN, plant ID, etc.) for logs.

    Masks identifiers securely using a one-way SHA-256 hash. The first 8
    characters of the hex digest are returned to allow deterministic
    cross-device log correlation without exposing the original value or its length.

    Example: '10602251600016' -> 'e3b0c442'
    """
    if not value or value == "None":
        return "****"
    id_str = str(value)
    return hashlib.sha256(id_str.encode("utf-8")).hexdigest()[:8]


# Keys in raw API response dicts that contain identifying or personal information.
_SENSITIVE_KEYS = frozenset(
    {
        "deviceSn",
        "parentSn",
        "batSn",
        "plantId",
        "gprsImei",
        "plantAddress",  # Full home/site address — hard-redact
        "plantName",
        "deviceName",
        "alarmName",
        "token",
        "access_token",
        "refresh_token",
        "password",
    }
)


def _sanitize_dict(raw: dict) -> dict[str, Any]:
    """Return a copy of a raw API response dict with sensitive fields masked.

    Used before logging raw API payloads so that SNs, plant IDs, and personal
    details (e.g. home address) are never written to the log in plain text.
    """
    result: dict[str, Any] = {}
    for k, v in raw.items():
        if k == "plantAddress":
            result[k] = "[REDACTED]"
        elif k in _SENSITIVE_KEYS and v:
            result[k] = _mask_id(str(v))
        elif isinstance(v, dict):
            result[k] = _sanitize_dict(v)
        elif isinstance(v, list):
            result[k] = _sanitize_list(v)
        else:
            result[k] = v
    return result


def _sanitize_list(raw_list: list) -> list[Any]:
    """Recursively sanitize items in a list, converting empty strings to None."""
    result: list[Any] = []
    for item in raw_list:
        if isinstance(item, dict):
            result.append(_sanitize_dict(item))
        elif isinstance(item, list):
            result.append(_sanitize_list(item))
        elif item == "":
            result.append(None)
        else:
            result.append(item)
    return result


class HyxiApiClient:  # pylint: disable=too-many-instance-attributes
    """Client for interacting with the HYXI Cloud API."""

    def __init__(
        self, access_key, secret_key, base_url, session: aiohttp.ClientSession
    ):
        self.access_key = access_key
        self.secret_key = secret_key
        self._secret_key_bytes = secret_key.encode("utf-8")
        self.base_url = base_url.rstrip("/")
        self.session = session
        self.token: str | None = None
        self.token_expires_at: float = 0.0

        # Structural & Metadata Cache
        self._discovery_cache: dict[str, Any] = {
            "plants": None,  # list[dict] | None
            "device_info": {},  # SN -> dict (static data)
            "hierarchy": {},  # SN -> list[dict] (sub-devices)
        }
        self._discovery_cache_time: float = 0.0
        self._discovery_cache_ttl = 3600  # 1 hour default

    def _update_discovery_cache(self, sn: str, entry: dict):
        """Update the discovery cache with basic entry structure."""
        info_cache = self._discovery_cache.get("device_info")
        if isinstance(info_cache, dict):
            info_cache[sn] = {
                "model": entry["model"],
                "device_type_code": entry["device_type_code"],
                "device_name": entry.get("device_name"),
            }

    def _generate_headers(self, path, method, is_token_request=False):
        """Generates headers matching HYXI's official Java SDK implementation."""
        now_ms = int(time.time() * 1000)
        timestamp = str(now_ms)

        # 🚀 Generate a truly unique Nonce for concurrent requests
        nonce = os.urandom(4).hex()

        hex_hash = _GRANT_TYPE_HASH if is_token_request else _EMPTY_STR_HASH
        string_to_sign = f"{path}\n{method.upper()}\n{hex_hash}\n"

        # 🚀 Do not poison the signature with an expired token!
        token_str = "" if is_token_request else (self.token or "")

        # Build the final string
        sign_string = f"{self.access_key}{token_str}{timestamp}{nonce}{string_to_sign}"
        hmac_bytes = hmac.new(
            self._secret_key_bytes, sign_string.encode("utf-8"), hashlib.sha512
        ).digest()
        signature = base64.b64encode(hmac_bytes).decode("utf-8")

        headers = {
            "accessKey": self.access_key,
            "timestamp": timestamp,
            "nonce": nonce,
            "sign": signature,
            "Content-Type": "application/json",
        }

        if is_token_request:
            headers["sign-headers"] = "grantType"
        elif token_str:
            headers["Authorization"] = token_str

        return headers

    async def _request(
        self, method: str, path: str, is_token_request: bool = False, **kwargs
    ) -> tuple[int, dict]:
        """Centralized helper for making HTTP requests."""
        url = f"{self.base_url}{path}"
        headers = self._generate_headers(
            path, method.upper(), is_token_request=is_token_request
        )

        kwargs.setdefault("timeout", 15)

        if method.upper() not in ("GET", "POST"):
            raise ValueError(f"Unsupported HTTP method: {method}")

        request_func = getattr(self.session, method.lower())
        async with request_func(url, headers=headers, **kwargs) as response:
            status = response.status

            if is_token_request and status in (401, 403):
                return status, {}

            response.raise_for_status()
            res = await response.json()
            return status, res

    def _apply_token_response(self, data: dict) -> bool:
        """Parse token and expiration from API response and update state."""
        token_val = data.get("token") or data.get("access_token")

        if not token_val:
            return False

        self.token = str(f"Bearer {token_val}")
        self.token_expires_at = self._calculate_token_expiration(data)

        return True

    def _calculate_token_expiration(self, data: dict) -> float:
        """Calculate token expiration timestamp from API response."""
        # 1. Grab the raw expiration value exactly as the API sent it
        raw_expires_in = data.get("expiresIn") or data.get("expires_in")
        _LOGGER.debug(
            "HYXI API returned raw token expiration: %s seconds",
            raw_expires_in,
        )

        # 3. Apply the 5-minute (300s) safety buffer
        buffer_secs = 300
        expires_at_val = raw_expires_in or 6600
        token_expires_at = time.time() + float(expires_at_val) - buffer_secs

        # 4. Log the actual scheduled refresh time
        refresh_time_str = datetime.fromtimestamp(token_expires_at).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        _LOGGER.debug(
            "HYXI Token proactive refresh scheduled in %s seconds (at %s)",
            int(float(expires_at_val)) - buffer_secs,
            refresh_time_str,
        )
        return token_expires_at

    async def _refresh_token(self):
        """Async version of token refresh."""
        if self.token and time.time() < self.token_expires_at:
            return True

        path = "/api/authorization/v1/token"

        try:
            status, res = await self._request(
                "POST", path, is_token_request=True, json={"grantType": 1}
            )

            if status in (401, 403):
                _LOGGER.error("HYXI API: Token request unauthorized (401/403)")
                return "auth_failed"

            if not res.get("success"):
                _LOGGER.error("HYXI API Token Rejected: %s", _sanitize_dict(res))
                if res.get("code") in (401, 403, "401", "403"):
                    return "auth_failed"
                return False

            return self._apply_token_response(res.get("data", {}))
        except (aiohttp.ClientError, TimeoutError, Exception) as e:
            _LOGGER.error("HYXI Token Request Failed: %s", e)
        return False

    async def _fetch_device_metrics(self, sn, entry):
        """Helper to fetch detailed metrics for a single device."""
        q_path = "/api/device/v1/queryDeviceData"
        try:
            _, res_q = await self._request("GET", q_path, params={"deviceSn": sn})

            if res_q.get("success"):
                data_list = res_q.get("data", [])
                m_raw = _parse_data_list(data_list)
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug(
                        "HYXI Raw METRICS for %s (%s): %s",
                        _mask_id(sn),
                        entry.get("device_type_code"),
                        _sanitize_dict(m_raw),
                    )

                # 🚀 Sanitization: If this is a Collector, ignore battery/power metrics that shouldn't be here.
                # This prevents "Collector" entities in Home Assistant from showing ghost battery stats.
                if entry.get("device_type_code") == "COLLECTOR":
                    entry["metrics"].update(_filter_collector_metrics(m_raw))
                else:
                    entry["metrics"].update(m_raw)

                if "gridP" in m_raw or "pbat" in m_raw or "batP" in m_raw:
                    entry["metrics"].update(_compute_derived_metrics(m_raw))
            else:
                _LOGGER.warning(
                    "HYXI API metrics rejected for %s: %s",
                    _mask_id(sn),
                    res_q.get("message"),
                )
        except (aiohttp.ClientError, TimeoutError, Exception) as e:
            _LOGGER.error("Error fetching metrics for %s: %s", _mask_id(sn), e)

    async def _fetch_ems_basic_data(self, ems_sn, entry):
        """Helper to fetch and merge EMS-specific basic details."""
        _LOGGER.debug("HYXI Probing EMS telemetry for %s...", _mask_id(ems_sn))
        m_raw = await self.query_ems_basic_details(ems_sn)
        if m_raw:
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "HYXI Raw METRICS for %s (%s) [EMS]: %s",
                    _mask_id(ems_sn),
                    entry.get("device_type_code", "EMS"),
                    _sanitize_dict(m_raw),
                )
            entry["metrics"].update(m_raw)
        else:
            _LOGGER.debug(
                "HYXI EMS telemetry probe returned no data for %s", _mask_id(ems_sn)
            )

    async def query_ems_basic_details(self, ems_sn):
        """Acquire basic data for Energy Storage Systems (ESS)."""
        path = "/api/ems/v1/queryBasicDetails"
        try:
            _, res = await self._request("GET", path, params={"emsSn": ems_sn})

            if res.get("code") == "0":
                data = res.get("data", [])
                return _parse_ems_kv(data)
        except (aiohttp.ClientError, TimeoutError, Exception) as e:
            _LOGGER.error(
                "HYXI EMS Basic Data Request Failed for %s: %s", _mask_id(ems_sn), e
            )
        return {}

    @staticmethod
    def _extract_device_info_metadata(entry, i_raw):
        """Helper to extract metadata from device info."""
        sw_ver = i_raw.get("swVerSys") or i_raw.get("swVerMaster") or i_raw.get("swVer")
        hw_ver = i_raw.get("hwVer")
        if sw_ver:
            entry["sw_version"] = sw_ver
        if hw_ver:
            entry["hw_version"] = hw_ver

        base_info = {
            "hw_version": hw_ver,
            "_sw_ver_sys": sw_ver,
            "signalIntensity": i_raw.get("signalIntensity"),
            "signalVal": i_raw.get("signalVal"),
            "wifiVer": i_raw.get("wifiVer"),
            "comMode": i_raw.get("comMode"),
            "swVerMaster": i_raw.get("swVerMaster"),
            "swVerSlave": i_raw.get("swVerSlave"),
        }

        device_type_code = entry.get("device_type_code", "").upper()
        if _BATTERY_DEVICE_REGEX.search(device_type_code):
            base_info.update(
                {
                    "batCap": _get_f("batCap", i_raw),
                    "packNum": int(i_raw.get("packNum") or 1),
                    "maxChargePower": _get_f("maxChargePower", i_raw)
                    or _get_f("maxChargingDischargingPower", i_raw),
                    "maxDischargePower": _get_f("maxDischargePower", i_raw)
                    or _get_f("maxChargingDischargingPower", i_raw),
                }
            )

        entry["metrics"].update(base_info)
        return base_info

    async def _fetch_device_info(self, sn, entry):
        """Helper to fetch static device info (firmware, capacity, limits)."""
        i_path = "/api/device/v1/queryDeviceInfo"
        try:
            _, res_i = await self._request("GET", i_path, params={"deviceSn": sn})

            if res_i.get("success"):
                data_raw = res_i.get("data")
                if isinstance(data_raw, dict):
                    i_raw = data_raw
                elif isinstance(data_raw, list):
                    i_raw = _parse_data_list(data_raw)
                else:
                    i_raw = {}

                # 👇 This will dump the EXACT info the cloud sends back
                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug(
                        "HYXI Raw INFO for %s: %s", _mask_id(sn), _sanitize_dict(i_raw)
                    )

                base_info = HyxiApiClient._extract_device_info_metadata(entry, i_raw)
                # Store in cache
                if sn not in self._discovery_cache["device_info"]:
                    # Ensure we preserve the name if it was set during discovery
                    self._discovery_cache["device_info"][sn] = {
                        "model": entry.get("model", "Unknown"),
                        "device_type_code": entry.get("device_type_code", "Unknown"),
                        "device_name": entry.get("device_name", "Unknown"),
                    }
                self._discovery_cache["device_info"][sn].update(base_info)
            else:
                _LOGGER.warning(
                    "HYXI INFO API Rejected for %s: %s",
                    _mask_id(sn),
                    res_i.get("message"),
                )

        except (aiohttp.ClientError, TimeoutError, Exception) as e:
            _LOGGER.error("Error fetching device info for %s: %s", _mask_id(sn), e)

    async def _fetch_all_for_device(self, sn, entry, dev_type):
        """Fires off concurrent tasks for Data and Info, merging the results."""
        tasks = [asyncio.create_task(self._fetch_device_info(sn, entry))]
        is_comm_unit = dev_type in ("COLLECTOR", "DMU", "3")

        if not is_comm_unit:
            tasks.append(asyncio.create_task(self._fetch_device_metrics(sn, entry)))
            tasks.append(asyncio.create_task(self._fetch_ems_basic_data(sn, entry)))

        # Wait for them to finish
        if tasks:
            await asyncio.gather(*tasks)

        return sn, entry

    async def _fetch_device_list_for_plant(self, plant_id: str) -> list[dict] | None:
        """Fetch the raw device list from the API for a specific plant."""
        d_path = "/api/plant/v1/devicePage"
        _, res_d = await self._request(
            "POST",
            d_path,
            json={"plantId": plant_id, "pageSize": 50, "currentPage": 1},
        )

        if not res_d.get("success"):
            _LOGGER.error(
                "HYXI API Device Fetch Rejected for Plant %s: %s",
                _mask_id(plant_id),
                _sanitize_dict(res_d),
            )
            return None

        data_val = res_d.get("data", {})
        devices = (
            data_val
            if isinstance(data_val, list)
            else data_val.get("deviceList", [])
            if isinstance(data_val, dict)
            else []
        )

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "HYXI Discovered Devices for Plant %s: %s",
                _mask_id(plant_id),
                [_mask_id(d.get("deviceSn", "UNKNOWN")) for d in devices],
            )
        return devices

    async def _fetch_devices_for_plant(self, plant_id, state: FetchState):
        """Helper to fetch devices for a single plant concurrently."""
        try:
            devices = await self._fetch_device_list_for_plant(plant_id)
            if devices is None:
                return

            await self._process_devices_for_plant(devices, state)

        except (aiohttp.ClientError, TimeoutError, Exception) as e:
            _LOGGER.error(
                "Error fetching devices for plant %s: %s", _mask_id(plant_id), e
            )

    async def _process_devices_for_plant(self, devices: list[dict], state: FetchState):
        """Helper to process a list of devices, extracting metrics and sub-devices."""
        sub_device_tasks = []
        for d in devices:
            sn = d.get("deviceSn")
            if not sn:
                continue

            state.discovered_sns.add(sn)
            entry, dev_type = HyxiApiClient._build_device_entry(sn, d, state.now)

            self._update_discovery_cache(sn, entry)

            state.metric_tasks.append(self._fetch_all_for_device(sn, entry, dev_type))

            # 🚀 DEEP DISCOVERY: If this is a Collector, DMU, or Inverter, find its children!
            if _PARENT_DEVICE_REGEX.search(dev_type):
                _LOGGER.debug(
                    "HYXI Parent Device Found: %s (%s). Probing for sub-devices...",
                    _mask_id(sn),
                    dev_type,
                )
                sub_device_tasks.append(self._fetch_sub_devices(sn, state))

        if sub_device_tasks:
            await asyncio.gather(*sub_device_tasks)

    async def _fetch_sub_device_list(self, parent_sn: str) -> list[dict]:
        """Fetch the list of sub-devices from the API."""
        sd_path = "/api/device/v1/getSubDevicePage"
        _, res_sd = await self._request(
            "POST",
            sd_path,
            json={"parentSn": parent_sn, "pageSize": 50, "currentPage": 1},
        )

        if not res_sd.get("success"):
            _LOGGER.error(
                "HYXI API Sub-Device Fetch Rejected for %s: %s",
                _mask_id(parent_sn),
                _sanitize_dict(res_sd),
            )
            return []

        data_val = res_sd.get("data", {})
        return data_val.get("childDevice", []) if isinstance(data_val, dict) else []

    async def _fetch_sub_devices(self, parent_sn, state: FetchState):
        """Fetch sub-devices under a communication unit (Collector/DMU)."""
        try:
            children = await self._fetch_sub_device_list(parent_sn)
            if not children:
                return

            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "HYXI Found %s sub-devices under %s: %s",
                    len(children),
                    _mask_id(parent_sn),
                    [_mask_id(c.get("deviceSn", "UNKNOWN")) for c in children],
                )

            for c in children:
                sn = c.get("deviceSn")
                if not sn or sn in state.discovered_sns:
                    continue

                state.discovered_sns.add(sn)
                entry, raw_type = HyxiApiClient._build_device_entry(sn, c, state.now)

                self._update_discovery_cache(sn, entry)

                # These are real devices, so fetch their metrics/info
                state.metric_tasks.append(
                    self._fetch_all_for_device(sn, entry, raw_type)
                )

        except (aiohttp.ClientError, TimeoutError, Exception) as e:
            _LOGGER.error(
                "Error fetching sub-devices for %s: %s", _mask_id(parent_sn), e
            )

    async def _fetch_alarms_for_plant(self, plant_id):
        """Helper to fetch active alarms for a single plant."""
        a_path = "/api/alarm/v1/plantAlarmPage"
        try:
            _, res_a = await self._request(
                "POST",
                a_path,
                json={"plantId": plant_id, "pageSize": 100, "currentPage": 1},
            )

            if not res_a.get("success"):
                _LOGGER.error(
                    "HYXI API Alarm Fetch Rejected for Plant %s: %s",
                    _mask_id(plant_id),
                    _sanitize_dict(res_a),
                )
                return []

            data_val = res_a.get("data", {})
            alarms = data_val.get("pageData", []) if isinstance(data_val, dict) else []

            # Enrichment: Map raw alarmCodes to official descriptions
            for a in alarms:
                code = str(a.get("alarmCode", ""))
                if alarm_name := ALARM_CODE_MAP.get(code):
                    a["alarmName"] = alarm_name

            # 👇 Dump the EXACT active alarms the cloud sends back
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "HYXI Raw ALARMS for Plant %s: %s",
                    _mask_id(plant_id),
                    [_sanitize_dict(a) for a in alarms]
                    if isinstance(alarms, list)
                    else alarms,
                )

            return alarms
        except (aiohttp.ClientError, TimeoutError, Exception) as e:
            _LOGGER.error(
                "Error fetching alarms for plant %s: %s", _mask_id(plant_id), e
            )
            return []

    async def get_all_device_data(
        self, allow_back_discovery: bool = False, force_discovery: bool = False
    ):
        """Fetches data with built-in retry logic and returns attempt count."""

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                data = await self._execute_fetch_all(
                    allow_back_discovery=allow_back_discovery,
                    force_discovery=force_discovery,
                )
                if data == "auth_failed":
                    return None  # Hard fail, don't retry bad credentials
                if data is not None:
                    # ✅ Success
                    return {"data": data, "attempts": attempt}

                # If we get here, data was None (soft failure). Trigger a retry manually.
                raise aiohttp.ClientError("Fetch returned None, triggering retry.")

            except (aiohttp.ClientError, TimeoutError) as err:
                if attempt < MAX_RETRIES:
                    wait_time = attempt * RETRY_DELAY
                    _LOGGER.debug(
                        "HYXI Connection attempt %s/%s failed. Retrying in %ss... (Error: %s)",
                        attempt,
                        MAX_RETRIES,
                        wait_time,
                        err,
                    )
                    await asyncio.sleep(wait_time)
                else:
                    _LOGGER.error(
                        "HYXI Cloud connection failed after %s attempts: %s",
                        MAX_RETRIES,
                        err,
                    )

        return None

    async def _fetch_plants(self):
        """Helper to fetch plants associated with the account."""
        p_path = "/api/plant/v1/page"
        _, res_p = await self._request(
            "POST", p_path, json={"pageSize": 10, "currentPage": 1}
        )

        if not res_p.get("success"):
            # 🚀 If the server rejects the token, wipe it and force a retry!
            if res_p.get("code") in ("A000002", "A000005"):
                _LOGGER.debug(
                    "HYXI Server rejected our token (A000002/A000005). Forcing immediate token refresh..."
                )
                self.token = None
                self.token_expires_at = 0
                # Raising this error kicks it back up to the retry loop
                raise aiohttp.ClientError("Server rejected token")

            _LOGGER.error("HYXI API Plant Fetch Rejected: %s", _sanitize_dict(res_p))
            return None

        data_p = res_p.get("data", {})
        plants = data_p.get("list", []) if isinstance(data_p, dict) else []

        # 👇 Log the discovered plants
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "HYXI Discovered Plants: %s",
                [_mask_id(p.get("plantId", "UNKNOWN")) for p in plants],
            )

        return plants

    def _build_plant_tasks(self, state: FetchState, include_devices: bool = True):
        """Extract plant processing loop to synchronously build tasks."""
        device_fetch_tasks = []
        alarm_fetch_tasks = []

        for p in state.plants:
            plant_id = p.get("plantId")
            if not plant_id:
                continue

            if include_devices:
                device_fetch_tasks.append(
                    self._fetch_devices_for_plant(plant_id, state)
                )
            alarm_fetch_tasks.append(self._fetch_alarms_for_plant(plant_id))

        return device_fetch_tasks, alarm_fetch_tasks

    async def _fetch_and_process_alarms(
        self,
        alarm_fetch_tasks,
        state: FetchState,
        allow_back_discovery: bool = False,
    ):
        """Helper to execute alarm tasks and trigger back-discovery processing."""
        if not alarm_fetch_tasks:
            return []

        alarm_results = await asyncio.gather(*alarm_fetch_tasks)
        return await self._process_alarms_and_back_discovery(
            alarm_results,
            state,
            allow_back_discovery=allow_back_discovery,
        )

    @staticmethod
    async def _execute_device_tasks(device_fetch_tasks):
        """Helper to conditionally execute device tasks concurrently."""
        if device_fetch_tasks:
            await asyncio.gather(*device_fetch_tasks)

    @staticmethod
    async def _execute_metric_tasks(plant_alarms, state: FetchState):
        """Helper to conditionally execute metrics and map alarms."""
        if state.metric_tasks:
            await HyxiApiClient._execute_metrics_and_map_alarms(plant_alarms, state)

    async def _process_plants_data(
        self, state: FetchState, allow_back_discovery: bool = False
    ):
        """Helper to concurrently process plants to gather metrics and alarms."""
        device_fetch_tasks, alarm_fetch_tasks = self._build_plant_tasks(state)

        await HyxiApiClient._execute_device_tasks(device_fetch_tasks)

        plant_alarms = await self._fetch_and_process_alarms(
            alarm_fetch_tasks,
            state,
            allow_back_discovery=allow_back_discovery,
        )

        # 3. Concurrent Metrics
        await self._execute_metric_tasks(plant_alarms, state)

    def _handle_back_discovery_alarm(
        self, a, plant_id, state: FetchState, sub_device_tasks
    ):
        """Helper to process a single alarm for back-discovery of unlisted devices."""
        sn = a.get("deviceSn")
        # Robustness: Skip null, empty, or dummy SNs (less than 5 chars)
        if not sn or len(str(sn)) < 5 or sn in state.discovered_sns:
            return

        _LOGGER.info(
            "HYXI Back-discovering device %s found in alarms for plant %s...",
            _mask_id(sn),
            _mask_id(plant_id),
        )
        state.discovered_sns.add(sn)
        dev_type = str(a.get("deviceType") or "UNKNOWN")
        friendly_name = (
            DEVICE_TYPE_MAP.get(dev_type) or dev_type.replace("_", " ").title()
        )

        device_name = a.get("deviceName")
        if not device_name:
            device_name = f"{friendly_name} {sn}"

        entry = {
            "sn": sn,
            "device_name": device_name,
            "model": friendly_name,
            "device_type_code": dev_type,
            "sw_version": None,
            "hw_version": None,
            "metrics": {"last_seen": state.now},
        }
        state.metric_tasks.append(self._fetch_all_for_device(sn, entry, dev_type))

        # 🚀 DEEP BACK-DISCOVERY: If this is a parent, search for ITS children too!
        dev_type_upper = dev_type.upper()
        if _PARENT_DEVICE_REGEX.search(dev_type_upper):
            sub_device_tasks.append(self._fetch_sub_devices(sn, state))

    async def _process_alarms_and_back_discovery(
        self,
        alarm_results,
        state: FetchState,
        allow_back_discovery: bool = False,
    ):
        """Helper to process alarms and perform back-discovery of unlisted devices."""
        _LOGGER.debug(
            "HYXI Processing alarms (allow_back_discovery=%s)", allow_back_discovery
        )
        plant_alarms = []
        sub_device_tasks: list[asyncio.Task] = []
        for i, alarms in enumerate(alarm_results):
            if not isinstance(alarms, list):
                continue

            plant_alarms.extend(alarms)
            plant_id = state.plants[i].get("plantId")

            # 🚀 Back-Discovery: Check if alarms contain SNs we didn't find in devicePage
            if allow_back_discovery:
                for a in alarms:
                    self._handle_back_discovery_alarm(
                        a, plant_id, state, sub_device_tasks
                    )

        if sub_device_tasks:
            await asyncio.gather(*sub_device_tasks)

        return plant_alarms

    @staticmethod
    async def _execute_metrics_and_map_alarms(plant_alarms, state: FetchState):
        """Helper to execute metric tasks and map alarms to devices."""
        # Precompute alarm mapping to optimize from O(N*M) to O(N+M)
        alarms_by_sn = defaultdict(list)
        for a in plant_alarms:
            sn = a.get("deviceSn")
            if sn:
                alarms_by_sn[sn].append(a)

        updated_entries = await asyncio.gather(*state.metric_tasks)
        for sn, entry in updated_entries:
            if sn:
                # Map the relevant active alarms to this specific device
                entry["alarms"] = alarms_by_sn.get(sn, [])
                state.results[sn] = entry

    async def _execute_fetch_all(
        self, allow_back_discovery: bool = False, force_discovery: bool = False
    ):
        """The actual fetching logic with discovery caching support."""

        token_status = await self._refresh_token()

        if token_status == "auth_failed":
            return "auth_failed"
        if not token_status:
            return None

        now = datetime.now(UTC).isoformat()
        state = FetchState(now=now)

        use_cache = (
            not force_discovery
            and self._discovery_cache["plants"] is not None
            and (time.time() - self._discovery_cache_time) < self._discovery_cache_ttl
        )

        if use_cache:
            _LOGGER.debug("HYXI using cached discovery data (Fast Polling)")
            state.plants = self._discovery_cache.get("plants") or []
            # Reconstruct entries from hierarchy or known SNS
            info_cache = self._discovery_cache.get("device_info")
            if isinstance(info_cache, dict):
                for sn, info in info_cache.items():
                    entry = {
                        "sn": sn,
                        "device_name": info.get("device_name", f"{info['model']} {sn}"),
                        "model": info["model"],
                        "device_type_code": info["device_type_code"],
                        "sw_version": info.get("_sw_ver_sys"),
                        "hw_version": info.get("hw_version"),
                        "metrics": {"last_seen": now},
                    }
                    state.metric_tasks.append(
                        self._fetch_all_for_device(sn, entry, info["device_type_code"])
                    )
                state.discovered_sns = set(info_cache.keys())

            # Fetch alarms (to allow back-discovery if enabled) and metrics
            _, alarm_fetch_tasks = self._build_plant_tasks(state, include_devices=False)
            plant_alarms = await self._fetch_and_process_alarms(
                alarm_fetch_tasks,
                state,
                allow_back_discovery=allow_back_discovery,
            )
            await self._execute_metric_tasks(plant_alarms, state)
            return state.results

        # Full Discovery Path
        plants = await self._fetch_plants()
        if plants is None:
            return None
        state.plants = plants

        # Clear cache for fresh discovery
        self._discovery_cache["plants"] = plants
        self._discovery_cache_time = time.time()
        self._discovery_cache["device_info"].clear()
        self._discovery_cache["hierarchy"].clear()

        await self._process_plants_data(
            state, allow_back_discovery=allow_back_discovery
        )

        return state.results

    @staticmethod
    def _build_device_entry(sn, device_data, now):
        """Build a standardized device entry dictionary from raw API data."""
        dev_type = str(device_data.get("deviceType") or "UNKNOWN")
        friendly_name = (
            DEVICE_TYPE_MAP.get(dev_type) or dev_type.replace("_", " ").title()
        )

        device_name = device_data.get("deviceName") or device_data.get("alias")
        if not device_name:
            device_name = f"{friendly_name} {sn}"

        entry = {
            "sn": sn,
            "device_name": device_name,
            "model": friendly_name,
            "device_type_code": dev_type,
            "sw_version": device_data.get("swVer"),
            "hw_version": device_data.get("hwVer"),
            "metrics": {"last_seen": now},
        }

        return entry, dev_type
