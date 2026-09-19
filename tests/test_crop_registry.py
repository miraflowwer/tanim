import csv
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DS = ROOT / "datasets"


def load_builder():
    path = ROOT / "scripts" / "build_crop_registry.py"
    spec = importlib.util.spec_from_file_location("build_crop_registry", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registry_rules_are_safe():
    registry = json.loads((DS / "crop_registry.json").read_text(encoding="utf-8"))
    assert registry["scope"] == "Luzon"
    assert registry["auto_join"]["method"] == "exact_normalized_label"
    assert registry["auto_join"]["required_families_for_planning"] == [
        "production", "area"
    ]
    assert "substring matches" in registry["auto_join"]["never_auto_merge"]

    overrides = {item["crop_id"]: item for item in registry["manual_overrides"]}
    assert {"tomato", "eggplant"} <= set(overrides)
    for crop_id in ("tomato", "eggplant"):
        assert overrides[crop_id]["demo_crop"] is True
        assert overrides[crop_id]["nccag_layer"] == "Vegetables"
        assert overrides[crop_id]["nccag_specificity"] == "group_layer"


def test_normalization_does_not_collapse_varieties():
    builder = load_builder()
    assert builder.normalize_crop_label(" Tomato ") == "tomato"
    assert builder.normalize_crop_label("Tomato, Native") == "tomato native"
    assert builder.normalize_crop_label("Tomato") != builder.normalize_crop_label("Tomato, Native")


def test_runtime_registry_requires_production_and_area():
    builder = load_builder()
    config = {
        "schema_version": 1,
        "scope": "Luzon",
        "manual_overrides": [
            {
                "crop_id": "tomato",
                "display_name": "Tomato",
                "aliases": ["tomato"],
                "demo_crop": True,
                "nccag_layer": "Vegetables",
            }
        ],
    }
    index = {
        "tomato": {
            "labels": {
                "PSA-PROD": ["Tomato"],
                "PSA-AREA": ["Tomato"],
                "PSA-FG": ["Tomato"],
            },
            "families": {
                "production": ["PSA-PROD"],
                "area": ["PSA-AREA"],
                "farmgate": ["PSA-FG"],
            },
        },
        "eggplant": {
            "labels": {"PSA-PROD": ["Eggplant"]},
            "families": {"production": ["PSA-PROD"]},
        },
    }

    runtime = builder.make_runtime_registry(index, config)
    assert runtime["crop_count"] == 1
    crop = runtime["crops"][0]
    assert crop["crop_id"] == "tomato"
    assert crop["planning_supported"] is True
    assert crop["join_method"] == "exact_normalized_label"
    assert "farmgate" in crop["matched_families"]


def test_demo_farm_size_has_explicit_margin():
    with open(DS / "demo_farm_plans.csv", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    for row in rows:
        estimate = float(row["farm_size_ha"])
        margin = float(row["farm_size_margin_ha"])
        assert estimate > 0
        assert margin >= 0
        assert max(0.0, estimate - margin) <= estimate <= estimate + margin
        assert margin == 0.0


if __name__ == "__main__":
    tests = [name for name in globals() if name.startswith("test_")]
    for name in sorted(tests):
        globals()[name]()
    print(f"OK: {len(tests)} crop registry checks passed")
