#!/usr/bin/env python3
"""Deterministic Glut Risk Coordination Indicator (GRCI) calculation.

The module follows docs/GRCI_SPEC.md. It does not use machine learning.

Risk thresholds are supplied by the caller. The MVP does not store final
product thresholds in this module.
"""

import math


REFERENCE_TYPES = {
    "local_committed_demand": {
        "label": "Local committed demand",
        "evidence_note": (
            "Compared against local committed buyer, cooperative, or LGU "
            "demand for this crop and period."
        ),
        "is_market_demand": True,
    },
    "local_historical_absorption": {
        "label": "Local historical absorption",
        "evidence_note": (
            "Compared against past local sold or accepted volume. "
            "This is not a forward demand commitment."
        ),
        "is_market_demand": True,
    },
    "national_utilization_context": {
        "label": "National utilization context (not Luzon demand)",
        "evidence_note": (
            "PSA Supply Utilization Accounts are national context. "
            "This is not Luzon demand."
        ),
        "is_market_demand": False,
    },
    "historical_production_baseline": {
        "label": "Historical production baseline (not market demand)",
        "evidence_note": (
            "Compared against historical production only. "
            "This is not market demand."
        ),
        "is_market_demand": False,
    },
    "demo_coordination_baseline": {
        "label": "Demo coordination baseline (not market demand)",
        "evidence_note": (
            "Synthetic DEMO-2026 baseline for reproducibility. "
            "This is not observed local market demand."
        ),
        "is_market_demand": False,
    },
}


def normalize_reference_type(value):
    """Return the canonical reference type string, or None when missing."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def describe_reference(reference_type):
    """Return the display label and evidence note for a reference type."""
    canonical = normalize_reference_type(reference_type)
    if canonical is None:
        return (None, None)
    record = REFERENCE_TYPES.get(canonical)
    if record is None:
        return (None, None)
    return (record["label"], record["evidence_note"])


def is_market_demand_reference(reference_type):
    """Return True only for references that may be called market demand."""
    canonical = normalize_reference_type(reference_type)
    record = REFERENCE_TYPES.get(canonical) if canonical else None
    return bool(record and record["is_market_demand"])


def valid_reference_types():
    """Return the sorted list of accepted reference type strings."""
    return sorted(REFERENCE_TYPES)


def _finite_number(value, name):
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a number") from error
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


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
    """Convert an area range into an expected supply range."""
    if yield_mt_per_ha is None:
        return None
    try:
        yield_value = _finite_number(yield_mt_per_ha, "reference yield")
    except ValueError:
        return None
    if yield_value <= 0:
        return None
    return (
        float(area_low) * yield_value,
        float(area_high) * yield_value,
    )


def supply_load_range(supply_low, supply_high, reference_amount):
    """Compare planned supply with a positive reference amount."""
    if reference_amount is None:
        return None
    try:
        reference = _finite_number(reference_amount, "reference amount")
    except ValueError:
        return None
    if reference <= 0:
        return None
    return (
        float(supply_low) / reference,
        float(supply_high) / reference,
    )


def validate_bands(bands):
    """Validate caller-provided risk bands.

    Bands must use strictly increasing upper limits and the final limit must
    be positive infinity. Labels must be unique non-empty strings.
    """
    if not bands:
        raise ValueError("bands must be a non-empty list of (upper, label)")

    validated = []
    previous = float("-inf")
    labels = set()

    for item in bands:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("each risk band must contain an upper limit and label")

        upper_raw, label_raw = item
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
    validated = validate_bands(bands)
    low_band = _classify_validated(low, validated)
    high_band = _classify_validated(high, validated)
    return (low_band, high_band, low_band != high_band)


def is_planning_supported(crop_record):
    """Check whether a crop record is safe for planning calculations."""
    if not isinstance(crop_record, dict):
        return False

    coverage = crop_record.get("coverage")
    if isinstance(coverage, dict):
        required = bool(coverage.get("production")) and bool(coverage.get("area"))
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
        "reference_amount": None,
        "reference_type": None,
        "reference_label": None,
        "reference_evidence_note": None,
        "supply_load_range": None,
        "status": "unclassified",
        "risk_state": None,
        "risk_band_range": None,
        "borderline": False,
        "uncertainty_note": None,
        "source_labels": [],
    }


def compute_grci(
    *,
    crop,
    location,
    harvest_period,
    plans,
    reference_yield,
    yield_source,
    reference_amount,
    reference_type,
    crop_record,
    bands=None,
    source_labels=None,
):
    """Compute one reproducible GRCI result.

    Expected user or data problems return a result with a clear status.
    Malformed risk-band configuration raises ValueError because it is a
    programming or configuration error.
    Reference quality is explicit: reference_type must be one of
    valid_reference_types(). Historical production must never be labelled
    as market demand; use describe_reference() for user wording.
    """
    result = _result_base(crop, location, harvest_period)
    result["reference_yield"] = reference_yield
    result["yield_source"] = yield_source
    result["reference_amount"] = reference_amount
    result["reference_type"] = normalize_reference_type(reference_type)
    result["source_labels"] = list(source_labels) if source_labels else []

    if crop is None or not str(crop).strip():
        result["status"] = "incomplete"
        result["uncertainty_note"] = "Missing crop."
        return result

    if not is_planning_supported(crop_record):
        result["status"] = "unsupported"
        result["uncertainty_note"] = (
            "Crop does not have a safe production and area join in the "
            "TANIM crop registry."
        )
        return result

    if location is None or not str(location).strip():
        result["status"] = "incomplete"
        result["uncertainty_note"] = "Missing location."
        return result

    if harvest_period is None or not str(harvest_period).strip():
        result["status"] = "incomplete"
        result["uncertainty_note"] = "Missing harvest period."
        return result

    if not plans:
        result["status"] = "incomplete"
        result["uncertainty_note"] = "No farm plans provided."
        return result

    try:
        area_low, area_high = collective_area_range(plans)
    except (ValueError, KeyError, TypeError):
        result["status"] = "invalid"
        result["uncertainty_note"] = "Invalid farm size or farm-size margin."
        return result

    result["planned_area_range"] = [area_low, area_high]

    if reference_yield is None:
        result["status"] = "incomplete"
        result["uncertainty_note"] = (
            "Missing reference yield. Planned supply cannot be calculated."
        )
        return result

    try:
        yield_value = _finite_number(reference_yield, "reference yield")
    except ValueError:
        result["status"] = "invalid"
        result["uncertainty_note"] = "Reference yield must be a valid number."
        return result

    if yield_value <= 0:
        result["status"] = "invalid"
        result["uncertainty_note"] = "Reference yield must be greater than zero."
        return result

    if yield_source is None or not str(yield_source).strip():
        result["status"] = "incomplete"
        result["uncertainty_note"] = "Missing reference-yield source."
        return result

    supply = planned_supply_range(area_low, area_high, yield_value)
    result["planned_supply_range"] = list(supply)

    if reference_amount is None:
        result["status"] = "incomplete"
        result["uncertainty_note"] = (
            "Missing reference amount. Supply load cannot be calculated."
        )
        return result

    try:
        reference_value = _finite_number(reference_amount, "reference amount")
    except ValueError:
        result["status"] = "invalid"
        result["uncertainty_note"] = "Reference amount must be a valid number."
        return result

    if reference_value <= 0:
        result["status"] = "invalid"
        result["uncertainty_note"] = "Reference amount must be greater than zero."
        return result

    canonical_reference = normalize_reference_type(reference_type)
    if canonical_reference is None:
        result["status"] = "incomplete"
        result["uncertainty_note"] = "Missing reference type."
        return result

    if canonical_reference not in REFERENCE_TYPES:
        result["status"] = "incomplete"
        result["uncertainty_note"] = (
            "Unknown reference type. Expected one of: "
            + ", ".join(valid_reference_types())
            + "."
        )
        return result

    label, evidence_note = describe_reference(canonical_reference)
    result["reference_label"] = label
    result["reference_evidence_note"] = evidence_note

    load = supply_load_range(supply[0], supply[1], reference_value)
    result["supply_load_range"] = list(load)

    if bands is None:
        result["status"] = "unclassified"
        result["uncertainty_note"] = (
            "Risk bands are not configured. Supply load is available but "
            "has no risk label."
        )
        return result

    low_band, high_band, borderline = classify_range(load[0], load[1], bands)
    result["status"] = "ok"
    result["risk_band_range"] = [low_band, high_band]
    result["borderline"] = borderline

    if borderline:
        result["risk_state"] = "borderline"
        result["uncertainty_note"] = (
            f"Supply load spans {low_band} to {high_band}. The farm-size "
            "estimate can change the final band."
        )
    else:
        result["risk_state"] = low_band
        if area_low != area_high:
            result["uncertainty_note"] = (
                "Farm size is approximate, so supply load is shown as a range."
            )

    return result
