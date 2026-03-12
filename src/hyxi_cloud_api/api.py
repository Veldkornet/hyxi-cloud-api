"""HYXi Cloud API Client for retrieving inverter and battery data."""

import asyncio
from typing import Any
import base64
import hashlib
import hmac
import logging
import os
import time
from datetime import UTC
from datetime import datetime

import aiohttp

_LOGGER = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # Seconds to wait between retries (multiplied by attempt number)

# Precomputed hashes for HMAC signature
_GRANT_TYPE_HASH = "301c53ad00c6576097395329bb1c57a3dbf065b7dfa46b800e4c26e292c88028f59bae543d287cff8203cc878801beba153befb52fa67a86ef8d60362ece6aae"
_EMPTY_STR_HASH = "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e"


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
    }
)


def _sanitize_dict(obj: Any) -> Any:
    """Return a copy of the object with sensitive fields masked.

    Handles dictionaries and lists recursively. Used before logging raw API
    payloads so that SNs, plant IDs, and personal details (e.g. home address)
    are never written to the log in plain text.
    """
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k == "plantAddress":
                result[k] = "[REDACTED]"
            elif k in _SENSITIVE_KEYS and v:
                result[k] = _mask_id(str(v))
            else:
                result[k] = _sanitize_dict(v)
        return result
    if isinstance(obj, list):
        return [_sanitize_dict(item) for item in obj]
    return obj


class HyxiApiClient:
    """Client for interacting with the HYXi Cloud API."""

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

    def _generate_headers(self, path, method, is_token_request=False):
        """Generates headers matching HYXi's official Java SDK implementation."""
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

    async def _request(self, method: str, path: str, is_token_request=False, **kwargs):
        """Centralized helper for making API requests to HYXi Cloud."""
        url = f"{self.base_url}{path}"
        headers = self._generate_headers(
            path, method, is_token_request=is_token_request
        )
        timeout = kwargs.pop("timeout", 15)

        async with self.session.request(
            method, url, headers=headers, timeout=timeout, **kwargs
        ) as response:
            if is_token_request and response.status in [401, 403]:
                return None, response.status

            response.raise_for_status()
            res_json = await response.json()
            return res_json, response.status

    async def _refresh_token(self):
        """Async version of token refresh."""
        if self.token and time.time() < self.token_expires_at:
            return True

        path = "/api/authorization/v1/token"

        try:
            res, status = await self._request(
                "POST", path, is_token_request=True, json={"grantType": 1}
            )

            if status in [401, 403]:
                _LOGGER.error("HYXi API: Token request unauthorized (401/403)")
                return "auth_failed"

            if not res.get("success"):
                _LOGGER.error("HYXi API Token Rejected: %s", _sanitize_dict(res))
                if res.get("code") in [401, 403, "401", "403"]:
                    return "auth_failed"
                return False

            data = res.get("data", {})
            token_val = data.get("token") or data.get("access_token")

            if not token_val:
                _LOGGER.error("HYXi API: Token missing in response data")
                return False

            self.token = f"Bearer {token_val}"

            # 1. Grab the raw expiration value exactly as the API sent it
            raw_expires_in = data.get("expiresIn") or data.get("expires_in")
            _LOGGER.debug(
                "HYXi API returned raw token expiration: %s seconds",
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
                "HYXi Token proactive refresh scheduled in %s seconds (at %s)",
                int(expires_in) - buffer_secs,
                refresh_time_str,
            )
            return True
        except Exception as e:
            _LOGGER.error("HYXi Token Request Failed: %s", e)
        return False

    async def _fetch_device_metrics(self, sn, entry):
        """Helper to fetch detailed metrics for a single device."""
        q_path = "/api/device/v1/queryDeviceData"
        try:
            res_q, _ = await self._request(
                "GET", q_path, params={"deviceSn": sn}
            )

            if res_q.get("success"):
                data_list = res_q.get("data", [])
                m_raw = {
                    item.get("dataKey"): item.get("dataValue")
                    for item in data_list
                    if isinstance(item, dict) and item.get("dataKey")
                }
                _LOGGER.debug(
                    "HYXi Raw Metrics for %s (%s): %s",
                    _mask_id(sn),
                    entry.get("device_type_code"),
                    _sanitize_dict(m_raw),
                )
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
                    "HYXi API metrics rejected for %s: %s",
                    _mask_id(sn),
                    res_q.get("message"),
                )
        except Exception as e:
            _LOGGER.error("Error fetching metrics for %s: %s", _mask_id(sn), e)

    async def _fetch_device_info(self, sn, entry):
        """Helper to fetch static device info (firmware, capacity, limits)."""
        i_path = "/api/device/v1/queryDeviceInfo"
        try:
            res_i, _ = await self._request(
                "GET", i_path, params={"deviceSn": sn}
            )

            if res_i.get("success"):
                data_list = res_i.get("data", [])
                i_raw = {
                    item.get("dataKey"): item.get("dataValue")
                    for item in data_list
                    if isinstance(item, dict) and item.get("dataKey")
                }

                # 👇 This will dump the EXACT info the cloud sends back
                _LOGGER.debug(
                    "HYXi Raw INFO for %s: %s", _mask_id(sn), _sanitize_dict(i_raw)
                )

                # Smart Firmware Finder
                sw_ver = (
                    i_raw.get("swVerSys")
                    or i_raw.get("swVerMaster")
                    or i_raw.get("swVer")
                )
                if sw_ver:
                    entry["sw_version"] = sw_ver

                # Merge static info into metrics
                entry["metrics"].update(
                    {
                        "signalIntensity": i_raw.get("signalIntensity"),
                        "signalVal": i_raw.get("signalVal"),
                        "wifiVer": i_raw.get("wifiVer"),
                        "comMode": i_raw.get("comMode"),
                        "batCap": i_raw.get("batCap"),
                        "maxChargePower": i_raw.get("maxChargePower")
                        or i_raw.get("maxChargingDischargingPower"),
                        "maxDischargePower": i_raw.get("maxDischargePower")
                        or i_raw.get("maxChargingDischargingPower"),
                    }
                )
            else:
                _LOGGER.warning(
                    "HYXi INFO API Rejected for %s: %s",
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

        # Wait for them to finish
        if tasks:
            await asyncio.gather(*tasks)

        return sn, entry

    async def _fetch_devices_for_plant(self, plant_id, now, metric_tasks):
        """Helper to fetch devices for a single plant concurrently."""
        d_path = "/api/plant/v1/devicePage"
        try:
            res_d, _ = await self._request(
                "POST",
                d_path,
                json={"plantId": plant_id, "pageSize": 50, "currentPage": 1},
            )

            if not res_d.get("success"):
                _LOGGER.error(
                    "HYXi API Device Fetch Rejected for Plant %s: %s",
                    _mask_id(plant_id),
                    _sanitize_dict(res_d),
                )
                return

            data_val = res_d.get("data", {})
            if isinstance(data_val, list):
                devices = data_val
            elif isinstance(data_val, dict):
                devices = data_val.get("deviceList", [])
            else:
                devices = []

            # 👇 Log the devices discovered for this plant
            _LOGGER.debug(
                "HYXi Discovered Devices for Plant %s: %s",
                _mask_id(plant_id),
                [_mask_id(d.get("deviceSn", "UNKNOWN")) for d in devices],
            )

            for d in devices:
                sn = d.get("deviceSn")
                if not sn:
                    continue

                dev_type = d.get("deviceType") or "UNKNOWN"
                friendly_name = dev_type.replace("_", " ").title()

                entry = {
                    "sn": sn,
                    "device_name": d.get("deviceName") or f"{friendly_name} {sn}",
                    "model": friendly_name,
                    "device_type_code": dev_type,
                    "sw_version": d.get("swVer"),
                    "hw_version": d.get("hwVer"),
                    "metrics": {"last_seen": now},
                }

                metric_tasks.append(self._fetch_all_for_device(sn, entry, dev_type))
        except Exception as e:
            _LOGGER.error(
                "Error fetching devices for plant %s: %s", _mask_id(plant_id), e
            )

    async def _fetch_alarms_for_plant(self, plant_id):
        """Helper to fetch active alarms for a single plant."""
        a_path = "/api/alarm/v1/plantAlarmPage"
        try:
            res_a, _ = await self._request(
                "POST",
                a_path,
                json={"plantId": plant_id, "pageSize": 100, "currentPage": 1},
            )

            if not res_a.get("success"):
                _LOGGER.error(
                    "HYXi API Alarm Fetch Rejected for Plant %s: %s",
                    _mask_id(plant_id),
                    _sanitize_dict(res_a),
                )
                return []

            data_val = res_a.get("data", {})
            alarms = data_val.get("pageData", []) if isinstance(data_val, dict) else []

            # 👇 Dump the EXACT active alarms the cloud sends back
            _LOGGER.debug(
                "HYXi Raw ALARMS for Plant %s: %s",
                _mask_id(plant_id),
                _sanitize_dict(alarms),
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
                if data:
                    # ✅ Success
                    return {"data": data, "attempts": attempt}

                # If we get here, data was None (soft failure). Trigger a retry manually.
                raise aiohttp.ClientError("Fetch returned None, triggering retry.")

            except (aiohttp.ClientError, TimeoutError) as err:
                if attempt < MAX_RETRIES:
                    wait_time = attempt * RETRY_DELAY
                    _LOGGER.debug(
                        "HYXi Connection attempt %s/%s failed. Retrying in %ss... (Error: %s)",
                        attempt,
                        MAX_RETRIES,
                        wait_time,
                        err,
                    )
                    await asyncio.sleep(wait_time)
                else:
                    _LOGGER.error(
                        "HYXi Cloud connection failed after %s attempts: %s",
                        MAX_RETRIES,
                        err,
                    )
            except Exception as e:
                _LOGGER.error("HYXi Unexpected Code Crash: %s", e)
                _LOGGER.debug("Traceback:", exc_info=True)
                break

        return None

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
        p_path = "/api/plant/v1/page"
        res_p, _ = await self._request(
            "POST", p_path, json={"pageSize": 10, "currentPage": 1}
        )

        if not res_p.get("success"):
            # 🚀 If the server rejects the token, wipe it and force a retry!
            if res_p.get("code") in ["A000002", "A000005"]:
                _LOGGER.debug(
                    "HYXi Server rejected our token (A000002/A000005). "
                    "Forcing immediate token refresh..."
                )
                self.token = None
                self.token_expires_at = 0
                # Raising this error kicks it back up to the retry loop
                raise aiohttp.ClientError("Server rejected token")

            _LOGGER.error("HYXi API Plant Fetch Rejected: %s", _sanitize_dict(res_p))
            return None

        data_p = res_p.get("data", {})
        plants = data_p.get("list", []) if isinstance(data_p, dict) else []

        # 👇 Log the discovered plants
        _LOGGER.debug(
            "HYXi Discovered Plants: %s",
            [_mask_id(p.get("plantId", "UNKNOWN")) for p in plants],
        )

        metric_tasks = []
        device_fetch_tasks = []
        alarm_fetch_tasks = []

        for p in plants:
            plant_id = p.get("plantId")
            if not plant_id:
                continue

            device_fetch_tasks.append(
                self._fetch_devices_for_plant(plant_id, now, metric_tasks)
            )
            alarm_fetch_tasks.append(self._fetch_alarms_for_plant(plant_id))

        if device_fetch_tasks:
            await asyncio.gather(*device_fetch_tasks)

        plant_alarms = []
        if alarm_fetch_tasks:
            alarm_results = await asyncio.gather(*alarm_fetch_tasks)
            for alarms in alarm_results:
                plant_alarms.extend(alarms)

        # 3. Concurrent Metrics
        if metric_tasks:
            # Pre-group alarms by device serial number for O(1) lookup
            alarms_by_sn = {}
            for a in plant_alarms:
                a_sn = a.get("deviceSn")
                if a_sn:
                    alarms_by_sn.setdefault(a_sn, []).append(a)

            updated_entries = await asyncio.gather(*metric_tasks)
            for sn, entry in updated_entries:
                if sn:
                    # Map the relevant active alarms to this specific device
                    entry["alarms"] = alarms_by_sn.get(sn, [])
                    results[sn] = entry

        return results
