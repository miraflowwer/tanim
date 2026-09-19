#!/usr/bin/env python3
import argparse
import json
import pathlib
import re
import unicodedata
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets" / "openstat_tables.json"
REGISTRY = ROOT / "datasets" / "crop_registry.json"
DEFAULT_OUT = ROOT / "datasets" / "generated" / "crop_registry.generated.json"
USER_AGENT = "TANIM/2026 crop registry builder"

CROP_HINTS = ("crop", "commodity", "item", "product")
SKIP_HINTS = (
    "geo", "region", "province", "location", "year", "month", "quarter",
    "semester", "period", "frequency", "unit", "indicator", "element",
)


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


def make_runtime_registry(index, config):
    overrides = override_lookup(config)
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

        display_name = override["display_name"] if override else key.title()
        crop = {
            "crop_id": crop_id,
            "display_name": display_name,
            "canonical_label": key,
            "planning_supported": True,
            "matched_families": sorted(families),
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
        if override:
            crop["manual_override"] = {
                field: value for field, value in override.items()
                if field != "aliases"
            }
        crops.append(crop)

    return {
        "schema_version": config["schema_version"],
        "scope": config["scope"],
        "join_method": "exact_normalized_label",
        "crop_count": len(crops),
        "crops": crops,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Build TANIM's safe cross-source crop registry from PSA metadata."
    )
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Build and validate the registry without writing a file.",
    )
    args = parser.parse_args()

    manifest = read_json(MANIFEST)
    config = read_json(REGISTRY)
    index = collect_label_index(manifest)
    registry = make_runtime_registry(index, config)

    if registry["crop_count"] == 0:
        raise RuntimeError("No crops have both production and area coverage")

    if args.check_only:
        print(f"OK: {registry['crop_count']} planning crops can be joined safely")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {registry['crop_count']} crops to {args.output}")


if __name__ == "__main__":
    main()
