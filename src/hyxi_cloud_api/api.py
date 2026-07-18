"""HYXI Cloud API Client for retrieving inverter and battery data.

This module is intentionally large: it includes the full ALARM_CODE_MAP,
INTERNAL_ERROR_MAP, and DEVICE_TYPE_MAP reference tables to avoid external
dependencies. Suppress the module-size warning accordingly.
"""  # pylint: disable=too-many-lines

from __future__ import annotations

import asyncio
import base64
import functools
import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

try:
    from datetime import UTC, datetime
except ImportError:
    from datetime import datetime, timezone

    UTC = timezone.utc  # noqa

import aiohttp


class TokenRejectedError(aiohttp.ClientError):
    """Raised when the HYXI Cloud API rejects an authentication token."""


@dataclass
class FetchState:
    """State object to hold shared data during a device fetch cycle."""

    now: str
    metric_tasks: list = field(default_factory=list)
    discovered_sns: set = field(default_factory=set)
    results: dict = field(default_factory=dict)
    plants: list = field(default_factory=list)


_LOGGER = logging.getLogger(__name__)
_battery_device_types = frozenset(
    (
        "INVERTER",
        "HYBRID_INVERTER",
        "STRING_INVERTER",
        "MICRO_INVERTER",
        "ESS",
        "HALO",
        "1",
        "15",
        "16",
        "MICRO_STORAGE_ALL_IN_ONE",
    )
)
_parent_device_types = frozenset(
    (
        "COLLECTOR",
        "DMU",
        "INVERTER",
        "HYBRID_INVERTER",
        "STRING_INVERTER",
        "MICRO_INVERTER",
        "ALL_IN_ONE",
        "MICRO_STORAGE_ALL_IN_ONE",
    )
)
_EMS_DEVICE_TYPES = frozenset(
    (
        "EMS",
        "ENERGY_STORAGE_BATTERY",
        "MICRO_STORAGE_ALL_IN_ONE",
        "15",
        "16",
    )
)
_COLLECTOR_FILTER_KEYWORDS = (
    "bat",
    "pv",
    "grid",
    "load",
    "ph1",
    "ph2",
    "ph3",
)

_COLLECTOR_FILTER_REGEX = re.compile(
    "|".join(_COLLECTOR_FILTER_KEYWORDS), re.IGNORECASE
)

_PV_KEYS = tuple((f"pv{i}v", f"pv{i}i", f"pv{i}p") for i in range(1, 5))

_METRICS_EXCLUDED_KEYS = frozenset({"deviceSn", "reportTimestamp", "collectTime"})

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
    "MICRO_STORAGE_ALL_IN_ONE": "Micro ESS",
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
    except ValueError, TypeError:
        return 0.0


@functools.lru_cache(maxsize=1024)
def _is_collector_key_allowed(key: str) -> bool:
    """Check if metric key is allowed for Collectors and cache the result."""
    return not _COLLECTOR_FILTER_REGEX.search(key)


def _filter_collector_metrics(m_raw: dict) -> dict:
    """Remove battery/power metrics that shouldn't be present on Collectors."""
    return {k: v for k, v in m_raw.items() if _is_collector_key_allowed(k)}


def _compute_load_metrics(m_raw: dict, derived: dict[str, float]) -> None:
    """Calculate home load metrics."""
    if "ph1Loadp" in m_raw or "ph2Loadp" in m_raw or "ph3Loadp" in m_raw:
        derived["home_load"] = (
            _get_f("ph1Loadp", m_raw)
            + _get_f("ph2Loadp", m_raw)
            + _get_f("ph3Loadp", m_raw)
        )

    if "loadPower" in m_raw or "totalPac" in m_raw:
        derived["load_power_w"] = _get_f("loadPower", m_raw)

        if (
            derived["load_power_w"] == 0.0
            and m_raw.get("status") == 1
            and "totalPac" in m_raw
        ):
            derived["load_power_w"] = _get_f("totalPac", m_raw)


def _compute_grid_metrics(m_raw: dict, derived: dict[str, float]) -> None:
    """Calculate grid import/export metrics."""
    grid = None
    if "gridP" in m_raw and m_raw["gridP"] is not None and m_raw["gridP"] != "":
        grid = _get_f("gridP", m_raw, 1000.0)
    elif "ph1p" in m_raw or "ph2p" in m_raw or "ph3p" in m_raw:
        # Sum up individual phase powers (which are in Watts) to compute grid power fallback
        grid = _get_f("ph1p", m_raw) + _get_f("ph2p", m_raw) + _get_f("ph3p", m_raw)
        # Store the derived gridP back in metrics (in kW to align with API standard format)
        derived["gridP"] = round(grid / 1000.0, 4)

    if grid is not None:
        derived["grid_import"] = abs(grid) if grid < 0 else 0.0
        derived["grid_export"] = grid if grid > 0 else 0.0


def _compute_battery_metrics(
    m_raw: dict, derived: dict[str, float], device_type: str
) -> None:
    """Calculate battery charge/discharge metrics."""
    bat_p_dc = _get_f("batP", m_raw)
    pbat = _get_f("pbat", m_raw)
    device_type_str = str(device_type or "")

    if "batP" in m_raw or "pbat" in m_raw or device_type_str in _EMS_DEVICE_TYPES:
        # ALL_IN_ONE: prefer pbat — batP can have an inverted sign convention,
        # while pbat is consistently negative-for-charging / positive-for-discharging.
        # Other devices: prefer batP (DC terminals), fall back to pbat.
        if device_type_str == "ALL_IN_ONE":
            power_source = pbat if pbat != 0.0 else bat_p_dc
        else:
            power_source = bat_p_dc if bat_p_dc != 0.0 else pbat
        derived["bat_charging"] = abs(power_source) if power_source < 0 else 0.0
        derived["bat_discharging"] = power_source if power_source > 0 else 0.0
        derived["bat_power_dc"] = bat_p_dc

    def _is_valid_metric(k: str) -> bool:
        v = m_raw.get(k)
        if v is None:
            return False
        if isinstance(v, str):
            v_cleaned = v.strip().lower()
            return bool(v_cleaned and v_cleaned not in ("null", "none", "na", "--"))
        return True

    # Unify cumulative battery charge energy telemetry keys to resolve polling/push mismatch
    total_echg_val = (
        _get_f("totalEchg", m_raw) if _is_valid_metric("totalEchg") else None
    )
    bat_charge_val = (
        _get_f("batCharge", m_raw) if _is_valid_metric("batCharge") else None
    )

    if total_echg_val is not None:
        derived["totalEchg"] = total_echg_val
        derived["bat_charge_total"] = total_echg_val
        if bat_charge_val is None:
            derived["batCharge"] = total_echg_val

    if bat_charge_val is not None:
        derived["batCharge"] = bat_charge_val
        if total_echg_val is None:
            derived["totalEchg"] = bat_charge_val
            derived["bat_charge_total"] = bat_charge_val

    # Unify cumulative battery discharge energy telemetry keys to resolve polling/push mismatch
    total_edchg_val = (
        _get_f("totalEdchg", m_raw) if _is_valid_metric("totalEdchg") else None
    )
    bat_discharge_val = (
        _get_f("batDisCharge", m_raw) if _is_valid_metric("batDisCharge") else None
    )

    if total_edchg_val is not None:
        derived["totalEdchg"] = total_edchg_val
        derived["bat_discharge_total"] = total_edchg_val
        if bat_discharge_val is None:
            derived["batDisCharge"] = total_edchg_val

    if bat_discharge_val is not None:
        derived["batDisCharge"] = bat_discharge_val
        if total_edchg_val is None:
            derived["totalEdchg"] = bat_discharge_val
            derived["bat_discharge_total"] = bat_discharge_val


def _compute_pv_metrics(m_raw: dict, derived: dict[str, float]) -> None:
    """Calculate PV string powers."""
    for v_k, i_k, p_k in _PV_KEYS:
        if v_k in m_raw or i_k in m_raw or p_k in m_raw:
            derived[p_k] = _get_f(p_k, m_raw) or round(
                _get_f(v_k, m_raw) * _get_f(i_k, m_raw), 2
            )

    # Derive pv1p from ppv - pv2p when pv1 data is not reported directly
    # (e.g. ALL_IN_ONE devices only report ppv and pv2p).
    # pylint: disable-next=fixme
    # TODO: Investigate whether the API will report pv1p natively for
    # ALL_IN_ONE in a future firmware/cloud update — remove this fallback
    # once pv1p is reported properly.
    if "pv1p" not in derived and "ppv" in m_raw and "pv2p" in derived:
        ppv_total = _get_f("ppv", m_raw)
        derived["pv1p"] = round(max(ppv_total - derived["pv2p"], 0), 2)


def _compute_micro_ess_fallback_metrics(m_raw: dict, derived: dict[str, float]) -> None:
    """Derive standard metrics from Micro ESS specific metrics."""
    if "pvPower" in m_raw and "ppv" not in m_raw:
        derived["ppv"] = _get_f("pvPower", m_raw)

    if "gridF" in m_raw and "f" not in m_raw:
        derived["f"] = _get_f("gridF", m_raw)


def _compute_derived_metrics(m_raw: dict, device_type: str = "") -> dict:
    """Calculate derived metrics from raw metrics map.

    Only keys that have relevant base data in m_raw will be included in the
    resulting dictionary to avoid 'ghost' sensors for unsupported features.
    """
    derived: dict[str, float] = {}

    _compute_load_metrics(m_raw, derived)
    _compute_grid_metrics(m_raw, derived)
    _compute_battery_metrics(m_raw, derived, device_type)
    _compute_pv_metrics(m_raw, derived)
    _compute_micro_ess_fallback_metrics(m_raw, derived)

    return derived


def _resolve_push_timestamp(device: dict[str, Any], now_utc: datetime) -> datetime:
    """Determine the last_seen timestamp from collectTime or reportTimestamp."""
    collect_time = device.get("collectTime")
    report_ts = device.get("reportTimestamp")

    if collect_time is not None:
        try:
            return datetime.fromtimestamp(float(collect_time), UTC)
        except ValueError, TypeError, OverflowError, OSError:
            pass

    if report_ts is not None:
        try:
            return datetime.fromtimestamp(float(report_ts) / 1000.0, UTC)
        except ValueError, TypeError, OverflowError, OSError:
            pass

    return now_utc


def _extract_raw_push_metrics(device: dict[str, Any]) -> dict[str, Any]:
    """Extract metrics from flat payload dictionary, stripping metadata/routing keys."""
    raw_metrics: dict[str, Any] = {}
    for k, v in device.items():
        if k in _METRICS_EXCLUDED_KEYS:
            continue
        raw_metrics[k] = v
    return raw_metrics


def _merge_push_metrics(
    sn: str,
    raw_metrics: dict[str, Any],
    device_type: str,
    existing_metrics: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    """Filter collector metrics and merge with existing metrics."""
    if device_type == "COLLECTOR":
        metrics_to_update = _filter_collector_metrics(raw_metrics)
    else:
        metrics_to_update = raw_metrics.copy()

    merged_metrics: dict[str, Any] = {}
    if existing_metrics and sn in existing_metrics:
        # Copy existing to avoid mutating caller's dictionary directly
        merged_metrics = dict(existing_metrics[sn])

    for k, v in metrics_to_update.items():
        if v is not None:
            merged_metrics[k] = v

    return merged_metrics


def _flatten_nested_push_device(device: dict) -> dict:  # pylint: disable=too-many-statements
    """Flatten a nested push device payload into the flat layout expected by the SDK."""
    flat: dict = {}

    # 1. record
    if "record" in device and isinstance(device["record"], dict):
        rec = device["record"]
        if "deviceSn" in rec:
            flat["deviceSn"] = rec["deviceSn"]
        if "collectTime" in rec:
            try:
                flat["collectTime"] = float(rec["collectTime"]) / 1000.0
            except ValueError, TypeError:
                flat["collectTime"] = rec["collectTime"]
        if "parentSn" in rec:
            flat["parentSn"] = rec["parentSn"]
        if "deviceState" in rec:
            flat["deviceState"] = rec["deviceState"]

    # Map discrepancies between Flat Push payload and Flat Pull payload
    _key_map = {
        "gridEin": "totalEnt",
        "gridEIn": "totalEnt",
        "gridEout": "totalEpt",
        "gridEOut": "totalEpt",
    }

    # Copy all root-level keys that are primitive types (support new flat format)
    for k, v in device.items():
        if not isinstance(v, dict) and not isinstance(v, list) and v is not None:
            # Normalize push metric names to match pull metric names
            mapped_k = _key_map.get(k, k)

            if mapped_k == "collectTime":
                try:
                    num_val = float(v)
                    if num_val > 10000000000:
                        flat[mapped_k] = num_val / 1000.0
                    else:
                        flat[mapped_k] = v
                except ValueError, TypeError:
                    flat[mapped_k] = v
            else:
                flat[mapped_k] = v

    # 2. system
    if "system" in device and isinstance(device["system"], dict):
        sys_info = device["system"]
        if "workMode" in sys_info:
            flat["workMode"] = sys_info["workMode"]

    # 3. ac
    if "ac" in device and isinstance(device["ac"], dict):
        ac_info = device["ac"]
        if "frequencyHz" in ac_info:
            flat["f"] = ac_info["frequencyHz"]
        if "powerW" in ac_info:
            flat["acP"] = ac_info["powerW"]
        if "energyKwh" in ac_info:
            flat["acE"] = ac_info["energyKwh"]

    # 4. pv
    if "pv" in device and isinstance(device["pv"], dict):
        pv_info = device["pv"]
        if "totalPowerW" in pv_info:
            flat["ppv"] = pv_info["totalPowerW"]
        for i in range(1, 5):
            pv_key = f"pv{i}"
            if pv_key in pv_info and isinstance(pv_info[pv_key], dict):
                pvi = pv_info[pv_key]
                if "voltageV" in pvi:
                    flat[f"pv{i}v"] = pvi["voltageV"]
                if "currentA" in pvi:
                    flat[f"pv{i}i"] = pvi["currentA"]
                if "powerW" in pvi:
                    flat[f"pv{i}p"] = pvi["powerW"]

    # 5. battery
    if "battery" in device and isinstance(device["battery"], dict):
        bat = device["battery"]
        if "serialNumber" in bat:
            flat["batSn"] = bat["serialNumber"]
        if "capacityKwh" in bat:
            flat["batCap"] = bat["capacityKwh"]
        if "socPercent" in bat:
            flat["batSoc"] = bat["socPercent"]
        if "sohPercent" in bat:
            flat["batSoh"] = bat["sohPercent"]
        if "powerW" in bat:
            flat["batP"] = bat["powerW"]
        if "pbatW" in bat:
            flat["pbat"] = bat["pbatW"]
        if "voltageV" in bat:
            flat["batV"] = bat["voltageV"]
        if "currentA" in bat:
            flat["batI"] = bat["currentA"]
        if "chargeEnergyKwh" in bat:
            flat["batCharge"] = bat["chargeEnergyKwh"]
        if "dischargeEnergyKwh" in bat:
            flat["batDisCharge"] = bat["dischargeEnergyKwh"]

        # battery.temperature
        if "temperature" in bat and isinstance(bat["temperature"], dict):
            btemp = bat["temperature"]
            if "chargeTempC" in btemp:
                flat["batTch"] = btemp["chargeTempC"]
            if "cellLowTempC" in btemp:
                flat["batTcl"] = btemp["cellLowTempC"]

        # battery.limits
        if "limits" in bat and isinstance(bat["limits"], dict):
            blim = bat["limits"]
            if "maxChargePowerW" in blim:
                flat["maxChargePower"] = blim["maxChargePowerW"]
            if "maxDischargePowerW" in blim:
                flat["maxDischargePower"] = blim["maxDischargePowerW"]

        # battery.cellVoltage
        if "cellVoltage" in bat and isinstance(bat["cellVoltage"], dict):
            bvol = bat["cellVoltage"]
            if "cellVoltageLowV" in bvol:
                flat["batVcl"] = bvol["cellVoltageLowV"]
            if "cellVoltageHighV" in bvol:
                flat["batVch"] = bvol["cellVoltageHighV"]

    # 6. dcBus
    if "dcBus" in device and isinstance(device["dcBus"], dict):
        dbus = device["dcBus"]
        if "vbus" in dbus:
            flat["vbus"] = dbus["vbus"]

    # 7. temperatures
    if "temperatures" in device and isinstance(device["temperatures"], dict):
        temps = device["temperatures"]
        if "inverterTempC" in temps:
            flat["tinv"] = temps["inverterTempC"]

    # 8. phases
    if "phases" in device and isinstance(device["phases"], dict):
        phs = device["phases"]
        for i in range(1, 4):
            ph_key = f"ph{i}"
            if ph_key in phs and isinstance(phs[ph_key], dict):
                phi = phs[ph_key]
                if "voltageV" in phi:
                    flat[f"ph{i}v"] = phi["voltageV"]
                if "currentA" in phi:
                    flat[f"ph{i}i"] = phi["currentA"]
                if "powerW" in phi:
                    flat[f"ph{i}p"] = phi["powerW"]
                if "epsPowerW" in phi:
                    flat[f"ph{i}Loadp"] = phi["epsPowerW"]

    # 9. grid
    if "grid" in device and isinstance(device["grid"], dict):
        grd = device["grid"]
        if "powerW" in grd and grd["powerW"] is not None:
            try:
                flat["gridP"] = float(grd["powerW"]) / 1000.0
            except ValueError, TypeError:
                flat["gridP"] = grd["powerW"]
        if "frequencyHz" in grd:
            flat["gridF"] = grd["frequencyHz"]
        if "powerFactor" in grd:
            flat["gridPfd"] = grd["powerFactor"]
        if "energyInKwh" in grd:
            flat["totalEnt"] = grd["energyInKwh"]
        if "energyOutKwh" in grd:
            flat["totalEpt"] = grd["energyOutKwh"]

    # Copy any other keys at the root that aren't dictionaries
    for k, v in device.items():
        if k not in flat and not isinstance(v, dict):
            mapped_k = _key_map.get(k, k)
            flat[mapped_k] = v

    return flat


# Deployment-configured secret for log masking. If not provided,
# falls back to a process-random secret.
_LOG_SALT = os.environ.get("HYXI_LOG_SALT", "").encode("utf-8") or secrets.token_bytes(
    16
)


def set_log_salt(salt: str | bytes) -> None:
    """Set a deployment-stable secret for cross-device log correlation."""
    global _LOG_SALT  # pylint: disable=global-statement
    if isinstance(salt, str):
        salt = salt.encode("utf-8")
    _LOG_SALT = salt
    _mask_id.cache_clear()


@functools.lru_cache(maxsize=1024)
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
    return hmac.new(_LOG_SALT, id_str.encode("utf-8"), hashlib.sha256).hexdigest()[:8]


# Keys in raw API response dicts that contain identifying or personal information.
_SENSITIVE_KEYS = frozenset(
    {
        "deviceSn",
        "parentSn",
        "batSn",
        "emsSn",
        "alias",
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


_PEAK_SHAVING_VALUES = {
    "close": "0",
    "charge": "1",
    "discharge": "2",
    "stop": "3",
    "hold": "4",
}


class HyxiApiClient:  # pylint: disable=too-many-instance-attributes
    """Client for interacting with the HYXI Cloud API."""

    DEFAULT_BASE_URL = "https://open.hyxicloud.com"

    # ── VPP Awareness ────────────────────────────────────────────────────
    # workMode values that indicate an active VPP program is controlling
    # this device. The 'workMode' field is already returned in regular
    # polling metrics — no separate API call is needed.
    #
    # Confirmed values (live observation + HYXI community research):
    #   "13" = VPP Charge (remote grid charge active)
    #   "14" = VPP Discharge (remote grid discharge active)
    #   "16" = VPP Enrolled / Standby (device registered, NOT under active dispatch)
    #
    # Standard non-VPP modes for reference (NOT included here):
    #   "0" = Self-use / general
    #   "1" = Backup priority
    #   "2" = Time-of-use / peak shaving
    #   "3" = Feed-in priority
    #
    # workMode is returned as a string or integer from the API, cast to string for matching.
    # Source: live workMode value observed during active VPP dispatch,
    # corroborated by HYXI community register documentation.
    VPP_ACTIVE_MODES: frozenset[str] = frozenset(
        {"13", "14"}
    )  # "16" = standby only, not active dispatch

    class ControlError(Exception):
        """Raised when a device control command fails."""

    class SubscriptionError(Exception):
        """Raised when a subscription request fails."""

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

            if not is_token_request and not res.get("success") and res.get("code"):
                api_code = res.get("code")
                if (
                    api_code.startswith("A0000") and api_code != "A000012"
                ) or api_code == "C000006":
                    _LOGGER.debug(
                        "HYXI Server rejected our token (%s). Forcing immediate token refresh...",
                        api_code,
                    )
                    self.token = None
                    self.token_expires_at = 0
                    raise TokenRejectedError("Server rejected token")

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
        except Exception as e:
            _LOGGER.error("HYXI Token Request Failed: %s", e)
        return False

    async def _ensure_authenticated(self, error_cls: type[Exception]) -> None:
        """Refresh the API token or raise the provided domain error."""
        token_status = await self._refresh_token()
        if token_status == "auth_failed":
            raise error_cls("Authentication failed")
        if not token_status:
            raise error_cls("Could not obtain API token")

    async def _fetch_device_metrics(self, sn, entry):
        """Helper to fetch detailed metrics for a single device."""
        q_path = "/api/device/v1/queryDeviceData"
        try:
            _, res_q = await self._request("GET", q_path, params={"deviceSn": sn})

            if res_q.get("success"):
                data_list = res_q.get("data", [])
                m_raw = _parse_data_list(data_list)

                # 🚀 Sanitization: If this is a Collector, ignore battery/power metrics that shouldn't be here.
                # This prevents "Collector" entities in Home Assistant from showing ghost battery stats.
                if entry.get("device_type_code") == "COLLECTOR":
                    entry["metrics"].update(_filter_collector_metrics(m_raw))
                else:
                    entry["metrics"].update(m_raw)

                if (
                    "gridP" in m_raw
                    or "pbat" in m_raw
                    or "batP" in m_raw
                    or "pvPower" in m_raw
                    or "gridF" in m_raw
                ):
                    entry["metrics"].update(
                        _compute_derived_metrics(
                            m_raw, entry.get("device_type_code", "")
                        )
                    )
            else:
                _LOGGER.warning(
                    "HYXI API metrics rejected for %s: %s",
                    _mask_id(sn),
                    _sanitize_dict(res_q),
                )
        except TokenRejectedError:  # pylint: disable=try-except-raise
            raise
        except Exception as e:
            _LOGGER.error("Error fetching metrics for %s: %s", _mask_id(sn), e)

    async def query_ems_basic_details(self, ems_sn):
        """Acquire basic data for Energy Storage Systems (ESS)."""
        path = "/api/ems/v1/queryBasicDetails"
        try:
            _, res = await self._request("GET", path, params={"emsSn": ems_sn})

            if res.get("code") == "0":
                data = res.get("data", [])
                return _parse_ems_kv(data)

            _LOGGER.warning(
                "HYXI EMS Basic Data Request Rejected for %s: %s",
                _mask_id(ems_sn),
                _sanitize_dict(res),
            )
        except TokenRejectedError:  # pylint: disable=try-except-raise
            raise
        except Exception as e:
            _LOGGER.error(
                "HYXI EMS Basic Data Request Failed for %s: %s", _mask_id(ems_sn), e
            )
        return {}

    @staticmethod
    def _extract_battery_info(i_raw):
        """Helper to extract battery-specific device info."""
        return {
            "batCap": _get_f("batCap", i_raw),
            "packNum": int(i_raw.get("packNum") or 1),
            "maxChargePower": _get_f("maxChargePower", i_raw)
            or _get_f("maxChargingDischargingPower", i_raw),
            "maxDischargePower": _get_f("maxDischargePower", i_raw)
            or _get_f("maxChargingDischargingPower", i_raw),
        }

    @staticmethod
    def _extract_device_info_metadata(entry, i_raw):
        """Helper to extract metadata from device info."""
        sw_ver = i_raw.get("swVerSys") or i_raw.get("swVerMaster") or i_raw.get("swVer")
        hw_ver = i_raw.get("hwVer")
        if sw_ver:
            entry["sw_version"] = sw_ver
        if hw_ver:
            entry["hw_version"] = hw_ver

        detailed_model = i_raw.get("model")
        if detailed_model and detailed_model != entry.get("model"):
            entry["model"] = detailed_model

        base_info = {
            "hw_version": hw_ver,
            "_sw_ver_sys": sw_ver,
            "signalIntensity": i_raw.get("signalIntensity"),
            "signalVal": i_raw.get("signalVal"),
            "wifiVer": i_raw.get("wifiVer") or i_raw.get("swVerWifi"),
            "comMode": i_raw.get("comMode"),
            "swVerMaster": i_raw.get("swVerMaster"),
            "swVerSlave": i_raw.get("swVerSlave"),
            "ratedFrequency": i_raw.get("ratedFrequency"),
        }

        device_type_code = entry.get("device_type_code", "")
        if device_type_code in _battery_device_types:
            base_info.update(HyxiApiClient._extract_battery_info(i_raw))

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
                    _sanitize_dict(res_i),
                )

        except TokenRejectedError:  # pylint: disable=try-except-raise
            raise
        except Exception as e:
            _LOGGER.error("Error fetching device info for %s: %s", _mask_id(sn), e)

    async def _fetch_all_for_device(self, sn, entry, dev_type):
        """Fires off concurrent tasks for Data and Info, merging the results."""
        tasks = [asyncio.create_task(self._fetch_device_info(sn, entry))]
        is_comm_unit = dev_type in ("COLLECTOR", "DMU", "3")

        ems_task = None
        if not is_comm_unit:
            tasks.append(asyncio.create_task(self._fetch_device_metrics(sn, entry)))

            actual_type = entry.get("device_type_code", dev_type)
            if actual_type in _EMS_DEVICE_TYPES:
                ems_task = asyncio.create_task(self.query_ems_basic_details(sn))
                tasks.append(ems_task)

        # Wait for them to finish
        if tasks:
            await asyncio.gather(*tasks)

        if ems_task:
            m_raw = ems_task.result()
            if m_raw:
                entry["metrics"].update(m_raw)
            else:
                _LOGGER.debug(
                    "HYXI EMS telemetry probe returned no data for %s", _mask_id(sn)
                )

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
                "HYXI Discovered Devices for Plant %s: [%s]",
                _mask_id(plant_id),
                ", ".join(_mask_id(d.get("deviceSn", "UNKNOWN")) for d in devices),
            )
        return devices

    async def _fetch_devices_for_plant(self, plant_id, state: FetchState):
        """Helper to fetch devices for a single plant concurrently."""
        try:
            devices = await self._fetch_device_list_for_plant(plant_id)
            if devices is None:
                return

            await self._process_devices_for_plant(devices, state)

        except TokenRejectedError:  # pylint: disable=try-except-raise
            raise
        except Exception as e:
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
            if dev_type in _parent_device_types:
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
        try:
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
        except TokenRejectedError:  # pylint: disable=try-except-raise
            raise
        except Exception as e:
            _LOGGER.error(
                "Error fetching sub-device list for %s: %s", _mask_id(parent_sn), e
            )
            return []

    async def _fetch_sub_devices(self, parent_sn, state: FetchState):
        """Fetch sub-devices under a communication unit (Collector/DMU)."""
        try:
            children = await self._fetch_sub_device_list(parent_sn)
            if not children:
                return

            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "HYXI Found %s sub-devices under %s: [%s]",
                    len(children),
                    _mask_id(parent_sn),
                    ", ".join(_mask_id(c.get("deviceSn", "UNKNOWN")) for c in children),
                )

            for c in children:
                sn = c.get("deviceSn")
                if not sn or sn in state.discovered_sns:
                    continue

                state.discovered_sns.add(sn)
                entry, raw_type = HyxiApiClient._build_device_entry(sn, c, state.now)

                self._update_discovery_cache(sn, entry)

                # These are real devices, so store args for later metric/info fetch
                state.metric_tasks.append((sn, entry, raw_type))

        except TokenRejectedError:  # pylint: disable=try-except-raise
            raise
        except Exception as e:
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

            return alarms
        except TokenRejectedError:  # pylint: disable=try-except-raise  # pylint: disable=try-except-raise
            raise
        except Exception as e:
            _LOGGER.error(
                "Error fetching alarms for plant %s: %s", _mask_id(plant_id), e
            )
            return []

    async def get_all_device_data(
        self, allow_back_discovery: bool = False, force_discovery: bool = False
    ):
        """Fetches data with built-in retry logic and returns attempt count."""

        for attempt in range(1, MAX_RETRIES + 1):
            err: aiohttp.ClientError | TimeoutError | None = None
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
                err = aiohttp.ClientError("Fetch returned None, triggering retry.")

            except (aiohttp.ClientError, TimeoutError) as e:
                err = e

            if err is not None:
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
            _LOGGER.error("HYXI API Plant Fetch Rejected: %s", _sanitize_dict(res_p))
            return None

        data_p = res_p.get("data", {})
        plants = data_p.get("list", []) if isinstance(data_p, dict) else []

        if not plants:
            _LOGGER.warning(
                "HYXI API: No plants found associated with this account. "
                "If your developer email differs from your app email, you must share "
                "your Plant from the app to the developer email first."
            )
        elif _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "HYXI Discovered Plants: [%s]",
                ", ".join(_mask_id(p.get("plantId", "UNKNOWN")) for p in plants),
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

    async def _execute_metric_tasks(self, plant_alarms, state: FetchState):
        """Helper to conditionally execute metrics and map alarms."""
        if state.metric_tasks:
            await self._execute_metrics_and_map_alarms(plant_alarms, state)

    async def _process_plants_data(
        self, state: FetchState, allow_back_discovery: bool = False
    ):
        """Helper to concurrently process plants to gather metrics and alarms."""
        device_fetch_tasks, alarm_fetch_tasks = self._build_plant_tasks(state)

        _, plant_alarms = await asyncio.gather(
            HyxiApiClient._execute_device_tasks(device_fetch_tasks),
            self._fetch_and_process_alarms(
                alarm_fetch_tasks,
                state,
                allow_back_discovery=allow_back_discovery,
            ),
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

        entry, dev_type = HyxiApiClient._build_device_entry(sn, a, state.now)
        state.metric_tasks.append((sn, entry, dev_type))

        # 🚀 DEEP BACK-DISCOVERY: If this is a parent, search for ITS children too!
        if dev_type in _parent_device_types:
            sub_device_tasks.append((sn, state))

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
            tasks = [self._fetch_sub_devices(sn, s) for sn, s in sub_device_tasks]
            await asyncio.gather(*tasks)

        return plant_alarms

    async def _execute_metrics_and_map_alarms(self, plant_alarms, state: FetchState):
        """Helper to execute metric tasks and map alarms to devices."""
        # Precompute alarm mapping to optimize from O(N*M) to O(N+M)
        alarms_by_sn = defaultdict(list)
        for a in plant_alarms:
            sn = a.get("deviceSn")
            if sn:
                alarms_by_sn[sn].append(a)

        # Convert argument tuples to coroutines just in time
        tasks = [
            self._fetch_all_for_device(sn, entry, dev_type)
            for sn, entry, dev_type in state.metric_tasks
        ]

        if tasks:
            updated_entries = await asyncio.gather(*tasks)
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
            return await self._execute_fetch_cached(state, allow_back_discovery)

        return await self._execute_fetch_full_discovery(state, allow_back_discovery)

    async def _execute_fetch_cached(
        self, state: FetchState, allow_back_discovery: bool
    ):
        """Execute the fetching logic using cached discovery data (Fast Polling)."""
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
                    "metrics": {"last_seen": state.now},
                }
                state.metric_tasks.append((sn, entry, info["device_type_code"]))
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

    async def _execute_fetch_full_discovery(
        self, state: FetchState, allow_back_discovery: bool
    ):
        """Execute the fetching logic using full discovery path."""
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
        dev_type = str(device_data.get("deviceType") or "UNKNOWN").upper()
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

    # ── Device Control API ──────────────────────────────────────────────

    async def set_device_control(
        self, device_sn: str, control_map: dict[int | str, str]
    ) -> dict:
        """Send a controlMap write to a device.

        Endpoint: POST /api/device/v2/control
        Body: {"deviceControlMap": {"<sn>": {"<controlId>": <value>, ...}}}

        control_map keys are HYXI controlIds (1020/1021/1062/1063/1064/1065/...).
        Values are strings per the developer docs ('' for idle/self-consumption,
        a wattage like '100' for 1063/1064, '0'/'1' for switches).
        """
        if not control_map:
            _LOGGER.warning("set_device_control called with empty settings")
            return {}

        await self._ensure_authenticated(self.ControlError)

        path = "/api/device/v2/control"
        body = {
            "deviceControlMap": {device_sn: {str(k): v for k, v in control_map.items()}}
        }
        _LOGGER.debug(
            "HYXI CONTROL request for %s: %s",
            _mask_id(device_sn),
            body["deviceControlMap"][device_sn],
        )
        try:
            _, res = await self._request("POST", path, json=body)
        except TokenRejectedError:
            _LOGGER.debug(
                "Token rejected, forcing re-authentication and retrying control..."
            )
            await self._ensure_authenticated(self.ControlError)
            _, res = await self._request("POST", path, json=body)

        if res is None or not res.get("success"):
            code = res.get("code", "unknown") if res else "no_response"
            msg = res.get("msg", "") if res else ""
            raise self.ControlError(f"controlMap write failed (code={code}): {msg}")
        _LOGGER.debug(
            "HYXI CONTROL response for %s: success=%s",
            _mask_id(device_sn),
            res.get("success"),
        )
        return res

    # ── Subscription API ────────────────────────────────────────────────

    async def _post_subscription(self, path: str, body: dict) -> dict:
        """Send an authenticated subscription request."""
        await self._ensure_authenticated(self.SubscriptionError)

        _LOGGER.debug("HYXI subscription request to %s", path)
        try:
            _, res = await self._request("POST", path, json=body)
        except TokenRejectedError:
            _LOGGER.debug(
                "Token rejected, forcing re-authentication and retrying subscription..."
            )
            await self._ensure_authenticated(self.SubscriptionError)
            _, res = await self._request("POST", path, json=body)

        if res is None or not res.get("success"):
            code = res.get("code", "unknown") if res else "no_response"
            msg = res.get("msg", "") if res else ""
            raise self.SubscriptionError(
                f"subscription request failed (code={code}): {msg}"
            )
        return res

    @staticmethod
    def _validate_subscription_device_sns(device_sn_list: list[str]) -> None:
        """Validate subscription device SN list constraints."""
        if not device_sn_list:
            raise ValueError("device_sn_list must contain at least one device SN")
        if len(device_sn_list) > 1000:
            raise ValueError("device_sn_list cannot contain more than 1000 device SNs")

    @staticmethod
    def _validate_callback_url(callback_url: str) -> None:
        """Validate the subscriber callback URL."""
        if not callback_url or not callback_url.strip():
            raise ValueError("callback_url must be a non-empty string")
        parsed = urlparse(callback_url.strip())
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("callback_url must be a valid http/https URL")

    @staticmethod
    def _validate_post_rate_ms(post_rate: int) -> None:
        """Validate millisecond subscription push rate."""
        if not 5000 <= post_rate <= 3600000:
            raise ValueError("post_rate must be between 5000 and 3600000 milliseconds")

    async def subscribe_real_time_data(
        self,
        callback_url: str,
        device_sn_list: list[str],
        post_rate: int,
        data_code_list: list[str] | None = None,
    ) -> dict:
        """Subscribe to real-time device data notifications.

        Endpoint: POST /api/subscribe/v1/realTimeData
        """
        self._validate_callback_url(callback_url)
        self._validate_subscription_device_sns(device_sn_list)
        self._validate_post_rate_ms(post_rate)

        body: dict[str, Any] = {
            "callBackUrl": callback_url,
            "deviceSnList": device_sn_list,
            "postRate": int(post_rate),
        }
        if data_code_list is not None:
            body["dataCodeList"] = data_code_list

        return await self._post_subscription("/api/subscribe/v1/realTimeData", body)

    async def subscribe_alarm(
        self,
        callback_url: str,
        device_sn_list: list[str],
        post_rate: int,
        alarm_code_list: list[str] | None = None,
    ) -> dict:
        """Subscribe to device alarm notifications.

        Endpoint: POST /api/subscribe/v1/alarm
        """
        self._validate_callback_url(callback_url)
        self._validate_subscription_device_sns(device_sn_list)
        self._validate_post_rate_ms(post_rate)

        body: dict[str, Any] = {
            "callBackUrl": callback_url,
            "deviceSnList": device_sn_list,
            "postRate": int(post_rate),
        }
        if alarm_code_list is not None:
            body["alarmCodeList"] = alarm_code_list

        return await self._post_subscription("/api/subscribe/v1/alarm", body)

    async def subscribe_fm_real_time_data(
        self,
        callback_url: str,
        device_sn_list: list[str],
        post_rate: int,
    ) -> dict:
        """Subscribe to FCAS/frequency modulation real-time device data.

        Endpoint: POST /api/subscribe/v1/FMRealTimeData

        Args:
            post_rate: Push rate in hours. Must be between 1 and 6.
        """
        self._validate_callback_url(callback_url)
        self._validate_subscription_device_sns(device_sn_list)
        if not 1 <= post_rate <= 6:
            raise ValueError("post_rate must be between 1 and 6 hours")

        body = {
            "callBackUrl": callback_url,
            "deviceSnList": device_sn_list,
            "postRate": int(post_rate),
        }
        return await self._post_subscription("/api/subscribe/v1/FMRealTimeData", body)

    async def cancel_subscription(self, subscribe_code: str) -> dict:
        """Cancel a subscription by subscription code.

        Endpoint: POST /api/subscribe/v1/cancel
        """
        if not subscribe_code or not subscribe_code.strip():
            raise ValueError("subscribe_code must be a non-empty string")

        return await self._post_subscription(
            "/api/subscribe/v1/cancel",
            {"subscribeCode": subscribe_code.strip()},
        )

    async def set_mode_idle(self, device_sn: str) -> dict:
        """Set inverter to Idle mode (controlId 1062).

        For **Three-Phase** devices (e.g. HYBRID_INVERTER).
        Battery neither charges nor discharges.
        """
        return await self.set_device_control(device_sn, {1062: ""})

    async def set_mode_charge(self, device_sn: str, watts: int) -> dict:
        """Set inverter to Charge mode (controlId 1063) with wattage.

        For **Three-Phase** devices (e.g. HYBRID_INVERTER).
        Battery charges using PV first; any shortfall is drawn from the grid.

        Args:
            device_sn: Device serial number.
            watts: Charge power in Watts. Must be a positive integer.
        """
        if watts <= 0:
            raise ValueError(f"watts must be a positive integer, got {watts}")
        return await self.set_device_control(device_sn, {1063: str(int(watts))})

    async def set_mode_discharge(self, device_sn: str, watts: int) -> dict:
        """Set inverter to Discharge mode (controlId 1064) with wattage.

        For **Three-Phase** devices (e.g. HYBRID_INVERTER).
        Battery discharges to cover household consumption first; excess is injected into the grid.

        Args:
            device_sn: Device serial number.
            watts: Discharge power in Watts. Must be a positive integer.
        """
        if watts <= 0:
            raise ValueError(f"watts must be a positive integer, got {watts}")
        return await self.set_device_control(device_sn, {1064: str(int(watts))})

    async def set_mode_self_consume(self, device_sn: str) -> dict:
        """Set inverter to Self-consumption mode (controlId 1065).

        For **Three-Phase** devices (e.g. HYBRID_INVERTER).
        Battery discharges only to match household demand. Excess PV is injected into the grid.
        """
        return await self.set_device_control(device_sn, {1065: ""})

    async def set_peak_shaving(self, device_sn: str, action: str) -> dict:
        """Set Peak Shaving control (controlId 1021).

        For **Single Phase** devices (e.g. ALL_IN_ONE). Used for VPP operations.
        All charge/discharge operations run at the inverter's full power.

        action: one of 'close', 'charge', 'discharge', 'stop', 'hold'
        """
        value = _PEAK_SHAVING_VALUES.get(action)
        if value is None:
            raise ValueError(
                f"Invalid peak shaving action '{action}'. "
                f"Must be one of: {', '.join(_PEAK_SHAVING_VALUES)}"
            )
        return await self.set_device_control(device_sn, {1021: value})

    async def set_frequency_control(self, device_sn: str, enabled: bool) -> dict:
        """Enable or disable Frequency Control (controlId 1020).

        For **Single Phase** devices (e.g. ALL_IN_ONE).
        Used for VPP business and FCAS response functionality.
        """
        return await self.set_device_control(device_sn, {1020: "1" if enabled else "0"})

    # ── Microinverter Controls ───────────────────────────────────────────

    async def set_micro_power(self, device_sn: str, power_on: bool) -> dict:
        """Turn on or off a Microinverter (controlId 3011).

        For **MICRO_INVERTER** devices.

        Args:
            device_sn: Device serial number.
            power_on: True to turn on ("1"), False to turn off ("0").
        """
        return await self.set_device_control(
            device_sn, {3011: "1" if power_on else "0"}
        )

    async def set_micro_power_limit(self, device_sn: str, percentage: int) -> dict:
        """Set Maximum Power Limitation for a Microinverter (controlId 3012).

        For **MICRO_INVERTER** devices.
        Actual power limit = percentage * rated power.

        Args:
            device_sn: Device serial number.
            percentage: Power limit as a percentage of rated power (0-100).
        """
        if not 0 <= percentage <= 100:
            raise ValueError(f"percentage must be between 0 and 100, got {percentage}")
        return await self.set_device_control(device_sn, {3012: str(int(percentage))})

    async def restart_device(self, device_sn: str) -> dict:
        """Restart a Microinverter (controlId 3013).

        For **MICRO_INVERTER** devices.
        """
        return await self.set_device_control(device_sn, {3013: "1"})

    # ── Alarm Controls ───────────────────────────────────────────────────

    async def alter_alarm(self, alarm_ids: list[int]) -> dict:
        """Process/Acknowledge alarm information.

        Endpoint: POST /api/alarm/v1/alterAlarm
        Body: {"ids": [id1, id2, ...], "state": 1}
        """
        token_status = await self._refresh_token()
        if token_status == "auth_failed":
            raise self.ControlError("Authentication failed")
        if not token_status:
            raise self.ControlError("Could not obtain API token")

        path = "/api/alarm/v1/alterAlarm"
        body = {
            "ids": alarm_ids,
            "state": 1,
        }
        _LOGGER.debug(
            "HYXI ALTER_ALARM request for ids %s: %s",
            alarm_ids,
            body,
        )
        _, res = await self._request("POST", path, json=body)
        if res is None or not res.get("success"):
            code = res.get("code", "unknown") if res else "no_response"
            msg = res.get("msg", "") if res else ""
            raise self.ControlError(f"alarm alteration failed (code={code}): {msg}")
        _LOGGER.debug(
            "HYXI ALTER_ALARM response: success=%s",
            res.get("success"),
        )
        return res

    @staticmethod
    def compute_derived_metrics(m_raw: dict, device_type: str = "") -> dict:
        """Calculate derived metrics (grid import/export, bat charging/discharging, etc.) from raw metrics."""
        return _compute_derived_metrics(m_raw, device_type)

    def process_push_data(
        self,
        payload: dict,
        existing_metrics: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Process real-time push data from HYXI Cloud.

        Parses the flat push payload, matches it to the discovery cache,
        filters collector metrics, and computes derived metrics.

        Returns a dictionary of:
        {
            "device_sn": {
                "sn": "device_sn",
                "metrics": { ... },
                "model": "...",
                "device_type_code": "..."
            }
        }
        """
        if not isinstance(payload, dict):
            _LOGGER.warning("HYXI Push: Payload is not a dictionary")
            return {}

        data_list = payload.get("dataList")
        if not isinstance(data_list, list):
            _LOGGER.warning("HYXI Push: dataList is missing or not a list")
            return {}

        now_utc = datetime.now(UTC)
        results = {}

        for device in data_list:
            if not isinstance(device, dict):
                continue

            device = _flatten_nested_push_device(device)

            sn = device.get("deviceSn")
            if not sn:
                continue

            # Retrieve info from discovery cache
            device_info = self._discovery_cache.get("device_info", {}).get(sn, {})
            device_type = str(device_info.get("device_type_code") or "")

            raw_metrics = _extract_raw_push_metrics(device)
            last_seen = _resolve_push_timestamp(device, now_utc)

            merged_metrics = _merge_push_metrics(
                sn, raw_metrics, device_type, existing_metrics
            )
            merged_metrics["last_seen"] = last_seen.isoformat()

            # Compute derived metrics on the full merged dataset
            derived = _compute_derived_metrics(merged_metrics, device_type)
            merged_metrics.update(derived)

            results[sn] = {
                "sn": sn,
                "metrics": merged_metrics,
                "model": device_info.get("model", "Unknown"),
                "device_type_code": device_info.get("device_type_code", "Unknown"),
            }

        return results

    def process_alarm_push_data(self, payload: dict) -> dict[str, list[dict]]:
        """Process alarm push data from HYXI Cloud.

        Parses the alarm push callback payload and returns a dict mapping
        device SN to a list of alarm records in the same shape that
        coordinator.data[sn]["alarms"] uses during polling.

        Alarm push payload shape (dataList item):
            {
                "deviceSn": "...",
                "alarmCode": "1234",
                "alarmName": "Over temperature alarm",
                "alarmState": "1",        # "0"=resolved, "1"/"2"=active
                "alarmTime": 1712728593000,   # ms epoch
                "endTime": null or ms epoch,
                "happenTime": 1712728593000,  # alternative field name
            }

        Returns:
            {
                "device_sn": [
                    {"alarmCode": "1234", "alarmName": "...", "alarmState": "1", ...}
                ]
            }
        """
        if not isinstance(payload, dict):
            _LOGGER.warning("HYXI Alarm Push: Payload is not a dictionary")
            return {}

        data_list = payload.get("dataList")
        if not isinstance(data_list, list):
            _LOGGER.warning("HYXI Alarm Push: dataList is missing or not a list")
            return {}

        results: dict[str, list[dict]] = {}

        for item in data_list:
            if not isinstance(item, dict):
                continue

            sn = item.get("deviceSn")
            if not sn:
                continue

            alarm_code = f"{item.get('alarmCode', '')}"

            # Resolve alarm name: use payload name if present, fall back to ALARM_CODE_MAP
            alarm_name = item.get("alarmName") or ALARM_CODE_MAP.get(
                alarm_code, f"Unknown alarm ({alarm_code})"
            )

            # Normalise state — push may use "alarmState" or "happenState"
            alarm_state = item.get("alarmState") or item.get("happenState")

            # Normalise time fields — push may use "alarmTime" or "happenTime"
            alarm_time = item.get("alarmTime") or item.get("happenTime")
            end_time = item.get("endTime") or item.get("recoverTime")

            alarm_record = {
                "alarmCode": alarm_code,
                "alarmName": alarm_name,
                "alarmState": alarm_state,
                "alarmTime": alarm_time,
                "endTime": end_time,
            }

            results.setdefault(sn, []).append(alarm_record)
            _LOGGER.debug(
                "HYXI Alarm Push: %s — code %s (%s) state=%s",
                sn,
                alarm_code,
                alarm_name,
                alarm_state,
            )

        return results
