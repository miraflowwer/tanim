#!/usr/bin/env python3
"""Deterministic Glut Risk Coordination Indicator (GRCI).

The module follows docs/GRCI_SPEC.md. It does not use machine learning.
Risk thresholds are supplied by the caller.
"""

import csv
import math
import pathlib
import re as _re
from datetime import UTC
from datetime import date as _date
from datetime import datetime as _datetime


ENGINE_VERSION = "0.1.0"


YIELD_SUMMARY_DEFAULT = (
    pathlib.Path(__file__).resolve().parents[1]
    / "datasets"
    / "generated"
    / "yield_summary.csv"
)

YIELD_SUMMARY_FIELDS = [
    "crop_id",
    "display_name",
    "region_id",
    "region_label",
    "ref_period",
    "n_years",
    "avg_yield_mt_per_ha",
    "min_yield_mt_per_ha",
    "max_yield_mt_per_ha",
    "unit",
    "source_id",
    "data_status",
]

YIELD_REGION_IDS = {"NCR", "CAR", "I", "II", "III", "IV-A", "MIMAROPA", "V"}

REFERENCE_TYPES = {
    "local_committed_demand": {
        "label": "Local committed demand",
        "evidence_note": (
            "Confirmed local buyer, cooperative, or LGU demand for the crop "
            "and planning period."
        ),
        "quality": "direct",
        "scope": "local",
        "comparison_mode": "risk",
        "market_demand_wording_allowed": True,
    },
    "local_historical_absorption": {
        "label": "Local historical absorption (not committed demand)",
        "evidence_note": (
            "Past local sold or accepted volume. It is a historical absorption "
            "proxy, not a current or committed demand value."
        ),
        "quality": "historical_proxy",
        "scope": "local",
        "comparison_mode": "risk_proxy",
        "market_demand_wording_allowed": False,
    },
    "national_utilization_context": {
        "label": "National utilization context (not Luzon demand)",
        "evidence_note": (
            "National utilization data provide context only. They are not a "
            "Luzon or local demand reference and do not produce a GRCI risk band."
        ),
        "quality": "national_context",
        "scope": "national",
        "comparison_mode": "context_only",
        "market_demand_wording_allowed": False,
    },
    "historical_production_baseline": {
        "label": "Historical production baseline (not market demand)",
        "evidence_note": (
            "Historical production can show how a plan compares with past "
            "supply. It is not market demand."
        ),
        "quality": "production_baseline",
        "scope": "declared_geography",
        "comparison_mode": "baseline",
        "market_demand_wording_allowed": False,
    },
    "demo_coordination_baseline": {
        "label": "Demo coordination baseline (not market demand)",
        "evidence_note": (
            "Synthetic DEMO-2026 baseline used only for a reproducible demo. "
            "It is not observed local market demand."
        ),
        "quality": "synthetic",
        "scope": "demo",
        "comparison_mode": "demo",
        "market_demand_wording_allowed": False,
    },
}

# Verification states (quality/review state, separate from reference type).
VERIFICATION_STATES = (
    "reviewed_verified",
    "user_provided_unverified",
    "official_context",
    "synthetic_demo",
    "stale",
    "superseded",
)

# Only reviewed local evidence may enter L; everything else is context-only.
ELIGIBLE_TYPES = frozenset(
    {"local_committed_demand", "local_historical_absorption"}
)


def is_eligible(reference_type, verification_status):
    """Eligibility: only reviewed_verified local demand/absorption enters L."""
    return (
        reference_type in ELIGIBLE_TYPES
        and verification_status == "reviewed_verified"
    )


def estimate_production(area_ha, yield_mt_per_ha, area_margin_ha=0.0):
    """Return S, S_low, S_high, A_low, A_high (S = A x Y, clamp at zero)."""
    area = _finite_number(area_ha, "farm size estimate")
    margin = _finite_number(area_margin_ha, "farm size margin")
    if not area > 0:
        raise ValueError("area_ha must be > 0")
    if not margin >= 0:
        raise ValueError("area_margin_ha must be >= 0")
    reference_yield = _finite_number(yield_mt_per_ha, "reference yield")
    if not reference_yield > 0:
        raise ValueError("yield_mt_per_ha must be > 0")
    area_low, area_high = area_range(area, margin)
    supply_low, supply_high = planned_supply_range(
        area_low, area_high, reference_yield
    )
    return {
        "s_mt": area * reference_yield,
        "s_low_mt": supply_low,
        "s_high_mt": supply_high,
        "a_low_ha": area_low,
        "a_high_ha": area_high,
    }


def supply_load(supply_mt, reference_mt):
    """Return L = S / R. Raises ValueError if reference missing/non-positive."""
    supply = _finite_number(supply_mt, "supply amount")
    if supply < 0:
        raise ValueError("supply_mt must be >= 0")
    if reference_mt is None:
        raise ValueError(
            "reference_mt must be > 0; missing evidence is not substitutable"
        )
    reference = _finite_number(reference_mt, "reference amount")
    if not reference > 0:
        raise ValueError(
            "reference_mt must be > 0; missing evidence is not substitutable"
        )
    return supply / reference


def normalize_reference_type(value):
    """Return a trimmed reference type, or None when it is missing."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def reference_metadata(reference_type):
    """Return a copy of the reference metadata, or None when unknown."""
    canonical = normalize_reference_type(reference_type)
    record = REFERENCE_TYPES.get(canonical) if canonical else None
    return dict(record) if record else None


def describe_reference(reference_type):
    """Return the user label and evidence note for a reference type."""
    record = reference_metadata(reference_type)
    if record is None:
        return (None, None)
    return (record["label"], record["evidence_note"])


def allows_market_demand_wording(reference_type):
    """Return True only when the reference may be called market demand."""
    record = reference_metadata(reference_type)
    return bool(record and record["market_demand_wording_allowed"])


def valid_reference_types():
    """Return all accepted reference type strings."""
    return sorted(REFERENCE_TYPES)


def normalize_source_labels(source_labels):
    """Return clean, de-duplicated source labels while keeping order."""
    if source_labels is None:
        return []
    if isinstance(source_labels, str):
        values = [source_labels]
    else:
        try:
            values = list(source_labels)
        except TypeError:
            values = [source_labels]

    result = []
    seen = set()
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _finite_number(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a number") from error
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _same_text(first, second):
    return str(first).strip().casefold() == str(second).strip().casefold()


def _plan_value(plan, keys):
    for key in keys:
        if key in plan and str(plan[key]).strip():
            return plan[key]
    return None


def validate_plan_context(plans, crop, location, harvest_period):
    """Reject plan rows that explicitly belong to another context."""
    for plan in plans:
        if not isinstance(plan, dict):
            return (False, "Every farm plan must be a record.")

        plan_crop = _plan_value(plan, ("crop_canonical", "crop"))
        if plan_crop is not None and not _same_text(plan_crop, crop):
            return (False, "A farm plan belongs to a different crop.")

        plan_location = _plan_value(plan, ("municipality", "location"))
        if plan_location is not None and not _same_text(plan_location, location):
            return (False, "A farm plan belongs to a different location.")

        plan_period = _plan_value(plan, ("harvest_period",))
        if plan_period is not None and not _same_text(plan_period, harvest_period):
            return (False, "A farm plan belongs to a different harvest period.")

    return (True, None)


def area_range(estimate_ha, margin_ha):
    """Return the lower and upper farm-area estimate in hectares."""
    estimate = _finite_number(estimate_ha, "farm size estimate")
    margin = _finite_number(margin_ha, "farm size margin")
    if estimate < 0 or margin < 0:
        raise ValueError("farm size estimate and margin must be non-negative")
    return (max(0.0, estimate - margin), estimate + margin)


def collective_area_range(plans):
    """Add plan ranges to get one collective planned-area range."""
    low_total = 0.0
    high_total = 0.0
    for plan in plans:
        low, high = area_range(
            plan["farm_size_ha"],
            plan["farm_size_margin_ha"],
        )
        low_total += low
        high_total += high
    return (low_total, high_total)


def planned_supply_range(area_low, area_high, yield_mt_per_ha):
    """Convert an area range into an expected supply range in MT."""
    low = _finite_number(area_low, "area lower value")
    high = _finite_number(area_high, "area upper value")
    if low < 0 or high < 0:
        raise ValueError("area values must be non-negative")
    if high < low:
        raise ValueError("area upper value must not be below the lower value")

    if yield_mt_per_ha is None:
        return None
    try:
        yield_value = _finite_number(yield_mt_per_ha, "reference yield")
    except ValueError:
        return None
    if yield_value <= 0:
        return None
    return (low * yield_value, high * yield_value)


def supply_load_range(supply_low, supply_high, reference_amount):
    """Compare planned supply with a positive reference amount."""
    low = _finite_number(supply_low, "supply lower value")
    high = _finite_number(supply_high, "supply upper value")
    if low < 0 or high < 0:
        raise ValueError("supply values must be non-negative")
    if high < low:
        raise ValueError("supply upper value must not be below the lower value")

    if reference_amount is None:
        return None
    try:
        reference = _finite_number(reference_amount, "reference amount")
    except ValueError:
        return None
    if reference <= 0:
        return None
    return (low / reference, high / reference)


def validate_bands(bands):
    """Validate caller-provided risk bands."""
    if not bands:
        raise ValueError("bands must be a non-empty list of (upper, label)")

    validated = []
    previous = float("-inf")
    labels = set()

    for item in bands:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("each risk band must contain an upper limit and label")

        upper_raw, label_raw = item
        if isinstance(upper_raw, bool):
            raise ValueError("risk band upper limits must be numbers")
        try:
            upper = float(upper_raw)
        except (TypeError, ValueError) as error:
            raise ValueError("risk band upper limits must be numbers") from error

        if math.isnan(upper):
            raise ValueError("risk band upper limits cannot be NaN")
        if upper <= previous:
            raise ValueError("risk band upper limits must increase")

        label = str(label_raw).strip()
        if not label:
            raise ValueError("risk band labels cannot be empty")
        if label in labels:
            raise ValueError("risk band labels must be unique")

        validated.append((upper, label))
        previous = upper
        labels.add(label)

    if not math.isinf(validated[-1][0]) or validated[-1][0] < 0:
        raise ValueError("the final risk band must end at positive infinity")

    return validated


def _classify_validated(value, bands):
    number = _finite_number(value, "supply load")
    if number < 0:
        raise ValueError("supply load cannot be negative")
    for upper, label in bands:
        if number <= upper:
            return label
    raise ValueError("risk bands do not cover the supply load")


def classify_load(value, bands):
    """Classify one supply-load value with validated caller bands."""
    return _classify_validated(value, validate_bands(bands))


def classify_range(low, high, bands):
    """Classify a load range and report whether it crosses a band."""
    low_number = _finite_number(low, "supply-load lower value")
    high_number = _finite_number(high, "supply-load upper value")
    if low_number < 0 or high_number < 0:
        raise ValueError("supply-load values must be non-negative")
    if high_number < low_number:
        raise ValueError(
            "supply-load upper value must not be below the lower value"
        )

    validated = validate_bands(bands)
    low_band = _classify_validated(low_number, validated)
    high_band = _classify_validated(high_number, validated)
    return (low_band, high_band, low_band != high_band)


def format_estimated_range(low, high, unit):
    """Format an estimated low-to-high range for the interface."""
    low_number = _finite_number(low, "range lower value")
    high_number = _finite_number(high, "range upper value")
    unit_text = str(unit).strip() if unit is not None else ""
    if low_number < 0 or high_number < 0:
        raise ValueError("range values must be non-negative")
    if high_number < low_number:
        raise ValueError("range upper value must not be below the lower value")
    if not unit_text:
        raise ValueError("range unit cannot be empty")
    return (
        f"Estimated range: {low_number:g} {unit_text} "
        f"to {high_number:g} {unit_text}"
    )


def load_yield_summary(path=None):
    """Load and validate the committed regional yield summary."""
    target = pathlib.Path(path) if path is not None else YIELD_SUMMARY_DEFAULT
    with target.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != YIELD_SUMMARY_FIELDS:
            raise ValueError(
                f"yield summary schema changed: {reader.fieldnames}"
            )

        index = {}
        for line_number, row in enumerate(reader, start=2):
            crop_id = row["crop_id"].strip()
            region_id = row["region_id"].strip()
            if not crop_id or not region_id:
                raise ValueError(
                    f"yield summary row {line_number} has a missing key"
                )

            if not row["display_name"].strip():
                raise ValueError(
                    f"yield summary row {line_number} has no display name"
                )
            if region_id not in YIELD_REGION_IDS:
                raise ValueError(
                    f"yield summary row {line_number} has an invalid region id"
                )
            if not row["region_label"].strip():
                raise ValueError(
                    f"yield summary row {line_number} has no region label"
                )

            key = (crop_id, region_id)
            if key in index:
                raise ValueError(
                    f"yield summary has duplicate key {crop_id}/{region_id}"
                )

            try:
                n_years = int(row["n_years"])
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"yield summary row {line_number} has a bad year count"
                ) from error

            avg = _finite_number(
                row["avg_yield_mt_per_ha"],
                f"yield summary row {line_number} average",
            )
            low = _finite_number(
                row["min_yield_mt_per_ha"],
                f"yield summary row {line_number} minimum",
            )
            high = _finite_number(
                row["max_yield_mt_per_ha"],
                f"yield summary row {line_number} maximum",
            )

            if n_years != 5:
                raise ValueError(
                    f"yield summary row {line_number} must use all five years"
                )
            if avg <= 0 or low < 0 or high < 0 or not low <= avg <= high:
                raise ValueError(
                    f"yield summary row {line_number} has invalid yield values"
                )
            if row["unit"].strip() != "mt_per_ha":
                raise ValueError(
                    f"yield summary row {line_number} has an invalid unit"
                )
            if row["ref_period"].strip() != "2021-2025":
                raise ValueError(
                    f"yield summary row {line_number} has an invalid reference period"
                )
            if row["source_id"].strip() != "PSA-OPENSTAT-CROPS":
                raise ValueError(
                    f"yield summary row {line_number} has an invalid source id"
                )
            if row["data_status"].strip() != "observed":
                raise ValueError(
                    f"yield summary row {line_number} has an invalid data status"
                )

            index[key] = {
                "crop_id": crop_id,
                "display_name": row["display_name"].strip(),
                "region_id": region_id,
                "region_label": row["region_label"].strip(),
                "ref_period": row["ref_period"].strip(),
                "n_years": n_years,
                "avg_yield_mt_per_ha": avg,
                "min_yield_mt_per_ha": low,
                "max_yield_mt_per_ha": high,
                "unit": row["unit"].strip(),
                "source_id": row["source_id"].strip(),
                "data_status": row["data_status"].strip(),
            }

    if not index:
        raise ValueError("yield summary is empty")
    return index


def reference_yield_for(index, crop_id, region_id):
    """Return one crop-region yield record, or None when it is absent."""
    if not isinstance(index, dict):
        raise ValueError("yield summary index must be a dict")
    crop_key = str(crop_id).strip() if crop_id is not None else ""
    region_key = str(region_id).strip() if region_id is not None else ""
    if not crop_key or not region_key:
        return None
    return index.get((crop_key, region_key))


def is_planning_supported(crop_record):
    """Check whether a crop record is safe for planning calculations."""
    if not isinstance(crop_record, dict):
        return False

    coverage = crop_record.get("coverage")
    if isinstance(coverage, dict):
        required = (
            coverage.get("production") is True
            and coverage.get("area") is True
        )
        if "planning_supported" in crop_record:
            return required and crop_record.get("planning_supported") is True
        return required

    return crop_record.get("planning_supported") is True


def _result_base(crop, location, harvest_period):
    return {
        "crop": crop,
        "location": location,
        "harvest_period": harvest_period,
        "planned_area_range": None,
        "reference_yield": None,
        "yield_source": None,
        "planned_supply_range": None,
        "expected_production_range": None,
        "reference_amount": None,
        "reference_unit": None,
        "reference_type": None,
        "reference_geography": None,
        "reference_period": None,
        "reference_label": None,
        "reference_evidence_note": None,
        "reference_quality": None,
        "reference_scope": None,
        "reference_mode": None,
        "market_demand_wording_allowed": False,
        "supply_load_range": None,
        "status": "unclassified",
        "comparison_state": None,
        "comparison_band_range": None,
        "risk_state": None,
        "risk_band_range": None,
        "borderline": False,
        "uncertainty_state": None,
        "uncertainty_note": None,
        "explanation": None,
        "provenance": None,
        "source_labels": [],
    }


def _describe_amount(low, high, unit):
    if low == high:
        return f"{low:g} {unit}"
    return f"{low:g} to {high:g} {unit}"


def _explain_no_result(note):
    return f"No result can be shown. {note}"


def _validate_yield_record(yield_record, crop, yield_value):
    if yield_record is None:
        return None
    if not isinstance(yield_record, dict):
        return "Yield provenance must be a record."

    record_crop = str(yield_record.get("crop_id", "")).strip()
    if not record_crop or not _same_text(record_crop, crop):
        return "Yield provenance belongs to a different crop."

    record_region = str(yield_record.get("region_id", "")).strip()
    if record_region not in YIELD_REGION_IDS:
        return "Yield provenance has an invalid region id."

    if str(yield_record.get("unit", "")).strip() != "mt_per_ha":
        return "Yield provenance must use mt_per_ha."

    try:
        record_yield = _finite_number(
            yield_record.get("avg_yield_mt_per_ha"),
            "yield provenance average",
        )
    except ValueError:
        return "Yield provenance has an invalid average yield."

    if not math.isclose(record_yield, yield_value, rel_tol=0.0, abs_tol=1e-9):
        return "Reference yield does not match the supplied yield provenance."

    if str(yield_record.get("source_id", "")).strip() != "PSA-OPENSTAT-CROPS":
        return "Yield provenance has an invalid source id."
    if str(yield_record.get("ref_period", "")).strip() != "2021-2025":
        return "Yield provenance has an invalid reference period."
    try:
        n_years = int(yield_record.get("n_years"))
    except (TypeError, ValueError):
        return "Yield provenance has an invalid year count."
    if n_years != 5:
        return "Yield provenance must use all five reference years."
    if str(yield_record.get("data_status", "")).strip() != "observed":
        return "Yield provenance must come from observed source data."
    return None


def compute_grci(
    *,
    crop,
    location,
    harvest_period,
    plans,
    reference_yield,
    yield_source,
    reference_amount,
    reference_unit,
    reference_type,
    reference_geography,
    reference_period,
    crop_record,
    bands=None,
    source_labels=None,
    yield_record=None,
):
    """Compute one reproducible GRCI result."""
    result = _result_base(crop, location, harvest_period)

    canonical_reference = normalize_reference_type(reference_type)
    clean_sources = normalize_source_labels(source_labels)
    clean_yield_source = (
        str(yield_source).strip() if yield_source is not None else None
    )
    if clean_yield_source == "":
        clean_yield_source = None

    result["reference_yield"] = reference_yield
    result["yield_source"] = clean_yield_source
    result["reference_amount"] = reference_amount
    result["reference_unit"] = (
        str(reference_unit).strip().upper()
        if reference_unit is not None
        else None
    )
    result["reference_type"] = canonical_reference
    result["reference_geography"] = (
        str(reference_geography).strip()
        if reference_geography is not None
        else None
    )
    result["reference_period"] = (
        str(reference_period).strip()
        if reference_period is not None
        else None
    )
    result["source_labels"] = clean_sources
    result["provenance"] = {
        "yield_source": clean_yield_source,
        "yield_crop_id": (
            yield_record.get("crop_id")
            if isinstance(yield_record, dict)
            else None
        ),
        "yield_region_id": (
            yield_record.get("region_id")
            if isinstance(yield_record, dict)
            else None
        ),
        "yield_ref_period": (
            yield_record.get("ref_period")
            if isinstance(yield_record, dict)
            else None
        ),
        "yield_n_years": (
            yield_record.get("n_years")
            if isinstance(yield_record, dict)
            else None
        ),
        "yield_unit": (
            yield_record.get("unit")
            if isinstance(yield_record, dict)
            else None
        ),
        "yield_source_id": (
            yield_record.get("source_id")
            if isinstance(yield_record, dict)
            else None
        ),
        "reference_type": canonical_reference,
        "reference_amount": reference_amount,
        "reference_unit": result["reference_unit"],
        "reference_geography": result["reference_geography"],
        "reference_period": result["reference_period"],
        "source_labels": clean_sources,
    }

    if crop is None or not str(crop).strip():
        result["status"] = "incomplete"
        result["uncertainty_note"] = "Missing crop."
        result["explanation"] = _explain_no_result("Missing crop.")
        return result

    if not is_planning_supported(crop_record):
        result["status"] = "unsupported"
        result["uncertainty_note"] = (
            "Crop does not have a safe production and area join in the "
            "TANIM crop registry."
        )
        result["explanation"] = _explain_no_result(
            "The crop has no safe production and area join."
        )
        return result

    if location is None or not str(location).strip():
        result["status"] = "incomplete"
        result["uncertainty_note"] = "Missing location."
        result["explanation"] = _explain_no_result("Missing location.")
        return result

    if harvest_period is None or not str(harvest_period).strip():
        result["status"] = "incomplete"
        result["uncertainty_note"] = "Missing harvest period."
        result["explanation"] = _explain_no_result("Missing harvest period.")
        return result

    if not plans:
        result["status"] = "incomplete"
        result["uncertainty_note"] = "No farm plans provided."
        result["explanation"] = _explain_no_result("No farm plans were given.")
        return result

    context_ok, context_error = validate_plan_context(
        plans,
        crop,
        location,
        harvest_period,
    )
    if not context_ok:
        result["status"] = "invalid"
        result["uncertainty_note"] = context_error
        result["explanation"] = _explain_no_result(context_error)
        return result

    if canonical_reference is None:
        result["status"] = "incomplete"
        result["uncertainty_note"] = "Missing reference type."
        result["explanation"] = _explain_no_result("The reference type is missing.")
        return result

    metadata = reference_metadata(canonical_reference)
    if metadata is None:
        note = (
            "Unknown reference type. Expected one of: "
            + ", ".join(valid_reference_types())
            + "."
        )
        result["status"] = "invalid"
        result["uncertainty_note"] = note
        result["explanation"] = _explain_no_result(note)
        return result

    result["reference_label"] = metadata["label"]
    result["reference_evidence_note"] = metadata["evidence_note"]
    result["reference_quality"] = metadata["quality"]
    result["reference_scope"] = metadata["scope"]
    result["reference_mode"] = metadata["comparison_mode"]
    result["market_demand_wording_allowed"] = metadata[
        "market_demand_wording_allowed"
    ]
    result["provenance"]["reference_label"] = metadata["label"]
    result["provenance"]["reference_evidence_note"] = metadata["evidence_note"]
    result["provenance"]["reference_quality"] = metadata["quality"]
    result["provenance"]["reference_mode"] = metadata["comparison_mode"]

    if not clean_sources:
        note = "Missing comparison-reference source label."
        result["status"] = "incomplete"
        result["uncertainty_note"] = note
        result["explanation"] = _explain_no_result(note)
        return result

    if result["reference_unit"] != "MT":
        note = "Reference amount must use MT so it matches planned supply."
        result["status"] = "invalid"
        result["uncertainty_note"] = note
        result["explanation"] = _explain_no_result(note)
        return result

    if not result["reference_geography"]:
        result["status"] = "incomplete"
        result["uncertainty_note"] = "Missing reference geography."
        result["explanation"] = _explain_no_result(
            "The reference geography is missing."
        )
        return result

    if not result["reference_period"]:
        result["status"] = "incomplete"
        result["uncertainty_note"] = "Missing reference period."
        result["explanation"] = _explain_no_result(
            "The reference period is missing."
        )
        return result

    if metadata["scope"] == "national":
        if "philipp" not in result["reference_geography"].casefold():
            note = (
                "National utilization context must keep its national geography."
            )
            result["status"] = "invalid"
            result["uncertainty_note"] = note
            result["explanation"] = _explain_no_result(note)
            return result

    if metadata["scope"] == "local":
        if "philipp" in result["reference_geography"].casefold():
            note = "A local reference cannot use a national geography."
            result["status"] = "invalid"
            result["uncertainty_note"] = note
            result["explanation"] = _explain_no_result(note)
            return result

    try:
        area_low, area_high = collective_area_range(plans)
    except (ValueError, KeyError, TypeError):
        note = "Invalid farm size or farm-size margin."
        result["status"] = "invalid"
        result["uncertainty_note"] = note
        result["explanation"] = _explain_no_result(
            "A farm size or margin value is not usable."
        )
        return result

    result["planned_area_range"] = [area_low, area_high]
    result["uncertainty_state"] = (
        "point" if area_low == area_high else "range"
    )

    if reference_yield is None:
        note = "Missing reference yield. Planned supply cannot be calculated."
        result["status"] = "incomplete"
        result["uncertainty_note"] = note
        result["explanation"] = _explain_no_result(
            "The reference yield is missing, so expected production "
            "cannot be calculated."
        )
        return result

    try:
        yield_value = _finite_number(reference_yield, "reference yield")
    except ValueError:
        note = "Reference yield must be a valid number."
        result["status"] = "invalid"
        result["uncertainty_note"] = note
        result["explanation"] = _explain_no_result(note)
        return result

    if yield_value <= 0:
        note = "Reference yield must be greater than zero."
        result["status"] = "invalid"
        result["uncertainty_note"] = note
        result["explanation"] = _explain_no_result(note)
        return result

    if clean_yield_source is None:
        note = "Missing reference-yield source."
        result["status"] = "incomplete"
        result["uncertainty_note"] = note
        result["explanation"] = _explain_no_result(
            "The reference-yield source is missing."
        )
        return result

    yield_record_error = _validate_yield_record(
        yield_record,
        crop,
        yield_value,
    )
    if yield_record_error:
        result["status"] = "invalid"
        result["uncertainty_note"] = yield_record_error
        result["explanation"] = _explain_no_result(yield_record_error)
        return result

    supply = planned_supply_range(area_low, area_high, yield_value)
    result["planned_supply_range"] = list(supply)
    result["expected_production_range"] = list(supply)

    if reference_amount is None:
        note = "Missing reference amount. Supply load cannot be calculated."
        result["status"] = "incomplete"
        result["uncertainty_note"] = note
        result["explanation"] = (
            f"Planned area is {_describe_amount(area_low, area_high, 'ha')}. "
            f"At {yield_value:g} MT per ha, expected production is "
            f"{_describe_amount(supply[0], supply[1], 'MT')}. "
            "The comparison reference is missing, so no comparison is shown."
        )
        return result

    try:
        reference_value = _finite_number(reference_amount, "reference amount")
    except ValueError:
        note = "Reference amount must be a valid number."
        result["status"] = "invalid"
        result["uncertainty_note"] = note
        result["explanation"] = _explain_no_result(note)
        return result

    if reference_value <= 0:
        note = "Reference amount must be greater than zero."
        result["status"] = "invalid"
        result["uncertainty_note"] = note
        result["explanation"] = _explain_no_result(note)
        return result

    if metadata["comparison_mode"] == "context_only":
        result["status"] = "context_only"
        result["uncertainty_note"] = (
            "This reference is context only. TANIM does not compare local "
            "planned supply with a national utilization amount."
        )
        result["explanation"] = (
            f"Planned area is {_describe_amount(area_low, area_high, 'ha')}. "
            f"At {yield_value:g} MT per ha, expected production is "
            f"{_describe_amount(supply[0], supply[1], 'MT')}. "
            f"{metadata['label']} is shown only as context. "
            f"{metadata['evidence_note']}"
        )
        return result

    load = supply_load_range(supply[0], supply[1], reference_value)
    result["supply_load_range"] = list(load)

    if bands is None:
        result["status"] = "unclassified"
        result["uncertainty_note"] = (
            "Risk bands are not configured. Supply load is available but "
            "has no comparison label."
        )
        result["explanation"] = (
            f"Planned area is {_describe_amount(area_low, area_high, 'ha')}. "
            f"At {yield_value:g} MT per ha, expected production is "
            f"{_describe_amount(supply[0], supply[1], 'MT')}. "
            f"Compared with {metadata['label']} of {reference_value:g} MT, "
            f"supply load is {_describe_amount(load[0], load[1], 'ratio')}. "
            "Comparison bands are not set."
        )
        return result

    low_band, high_band, borderline = classify_range(load[0], load[1], bands)
    state = "borderline" if borderline else low_band
    result["comparison_state"] = state
    result["comparison_band_range"] = [low_band, high_band]
    result["borderline"] = borderline
    if borderline:
        result["uncertainty_state"] = "borderline"

    mode = metadata["comparison_mode"]
    if mode == "baseline":
        result["status"] = "baseline"
        if borderline:
            result["uncertainty_note"] = (
                f"Baseline comparison spans {low_band} to {high_band}. "
                "Farm-size uncertainty can change the comparison band."
            )
        elif area_low != area_high:
            result["uncertainty_note"] = (
                "Farm size is approximate, so the baseline comparison is a range."
            )
        result["explanation"] = (
            f"Planned area is {_describe_amount(area_low, area_high, 'ha')}. "
            f"At {yield_value:g} MT per ha, expected production is "
            f"{_describe_amount(supply[0], supply[1], 'MT')}. "
            f"Compared with {metadata['label']} of {reference_value:g} MT, "
            f"supply load is {_describe_amount(load[0], load[1], 'ratio')}. "
            f"Baseline comparison state is {state}. "
            f"{metadata['evidence_note']}"
        )
        return result

    result["status"] = "ok"
    result["risk_state"] = state
    result["risk_band_range"] = [low_band, high_band]

    if borderline:
        result["uncertainty_note"] = (
            f"Supply load spans {low_band} to {high_band}. The farm-size "
            "estimate can change the final band."
        )
    elif area_low != area_high:
        result["uncertainty_note"] = (
            "Farm size is approximate, so supply load is shown as a range."
        )

    state_wording = {
        "risk": "Risk state",
        "risk_proxy": "Proxy risk state",
        "demo": "Demo risk state",
    }.get(mode, "Comparison state")
    result["explanation"] = (
        f"Planned area is {_describe_amount(area_low, area_high, 'ha')}. "
        f"At {yield_value:g} MT per ha, expected production is "
        f"{_describe_amount(supply[0], supply[1], 'MT')}. "
        f"Compared with {metadata['label']} of {reference_value:g} MT, "
        f"supply load is {_describe_amount(load[0], load[1], 'ratio')}. "
        f"{state_wording} is {state}. "
        f"{metadata['evidence_note']}"
    )

    return result

# --- authoritative planning/evidence policy (production) ---
# These policy constants and helpers are intentionally kept in this framework
# independent module.  The FastAPI adapter re-exports them; it does not
# recalculate or redefine domain policy.

ACTIVE_PLAN_STATUSES = frozenset({"draft", "planned"})
INACTIVE_PLAN_STATUSES = frozenset({"harvested", "cancelled"})
PLAN_STATUSES = ACTIVE_PLAN_STATUSES | INACTIVE_PLAN_STATUSES

REVIEW_STATES = (
    "draft",
    "under_review",
    "verified",
    "rejected",
    "superseded",
    "expired",
)
REVIEW_TRANSITIONS = {
    "draft": frozenset({"under_review"}),
    "under_review": frozenset({"verified", "rejected"}),
    # A rejected candidate may be corrected and resubmitted.
    "rejected": frozenset({"draft", "under_review"}),
    "verified": frozenset({"superseded", "expired"}),
    "superseded": frozenset(),
    "expired": frozenset(),
}
TERMINAL_REVIEW_STATES = frozenset({"superseded", "expired"})
REFERENCE_REVIEW_STATES = REVIEW_STATES
REFERENCE_REVIEW_TRANSITIONS = REVIEW_TRANSITIONS
ELIGIBLE_VERIFICATION_STATES = frozenset({"reviewed_verified"})
REFERENCE_ELIGIBLE_TYPES = ELIGIBLE_TYPES


def is_active_plan_status(status):
    """Return whether a plan contributes to future coordination totals."""
    if status is None:
        return False
    return str(status).strip().casefold() in ACTIVE_PLAN_STATUSES


def is_active_plan(plan):
    """Return whether a plan record contributes to future coordination totals."""
    return isinstance(plan, dict) and is_active_plan_status(plan.get("status"))


def active_plans(plans):
    """Filter plan records using the one lifecycle rule used by all adapters."""
    if plans is None:
        return []
    values = plans.values() if isinstance(plans, dict) else plans
    return [plan for plan in values if is_active_plan(plan)]


def _record_value(record, *keys):
    if not isinstance(record, dict):
        return None
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return value
    return None


def _canonical_context_text(value):
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text.casefold() if text else None


def _as_calculation_date(value):
    if isinstance(value, _datetime):
        return value.date()
    if isinstance(value, _date):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return _date.fromisoformat(text[:10])
    except ValueError:
        return None


def period_key(value):
    """Canonical planning period.

    Plan harvest dates are interpreted as half-year planning periods, so
    2026-12-01 and 2026-H2 refer to the same declared 2026-H2 period.
    Other labels remain exact, case-insensitive tokens; no fuzzy period
    matching is performed.
    """
    parsed = _as_calculation_date(value)
    if parsed is not None:
        return f"{parsed.year:04d}-H{1 if parsed.month <= 6 else 2}"

    if value is None:
        return None
    text = " ".join(str(value).strip().upper().split())
    if not text:
        return None
    normalized = _re.sub(r"[._/\\s]+", "-", text)
    normalized = _re.sub(r"-+", "-", normalized)
    # Canonicalize compact half/quarter labels while preserving granularity.
    match = _re.fullmatch(r"(\d{4})-?([HQ][1-4])", normalized)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return normalized


def period_matches(reference_period, planning_period):
    """Return True only when reference and plan periods are exactly applicable."""
    left = period_key(reference_period)
    right = period_key(planning_period)
    return left is not None and right is not None and left == right


def reference_context_key(reference):
    """Return the versioning/matching scope for an evidence reference."""
    return (
        _canonical_context_text(
            _record_value(reference, "org_id", "organization_id")
        ),
        _canonical_context_text(_record_value(reference, "crop_code", "crop")),
        _canonical_context_text(
            _record_value(reference, "geography", "coordination_scope")
        ),
        period_key(_record_value(reference, "period", "planning_period")),
    )


def reference_applies(
    reference,
    *,
    organization_id,
    crop_code,
    geography,
    planning_period,
    calculation_date,
    require_verified=True,
):
    """Check every production evidence predicate for one calculation date.

    References must match organization, crop, geography, and period exactly.
    They must be reviewed verified, in the verified review state, and valid
    on the calculation date. Missing effective_from is intentionally rejected.
    """
    if not isinstance(reference, dict):
        return False

    ref_org, ref_crop, ref_geo, ref_period = reference_context_key(reference)
    if ref_org != _canonical_context_text(organization_id):
        return False
    if ref_crop != _canonical_context_text(crop_code):
        return False
    if ref_geo != _canonical_context_text(geography):
        return False
    if ref_period != period_key(planning_period):
        return False

    reference_type = normalize_reference_type(
        _record_value(reference, "reference_type")
    )
    verification = str(
        _record_value(reference, "verification_status") or ""
    ).strip()
    review_state = str(
        _record_value(reference, "review", "review_state") or ""
    ).strip().casefold()
    if require_verified and (
        not is_eligible(reference_type, verification)
        or review_state != "verified"
    ):
        return False

    calculation_day = _as_calculation_date(calculation_date)
    effective_from = _as_calculation_date(reference.get("effective_from"))
    effective_to = _as_calculation_date(reference.get("effective_to"))
    if calculation_day is None or effective_from is None:
        return False
    if effective_from > calculation_day:
        return False
    if effective_to is not None and calculation_day > effective_to:
        return False
    return True


def select_eligible_reference(
    references,
    *,
    organization_id,
    crop_code,
    geography,
    planning_period,
    calculation_date,
):
    """Select the newest eligible reference in one exact tenant/context scope."""
    values = references.values() if isinstance(references, dict) else (references or [])
    eligible = [
        reference
        for reference in values
        if reference_applies(
            reference,
            organization_id=organization_id,
            crop_code=crop_code,
            geography=geography,
            planning_period=planning_period,
            calculation_date=calculation_date,
        )
    ]
    eligible.sort(
        key=lambda item: (
            int(item.get("version", 0) or 0),
            str(item.get("effective_from") or ""),
            str(item.get("verified_at") or ""),
            str(item.get("id") or ""),
        ),
        reverse=True,
    )
    return eligible[0] if eligible else None


def next_reference_version(
    references,
    *,
    organization_id,
    crop_code,
    geography,
    planning_period,
):
    """Return the next version scoped to org/crop/geography/planning period."""
    values = references.values() if isinstance(references, dict) else (references or [])
    context = (
        _canonical_context_text(organization_id),
        _canonical_context_text(crop_code),
        _canonical_context_text(geography),
        period_key(planning_period),
    )
    versions = []
    for reference in values:
        if reference_context_key(reference) != context:
            continue
        try:
            versions.append(int(reference.get("version", 0)))
        except (TypeError, ValueError):
            continue
    return max(versions, default=0) + 1


def transition_reference(
    reference,
    to_state,
    *,
    actor_user_id=None,
    at=None,
    note=None,
):
    """Apply one valid immutable-history transition and return the same record.

    Review history entries are copied before append so prior entries cannot be
    changed by a later transition. Invalid transitions raise ValueError.
    """
    if not isinstance(reference, dict):
        raise ValueError("reference must be a record")
    target = str(to_state).strip().casefold()
    if target not in REVIEW_STATES:
        raise ValueError(f"unknown reference review state: {to_state}")
    current = str(reference.get("review") or "draft").strip().casefold()
    if target not in REVIEW_TRANSITIONS.get(current, frozenset()):
        raise ValueError(f"invalid reference transition: {current} -> {target}")

    timestamp = at
    if timestamp is None:
        timestamp = _datetime.now(UTC).isoformat()
    history = [
        dict(entry) if isinstance(entry, dict) else {"value": entry}
        for entry in (reference.get("review_history") or [])
    ]
    history.append(
        {
            "from": current,
            "to": target,
            "actor_user_id": actor_user_id,
            "at": timestamp,
            "note": note,
        }
    )
    reference["review_history"] = history
    reference["review"] = target
    if target == "verified":
        reference["verification_status"] = "reviewed_verified"
        reference["reviewer_id"] = actor_user_id
        reference["verified_at"] = timestamp
    elif target == "rejected":
        reference["verification_status"] = "user_provided_unverified"
    elif target == "superseded":
        reference["verification_status"] = "superseded"
    elif target == "expired":
        reference["verification_status"] = "stale"
    return reference


def classify_coordination_load(load, thresholds):
    """Map a supply load to the API's coordination status using one policy."""
    number = _finite_number(load, "supply load")
    if number < 0:
        raise ValueError("supply load cannot be negative")
    if not isinstance(thresholds, dict):
        raise ValueError("thresholds must be a mapping")
    try:
        elevated = _finite_number(
            thresholds["elevated_load"], "elevated_load threshold"
        )
        high = _finite_number(thresholds["high_load"], "high_load threshold")
    except (KeyError, TypeError) as error:
        raise ValueError("thresholds must define elevated_load and high_load") from error
    if elevated <= 0 or high <= elevated:
        raise ValueError("high_load must exceed positive elevated_load")
    if number >= high:
        return "high_coordination_load"
    if number >= elevated:
        return "elevated_coordination_load"
    return "within_reference"


def reference_matches_calculation(
    reference,
    *,
    organization_id,
    crop_code,
    geography,
    harvest_period,
    calculation_date,
):
    """Compatibility name for the API adapter's calculation lookup."""
    return reference_applies(
        reference,
        organization_id=organization_id,
        crop_code=crop_code,
        geography=geography,
        planning_period=harvest_period,
        calculation_date=calculation_date,
    )
