#!/usr/bin/env python3
"""TANIM MVP backend service.

One farmer plan goes through three deterministic steps:

1. Validate the plan and resolve its crop, region, and comparison reference.
2. Look up the committed regional yield and the comparison reference.
3. Call scripts/grci.py compute_grci() and wrap the result in a JSON envelope.

Rules kept from docs/GRCI_SPEC.md and specs/mvp-backend.md:

- scripts/grci.py owns every formula, field, and risk label. This module only
  calls it, so there is no second copy of the calculation.
- Only committed local files are read. No network module is imported and no
  network call is made, so the demo works with the network unplugged.
- Nothing is guessed. An unknown crop, an unsupported crop, a missing
  crop-region yield row, or an unusable comparison is an error envelope.
- Crop lookup uses the manual registry aliases only (exact match, no
  substring or fuzzy match). planning_supported = False is crop_unsupported.
  Both committed demo aliases (tomato, eggplant) map to supported crops, so
  that code only fires once an unsupported crop gets an alias.
- Region lookup is exact on (crop_id, region_id) after the request region is
  normalized. The request may use IV-A or a label such as CALABARZON (IV-A).
- A missing comparison falls back to datasets/demo_coordination_baseline.csv
  and marks the reference with from_demo = True.
- The error envelope keeps the four documented codes: yield_not_found,
  crop_not_found, crop_unsupported, invalid_input. Engine states invalid,
  unsupported, and incomplete are translated into those codes instead of
  leaking a raw engine result.
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


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
DATASETS = ROOT / "datasets"
GENERATED = DATASETS / "generated"

CROP_REGISTRY_PATH = DATASETS / "crop_registry.json"
RUNTIME_REGISTRY_PATH = GENERATED / "crop_registry.generated.json"
YIELD_SUMMARY_PATH = GENERATED / "yield_summary.csv"
DEMO_BASELINE_PATH = DATASETS / "demo_coordination_baseline.csv"
DEMO_REQUEST_PATH = ROOT / "examples" / "tomato_calabarzon_request.json"

# Caller-overridable demo bands. These are not final product thresholds.
DEFAULT_BANDS = [
    (1.0, "low"),
    (1.5, "watch"),
    (float("inf"), "high"),
]

DEFAULT_SOURCE_LABELS = ["PSA-OPENSTAT-CROPS", "DEMO-2026"]

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


def _read_json_file(path, what):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
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
    """Return {alias: crop_id} from the manual crop registry.

    The manual registry supplies aliases only. Crop support comes from the
    generated runtime registry.
    """
    global _CROP_ALIASES
    if path is None and _CROP_ALIASES is not None:
        return _CROP_ALIASES

    target = pathlib.Path(path) if path is not None else CROP_REGISTRY_PATH
    payload = _read_json_file(target, "crop registry")
    if not isinstance(payload, dict):
        raise ServiceError(
            "invalid_input",
            f"Cannot read the committed crop registry ({target.name}): "
            "expected a JSON object.",
        )

    aliases = {}
    for record in payload.get("manual_overrides", []):
        if not isinstance(record, dict):
            continue
        crop_id = _clean_text(record.get("crop_id"))
        if crop_id is None:
            continue
        labels = list(record.get("aliases") or [])
        labels.append(record.get("display_name"))
        labels.append(crop_id)
        for label in labels:
            key = _crop_key(label)
            if key:
                aliases.setdefault(key, crop_id)

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

    crops = {}
    for record in payload.get("crops", []):
        if not isinstance(record, dict):
            continue
        crop_id = _clean_text(record.get("crop_id"))
        if crop_id:
            crops[crop_id] = record

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
            rows = list(csv.DictReader(handle))
    except OSError as error:
        raise ServiceError(
            "invalid_input",
            f"Cannot read the committed demo baseline ({target.name}): {error}.",
        ) from error

    references = {}
    for row in rows:
        crop_id = _crop_key(row.get("crop_canonical"))
        if crop_id is None:
            continue
        references[crop_id] = {
            "amount": row.get("reference_qty_mt"),
            "unit": "MT",
            "type": _clean_text(row.get("reference_type")),
            "geography": _clean_text(row.get("reference_geography")),
            "period": _clean_text(row.get("reference_period")),
        }

    if path is None:
        _DEMO_REFERENCES = references
    return references


def _yield_source_text(yield_record):
    """Describe the committed yield row used for one result."""
    source_id = _clean_text(yield_record.get("source_id")) or "unknown source"
    ref_period = _clean_text(yield_record.get("ref_period")) or "unknown period"
    return f"{source_id} {ref_period} regional average yield"


def _validate_reference(reference, source_label):
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

    return {
        "amount": amount,
        "unit": unit,
        "type": reference_type,
        "geography": _clean_text(reference["geography"]),
        "period": _clean_text(reference["period"]),
        "from_demo": False,
    }


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
            f"Unknown crop '{_clean_text(plan.get('crop'))}'. The manual crop "
            "registry matches aliases exactly; add one before planning this "
            "crop.",
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
    """Return validated risk bands, defaulting to the demo bands."""
    if bands is None:
        return list(DEFAULT_BANDS)
    try:
        return ENGINE.validate_bands(bands)
    except (TypeError, ValueError) as error:
        raise ServiceError("invalid_input", f"bands are not usable: {error}.")


def _resolve_source_labels(source_labels):
    """Return clean source labels, defaulting to the committed sources."""
    labels = ENGINE.normalize_source_labels(
        DEFAULT_SOURCE_LABELS if source_labels is None else source_labels
    )
    if not labels:
        raise ServiceError(
            "invalid_input",
            "source_labels must keep at least one non-empty label.",
        )
    return labels


def get_grci_for_plan(plan, comparison=None, bands=None, source_labels=None):
    """Return the GRCI envelope for one farmer plan.

    plan: crop, region_id, location or municipality, farm_size_ha,
        farm_size_margin_ha, planting_date, harvest_period.
    comparison: a full five-field reference, or None for the committed demo
        baseline fallback. A partial comparison is invalid_input.
    bands: caller risk bands; defaults to the demo bands.
    source_labels: caller source labels; defaults to the committed sources.

    Never raises on bad or missing data. Failures come back as
    {"result": None, "error": {"code": ..., "message": ...}}.
    """
    lookup = _empty_lookup()

    try:
        resolved_bands = _resolve_bands(bands)
        lookup["bands"] = [
            [_json_band(upper), label] for upper, label in resolved_bands
        ]
        resolved_labels = _resolve_source_labels(source_labels)
        context = validate_plan(plan)

        crop_id = context["crop_id"]
        lookup["crop_id"] = crop_id

        crop_record = load_runtime_crops().get(crop_id)
        if crop_record is None:
            raise ServiceError(
                "crop_not_found",
                f"Crop '{crop_id}' is not in the committed runtime crop "
                "registry.",
            )
        crop_record = copy.deepcopy(crop_record)
        lookup["crop_record"] = crop_record
        if not ENGINE.is_planning_supported(crop_record):
            raise ServiceError(
                "crop_unsupported",
                f"Crop '{crop_id}' has no safe production and area join, so no "
                "supply figure is shown.",
            )

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
        lookup["yield_record"] = yield_record

        if comparison is None:
            demo_row = load_demo_references().get(crop_id)
            if demo_row is None:
                raise ServiceError(
                    "invalid_input",
                    f"No demo comparison baseline is committed for {crop_id}. "
                    "Send a comparison record to compare planned supply.",
                )
            reference = _validate_reference(demo_row, "demo comparison baseline")
            reference["from_demo"] = True
        else:
            reference = _validate_reference(comparison, "comparison")
        lookup["reference_used"] = reference

        result = ENGINE.compute_grci(
            crop=crop_id,
            location=context["location"],
            harvest_period=context["harvest_period"],
            plans=[
                {
                    "crop_canonical": crop_id,
                    "municipality": context["location"],
                    "harvest_period": context["harvest_period"],
                    "farm_size_ha": context["farm_size_ha"],
                    "farm_size_margin_ha": context["farm_size_margin_ha"],
                }
            ],
            reference_yield=yield_record["avg_yield_mt_per_ha"],
            yield_source=_yield_source_text(yield_record),
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

    return _envelope(plan, lookup, result, None)


def read_request_file(path):
    """Return a request payload with a plan key, or raise ServiceError."""
    target = pathlib.Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as error:
        raise ServiceError(
            "invalid_input",
            f"Cannot read the request file {target.name}: {error}.",
        ) from error

    try:
        payload = json.loads(text)
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
    if "plan" not in payload:
        raise ServiceError(
            "invalid_input",
            'Request file needs a "plan" object, plus optional "comparison", '
            '"bands", and "source_labels".',
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
    return get_grci_for_plan(
        payload.get("plan"),
        comparison=payload.get("comparison"),
        bands=payload.get("bands"),
        source_labels=payload.get("source_labels"),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Run one TANIM farmer plan through the GRCI engine and print the "
            "JSON envelope."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--demo",
        action="store_true",
        help="Run the committed tomato / CALABARZON sample request.",
    )
    source.add_argument(
        "--request",
        type=pathlib.Path,
        metavar="PATH",
        help="Run a plan/comparison request JSON file.",
    )
    args = parser.parse_args(argv)

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
        text = json.dumps(envelope, ensure_ascii=False, allow_nan=False)
    except ValueError:
        # Safety net: never traceback on stage. Every other branch already
        # emits strict JSON, so this only fires on unexpected data.
        envelope = _envelope(
            None,
            _empty_lookup(),
            None,
            {
                "code": "invalid_input",
                "message": "The envelope holds a value that strict JSON cannot carry.",
            },
        )
        text = json.dumps(envelope, ensure_ascii=False, allow_nan=False)

    print(text)
    return 2 if envelope["error"] is not None else 0


if __name__ == "__main__":
    sys.exit(main())