# ruff: noqa: E701, E702`n"""Pure ingestion validation and versioning rules.

The service is deliberately side-effect free until a validated normalized
payload is handed to a repository transaction. A failed run therefore cannot
replace the promoted version.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Iterable

ALLOWED_UNITS = frozenset({"MT", "MT/HA", "MT_PER_HA", "HA"})
NORMALIZATION_VERSION = "crop-aliases-v1"
STAGES = ("fetch", "validate", "normalize", "version", "stage", "promote", "monitor")
RETRYABLE_STATUSES = frozenset({"failed", "validation_failed"})
REQUIRED_FIELDS = ("crop_code", "unit", "geography", "period_start", "period_end")

@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    normalized_rows: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    summary: dict[str, int]
    checksum: str

def _date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}_invalid") from exc

def canonical_json(rows: Iterable[dict[str, Any]]) -> str:
    return json.dumps(list(rows), sort_keys=True, separators=(",", ":"), default=str)

def checksum_rows(rows: Iterable[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_json(rows).encode("utf-8")).hexdigest()

def _canonical_crop(value: Any, crop_codes: set[str], aliases: dict[str, str]) -> str:
    raw = str(value or "").strip().casefold()
    canonical = aliases.get(raw, raw)
    if canonical not in crop_codes:
        raise ValueError("crop_unknown")
    return canonical

def validate_rows(
    rows: Iterable[dict[str, Any]],
    *,
    crop_codes: Iterable[str],
    aliases: dict[str, str] | None = None,
    now: date | None = None,
    max_age_days: int | None = None,
) -> ValidationResult:
    crop_set = {str(code).strip().casefold() for code in crop_codes}
    alias_map = {str(key).strip().casefold(): str(value).strip().casefold() for key, value in (aliases or {}).items()}
    normalized: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: set[tuple[str, str, date, date, str]] = set()
    today = now or datetime.now(UTC).date()
    configured_age = max_age_days if max_age_days is not None else int(os.environ.get("TANIM_INGESTION_MAX_AGE_DAYS", "730"))
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            errors.append({"row": index, "code": "row_not_object"})
            continue
        missing = [field for field in REQUIRED_FIELDS if raw.get(field) in (None, "")]
        if missing:
            errors.append({"row": index, "code": "critical_blank", "fields": missing})
            continue
        try:
            crop = _canonical_crop(raw.get("crop_code"), crop_set, alias_map)
            unit = str(raw.get("unit")).strip().upper()
            if unit not in ALLOWED_UNITS:
                raise ValueError("unit_invalid")
            geography = " ".join(str(raw.get("geography")).strip().split())
            if not geography:
                raise ValueError("geography_invalid")
            period_start = _date(raw.get("period_start"), "period_start")
            period_end = _date(raw.get("period_end"), "period_end")
            if period_end < period_start:
                raise ValueError("date_range_invalid")
            if period_start > today + timedelta(days=1):
                raise ValueError("date_future")
            if (today - period_end).days > configured_age:
                raise ValueError("data_stale")
            value_key = next((key for key in ("value", "value_mt", "amount_mt", "yield_mt_per_ha") if raw.get(key) is not None), None)
            if value_key is None:
                raise ValueError("critical_blank")
            value = float(raw[value_key])
            if not math.isfinite(value):
                raise ValueError("value_not_finite")
            if value < 0:
                raise ValueError("negative_value")
            key = (crop, geography.casefold(), period_start, period_end, unit)
            if key in seen:
                raise ValueError("duplicate_row")
            seen.add(key)
            normalized.append({**raw, "crop_code": crop, "unit": unit, "geography": geography, "period_start": period_start.isoformat(), "period_end": period_end.isoformat(), value_key: value})
        except (TypeError, ValueError) as exc:
            errors.append({"row": index, "code": str(exc) or "row_invalid"})
    summary: dict[str, int] = {}
    for error in errors:
        summary[error["code"]] = summary.get(error["code"], 0) + 1
    return ValidationResult(not errors and bool(normalized), normalized, errors, summary, checksum_rows(normalized))

def safe_retry_allowed(status: str) -> bool:
    return str(status).strip().casefold() in RETRYABLE_STATUSES

def platform_can_promote(is_platform: bool) -> bool:
    return bool(is_platform)

def lifecycle_status(result: ValidationResult) -> str:
    return "validated" if result.valid else "validation_failed"