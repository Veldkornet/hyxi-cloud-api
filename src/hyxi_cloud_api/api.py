"""HYXI Cloud API Client for retrieving inverter and battery data.

This module is intentionally large: it includes the full ALARM_CODE_MAP,
INTERNAL_ERROR_MAP, and DEVICE_TYPE_MAP reference tables to avoid external
dependencies. Suppress the module-size warning accordingly.
"""  # pylint: disable=too-many-lines

import asyncio
import base64
import hashlib
import hmac
import logging
import os
import time
from collections import defaultdict
from datetime import UTC
from datetime import datetime

import aiohttp

_LOGGER = logging.getLogger(__name__)

_PARENT_DEVICE_TYPES = ("COLLECTOR", "DMU", "INVERTER")
_BANNED_COLLECTOR_KEYS = ("bat", "pv", "grid", "pbat", "load", "ph1", "ph2", "ph3")

# Official HYXI Alarm Code Reference Table
ALARM_CODE_MAP = {
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
        item.get("dataKey"): item.get("dataValue")
        for item in data_list
        if isinstance(item, dict) and item.get("dataKey")
    }


def _parse_ems_kv(data: list) -> dict:
    """Extract prop and value from nested EMS Field KV structure.

    Keys are lowercased to match HA sensor entity key conventions.
    """
    res = {}
    for module in data:
        if not isinstance(module, dict):
            continue
        field_kv = module.get("filedKv", [])
        for item in field_kv:
            prop = item.get("prop")
            if prop:
                res[prop.lower()] = item.get("value")
    return res


def _get_f(key: str, data_map: dict, mult: float = 1.0) -> float:
    """Helper to safely extract and multiply float values."""
    try:
        val = data_map.get(key)
        if val is None or val == "":
            return 0.0
        return round(float(val) * mult, 2)
    except (ValueError, TypeError):
        return 0.0


def _mask_id(value: str) -> str:
    """Mask an identifier (SN, plant ID, etc.) for logs.

    Replaces middle characters with 'X' to preserve the true length while
    hiding the sensitive portion. IDs shorter than 8 characters are fully
    redacted as '****' to prevent short numeric IDs from being revealed.

    Example: '10602251600016' -> '106XXXXXXXX016'
    """
    if not value:
        return "****"
    id_str = str(value)
    if len(id_str) < 8:
        return "****"
    middle_len = len(id_str) - 6
    return f"{id_str[:3]}{'X' * middle_len}{id_str[-3:]}"


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
    }
)


def _sanitize_dict(raw: dict) -> dict:
    """Return a copy of a raw API response dict with sensitive fields masked.

    Used before logging raw API payloads so that SNs, plant IDs, and personal
    details (e.g. home address) are never written to the log in plain text.
    """
    result = {}
    for k, v in raw.items():
        if k == "plantAddress":
            result[k] = "[REDACTED]"
        elif (k in _SENSITIVE_KEYS or k.lower() == "alarmstate") and v:
            if k in _SENSITIVE_KEYS:
                result[k] = _mask_id(str(v))
            else:
                result[k] = v
        else:
            result[k] = v
    return result


class HyxiApiClient:
    """Client for interacting with the HYXI Cloud API."""

    def __init__(
        self, access_key, secret_key, base_url, session: aiohttp.ClientSession
    ):
        self.access_key = access_key
        self.secret_key = secret_key
        self._secret_key_bytes = secret_key.encode("utf-8")
        self.base_url = base_url.rstrip("/")
        self.session = session
        self.token = None
        self.token_expires_at = 0

    def _get_error_message(self, res: dict) -> str:
        """Extract the official error description from a response dict."""
        code = str(res.get("code") or "")
        msg = res.get("message") or ""
        official_desc = INTERNAL_ERROR_MAP.get(code)

        if official_desc:
            return f"{official_desc} ({code})"
        return f"{msg} ({code})" if code else msg

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

    def _apply_token_response(self, data: dict) -> bool:
        """Parse token and expiration from API response and update state."""
        token_val = data.get("token") or data.get("access_token")

        if not token_val:
            return False

        self.token = f"Bearer {token_val}"

        # 1. Grab the raw expiration value exactly as the API sent it
        raw_expires_in = data.get("expiresIn") or data.get("expires_in")
        _LOGGER.debug(
            "HYXI API returned raw token expiration: %s seconds",
            raw_expires_in,
        )

        # 2. Default to 6600 if the API didn't provide one
        expires_in = raw_expires_in or 6600

        # 3. Apply the 5-minute (300s) safety buffer
        buffer_secs = 300
        self.token_expires_at = time.time() + int(expires_in) - buffer_secs

        # 4. Log the actual scheduled refresh time
        refresh_time_str = datetime.fromtimestamp(self.token_expires_at).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        _LOGGER.debug(
            "HYXI Token proactive refresh scheduled in %s seconds (at %s)",
            int(expires_in) - buffer_secs,
            refresh_time_str,
        )
        return True

    async def _refresh_token(self):
        """Async version of token refresh."""
        if self.token and time.time() < self.token_expires_at:
            return True

        path = "/api/authorization/v1/token"

        try:
            async with self.session.post(
                f"{self.base_url}{path}",
                json={"grantType": 1},
                headers=self._generate_headers(path, "POST", is_token_request=True),
                timeout=15,
            ) as response:
                if response.status in [401, 403]:
                    _LOGGER.error("HYXI API: Token request unauthorized (401/403)")
                    return "auth_failed"

                response.raise_for_status()
                res = await response.json()

                if not res.get("success"):
                    _LOGGER.error("HYXI API Token Rejected: %s", _sanitize_dict(res))
                    if res.get("code") in [401, 403, "401", "403"]:
                        return "auth_failed"
                    return False

                return self._apply_token_response(res.get("data", {}))
        except Exception as e:
            _LOGGER.error("HYXI Token Request Failed: %s", e)
        return False

    async def _fetch_device_metrics(self, sn, entry):
        """Helper to fetch detailed metrics for a single device."""
        q_path = "/api/device/v1/queryDeviceData"
        try:
            async with self.session.get(
                f"{self.base_url}{q_path}",
                params={"deviceSn": sn},
                headers=self._generate_headers(q_path, "GET"),
                timeout=15,
            ) as resp_q:
                resp_q.raise_for_status()
                res_q = await resp_q.json()

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
                    # We use a comprehension here with an external helper to avoid excessive nesting (R1702 pylint)
                    sanitized = {
                        k: v for k, v in m_raw.items()
                        if not any(x in k.lower() for x in _BANNED_COLLECTOR_KEYS)
                    }
                    entry["metrics"].update(sanitized)
                else:
                    entry["metrics"].update(m_raw)

                if "gridP" in m_raw or "pbat" in m_raw:
                    grid = _get_f("gridP", m_raw, 1000.0)
                    pbat = _get_f("pbat", m_raw)

                    entry["metrics"].update(
                        {
                            "home_load": _get_f("ph1Loadp", m_raw)
                            + _get_f("ph2Loadp", m_raw)
                            + _get_f("ph3Loadp", m_raw),
                            "grid_import": abs(grid) if grid < 0 else 0,
                            "grid_export": grid if grid > 0 else 0,
                            "bat_charging": abs(pbat) if pbat < 0 else 0,
                            "bat_discharging": pbat if pbat > 0 else 0,
                            "bat_charge_total": _get_f("batCharge", m_raw),
                            "bat_discharge_total": _get_f("batDisCharge", m_raw),
                        }
                    )
            else:
                _LOGGER.warning(
                    "HYXI API metrics rejected for %s: %s",
                    _mask_id(sn),
                    res_q.get("message"),
                )
        except Exception as e:
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
            async with self.session.get(
                f"{self.base_url}{path}",
                params={"emsSn": ems_sn},
                headers=self._generate_headers(path, "GET"),
                timeout=15,
            ) as resp:
                resp.raise_for_status()
                res = await resp.json()

                if res.get("code") == "0":
                    data = res.get("data", [])
                    return _parse_ems_kv(data)
        except Exception as e:
            _LOGGER.error(
                "HYXI EMS Basic Data Request Failed for %s: %s", _mask_id(ems_sn), e
            )
        return {}

    async def _fetch_device_info(self, sn, entry):
        """Helper to fetch static device info (firmware, capacity, limits)."""
        i_path = "/api/device/v1/queryDeviceInfo"
        try:
            async with self.session.get(
                f"{self.base_url}{i_path}",
                params={"deviceSn": sn},
                headers=self._generate_headers(i_path, "GET"),
                timeout=15,
            ) as resp_i:
                res_i = await resp_i.json()

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

                # Smart Firmware Finder
                sw_ver = (
                    i_raw.get("swVerSys")
                    or i_raw.get("swVerMaster")
                    or i_raw.get("swVer")
                )
                if sw_ver:
                    entry["sw_version"] = sw_ver

                # Base metadata for all devices
                base_info = {
                    "signalIntensity": i_raw.get("signalIntensity"),
                    "signalVal": i_raw.get("signalVal"),
                    "wifiVer": i_raw.get("wifiVer"),
                    "comMode": i_raw.get("comMode"),
                }

                # Device-specific metadata (e.g. Battery info for Inverters)
                if any(
                    x in entry.get("device_type_code", "").upper()
                    for x in ["INVERTER", "ESS", "HALO", "1", "15"]
                ):
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
            else:
                _LOGGER.warning(
                    "HYXI INFO API Rejected for %s: %s",
                    _mask_id(sn),
                    res_i.get("message"),
                )

        except Exception as e:
            _LOGGER.error("Error fetching device info for %s: %s", _mask_id(sn), e)

    async def _fetch_all_for_device(self, sn, entry, dev_type):
        """Fires off concurrent tasks for Data and Info, merging the results."""
        tasks = [asyncio.create_task(self._fetch_device_info(sn, entry))]

        if dev_type != "COLLECTOR":
            tasks.append(asyncio.create_task(self._fetch_device_metrics(sn, entry)))

            tasks.append(asyncio.create_task(self._fetch_ems_basic_data(sn, entry)))

        # Wait for them to finish
        if tasks:
            await asyncio.gather(*tasks)

        return sn, entry

    async def _fetch_devices_for_plant(
        self, plant_id, now, metric_tasks, discovered_sns
    ):
        """Helper to fetch devices for a single plant concurrently."""
        d_path = "/api/plant/v1/devicePage"
        try:
            async with self.session.post(
                f"{self.base_url}{d_path}",
                json={"plantId": plant_id, "pageSize": 50, "currentPage": 1},
                headers=self._generate_headers(d_path, "POST"),
                timeout=15,
            ) as resp_d:
                resp_d.raise_for_status()
                res_d = await resp_d.json()

            if not res_d.get("success"):
                _LOGGER.error(
                    "HYXI API Device Fetch Rejected for Plant %s: %s",
                    _mask_id(plant_id),
                    _sanitize_dict(res_d),
                )
                return

            data_val = res_d.get("data", {})
            devices = (
                data_val
                if isinstance(data_val, list)
                else data_val.get("deviceList", [])
                if isinstance(data_val, dict)
                else []
            )

            # 👇 Log the devices discovered for this plant
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "HYXI Discovered Devices for Plant %s: %s",
                    _mask_id(plant_id),
                    [_mask_id(d.get("deviceSn", "UNKNOWN")) for d in devices],
                )

            for d in devices:
                sn = d.get("deviceSn")
                if not sn:
                    continue

                discovered_sns.add(sn)
                dev_type = str(d.get("deviceType") or "UNKNOWN")
                friendly_name = (
                    DEVICE_TYPE_MAP.get(dev_type) or dev_type.replace("_", " ").title()
                )

                device_name = d.get("deviceName") or d.get("alias")
                if not device_name or device_name == "":
                    device_name = f"{friendly_name} {sn}"

                entry = {
                    "sn": sn,
                    "device_name": device_name,
                    "model": friendly_name,
                    "device_type_code": dev_type,
                    "sw_version": d.get("swVer"),
                    "hw_version": d.get("hwVer"),
                    "metrics": {"last_seen": now},
                }

                metric_tasks.append(self._fetch_all_for_device(sn, entry, dev_type))

                # 🚀 DEEP DISCOVERY: If this is a Collector, DMU, or Inverter, find its children!
                if any(x in dev_type for x in ["COLLECTOR", "DMU", "INVERTER"]):
                    _LOGGER.debug(
                        "HYXI Parent Device Found: %s (%s). Probing for sub-devices...",
                        _mask_id(sn),
                        dev_type,
                    )
                    await self._fetch_sub_devices(
                        sn, plant_id, now, metric_tasks, discovered_sns
                    )

        except Exception as e:
            _LOGGER.error(
                "Error fetching devices for plant %s: %s", _mask_id(plant_id), e
            )

    async def _fetch_sub_devices(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, parent_sn, plant_id, now, metric_tasks, discovered_sns
    ):
        """Fetch sub-devices under a communication unit (Collector/DMU)."""
        sd_path = "/api/device/v1/getSubDevicePage"
        try:
            async with self.session.post(
                f"{self.base_url}{sd_path}",
                json={"parentSn": parent_sn, "pageSize": 50, "currentPage": 1},
                headers=self._generate_headers(sd_path, "POST"),
                timeout=15,
            ) as resp_sd:
                resp_sd.raise_for_status()
                res_sd = await resp_sd.json()

            if not res_sd.get("success"):
                _LOGGER.error(
                    "HYXI API Sub-Device Fetch Rejected for %s: %s",
                    _mask_id(parent_sn),
                    _sanitize_dict(res_sd),
                )
                return

            data_val = res_sd.get("data", {})
            # Normalized extract: childDevice list
            children = (
                data_val.get("childDevice", []) if isinstance(data_val, dict) else []
            )

            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "HYXI Found %s sub-devices under %s: %s",
                    len(children),
                    _mask_id(parent_sn),
                    [_mask_id(c.get("deviceSn", "UNKNOWN")) for c in children],
                )

            for c in children:
                sn = c.get("deviceSn")
                if not sn or sn in discovered_sns:
                    continue

                discovered_sns.add(sn)

                # Sub-device responses often use numeric types (e.g. 1, 15)
                raw_type = str(c.get("deviceType") or "UNKNOWN")
                friendly_name = (
                    DEVICE_TYPE_MAP.get(raw_type) or raw_type.replace("_", " ").title()
                )

                device_name = c.get("deviceName") or c.get("alias")
                if not device_name or device_name == "":
                    device_name = f"{friendly_name} {sn}"

                entry = {
                    "sn": sn,
                    "device_name": device_name,
                    "model": friendly_name,
                    "device_type_code": raw_type,
                    "sw_version": c.get("swVer"),
                    "hw_version": c.get("hwVer"),
                    "metrics": {"last_seen": now},
                }

                # These are real devices, so fetch their metrics/info
                metric_tasks.append(self._fetch_all_for_device(sn, entry, raw_type))

        except Exception as e:
            _LOGGER.error(
                "Error fetching sub-devices for %s: %s", _mask_id(parent_sn), e
            )

    async def _fetch_alarms_for_plant(self, plant_id):
        """Helper to fetch active alarms for a single plant."""
        a_path = "/api/alarm/v1/plantAlarmPage"
        try:
            async with self.session.post(
                f"{self.base_url}{a_path}",
                json={"plantId": plant_id, "pageSize": 100, "currentPage": 1},
                headers=self._generate_headers(a_path, "POST"),
                timeout=15,
            ) as resp_a:
                resp_a.raise_for_status()
                res_a = await resp_a.json()

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
                if code in ALARM_CODE_MAP:
                    a["alarmName"] = ALARM_CODE_MAP[code]

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
        except Exception as e:
            _LOGGER.error(
                "Error fetching alarms for plant %s: %s", _mask_id(plant_id), e
            )
            return []

    async def get_all_device_data(self):
        """Fetches data with built-in retry logic and returns attempt count."""

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                data = await self._execute_fetch_all()
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
        async with self.session.post(
            f"{self.base_url}{p_path}",
            json={"pageSize": 10, "currentPage": 1},
            headers=self._generate_headers(p_path, "POST"),
            timeout=15,
        ) as resp_p:
            resp_p.raise_for_status()
            res_p = await resp_p.json()

        if not res_p.get("success"):
            # 🚀 If the server rejects the token, wipe it and force a retry!
            if res_p.get("code") in ["A000002", "A000005"]:
                _LOGGER.debug(
                    "HYXI Server rejected our token (A000002/A000005). "
                    "Forcing immediate token refresh..."
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

    async def _process_plants_data(self, plants, now, results):
        """Helper to concurrently process plants to gather metrics and alarms."""
        metric_tasks = []
        device_fetch_tasks = []
        alarm_fetch_tasks = []
        discovered_sns = set()

        for p in plants:
            plant_id = p.get("plantId")
            if not plant_id:
                continue

            device_fetch_tasks.append(
                self._fetch_devices_for_plant(
                    plant_id, now, metric_tasks, discovered_sns
                )
            )
            alarm_fetch_tasks.append(self._fetch_alarms_for_plant(plant_id))

        if device_fetch_tasks:
            await asyncio.gather(*device_fetch_tasks)

        plant_alarms = []
        if alarm_fetch_tasks:
            alarm_results = await asyncio.gather(*alarm_fetch_tasks)
            for i, alarms in enumerate(alarm_results):
                if not isinstance(alarms, list):
                    continue

                plant_alarms.extend(alarms)
                plant_id = plants[i].get("plantId")

                # 🚀 Back-Discovery: Check if alarms contain SNs we didn't find in devicePage
                for a in alarms:
                    sn = a.get("deviceSn")
                    if sn and sn not in discovered_sns:
                        _LOGGER.debug(
                            "HYXI: Back-discovering device %s found in alarms for plant %s...",
                            _mask_id(sn),
                            _mask_id(plant_id),
                        )
                        discovered_sns.add(sn)
                        dev_type = str(a.get("deviceType") or "UNKNOWN")
                        friendly_name = (
                            DEVICE_TYPE_MAP.get(dev_type)
                            or dev_type.replace("_", " ").title()
                        )

                        device_name = a.get("deviceName")
                        if not device_name or device_name == "":
                            device_name = f"{friendly_name} {sn}"

                        entry = {
                            "sn": sn,
                            "device_name": device_name,
                            "model": friendly_name,
                            "device_type_code": dev_type,
                            "sw_version": None,
                            "hw_version": None,
                            "metrics": {"last_seen": now},
                        }
                        metric_tasks.append(
                            self._fetch_all_for_device(sn, entry, dev_type)
                        )

                        # 🚀 DEEP BACK-DISCOVERY: If this is a parent, search for ITS children too!
                        if any(
                            x in dev_type.upper()
                            for x in ["COLLECTOR", "DMU", "INVERTER"]
                        ):
                            await self._fetch_sub_devices(
                                sn, plant_id, now, metric_tasks, discovered_sns
                            )

        # 3. Concurrent Metrics
        if metric_tasks:
            # Precompute alarm mapping to optimize from O(N*M) to O(N+M)
            alarms_by_sn = defaultdict(list)
            for a in plant_alarms:
                sn = a.get("deviceSn")
                if sn:
                    alarms_by_sn[sn].append(a)

            updated_entries = await asyncio.gather(*metric_tasks)
            for sn, entry in updated_entries:
                if sn:
                    # Map the relevant active alarms to this specific device
                    entry["alarms"] = alarms_by_sn.get(sn, [])
                    results[sn] = entry

    async def _execute_fetch_all(self):
        """The actual fetching logic moved to a private method for the retry loop."""

        token_status = await self._refresh_token()

        if token_status == "auth_failed":
            return "auth_failed"
        if not token_status:
            return None

        results = {}
        now = datetime.now(UTC).isoformat()

        # 1. Get Plants
        plants = await self._fetch_plants()
        if plants is None:
            return None

        # 2 & 3. Process Plants for Devices, Alarms, and Metrics
        await self._process_plants_data(plants, now, results)

        return results
