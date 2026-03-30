import timeit
import random
import string

_COLLECTOR_FILTER_KEYWORDS = (
    "bat",
    "pv",
    "grid",
    "load",
    "ph1",
    "ph2",
    "ph3",
)

def _filter_collector_metrics_original(m_raw: dict) -> dict:
    """Remove battery/power metrics that shouldn't be present on Collectors."""
    filtered = {}
    for k, v in m_raw.items():
        k_lower = k.lower()
        for x in _COLLECTOR_FILTER_KEYWORDS:
            if x in k_lower:
                break
        else:
            filtered[k] = v
    return filtered

def _filter_collector_metrics_unrolled_const_local(m_raw: dict) -> dict:
    filtered = {}
    k1, k2, k3, k4, k5, k6, k7 = _COLLECTOR_FILTER_KEYWORDS
    for k, v in m_raw.items():
        kl = k.lower()
        if (
            k1 in kl
            or k2 in kl
            or k3 in kl
            or k4 in kl
            or k5 in kl
            or k6 in kl
            or k7 in kl
        ):
            continue
        filtered[k] = v
    return filtered

# Generate some dummy data
keys = [
    "totalE", "pbat", "gridP", "ph1Loadp", "ph2Loadp", "ph3Loadp",
    "temp", "vpv1", "ipv1", "ppv1", "vbat", "ibat", "soc",
    "signalIntensity", "swVerSys", "maxChargePower", "batCap"
]
# Add some random keys to make it larger
for _ in range(100):
    keys.append(''.join(random.choices(string.ascii_lowercase, k=10)))

m_raw = {k: random.random() for k in keys}

def run_benchmark():
    n = 10000
    t_orig = timeit.timeit(lambda: _filter_collector_metrics_original(m_raw), number=n)
    t_unroll = timeit.timeit(lambda: _filter_collector_metrics_unrolled_const_local(m_raw), number=n)

    print(f"Original:  {t_orig:.4f}s")
    print(f"Unrolled Local:  {t_unroll:.4f}s")
    print(f"Improvement: {(t_orig - t_unroll) / t_orig * 100:.2f}%")

if __name__ == "__main__":
    assert _filter_collector_metrics_original(m_raw) == _filter_collector_metrics_unrolled_const_local(m_raw)
    run_benchmark()
