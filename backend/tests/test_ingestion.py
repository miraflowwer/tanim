"""Pure ingestion contract tests; no database or filesystem is required."""
from __future__ import annotations

from datetime import date

import pytest

from backend.app.ingestion import (
    checksum_rows,
    lifecycle_status,
    platform_can_promote,
    safe_retry_allowed,
    validate_rows,
)

BASE_ROW = {
    "crop_code": "tomato",
    "unit": "MT",
    "geography": "Calamba",
    "period_start": "2026-01-01",
    "period_end": "2026-01-31",
    "value": 12.5,
}


def test_valid_rows_are_normalized_and_hashed():
    result = validate_rows(
        [{**BASE_ROW, "crop_code": "kamatis"}],
        crop_codes={"tomato"},
        aliases={"kamatis": "tomato"},
        now=date(2026, 2, 1),
        max_age_days=60,
    )
    assert result.valid is True
    assert result.normalized_rows[0]["crop_code"] == "tomato"
    assert result.checksum == checksum_rows(result.normalized_rows)
    assert lifecycle_status(result) == "validated"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("crop_code", "unknown", "crop_unknown"),
        ("unit", "LITRE", "unit_invalid"),
        ("value", -1, "negative_value"),
        ("period_start", "2026-03-01", "date_future"),
        ("period_end", "2025-01-01", "date_range_invalid"),
    ],
)
def test_invalid_rows_are_rejected_without_normalized_output(field, value, code):
    row = {**BASE_ROW, field: value}
    result = validate_rows(
        [row],
        crop_codes={"tomato"},
        now=date(2026, 2, 1),
        max_age_days=60,
    )
    assert result.valid is False
    assert result.normalized_rows == []
    assert result.summary[code] == 1


def test_stale_blank_duplicate_and_non_finite_values_are_rejected():
    stale = {**BASE_ROW, "period_start": "2023-01-01", "period_end": "2023-01-31"}
    blank = {**BASE_ROW, "geography": ""}
    duplicate = [BASE_ROW, {**BASE_ROW}]
    non_finite = {**BASE_ROW, "value": float("nan")}

    assert validate_rows([stale], crop_codes={"tomato"}, now=date(2026, 2, 1), max_age_days=60).summary["data_stale"] == 1
    assert validate_rows([blank], crop_codes={"tomato"}, now=date(2026, 2, 1), max_age_days=60).summary["critical_blank"] == 1
    assert validate_rows(duplicate, crop_codes={"tomato"}, now=date(2026, 2, 1), max_age_days=60).summary["duplicate_row"] == 1
    assert validate_rows([non_finite], crop_codes={"tomato"}, now=date(2026, 2, 1), max_age_days=60).summary["value_not_finite"] == 1


def test_retry_and_promotion_authority_are_explicit():
    assert safe_retry_allowed("failed") is True
    assert safe_retry_allowed("validation_failed") is True
    assert safe_retry_allowed("promoted") is False
    assert platform_can_promote(True) is True
    assert platform_can_promote(False) is False