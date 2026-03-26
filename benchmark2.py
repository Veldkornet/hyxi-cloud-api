import timeit
import random

setup = """
_SENSITIVE_KEYS = {"sn", "deviceSn", "plantId", "email", "phone", "password", "token", "access_token"}

def _mask_id(value: str) -> str:
    if not value: return "****"
    id_str = str(value)
    if len(id_str) < 8: return "****"
    middle_len = len(id_str) - 6
    return id_str[:3] + ("X" * middle_len) + id_str[-3:]

def original_sanitize_dict(raw: dict) -> dict:
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

def new_sanitize_dict(raw: dict) -> dict:
    result = {}
    for k, v in raw.items():
        if k == "plantAddress":
            result[k] = "[REDACTED]"
        elif k in _SENSITIVE_KEYS and v:
            result[k] = _mask_id(str(v))
        else:
            result[k] = v
    return result

test_data = {
    "sn": "12345678",
    "deviceSn": "87654321",
    "plantAddress": "123 Main St",
    "some_other_key": "value",
    "alarmstate": True,
    "alarmState": False,
    "another_key": "another_value",
    "bunch_of": "other",
    "keys_that": "are",
    "not_sensitive": "at",
    "all": "and",
    "they_should": "be",
    "fast": "to",
    "process": "because",
    "no_lower": "is_called"
}
"""

stmt_orig = "original_sanitize_dict(test_data)"
stmt_new = "new_sanitize_dict(test_data)"

if __name__ == "__main__":
    t_orig = timeit.timeit(stmt_orig, setup=setup, number=100000)
    t_new = timeit.timeit(stmt_new, setup=setup, number=100000)
    print(f"Original: {t_orig:.5f}s")
    print(f"New: {t_new:.5f}s")
    print(f"Improvement: {(t_orig - t_new) / t_orig * 100:.2f}%")
