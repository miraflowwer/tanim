#!/usr/bin/env python3
"""TANIM MVP backend service.

One or more farmer plans go through three deterministic steps:

1. Validate the plan and resolve its crop, region, and comparison reference.
2. Look up the committed regional yield and the comparison reference.
3. Call scripts/grci.py compute_grci() and wrap the result in a JSON envelope.

Rules kept from docs/GRCI_SPEC.md:

- scripts/grci.py owns every formula, field, and risk label. This module only
  calls it, so there is no second copy of the calculation.
- Only committed local files are read for calculations. The optional local
  HTTP server does not contact any external service, so the demo works with
  the internet disconnected.
- Nothing is guessed. An unknown crop, an unsupported crop, a missing
  crop-region yield row, or an unusable comparison is an error envelope.
- Crop lookup accepts exact runtime crop ids, display names, canonical labels,
  and reviewed manual aliases. Alias collisions fail closed.
- Region lookup is exact on (crop_id, region_id) after the request region is
  normalized. The request may use IV-A or a label such as CALABARZON (IV-A).
- The synthetic demo reference is used only when the request explicitly sets
  use_demo_reference=true. Normal planning requires a traceable comparison.
- Normal comparison amounts and source labels are user-provided and marked
  unverified. Direct local committed demand is reserved for a reviewed source
  integration and is rejected from the farmer request path.
- Service errors use stable codes such as yield_not_found, crop_not_found,
  crop_unsupported, comparison_required, and invalid_input. Engine states
  invalid, unsupported, and incomplete are translated instead of leaking a
  raw rejected result.
- Risk band upper bounds print as the string "inf" when they are infinite so
  every emitted document stays valid JSON for strict parsers such as
  JSON.parse.

Stdlib only. Python 3.12+.
"""

import argparse
import copy
import csv
import datetime
import importlib.util
import json
import math
import pathlib
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
DATASETS = ROOT / "datasets"
GENERATED = DATASETS / "generated"

CROP_REGISTRY_PATH = DATASETS / "crop_registry.json"
RUNTIME_REGISTRY_PATH = GENERATED / "crop_registry.generated.json"
YIELD_SUMMARY_PATH = GENERATED / "yield_summary.csv"
DEMO_BASELINE_PATH = DATASETS / "demo_coordination_baseline.csv"
DEMO_PLANS_PATH = DATASETS / "demo_farm_plans.csv"
DEMO_REQUEST_PATH = ROOT / "examples" / "tomato_calabarzon_request.json"
MAX_REQUEST_BYTES = 64 * 1024

# Fixed demo bands only. These are not production thresholds.
DEFAULT_BANDS = [
    (1.0, "low"),
    (1.5, "watch"),
    (float("inf"), "high"),
]

PLANTING_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HARVEST_PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

PLAN_REQUIRED_FIELDS = (
    "crop",
    "region_id",
    "farm_size_ha",
    "farm_size_margin_ha",
    "planting_date",
    "harvest_period",
)
LOCATION_FIELDS = ("location", "municipality")
COMPARISON_FIELDS = ("amount", "unit", "type", "geography", "period")
COMPARISON_OPTIONAL_FIELDS = ("region_id",)
REQUEST_FIELDS = {
    "plan",
    "plans",
    "comparison",
    "bands",
    "source_labels",
    "use_demo_reference",
}
# These are the only reference types the free-text farmer form may submit.
# Direct committed demand remains an engine type for a future reviewed
# integration, but a typed amount and source label are not proof of demand.
MANUAL_REFERENCE_TYPES = (
    "historical_production_baseline",
    "local_historical_absorption",
    "national_utilization_context",
)
EVIDENCE_STATUS_USER_PROVIDED = "user_provided_unverified"
EVIDENCE_STATUS_FIXED_DEMO = "fixed_synthetic"
EVIDENCE_STATUS_REVIEWED = "reviewed_verified"
REGION_ORDER = ("NCR", "CAR", "I", "II", "III", "IV-A", "MIMAROPA", "V")

# Engine states that must not reach the interface as a raw result.
ENGINE_ERROR_CODES = {
    "invalid": "invalid_input",
    "unsupported": "crop_unsupported",
    "incomplete": "invalid_input",
}

_RUNTIME_CROPS = None
_YIELD_INDEX = None
_CROP_ALIASES = None
_DEMO_REFERENCES = None
_DEMO_PLANS = None


class ServiceError(Exception):
    """Internal control-flow error that becomes an error envelope."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def load_engine(path=None):
    """Load scripts/grci.py as the single calculation engine."""
    target = pathlib.Path(path) if path is not None else HERE / "grci.py"
    spec = importlib.util.spec_from_file_location("tanim_grci", target)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load the GRCI engine from {target}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ENGINE = load_engine()


def _clean_text(value):
    """Return trimmed text, or None when the value is blank or missing."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _has_value(value):
    """Return True when a JSON field carries usable text or a number."""
    if value is None or isinstance(value, bool):
        return False
    return str(value).strip() != ""


def _same_text(first, second):
    return str(first).strip().casefold() == str(second).strip().casefold()


def _finite_number(value, name):
    """Return a finite float, or raise invalid_input."""
    if isinstance(value, bool):
        raise ServiceError("invalid_input", f"{name} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ServiceError("invalid_input", f"{name} must be a number.")
    if not math.isfinite(number):
        raise ServiceError("invalid_input", f"{name} must be a finite number.")
    return number


def _crop_key(value):
    """Return the exact-match alias key for one crop label."""
    text = _clean_text(value)
    return text.casefold() if text else None


def _json_band(bound):
    """Return a JSON-safe band upper bound."""
    return "inf" if math.isinf(bound) else bound


def _json_safe(value):
    """Return a strict-JSON-safe copy of caller data.

    The engine result never carries a non-finite float, but the echoed plan is
    caller data, so it is cleaned here. A non-finite float becomes "inf",
    "-inf", or "nan" text so strict parsers such as JSON.parse still accept
    the document instead of failing on the Python Infinity literal.
    """
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    return value


def _strict_json_loads(text):
    """Parse strict JSON and reject duplicate keys and non-finite constants."""
    def reject_constant(value):
        raise ValueError(f"non-standard JSON constant: {value}")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(
        text,
        parse_constant=reject_constant,
        object_pairs_hook=unique_object,
    )


def _read_json_file(path, what):
    try:
        return _strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ServiceError(
            "invalid_input",
            f"Cannot read the committed {what} ({path.name}): {error}.",
        ) from error


def normalize_region_id(value):
    """Return the region id for IV-A or CALABARZON (IV-A), or None.

    Accepted forms: the exact region id (any case), a label that carries the
    region id in parentheses, and a generated label such as
    "REGION IV-A (CALABARZON)". The (crop_id, region_id) yield lookup itself
    stays exact and case-sensitive.
    """
    text = _clean_text(value)
    if text is None:
        return None

    candidate = text.upper()
    if candidate in ENGINE.YIELD_REGION_IDS:
        return candidate

    if "(" in candidate and ")" in candidate:
        inner = candidate[candidate.index("(") + 1:candidate.rindex(")")].strip()
        if inner in ENGINE.YIELD_REGION_IDS:
            return inner

    match = re.match(r"^REGION\s+([A-Z]+-?[A-Z]?)\s*\(", candidate)
    if match and match.group(1) in ENGINE.YIELD_REGION_IDS:
        return match.group(1)

    return None


def load_crop_aliases(path=None):
    """Return an exact alias-to-crop_id map for every runtime crop.

    Runtime crop ids, display names, and canonical labels are accepted.
    Reviewed manual aliases are added only when they point to a runtime crop.
    Any collision fails closed instead of silently choosing a crop.
    """
    global _CROP_ALIASES
    if path is None and _CROP_ALIASES is not None:
        return _CROP_ALIASES

    runtime = load_runtime_crops()
    aliases = {}

    def add_alias(label, crop_id):
        key = _crop_key(label)
        if not key:
            return
        previous = aliases.get(key)
        if previous is not None and previous != crop_id:
            raise ServiceError(
                "invalid_input",
                f"Crop alias '{label}' maps to more than one crop.",
            )
        aliases[key] = crop_id

    for crop_id, record in runtime.items():
        add_alias(crop_id, crop_id)
        add_alias(record.get("display_name"), crop_id)
        add_alias(record.get("canonical_label"), crop_id)

    target = pathlib.Path(path) if path is not None else CROP_REGISTRY_PATH
    payload = _read_json_file(target, "crop registry")
    if not isinstance(payload, dict):
        raise ServiceError(
            "invalid_input",
            f"Cannot read the committed crop registry ({target.name}): "
            "expected a JSON object.",
        )

    overrides = payload.get("manual_overrides", [])
    if not isinstance(overrides, list):
        raise ServiceError(
            "invalid_input",
            "Crop registry manual_overrides must be a list.",
        )

    for record in overrides:
        if not isinstance(record, dict):
            raise ServiceError(
                "invalid_input",
                "Crop registry contains a non-record manual override.",
            )
        crop_id = _clean_text(record.get("crop_id"))
        if crop_id is None:
            raise ServiceError(
                "invalid_input",
                "Crop registry contains a manual override without crop_id.",
            )
        if crop_id not in runtime:
            raise ServiceError(
                "invalid_input",
                f"Manual crop alias points to missing runtime crop '{crop_id}'.",
            )
        raw_aliases = record.get("aliases") or []
        if not isinstance(raw_aliases, list):
            raise ServiceError(
                "invalid_input",
                f"Manual aliases for '{crop_id}' must be a list.",
            )
        labels = list(raw_aliases)
        labels.extend((record.get("display_name"), crop_id))
        for label in labels:
            add_alias(label, crop_id)

    if path is None:
        _CROP_ALIASES = aliases
    return aliases


def load_runtime_crops(path=None):
    """Return {crop_id: record} from the generated runtime crop registry."""
    global _RUNTIME_CROPS
    if path is None and _RUNTIME_CROPS is not None:
        return _RUNTIME_CROPS

    target = pathlib.Path(path) if path is not None else RUNTIME_REGISTRY_PATH
    payload = _read_json_file(target, "runtime crop registry")
    if not isinstance(payload, dict):
        raise ServiceError(
            "invalid_input",
            f"Cannot read the committed runtime crop registry ({target.name}): "
            "expected a JSON object.",
        )

    records = payload.get("crops")
    if not isinstance(records, list):
        raise ServiceError(
            "invalid_input",
            "Runtime crop registry must contain a crops list.",
        )

    crops = {}
    for record in records:
        if not isinstance(record, dict):
            raise ServiceError(
                "invalid_input",
                "Runtime crop registry contains a non-record crop.",
            )
        crop_id = _clean_text(record.get("crop_id"))
        if not crop_id:
            raise ServiceError(
                "invalid_input",
                "Runtime crop registry contains a crop without crop_id.",
            )
        if crop_id in crops:
            raise ServiceError(
                "invalid_input",
                f"Runtime crop registry has duplicate crop_id '{crop_id}'.",
            )
        crops[crop_id] = record

    if not crops:
        raise ServiceError("invalid_input", "Runtime crop registry is empty.")

    if path is None:
        _RUNTIME_CROPS = crops
    return crops


def load_yield_index(path=None):
    """Return the validated (crop_id, region_id) yield index."""
    global _YIELD_INDEX
    if path is None and _YIELD_INDEX is not None:
        return _YIELD_INDEX

    target = pathlib.Path(path) if path is not None else YIELD_SUMMARY_PATH
    try:
        index = ENGINE.load_yield_summary(target)
    except (OSError, ValueError) as error:
        raise ServiceError(
            "invalid_input",
            f"The committed yield summary is not usable: {error}.",
        ) from error

    if path is None:
        _YIELD_INDEX = index
    return index


def load_demo_references(path=None):
    """Return {crop_id: reference} from the committed demo baseline."""
    global _DEMO_REFERENCES
    if path is None and _DEMO_REFERENCES is not None:
        return _DEMO_REFERENCES

    target = pathlib.Path(path) if path is not None else DEMO_BASELINE_PATH
    try:
        with target.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {
                "crop_canonical",
                "reference_period",
                "reference_geography",
                "reference_qty_mt",
                "reference_yield_mt_per_ha",
                "reference_type",
                "source_id",
                "data_status",
            }
            if not required <= set(reader.fieldnames or []):
                raise ServiceError(
                    "invalid_input",
                    "Demo baseline schema is missing required fields.",
                )
            rows = list(reader)
    except OSError as error:
        raise ServiceError(
            "invalid_input",
            f"Cannot read the committed demo baseline ({target.name}): {error}.",
        ) from error

    if not rows:
        raise ServiceError("invalid_input", "Demo baseline is empty.")

    references = {}
    for row in rows:
        crop_id = _crop_key(row.get("crop_canonical"))
        if crop_id is None:
            raise ServiceError(
                "invalid_input",
                "Demo baseline contains a row without crop_canonical.",
            )
        if crop_id in references:
            raise ServiceError(
                "invalid_input",
                f"Demo baseline has duplicate crop '{crop_id}'.",
            )

        amount = _finite_number(
            row.get("reference_qty_mt"),
            f"demo baseline amount for {crop_id}",
        )
        yield_value = _finite_number(
            row.get("reference_yield_mt_per_ha"),
            f"demo baseline yield for {crop_id}",
        )
        reference_type = _clean_text(row.get("reference_type"))
        geography = _clean_text(row.get("reference_geography"))
        period = _clean_text(row.get("reference_period"))
        source_id = _clean_text(row.get("source_id"))
        data_status = _clean_text(row.get("data_status"))
        if amount <= 0 or yield_value <= 0:
            raise ServiceError(
                "invalid_input",
                f"Demo baseline values for '{crop_id}' must be greater than zero.",
            )
        if reference_type != "demo_coordination_baseline":
            raise ServiceError(
                "invalid_input",
                "Demo baseline reference_type must stay demo_coordination_baseline.",
            )
        if source_id != "DEMO-2026" or data_status != "derived_demo":
            raise ServiceError(
                "invalid_input",
                "Demo baseline provenance must stay DEMO-2026 and derived_demo.",
            )
        if normalize_region_id(geography) is None or period is None:
            raise ServiceError(
                "invalid_input",
                f"Demo baseline context for '{crop_id}' is not usable.",
            )

        references[crop_id] = {
            "amount": amount,
            "unit": "MT",
            "type": reference_type,
            "geography": geography,
            "period": period,
            "yield_mt_per_ha": yield_value,
            "source_id": source_id,
            "data_status": data_status,
        }

    if path is None:
        _DEMO_REFERENCES = references
    return references


def load_demo_plans(path=None):
    """Return the exact committed farmer-plan fixture grouped by crop."""
    global _DEMO_PLANS
    if path is None and _DEMO_PLANS is not None:
        return _DEMO_PLANS

    target = pathlib.Path(path) if path is not None else DEMO_PLANS_PATH
    try:
        with target.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {
                "crop_canonical",
                "farm_size_ha",
                "farm_size_margin_ha",
                "planting_date",
                "harvest_period",
                "municipality",
                "source_id",
                "data_status",
            }
            if not required <= set(reader.fieldnames or []):
                raise ServiceError(
                    "invalid_input",
                    "Demo farm-plan schema is missing required fields.",
                )
            rows = list(reader)
    except OSError as error:
        raise ServiceError(
            "invalid_input",
            f"Cannot read the committed demo farm plans ({target.name}): {error}.",
        ) from error

    if not rows:
        raise ServiceError("invalid_input", "Demo farm-plan fixture is empty.")

    grouped = {}
    for row in rows:
        crop_id = _crop_key(row.get("crop_canonical"))
        location = _clean_text(row.get("municipality"))
        planting_date = _clean_text(row.get("planting_date"))
        harvest_period = _clean_text(row.get("harvest_period"))
        if crop_id is None or location is None:
            raise ServiceError(
                "invalid_input",
                "Demo farm-plan fixture contains a row without crop or location.",
            )
        area = _finite_number(row.get("farm_size_ha"), "demo farm size")
        margin = _finite_number(row.get("farm_size_margin_ha"), "demo farm margin")
        if area <= 0 or margin < 0:
            raise ServiceError(
                "invalid_input",
                "Demo farm size must be positive and margin must not be negative.",
            )
        if (
            row.get("source_id") != "DEMO-2026"
            or row.get("data_status") != "synthetic"
        ):
            raise ServiceError(
                "invalid_input",
                "Demo farm-plan provenance must stay DEMO-2026 and synthetic.",
            )
        if (
            planting_date is None
            or not PLANTING_DATE_PATTERN.match(planting_date)
            or harvest_period is None
            or not HARVEST_PERIOD_PATTERN.match(harvest_period)
            or harvest_period < planting_date[:7]
        ):
            raise ServiceError(
                "invalid_input",
                "Demo farm-plan fixture contains an invalid date.",
            )
        try:
            datetime.date.fromisoformat(planting_date)
        except ValueError as error:
            raise ServiceError(
                "invalid_input",
                "Demo farm-plan fixture contains an invalid calendar date.",
            ) from error

        grouped.setdefault(crop_id, []).append(
            {
                "crop_id": crop_id,
                "location": location,
                "farm_size_ha": area,
                "farm_size_margin_ha": margin,
                "planting_date": planting_date,
                "harvest_period": harvest_period,
            }
        )

    if path is None:
        _DEMO_PLANS = grouped
    return grouped


def _demo_plan_signature(plan):
    return (
        plan["crop_id"],
        plan["location"].casefold(),
        plan["farm_size_ha"],
        plan["farm_size_margin_ha"],
        plan["planting_date"],
        plan["harvest_period"],
    )


def _yield_source_text(yield_record):
    """Describe the committed yield row used for one result."""
    source_id = _clean_text(yield_record.get("source_id")) or "unknown source"
    ref_period = _clean_text(yield_record.get("ref_period")) or "unknown period"
    return f"{source_id} {ref_period} regional average yield"


def _validate_reference(reference, source_label, *, allow_internal=False):
    """Validate one comparison record and return the normalized copy.

    A comparison is all-or-nothing: all five fields must be present and no
    value is merged from another source.
    """
    if not isinstance(reference, dict):
        raise ServiceError(
            "invalid_input",
            f"{source_label} must be a JSON object with "
            + ", ".join(COMPARISON_FIELDS)
            + ".",
        )

    allowed_fields = set(COMPARISON_FIELDS) | set(COMPARISON_OPTIONAL_FIELDS)
    if allow_internal:
        allowed_fields.update(("yield_mt_per_ha", "source_id", "data_status"))
    unknown = sorted(set(reference) - allowed_fields)
    if unknown:
        raise ServiceError(
            "invalid_input",
            f"{source_label} contains unknown field(s): {', '.join(unknown)}.",
        )

    missing = [
        name for name in COMPARISON_FIELDS if not _has_value(reference.get(name))
    ]
    if missing:
        raise ServiceError(
            "invalid_input",
            f"{source_label} must contain all of "
            + ", ".join(COMPARISON_FIELDS)
            + f" (missing: {', '.join(missing)}).",
        )

    amount = _finite_number(reference["amount"], f"{source_label} amount")
    if amount <= 0:
        raise ServiceError(
            "invalid_input",
            f"{source_label} amount must be greater than zero.",
        )

    unit = _clean_text(reference["unit"]).upper()
    if unit != "MT":
        raise ServiceError("invalid_input", f"{source_label} unit must be MT.")

    reference_type = ENGINE.normalize_reference_type(reference["type"])
    if ENGINE.reference_metadata(reference_type) is None:
        raise ServiceError(
            "invalid_input",
            f"{source_label} type must be one of: "
            + ", ".join(ENGINE.valid_reference_types())
            + ".",
        )
    if not allow_internal and reference_type == "local_committed_demand":
        raise ServiceError(
            "invalid_input",
            "local_committed_demand is reserved for reviewed/verified evidence. "
            "A user-entered amount and source label cannot be treated as "
            "confirmed local demand.",
        )
    if (
        not allow_internal
        and reference_type not in MANUAL_REFERENCE_TYPES
        and reference_type != "demo_coordination_baseline"
    ):
        raise ServiceError(
            "invalid_input",
            f"{source_label} type is not available for manual farmer input.",
        )

    region_id = None
    if _has_value(reference.get("region_id")):
        region_id = normalize_region_id(reference.get("region_id"))
        if region_id is None:
            raise ServiceError(
                "invalid_input",
                f"{source_label} region_id must be one of: "
                + ", ".join(REGION_ORDER)
                + ".",
            )

    return {
        "amount": amount,
        "unit": unit,
        "type": reference_type,
        "geography": _clean_text(reference["geography"]),
        "period": _clean_text(reference["period"]),
        "region_id": region_id,
        "from_demo": False,
    }


def _validate_reference_context(reference, context):
    """Require non-demo comparison evidence to match the plan context."""
    metadata = ENGINE.reference_metadata(reference["type"])
    if metadata is None:
        raise ServiceError("invalid_input", "Comparison reference type is not usable.")

    if metadata["scope"] == "national":
        if reference.get("region_id") is not None:
            raise ServiceError(
                "invalid_input",
                "National utilization context must not declare a Luzon region_id.",
            )
        return

    if "philipp" in reference["geography"].casefold():
        raise ServiceError(
            "invalid_input",
            "A non-national comparison cannot use a national geography.",
        )

    if reference.get("region_id") is None:
        raise ServiceError(
            "invalid_input",
            "A non-national comparison must declare region_id so TANIM can "
            "verify that the evidence matches the farmer plan.",
        )
    if reference["region_id"] != context["region_id"]:
        raise ServiceError(
            "invalid_input",
            "Comparison region_id must match the farmer plan region_id.",
        )

    geography_region = normalize_region_id(reference["geography"])
    if (
        geography_region is not None
        and geography_region != reference["region_id"]
    ):
        raise ServiceError(
            "invalid_input",
            "Comparison geography and region_id describe different regions.",
        )

    if (
        reference["type"] == "local_committed_demand"
        and reference["period"] != context["harvest_period"]
    ):
        raise ServiceError(
            "invalid_input",
            "Local committed demand period must match the plan harvest_period.",
        )


def validate_plan(plan):
    """Return the normalized plan context, or raise ServiceError."""
    if not isinstance(plan, dict):
        raise ServiceError("invalid_input", "plan must be a JSON object.")

    missing = [name for name in PLAN_REQUIRED_FIELDS if not _has_value(plan.get(name))]
    if missing:
        raise ServiceError(
            "invalid_input",
            "plan is missing required field(s): " + ", ".join(missing) + ".",
        )

    location_values = [_clean_text(plan.get(name)) for name in LOCATION_FIELDS]
    present = [value for value in location_values if value]
    if not present:
        raise ServiceError(
            "invalid_input",
            "plan must include location or municipality.",
        )
    if len(present) == 2 and not _same_text(present[0], present[1]):
        raise ServiceError(
            "invalid_input",
            "plan location and municipality must match when both are given.",
        )
    location = present[0]

    crop_id = load_crop_aliases().get(_crop_key(plan.get("crop")))
    if crop_id is None:
        raise ServiceError(
            "crop_not_found",
            f"Unknown crop '{_clean_text(plan.get('crop'))}'. TANIM matches "
            "audited crop ids, names, and reviewed aliases exactly; review the "
            "crop mapping before planning this crop.",
        )

    region_id = normalize_region_id(plan.get("region_id"))
    if region_id is None:
        raise ServiceError(
            "invalid_input",
            "region_id must be one of: "
            + ", ".join(sorted(ENGINE.YIELD_REGION_IDS))
            + " (a label such as CALABARZON (IV-A) is also accepted).",
        )

    farm_size_ha = _finite_number(plan.get("farm_size_ha"), "farm_size_ha")
    if farm_size_ha <= 0:
        raise ServiceError(
            "invalid_input",
            "farm_size_ha must be greater than zero.",
        )

    farm_size_margin_ha = _finite_number(
        plan.get("farm_size_margin_ha"),
        "farm_size_margin_ha",
    )
    if farm_size_margin_ha < 0:
        raise ServiceError(
            "invalid_input",
            "farm_size_margin_ha must not be negative.",
        )

    planting_date = _clean_text(plan.get("planting_date"))
    if not PLANTING_DATE_PATTERN.match(planting_date):
        raise ServiceError("invalid_input", "planting_date must use YYYY-MM-DD.")
    try:
        datetime.date.fromisoformat(planting_date)
    except ValueError:
        raise ServiceError(
            "invalid_input",
            "planting_date must be a real calendar date.",
        )

    harvest_period = _clean_text(plan.get("harvest_period"))
    if not HARVEST_PERIOD_PATTERN.match(harvest_period):
        raise ServiceError("invalid_input", "harvest_period must use YYYY-MM.")
    if harvest_period < planting_date[:7]:
        raise ServiceError(
            "invalid_input",
            "harvest_period cannot be earlier than the planting month.",
        )

    return {
        "crop_id": crop_id,
        "region_id": region_id,
        "location": location,
        "farm_size_ha": farm_size_ha,
        "farm_size_margin_ha": farm_size_margin_ha,
        "planting_date": planting_date,
        "harvest_period": harvest_period,
    }


def _empty_lookup():
    """Return the lookup section of the envelope with nothing resolved yet."""
    return {
        "crop_id": None,
        "plan_count": 0,
        "crop_record": None,
        "yield_record": None,
        "reference_used": None,
        "bands": None,
    }


def _envelope(plan, lookup, result, error):
    """Wrap one outcome in the documented input/lookup/result/error shape.

    The echoed plan is cleaned so every envelope stays valid strict JSON.
    """
    return {
        "input": _json_safe(plan),
        "lookup": lookup,
        "result": result,
        "error": error,
    }


def _resolve_bands(bands):
    """Return validated caller bands, or None when none were supplied."""
    if bands is None:
        return None
    try:
        return ENGINE.validate_bands(bands)
    except (TypeError, ValueError) as error:
        raise ServiceError("invalid_input", f"bands are not usable: {error}.")


def _resolve_source_labels(source_labels, *, demo=False):
    """Return traceable comparison-source labels.

    Demo mode is pinned to DEMO-2026. A non-demo comparison must provide at
    least one source label so a user-entered amount cannot look verified
    without provenance.
    """
    if demo:
        return ["DEMO-2026"]

    if isinstance(source_labels, str):
        raw_labels = [source_labels]
    elif isinstance(source_labels, (list, tuple)):
        raw_labels = list(source_labels)
    else:
        raw_labels = []

    if not raw_labels or any(
        not isinstance(value, str) or not value.strip()
        for value in raw_labels
    ):
        raise ServiceError(
            "invalid_input",
            "source_labels must contain one or more non-empty text labels.",
        )

    labels = ENGINE.normalize_source_labels(raw_labels)
    if not labels:
        raise ServiceError(
            "invalid_input",
            "source_labels must name the source of a non-demo comparison.",
        )
    return labels


def get_grci_for_plan(
    plan,
    comparison=None,
    bands=None,
    source_labels=None,
    use_demo_reference=False,
):
    """Return one validated service envelope.

    Historical yield is used for normal planning. The fixed synthetic
    DEMO-2026 yield and comparison are used only when use_demo_reference=True.
    A normal request without a comparison fails closed.
    """
    lookup = _empty_lookup()

    try:
        if not isinstance(use_demo_reference, bool):
            raise ServiceError(
                "invalid_input",
                "use_demo_reference must be true or false.",
            )
        if use_demo_reference and comparison is not None:
            raise ServiceError(
                "invalid_input",
                "Do not send comparison together with use_demo_reference=true.",
            )

        if use_demo_reference:
            if bands is not None:
                raise ServiceError(
                    "invalid_input",
                    "Fixed demo requests cannot override the demo bands.",
                )
            if source_labels is not None:
                raise ServiceError(
                    "invalid_input",
                    "Fixed demo source labels are pinned to DEMO-2026.",
                )
            resolved_bands = list(DEFAULT_BANDS)
        else:
            resolved_bands = _resolve_bands(bands)

        lookup["bands"] = (
            [[_json_band(upper), label] for upper, label in resolved_bands]
            if resolved_bands is not None
            else None
        )
        raw_plans = plan if isinstance(plan, list) else [plan]
        if not raw_plans:
            raise ServiceError(
                "invalid_input",
                "plans must contain at least one farmer plan.",
            )
        contexts = [validate_plan(item) for item in raw_plans]
        context = contexts[0]

        for other in contexts[1:]:
            if other["crop_id"] != context["crop_id"]:
                raise ServiceError(
                    "invalid_input",
                    "All farmer plans in one calculation must use the same crop.",
                )
            if other["region_id"] != context["region_id"]:
                raise ServiceError(
                    "invalid_input",
                    "All farmer plans in one calculation must use the same region.",
                )
            if not _same_text(other["location"], context["location"]):
                raise ServiceError(
                    "invalid_input",
                    "All farmer plans in one calculation must use the same location.",
                )
            if other["harvest_period"] != context["harvest_period"]:
                raise ServiceError(
                    "invalid_input",
                    "All farmer plans in one calculation must use the same harvest period.",
                )

        crop_id = context["crop_id"]
        lookup["crop_id"] = crop_id
        lookup["plan_count"] = len(contexts)

        crop_record = load_runtime_crops().get(crop_id)
        if crop_record is None:
            raise ServiceError(
                "crop_not_found",
                f"Crop '{crop_id}' is not in the committed runtime crop registry.",
            )
        lookup["crop_record"] = {
            "crop_id": crop_record.get("crop_id"),
            "display_name": crop_record.get("display_name"),
            "planning_supported": crop_record.get("planning_supported"),
            "coverage": copy.deepcopy(crop_record.get("coverage")),
        }
        if not ENGINE.is_planning_supported(crop_record):
            raise ServiceError(
                "crop_unsupported",
                f"Crop '{crop_id}' has no safe production and area join, so no "
                "supply figure is shown.",
            )

        if use_demo_reference:
            demo_plans = load_demo_plans().get(crop_id)
            if demo_plans is None:
                raise ServiceError(
                    "invalid_input",
                    f"No fixed demo plan fixture is committed for {crop_id}.",
                )
            requested_signature = sorted(
                _demo_plan_signature(item) for item in contexts
            )
            fixture_signature = sorted(
                _demo_plan_signature(item) for item in demo_plans
            )
            if requested_signature != fixture_signature:
                raise ServiceError(
                    "invalid_input",
                    "DEMO-2026 is locked to the committed farmer-plan fixture. "
                    "Use the fixed Tomato or Eggplant demo button.",
                )

            demo_row = load_demo_references().get(crop_id)
            if demo_row is None:
                raise ServiceError(
                    "invalid_input",
                    f"No fixed demo reference is committed for {crop_id}.",
                )
            reference = _validate_reference(
                demo_row,
                "demo comparison baseline",
                allow_internal=True,
            )
            reference["from_demo"] = True
            if reference["type"] != "demo_coordination_baseline":
                raise ServiceError(
                    "invalid_input",
                    "The committed demo reference type must stay "
                    "demo_coordination_baseline.",
                )
            demo_region = normalize_region_id(reference["geography"])
            if demo_region != context["region_id"]:
                raise ServiceError(
                    "invalid_input",
                    "The fixed demo reference is only valid for its committed region.",
                )
            demo_yield = _finite_number(
                demo_row.get("yield_mt_per_ha"),
                "demo reference yield",
            )
            if demo_yield <= 0:
                raise ServiceError(
                    "invalid_input",
                    "The committed demo yield must be greater than zero.",
                )
            if demo_row.get("source_id") != "DEMO-2026":
                raise ServiceError(
                    "invalid_input",
                    "The committed demo reference has an unexpected source id.",
                )
            if demo_row.get("data_status") != "derived_demo":
                raise ServiceError(
                    "invalid_input",
                    "The committed demo reference must stay marked derived_demo.",
                )
            yield_record = None
            yield_value = demo_yield
            yield_source = "DEMO-2026 synthetic yield"
            resolved_labels = _resolve_source_labels(None, demo=True)
        else:
            if comparison is None:
                raise ServiceError(
                    "comparison_required",
                    "A non-demo plan needs a traceable comparison reference. "
                    "TANIM does not substitute synthetic demand.",
                )
            reference = _validate_reference(comparison, "comparison")
            if reference["type"] == "demo_coordination_baseline":
                raise ServiceError(
                    "invalid_input",
                    "Use use_demo_reference=true for the committed demo baseline.",
                )
            _validate_reference_context(reference, context)
            resolved_labels = _resolve_source_labels(source_labels, demo=False)
            yield_record = ENGINE.reference_yield_for(
                load_yield_index(),
                crop_id,
                context["region_id"],
            )
            if yield_record is None:
                raise ServiceError(
                    "yield_not_found",
                    f"No committed {crop_id} yield row for region "
                    f"{context['region_id']}. TANIM never guesses a missing yield.",
                )
            yield_value = yield_record["avg_yield_mt_per_ha"]
            yield_source = _yield_source_text(yield_record)

        lookup["yield_record"] = yield_record
        evidence_status = (
            EVIDENCE_STATUS_FIXED_DEMO
            if use_demo_reference
            else EVIDENCE_STATUS_USER_PROVIDED
        )
        reference["evidence_status"] = evidence_status
        reference["evidence_verified"] = evidence_status == EVIDENCE_STATUS_REVIEWED
        lookup["reference_used"] = reference

        result = ENGINE.compute_grci(
            crop=crop_id,
            location=context["location"],
            harvest_period=context["harvest_period"],
            plans=[
                {
                    "crop_canonical": item["crop_id"],
                    "municipality": item["location"],
                    "harvest_period": item["harvest_period"],
                    "farm_size_ha": item["farm_size_ha"],
                    "farm_size_margin_ha": item["farm_size_margin_ha"],
                }
                for item in contexts
            ],
            reference_yield=yield_value,
            yield_source=yield_source,
            reference_amount=reference["amount"],
            reference_unit=reference["unit"],
            reference_type=reference["type"],
            reference_geography=reference["geography"],
            reference_period=reference["period"],
            crop_record=crop_record,
            bands=resolved_bands,
            source_labels=resolved_labels,
            yield_record=yield_record,
        )
    except ServiceError as error:
        return _envelope(
            plan,
            lookup,
            None,
            {"code": error.code, "message": error.message},
        )

    engine_code = ENGINE_ERROR_CODES.get(result.get("status"))
    if engine_code is not None:
        note = (
            result.get("uncertainty_note")
            or result.get("explanation")
            or "The engine rejected this plan."
        )
        return _envelope(plan, lookup, None, {"code": engine_code, "message": note})

    result["evidence_status"] = evidence_status
    result["evidence_verified"] = evidence_status == EVIDENCE_STATUS_REVIEWED
    result["evidence_status_note"] = {
        EVIDENCE_STATUS_FIXED_DEMO: (
            "Fixed synthetic DEMO-2026 fixture; not observed market demand."
        ),
        EVIDENCE_STATUS_USER_PROVIDED: (
            "User-provided comparison evidence; not independently reviewed or "
            "verified by TANIM."
        ),
        EVIDENCE_STATUS_REVIEWED: "Reviewed and verified by a trusted source integration.",
    }[evidence_status]
    result["provenance"]["evidence_status"] = result["evidence_status"]
    result["provenance"]["evidence_verified"] = result["evidence_verified"]
    if result["evidence_status"] != EVIDENCE_STATUS_REVIEWED:
        result["market_demand_wording_allowed"] = False

    return _envelope(plan, lookup, result, None)


def read_request_file(path):
    """Return a request payload with exactly one plan or plans key."""
    target = pathlib.Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as error:
        raise ServiceError(
            "invalid_input",
            f"Cannot read the request file {target.name}: {error}.",
        ) from error

    try:
        payload = _strict_json_loads(text)
    except ValueError as error:
        raise ServiceError(
            "invalid_input",
            f"Request file {target.name} is not valid JSON: {error}.",
        ) from error

    if not isinstance(payload, dict):
        raise ServiceError(
            "invalid_input",
            "Request file must contain a JSON object with a plan.",
        )
    has_plan = "plan" in payload
    has_plans = "plans" in payload
    if has_plan == has_plans:
        raise ServiceError(
            "invalid_input",
            'Request file must contain exactly one of "plan" or "plans".',
        )
    return payload


def build_envelope_from_request(payload):
    """Return the envelope for one request payload."""
    if not isinstance(payload, dict):
        return _envelope(
            None,
            _empty_lookup(),
            None,
            {
                "code": "invalid_input",
                "message": "Request payload must be a JSON object.",
            },
        )

    unknown = sorted(set(payload) - REQUEST_FIELDS)
    if unknown:
        return _envelope(
            None,
            _empty_lookup(),
            None,
            {
                "code": "invalid_input",
                "message": "Request contains unknown field(s): "
                + ", ".join(unknown)
                + ".",
            },
        )

    has_plan = "plan" in payload
    has_plans = "plans" in payload
    if has_plan == has_plans:
        return _envelope(
            None,
            _empty_lookup(),
            None,
            {
                "code": "invalid_input",
                "message": 'Request must contain exactly one of "plan" or "plans".',
            },
        )

    if has_plan and not isinstance(payload["plan"], dict):
        return _envelope(
            payload["plan"],
            _empty_lookup(),
            None,
            {
                "code": "invalid_input",
                "message": '"plan" must be a JSON object.',
            },
        )
    if has_plans and not isinstance(payload["plans"], list):
        return _envelope(
            payload["plans"],
            _empty_lookup(),
            None,
            {
                "code": "invalid_input",
                "message": '"plans" must be a JSON array.',
            },
        )

    plan_input = payload["plans"] if has_plans else payload["plan"]
    return get_grci_for_plan(
        plan_input,
        comparison=payload.get("comparison"),
        bands=payload.get("bands"),
        source_labels=payload.get("source_labels"),
        use_demo_reference=payload.get("use_demo_reference", False),
    )


def build_options():
    """Return frontend-safe crop, region, demo, and reference options."""
    runtime = load_runtime_crops()
    yield_index = load_yield_index()
    demo_references = load_demo_references()

    region_labels = {}
    regions_by_crop = {}
    for (crop_id, region_id), record in yield_index.items():
        crop_record = runtime.get(crop_id)
        if crop_record is None or not ENGINE.is_planning_supported(crop_record):
            continue
        regions_by_crop.setdefault(crop_id, set()).add(region_id)
        region_labels.setdefault(
            region_id,
            _clean_text(record.get("region_label")) or region_id,
        )

    demo_regions = {}
    for crop_id, reference in demo_references.items():
        region_id = normalize_region_id(reference.get("geography"))
        if region_id is not None:
            demo_regions.setdefault(crop_id, set()).add(region_id)

    rank = {region_id: index for index, region_id in enumerate(REGION_ORDER)}
    crops = []
    for crop_id in sorted(
        regions_by_crop,
        key=lambda value: (
            str(runtime[value].get("display_name") or value).casefold(),
            value,
        ),
    ):
        crop_record = runtime[crop_id]
        crop_regions = sorted(
            regions_by_crop[crop_id],
            key=lambda value: (rank.get(value, len(rank)), value),
        )
        crops.append(
            {
                "id": crop_id,
                "label": crop_record.get("display_name") or crop_id,
                "regions": crop_regions,
                "demo_regions": sorted(
                    demo_regions.get(crop_id, set()),
                    key=lambda value: (rank.get(value, len(rank)), value),
                ),
            }
        )

    regions = [
        {
            "id": region_id,
            "label": region_labels.get(region_id, region_id),
        }
        for region_id in REGION_ORDER
        if region_id in region_labels
    ]
    reference_types = []
    for reference_type in MANUAL_REFERENCE_TYPES:
        metadata = ENGINE.reference_metadata(reference_type)
        reference_types.append(
            {
                "id": reference_type,
                "label": metadata["label"],
                "scope": metadata["scope"],
                "quality": metadata["quality"],
            }
        )

    return {
        "crops": crops,
        "regions": regions,
        "reference_types": reference_types,
    }


class GrciRequestHandler(BaseHTTPRequestHandler):
    """Small local JSON API for the Step 7 web client."""

    server_version = "TANIM-MVP/0.1"

    def _send_json(self, status, payload):
        body = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in {"/api/health", "/api/options"}:
            try:
                options = build_options()
            except ServiceError as error:
                self._send_json(
                    500,
                    {
                        "error": {
                            "code": error.code,
                            "message": error.message,
                        }
                    },
                )
                return
            if self.path == "/api/health":
                self._send_json(
                    200,
                    {"status": "ok", "crop_count": len(options["crops"])},
                )
            else:
                self._send_json(200, options)
            return
        self._send_json(
            404,
            {"error": {"code": "not_found", "message": "Route not found."}},
        )

    def do_POST(self):
        if self.path != "/api/grci":
            self._send_json(
                404,
                {"error": {"code": "not_found", "message": "Route not found."}},
            )
            return

        if self.headers.get_content_type() != "application/json":
            self._send_json(
                415,
                {
                    "error": {
                        "code": "invalid_input",
                        "message": "Content-Type must be application/json.",
                    }
                },
            )
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_REQUEST_BYTES:
            self._send_json(
                413,
                {
                    "error": {
                        "code": "invalid_input",
                        "message": "Request body is too large.",
                    }
                },
            )
            return

        try:
            raw = self.rfile.read(length)
            payload = _strict_json_loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self._send_json(
                400,
                {
                    "error": {
                        "code": "invalid_input",
                        "message": "Request body must be valid UTF-8 JSON.",
                    }
                },
            )
            return

        envelope = build_envelope_from_request(payload)
        self._send_json(200 if envelope["error"] is None else 400, envelope)

    def log_message(self, format, *args):
        # Keep the pitch terminal quiet except for explicit startup text.
        return


def serve(host="127.0.0.1", port=8000):
    """Run the local Step 7 API until interrupted."""
    server = ThreadingHTTPServer((host, port), GrciRequestHandler)
    print(f"TANIM API listening on http://{host}:{server.server_port}")
    print("POST /api/grci | GET /api/options | GET /api/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run or serve the TANIM Step 7 GRCI service."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--demo",
        action="store_true",
        help="Run the committed fixed tomato demo request.",
    )
    source.add_argument(
        "--request",
        type=pathlib.Path,
        metavar="PATH",
        help="Run a plan/comparison request JSON file.",
    )
    source.add_argument(
        "--serve",
        action="store_true",
        help="Serve POST /api/grci for the local web client.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    if args.serve:
        if not 0 <= args.port <= 65535:
            parser.error("--port must be between 0 and 65535")
        serve(args.host, args.port)
        return 0

    request_path = DEMO_REQUEST_PATH if args.demo else args.request
    try:
        payload = read_request_file(request_path)
        envelope = build_envelope_from_request(payload)
    except ServiceError as error:
        envelope = _envelope(
            None,
            _empty_lookup(),
            None,
            {"code": error.code, "message": error.message},
        )

    try:
        output = json.dumps(envelope, ensure_ascii=False, allow_nan=False)
    except ValueError:
        envelope = _envelope(
            None,
            _empty_lookup(),
            None,
            {
                "code": "invalid_input",
                "message": "The envelope contains a value strict JSON cannot carry.",
            },
        )
        output = json.dumps(envelope, ensure_ascii=False, allow_nan=False)

    print(output)
    return 2 if envelope["error"] is not None else 0


if __name__ == "__main__":
    sys.exit(main())
