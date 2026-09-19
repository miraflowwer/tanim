#!/usr/bin/env python3
"""Glut Risk Coordination Indicator (GRCI) calculation.

Implements docs/GRCI_SPEC.md with fixed rules and no machine learning.

Conventions:
- Farm size is an estimate with a margin: low = max(0, A - M), high = A + M.
- Group plans sum lows and sum highs to give a collective planned-area range.
- Planned supply = planned area x reference yield (range when area is a range).
- Supply load = planned supply / reference amount (range when supply is a range).
- Risk bands are injected by the caller so tests do not lock unfinalized
  thresholds into this module. Bands are a sorted list of
  (upper_bound_inclusive, label) pairs, e.g.
  [(1.0, "low"), (1.5, "watch"), (float("inf"), "high")].
- Expected data gaps return an explicit result dict with a status
  risk_state instead of raising: unknown, unsupported, incomplete, invalid.
"""

ROOT_CROP_FAMILIES = ("production", "area")


def area_range(estimate_ha, margin_ha):
    """Return (low, high) planned-area range for one plan."""
    estimate = float(estimate_ha)
    margin = float(margin_ha)
    if estimate < 0 or margin < 0:
        raise ValueError("farm size estimate and margin must be non-negative")
    low = max(0.0, estimate - margin)
    high = estimate + margin
    return (low, high)


def collective_area_range(plans):
    """Sum per-plan lows and highs into a collective (low, high) range.

    Each plan is a mapping with farm_size_ha and farm_size_margin_ha.
    """
    low_total = 0.0
    high_total = 0.0
    for plan in plans:
        low, high = area_range(plan["farm_size_ha"], plan["farm_size_margin_ha"])
        low_total += low
        high_total += high
    return (low_total, high_total)


def planned_supply_range(area_low, area_high, yield_mt_per_ha):
    """Convert an area range into a supply range using reference yield."""
    if yield_mt_per_ha is None:
        return None
    yield_value = float(yield_mt_per_ha)
    if yield_value <= 0:
        return None
    return (float(area_low) * yield_value, float(area_high) * yield_value)


def supply_load_range(supply_low, supply_high, reference_amount):
    """Convert a supply range into a supply-load range.

    Returns None when the reference is missing or non-positive so callers
    never divide by zero.
    """
    if reference_amount is None:
        return None
    reference = float(reference_amount)
    if reference <= 0:
        return None
    return (float(supply_low) / reference, float(supply_high) / reference)


def classify_load(value, bands):
    """Classify a single supply-load value into a band label."""
    number = float(value)
    for upper, label in bands:
        if number <= float(upper):
            return label
    raise ValueError("bands do not cover value %r" % (value,))


def classify_range(low, high, bands):
    """Classify a range; report whether it crosses a risk boundary."""
    low_band = classify_load(low, bands)
    high_band = classify_load(high, bands)
    return (low_band, high_band, low_band != high_band)


def is_planning_supported(crop_record):
    """Check the crop-registry rule: production and area required."""
    if not isinstance(crop_record, dict):
        return False
    if "planning_supported" in crop_record:
        return crop_record.get("planning_supported") is True
    coverage = crop_record.get("coverage", {})
    return bool(coverage.get("production")) and bool(coverage.get("area"))


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
        "supply_load_range": None,
        "risk_state": "unknown",
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
    crop_record=None,
    bands=None,
    source_labels=None,
):
    """Compute one reproducible GRCI result dict.

    Never raises for expected data gaps; those become explicit risk_state
    values (unsupported, incomplete, unknown, invalid) with an
    uncertainty_note. Only programmer errors (negative area, malformed
    bands) raise ValueError.
    """
    labels = list(source_labels) if source_labels else []
    result = _result_base(crop, location, harvest_period)
    result["reference_yield"] = reference_yield
    result["yield_source"] = yield_source
    result["reference_amount"] = reference_amount
    result["reference_type"] = reference_type
    result["source_labels"] = labels

    if crop_record is not None and not is_planning_supported(crop_record):
        result["risk_state"] = "unsupported"
        result["uncertainty_note"] = (
            "Crop does not resolve to production and area coverage "
            "under exact normalized labels; kept separate, no calculation."
        )
        return result

    if location is None or not str(location).strip():
        result["risk_state"] = "incomplete"
        result["uncertainty_note"] = "Missing location; GRCI needs a place."
        return result

    if not plans:
        result["risk_state"] = "incomplete"
        result["uncertainty_note"] = "No farm plans provided."
        return result

    try:
        area_low, area_high = collective_area_range(plans)
    except (ValueError, KeyError, TypeError):
        result["risk_state"] = "invalid"
        result["uncertainty_note"] = "Invalid farm size or margin."
        raise
    result["planned_area_range"] = [area_low, area_high]

    if reference_yield is None:
        result["uncertainty_note"] = "Missing reference yield; planned supply unknown."
        return result
    try:
        if float(reference_yield) <= 0:
            result["uncertainty_note"] = (
                "Invalid reference yield; planned supply unknown."
            )
            return result
    except (TypeError, ValueError):
        result["uncertainty_note"] = "Missing reference yield; planned supply unknown."
        return result

    supply = planned_supply_range(area_low, area_high, reference_yield)
    result["planned_supply_range"] = list(supply)

    if reference_amount is None:
        result["uncertainty_note"] = "Missing reference amount; supply load unknown."
        return result
    try:
        if float(reference_amount) <= 0:
            result["uncertainty_note"] = (
                "Invalid reference amount; supply load unknown."
            )
            return result
    except (TypeError, ValueError):
        result["uncertainty_note"] = "Missing reference amount; supply load unknown."
        return result

    load = supply_load_range(supply[0], supply[1], reference_amount)
    result["supply_load_range"] = list(load)

    if bands is None:
        result["risk_state"] = "unknown"
        result["uncertainty_note"] = "Missing risk bands; supply load not classified."
        return result
    if not bands:
        raise ValueError("bands must be a non-empty list of (upper, label)")

    low_band, high_band, borderline = classify_range(load[0], load[1], bands)
    result["borderline"] = borderline
    if borderline:
        result["risk_state"] = "borderline"
        result["uncertainty_note"] = (
            "Supply load spans %s to %s; the farm-size estimate "
            "can change the final band." % (low_band, high_band)
        )
    else:
        result["risk_state"] = low_band
        if area_low != area_high:
            result["uncertainty_note"] = (
                "Farm size is approximate; supply load is a range."
            )
    return result
