#!/usr/bin/env python3
"""Deterministic Glut Risk Coordination Indicator (GRCI).

The module follows docs/GRCI_SPEC.md. It does not use machine learning.
Risk thresholds are supplied by the caller.
"""

import csv
import math
import pathlib

YIELD_SUMMARY_DEFAULT = (
    pathlib.Path(__file__).resolve().parents[1]
    / "datasets"
    / "generated"
    / "yield_summary.csv"
)


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


def format_estimated_range(low, high, unit):
    """Format a user-estimated range without implying statistical confidence."""
    low_number = _finite_number(low, "range lower value")
    high_number = _finite_number(high, "range upper value")
    if low_number < 0 or high_number < 0:
        raise ValueError("range values must be non-negative")
    if high_number < low_number:
        raise ValueError("range upper value must not be below the lower value")
    unit_text = str(unit).strip()
    if not unit_text:
        raise ValueError("range unit must not be empty")
    return f"Estimated range: {low_number:g} {unit_text} to {high_number:g} {unit_text}"


def load_yield_summary(path=None):
    """Load and strictly validate the generated yield summary."""
    target = pathlib.Path(path) if path is not None else YIELD_SUMMARY_DEFAULT
    with target.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "crop_id", "display_name", "region_id", "region_label",
            "ref_period", "n_years", "avg_yield_mt_per_ha",
            "min_yield_mt_per_ha", "max_yield_mt_per_ha",
            "unit", "source_id", "data_status",
        }
        if set(reader.fieldnames or []) != required:
            raise ValueError("yield summary schema is not the expected TANIM schema")
        rows = list(reader)

    index = {}
    for row in rows:
        key = (row["crop_id"].strip(), row["region_id"].strip())
        if not all(key):
            raise ValueError("yield summary crop_id and region_id must not be empty")
        if key in index:
            raise ValueError(f"duplicate yield summary row for {key}")
        n_years = int(row["n_years"])
        avg = _finite_number(row["avg_yield_mt_per_ha"], "average yield")
        minimum = _finite_number(row["min_yield_mt_per_ha"], "minimum yield")
        maximum = _finite_number(row["max_yield_mt_per_ha"], "maximum yield")
        if n_years <= 0 or minimum < 0 or avg < 0 or maximum < 0:
            raise ValueError(f"invalid yield summary values for {key}")
        if not minimum <= avg <= maximum:
            raise ValueError(f"yield summary range is inconsistent for {key}")
        if row["unit"] != "mt_per_ha":
            raise ValueError(f"unexpected yield unit for {key}")
        index[key] = {
            "crop_id": key[0], "display_name": row["display_name"],
            "region_id": key[1], "region_label": row["region_label"],
            "ref_period": row["ref_period"], "n_years": n_years,
            "avg_yield_mt_per_ha": avg,
            "min_yield_mt_per_ha": minimum,
            "max_yield_mt_per_ha": maximum,
            "unit": row["unit"], "source_id": row["source_id"],
            "data_status": row["data_status"],
        }
    return index


def reference_yield_for(index, crop_id, region_id):
    """Return one crop-region yield record, or None when unavailable."""
    if not isinstance(index, dict):
        raise ValueError("yield summary index must be a dict")
    return index.get((str(crop_id).strip(), str(region_id).strip()))


def _describe_amount(low, high, unit):
    if low == high:
        return f"{low:g} {unit}"
    return f"{low:g} to {high:g} {unit}"


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
    result["reference_yield"] = reference_yield
    result["yield_source"] = yield_source
    result["reference_amount"] = reference_amount
    result["reference_unit"] = (
        str(reference_unit).strip().upper()
        if reference_unit is not None
        else None
    )
    result["reference_type"] = normalize_reference_type(reference_type)
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
    result["source_labels"] = normalize_source_labels(source_labels)
    result["provenance"] = {
        "yield_source": yield_source,
        "yield_ref_period": yield_record.get("ref_period") if isinstance(yield_record, dict) else None,
        "yield_unit": yield_record.get("unit") if isinstance(yield_record, dict) else None,
        "reference_type": result["reference_type"],
        "reference_amount": reference_amount,
        "reference_unit": result["reference_unit"],
        "reference_geography": result["reference_geography"],
        "reference_period": result["reference_period"],
        "source_labels": list(result["source_labels"]),
    }

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

    context_ok, context_error = validate_plan_context(
        plans,
        crop,
        location,
        harvest_period,
    )
    if not context_ok:
        result["status"] = "invalid"
        result["uncertainty_note"] = context_error
        return result

    canonical_reference = normalize_reference_type(reference_type)
    if canonical_reference is None:
        result["status"] = "incomplete"
        result["uncertainty_note"] = "Missing reference type."
        return result

    metadata = reference_metadata(canonical_reference)
    if metadata is None:
        result["status"] = "invalid"
        result["uncertainty_note"] = (
            "Unknown reference type. Expected one of: "
            + ", ".join(valid_reference_types())
            + "."
        )
        return result

    result["reference_label"] = metadata["label"]
    result["reference_evidence_note"] = metadata["evidence_note"]
    result["reference_quality"] = metadata["quality"]
    result["reference_scope"] = metadata["scope"]
    result["reference_mode"] = metadata["comparison_mode"]
    result["market_demand_wording_allowed"] = metadata[
        "market_demand_wording_allowed"
    ]
    result["provenance"].update({
        "reference_label": metadata["label"],
        "reference_quality": metadata["quality"],
        "reference_scope": metadata["scope"],
        "reference_mode": metadata["comparison_mode"],
    })

    if result["reference_unit"] != "MT":
        result["status"] = "invalid"
        result["uncertainty_note"] = (
            "Reference amount must use MT so it matches planned supply."
        )
        return result

    if not result["reference_geography"]:
        result["status"] = "incomplete"
        result["uncertainty_note"] = "Missing reference geography."
        return result

    if not result["reference_period"]:
        result["status"] = "incomplete"
        result["uncertainty_note"] = "Missing reference period."
        return result

    if metadata["scope"] == "national":
        if "philipp" not in result["reference_geography"].casefold():
            result["status"] = "invalid"
            result["uncertainty_note"] = (
                "National utilization context must keep its national geography."
            )
            return result

    if metadata["scope"] == "local":
        if "philipp" in result["reference_geography"].casefold():
            result["status"] = "invalid"
            result["uncertainty_note"] = (
                "A local reference cannot use a national geography."
            )
            return result

    try:
        area_low, area_high = collective_area_range(plans)
    except (ValueError, KeyError, TypeError):
        result["status"] = "invalid"
        result["uncertainty_note"] = "Invalid farm size or farm-size margin."
        return result

    result["planned_area_range"] = [area_low, area_high]
    result["uncertainty_state"] = "point" if area_low == area_high else "range"

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
    result["expected_production_range"] = list(supply)

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
            "The national utilization value is context only and is not used as local demand."
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
            f"Expected production is {_describe_amount(supply[0], supply[1], 'MT')}. "
            f"The comparison ratio is {_describe_amount(load[0], load[1], 'ratio')}. "
            "No comparison band is shown because bands are not configured."
        )
        return result

    low_band, high_band, borderline = classify_range(load[0], load[1], bands)
    state = "borderline" if borderline else low_band
    result["comparison_state"] = state
    result["comparison_band_range"] = [low_band, high_band]
    result["borderline"] = borderline

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
        if borderline:
            result["uncertainty_state"] = "borderline"
        result["explanation"] = (
            f"Expected production is {_describe_amount(supply[0], supply[1], 'MT')}. "
            f"Compared with {result['reference_label']}, the baseline ratio is "
            f"{_describe_amount(load[0], load[1], 'ratio')}. "
            f"Comparison state is {state}. This is not a market-demand risk result."
        )
        return result

    result["status"] = "ok"
    result["risk_state"] = state
    result["risk_band_range"] = [low_band, high_band]

    if borderline:
        result["uncertainty_state"] = "borderline"
        result["uncertainty_note"] = (
            f"Supply load spans {low_band} to {high_band}. The farm-size "
            "estimate can change the final band."
        )
    elif area_low != area_high:
        result["uncertainty_note"] = (
            "Farm size is approximate, so supply load is shown as a range."
        )

    result["explanation"] = (
        f"Expected production is {_describe_amount(supply[0], supply[1], 'MT')}. "
        f"Compared with {result['reference_label']}, the supply-load ratio is "
        f"{_describe_amount(load[0], load[1], 'ratio')}. "
        f"Risk state is {state}."
    )
    return result
