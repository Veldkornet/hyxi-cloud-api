import timeit
import sys
from unittest.mock import MagicMock
sys.modules['aiohttp'] = MagicMock()

from hyxi_cloud_api.api import _sanitize_dict, _SENSITIVE_KEYS, _mask_id

data = {f"key{i}": f"value{i}" for i in range(100)}
data["plantAddress"] = "123 Main St"
data["deviceSn"] = "SN12345678"
data["alarmState"] = 1
data["alarmstate"] = 1
data["AlarmState"] = 1

def _sanitize_dict_old(raw: dict) -> dict:
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

def run_bench_old():
    _sanitize_dict_old(data)

def run_bench_new():
    _sanitize_dict(data)

if __name__ == "__main__":
    t_old = timeit.timeit("run_bench_old()", setup="from __main__ import run_bench_old", number=10000)
    print(f"Baseline Time: {t_old:.5f}s")

    t_new = timeit.timeit("run_bench_new()", setup="from __main__ import run_bench_new", number=10000)
    print(f"Improved Time: {t_new:.5f}s")
    print(f"Improvement: {(t_old - t_new) / t_old * 100:.2f}%")
