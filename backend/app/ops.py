"""Structured, privacy-safe request telemetry and process metrics."""
from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Mapping
from typing import Any

COUNTERS: dict[str, int] = {}
_LATENCIES: list[float] = []
_LOCK = threading.Lock()
_LOG = logging.getLogger("tanim.request")
_SENSITIVE = ("authorization", "token", "password", "secret", "cookie", "reset", "coordinate", "latitude", "longitude", "raw_export")

def bump(name: str, value: int = 1) -> int:
    with _LOCK:
        COUNTERS[name] = COUNTERS.get(name, 0) + value
        return COUNTERS[name]

def reset_metrics() -> None:
    with _LOCK:
        COUNTERS.clear()
        _LATENCIES.clear()

def _safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): ("[REDACTED]" if any(word in str(key).casefold() for word in _SENSITIVE) else _safe(item)) for key, item in value.items() if str(key).casefold() not in {"body", "payload"}}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value[:20]]
    if isinstance(value, str) and len(value) > 256:
        return value[:256] + "?"
    return value

def safe_log(event: str, **fields: Any) -> dict[str, Any]:
    payload = {"event": event, **_safe(fields)}
    _LOG.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return payload

def record_request(*, request_id: str, method: str, route: str, status: int, duration_ms: float, user_id: str | None = None, organization_id: str | None = None) -> None:
    with _LOCK:
        _LATENCIES.append(float(duration_ms))
        if len(_LATENCIES) > 1000:
            del _LATENCIES[:100]
    bump("requests_total")
    bump(f"responses_{status // 100}xx")
    safe_log("request", request_id=request_id, method=method, route=route, status=status, duration_ms=round(duration_ms, 2), user_id=user_id, organization_id=organization_id)

def metrics_snapshot() -> dict[str, Any]:
    with _LOCK:
        values = sorted(_LATENCIES)
        p95 = values[min(len(values) - 1, int(len(values) * 0.95))] if values else 0
        return {"counters": dict(COUNTERS), "request_latency_ms_p95": round(p95, 2), "samples": len(values)}

def metrics_text() -> str:
    snapshot = metrics_snapshot()
    lines = [f"tanim_request_latency_ms_p95 {snapshot['request_latency_ms_p95']}"]
    for name, value in sorted(snapshot["counters"].items()):
        lines.append(f"tanim_{name} {value}")
    return "\n".join(lines) + "\n"

def monotonic_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000