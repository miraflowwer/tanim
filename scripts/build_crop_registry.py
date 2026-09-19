#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import re
import unicodedata
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets" / "openstat_tables.json"
REGISTRY = ROOT / "datasets" / "crop_registry.json"
NCCAG = ROOT / "datasets" / "nccag_reference.json"
DEFAULT_OUT = ROOT / "datasets" / "generated" / "crop_registry.generated.json"
DEFAULT_COVERAGE = ROOT / "datasets" / "generated" / "crop_coverage.csv"
USER_AGENT = "TANIM/2026 crop registry builder"

CROP_HINTS = ("crop", "commodity", "item", "product")
SKIP_HINTS = (
    "geo", "region", "province", "location", "year", "month", "quarter",
    "semester", "period", "frequency", "unit", "indicator", "element",
)
COVERAGE_FAMILIES = ("production", "area", "farmgate", "retail", "sua")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def normalize_crop_label(label):
    text = unicodedata.normalize("NFKC", str(label)).strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slugify(label):
    return normalize_crop_label(label).replace(" ", "-")


def dimension_name(variable):
    return f"{variable.get('code', '')} {variable.get('text', '')}".lower()


def crop_dimension(metadata, table):
    variables = metadata.get("variables", [])
    if not variables:
        raise RuntimeError(f"{table['table_key']}: no metadata variables")

    hinted = [
        variable for variable in variables
        if any(hint in dimension_name(variable) for hint in CROP_HINTS)
        and not any(skip in dimension_name(variable) for skip in SKIP_HINTS)
    ]
    if len(hinted) == 1:
        return hinted[0]

    target_count = table.get("commodity_count")
    if target_count:
        matches = [
            variable for variable in variables
            if len(variable.get("values", [])) == target_count
            and not any(skip in dimension_name(variable) for skip in SKIP_HINTS)
        ]
        if len(matches) == 1:
            return matches[0]

    first_size = (table.get("verified_shape") or [None])[0]
    matches = [
        variable for variable in variables
        if len(variable.get("values", [])) == first_size
        and not any(skip in dimension_name(variable) for skip in SKIP_HINTS)
    ]
    if len(matches) == 1:
        return matches[0]

    raise RuntimeError(f"{table['table_key']}: crop dimension is ambiguous")


def source_labels(api_base, table):
    url = f"{api_base.rstrip('/')}/{table['path']}"
    metadata = http_json(url)
    variable = crop_dimension(metadata, table)
    return variable.get("valueTexts", variable.get("values", []))


def collect_label_index(manifest):
    index = {}
    for table in manifest["tables"]:
        labels = source_labels(manifest["api_base"], table)
        for label in labels:
            key = normalize_crop_label(label)
            if not key:
                continue
            record = index.setdefault(key, {"labels": {}, "families": {}})
            record["labels"].setdefault(table["table_key"], []).append(label)
            record["families"].setdefault(table["family"], []).append(table["table_key"])
    return index


def override_lookup(config):
    result = {}
    for item in config.get("manual_overrides", []):
        for alias in item.get("aliases", []):
            key = normalize_crop_label(alias)
            if key in result and result[key]["crop_id"] != item["crop_id"]:
                raise RuntimeError(f"duplicate manual alias: {alias}")
            result[key] = item
    return result


def nccag_lookup(nccag):
    return {
        normalize_crop_label(layer): layer
        for layer in nccag.get("crop_suitability_layers", [])
    }


def nccag_context(key, override, layers):
    if override and override.get("nccag_layer"):
        layer = override["nccag_layer"]
        if normalize_crop_label(layer) not in layers:
            raise RuntimeError(
                f"{override['crop_id']}: unknown NCCAG layer {layer}"
            )
        return {
            "available": True,
            "layer": layer,
            "specificity": override.get("nccag_specificity", "manual"),
            "mapping": "manual_override",
        }

    if key in layers:
        return {
            "available": True,
            "layer": layers[key],
            "specificity": "direct_label",
            "mapping": "exact_normalized_label",
        }

    return {
        "available": False,
        "layer": None,
        "specificity": None,
        "mapping": None,
    }


def make_runtime_registry(index, config, nccag):
    overrides = override_lookup(config)
    layers = nccag_lookup(nccag)
    crops = []
    used_ids = set()

    for key in sorted(index):
        entry = index[key]
        families = set(entry["families"])
        if not {"production", "area"} <= families:
            continue

        override = overrides.get(key)
        crop_id = override["crop_id"] if override else slugify(key)
        if crop_id in used_ids:
            raise RuntimeError(f"duplicate generated crop_id: {crop_id}")
        used_ids.add(crop_id)

        context = nccag_context(key, override, layers)
        display_name = override["display_name"] if override else key.title()
        coverage = {family: family in families for family in COVERAGE_FAMILIES}
        coverage["nccag"] = context["available"]

        crop = {
            "crop_id": crop_id,
            "display_name": display_name,
            "canonical_label": key,
            "planning_supported": True,
            "coverage": coverage,
            "nccag": context,
            "source_tables": {
                family: sorted(set(table_keys))
                for family, table_keys in sorted(entry["families"].items())
            },
            "source_labels": {
                table_key: sorted(set(labels))
                for table_key, labels in sorted(entry["labels"].items())
            },
            "join_method": "exact_normalized_label",
        }
        if coverage["sua"]:
            crop["sua_scope"] = "national"
        if override:
            crop["manual_override"] = {
                field: value for field, value in override.items()
                if field != "aliases"
            }
        crops.append(crop)

    runtime = {
        "schema_version": config["schema_version"],
        "verified_as_of": config["verified_as_of"],
        "source_manifest_verified_as_of": read_json(MANIFEST)["verified_as_of"],
        "scope": config["scope"],
        "join_method": "exact_normalized_label",
        "planning_rule": "production_and_area_required",
        "crop_count": len(crops),
        "crops": crops,
    }
    validate_runtime_registry(runtime)
    return runtime


def validate_runtime_registry(runtime):
    crops = runtime["crops"]
    ids = [crop["crop_id"] for crop in crops]
    if len(ids) != len(set(ids)):
        raise RuntimeError("runtime crop registry has duplicate crop_id values")
    if not crops:
        raise RuntimeError("No crops have both production and area coverage")

    for crop in crops:
        coverage = crop["coverage"]
        if not coverage["production"] or not coverage["area"]:
            raise RuntimeError(
                f"{crop['crop_id']}: planning crop lacks production or area coverage"
            )


def coverage_rows(runtime):
    rows = []
    for crop in runtime["crops"]:
        coverage = crop["coverage"]
        rows.append({
            "crop_id": crop["crop_id"],
            "display_name": crop["display_name"],
            "production": "yes" if coverage["production"] else "no",
            "area": "yes" if coverage["area"] else "no",
            "farmgate": "yes" if coverage["farmgate"] else "no",
            "retail": "yes" if coverage["retail"] else "no",
            "sua_context": "yes" if coverage["sua"] else "no",
            "sua_scope": crop.get("sua_scope", ""),
            "nccag_context": "yes" if coverage["nccag"] else "no",
            "nccag_layer": crop["nccag"]["layer"] or "",
            "nccag_specificity": crop["nccag"]["specificity"] or "",
            "demo_crop": "yes" if crop.get("manual_override", {}).get("demo_crop") else "no",
        })
    return rows


def write_runtime_registry(path, runtime):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(runtime, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_coverage_csv(path, runtime):
    rows = coverage_rows(runtime)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "crop_id", "display_name", "production", "area", "farmgate", "retail",
        "sua_context", "sua_scope", "nccag_context", "nccag_layer",
        "nccag_specificity", "demo_crop",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def audit_committed_snapshot(runtime, snapshot_path):
    if not snapshot_path.exists():
        return

    committed = read_json(snapshot_path)
    current = {crop["crop_id"]: crop for crop in runtime["crops"]}
    missing = sorted(
        crop["crop_id"] for crop in committed.get("crops", [])
        if crop["crop_id"] not in current
    )
    if missing:
        raise RuntimeError(
            "Previously supported Explorer crops disappeared: " + ", ".join(missing)
        )

    downgraded = []
    for old in committed.get("crops", []):
        new = current[old["crop_id"]]
        for family in ("production", "area"):
            if old.get("coverage", {}).get(family) and not new["coverage"].get(family):
                downgraded.append(f"{old['crop_id']}:{family}")
    if downgraded:
        raise RuntimeError(
            "Required crop coverage was downgraded: " + ", ".join(downgraded)
        )


def main():
    parser = argparse.ArgumentParser(
        description="Build TANIM's safe cross-source crop registry from PSA metadata."
    )
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--coverage-output",
        type=pathlib.Path,
        default=DEFAULT_COVERAGE,
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Build and audit the live registry without replacing generated files.",
    )
    args = parser.parse_args()

    manifest = read_json(MANIFEST)
    config = read_json(REGISTRY)
    nccag = read_json(NCCAG)
    index = collect_label_index(manifest)
    runtime = make_runtime_registry(index, config, nccag)

    if args.check_only:
        audit_committed_snapshot(runtime, args.output)
        print(
            f"OK: {runtime['crop_count']} Explorer crops have safe production "
            "and area joins"
        )
        return

    write_runtime_registry(args.output, runtime)
    write_coverage_csv(args.coverage_output, runtime)
    print(f"Wrote {runtime['crop_count']} crops to {args.output}")
    print(f"Wrote coverage matrix to {args.coverage_output}")


if __name__ == "__main__":
    main()
