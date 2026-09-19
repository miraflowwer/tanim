"""Perf S31/S35: calculation endpoint p95 < 750 ms."""
import time

from app.grci import estimate_production, supply_load


def _p95(samples):
    s = sorted(samples)
    idx = max(0, min(len(s) - 1, int(0.95 * len(s))))
    return s[idx]


def test_calc_p95_under_750ms():
    durations = []
    for _ in range(200):
        t0 = time.perf_counter()
        s = estimate_production(3.1, 3.0)["s_mt"]
        supply_load(s, 25.0)
        durations.append((time.perf_counter() - t0) * 1000.0)
    assert _p95(durations) < 750.0
