"""Observability (PRD §33): request ids, calculation ids, 10-field calc log, counters.

No PII is ever stored here — only opaque ids (plan/calc/request) and versions.
"""
import secrets
import time
import uuid
from datetime import UTC, datetime

CALC_LOGS: list = []
COUNTERS: dict = {}


def bump(counter: str, by: int = 1) -> int:
    COUNTERS[counter] = COUNTERS.get(counter, 0) + by
    return COUNTERS[counter]


def reset_observability() -> None:
    CALC_LOGS.clear()
    COUNTERS.clear()


def new_request_id() -> str:
    return str(uuid.uuid4())


def new_calculation_id() -> str:
    """UUIDv7 (time-ordered). Manual construction: works on Python < 3.14 too."""
    ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (ms << 80) | (0x7 << 76) | (rand_a << 64) | (0x2 << 62) | rand_b
    hexed = f"{value:032x}"
    return f"{hexed[:8]}-{hexed[8:12]}-{hexed[12:16]}-{hexed[16:20]}-{hexed[20:]}"


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def log_calculation(*, calculation_id: str, request_id: str, engine_version: str,
                    policy_version: int | str, dataset_version: str | None,
                    reference_version: int | str | None, organization_id: str,
                    status: str, duration_ms: int) -> dict:
    """Append the §33 10-field record. Raises if a PII-shaped value sneaks in."""
    entry = {
        "calculation_id": calculation_id,
        "request_id": request_id,
        "engine_version": engine_version,
        "policy_version": policy_version,
        "dataset_version": dataset_version,
        "reference_version": reference_version,
        "organization_id": organization_id,
        "status": status,
        "duration_ms": duration_ms,
        "timestamp": utcnow_iso(),
    }
    blob = str(entry).lower()
    for banned in ("gps", "latitude", "@example", "barangay", "income", "family"):
        if banned in blob:
            raise ValueError(f"observability entry must not carry PII ({banned})")
    CALC_LOGS.append(entry)
    return entry
