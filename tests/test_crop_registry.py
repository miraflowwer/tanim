import csv
import importlib.util
import json
import pathlib
import tempfile

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
    assert (
        builder.normalize_crop_label("Tomato")
        != builder.normalize_crop_label("Tomato, Native")
    )


def test_runtime_registry_requires_production_and_area():
    builder = load_builder()
    config = {
        "schema_version": 1,
        "verified_as_of": "2026-09-19",
        "scope": "Luzon",
        "manual_overrides": [
            {
                "crop_id": "tomato",
                "display_name": "Tomato",
                "aliases": ["tomato"],
                "demo_crop": True,
                "nccag_layer": "Vegetables",
                "nccag_specificity": "group_layer",
            }
        ],
    }
    nccag = {"crop_suitability_layers": ["Vegetables", "Cassava"]}
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
        "cassava": {
            "labels": {
                "PSA-PROD": ["Cassava"],
                "PSA-AREA": ["Cassava"],
                "PSA-SUA": ["Cassava"],
            },
            "families": {
                "production": ["PSA-PROD"],
                "area": ["PSA-AREA"],
                "sua": ["PSA-SUA"],
            },
        },
        "eggplant": {
            "labels": {"PSA-PROD": ["Eggplant"]},
            "families": {"production": ["PSA-PROD"]},
        },
    }

    runtime = builder.make_runtime_registry(index, config, nccag)
    assert runtime["crop_count"] == 2
    crops = {crop["crop_id"]: crop for crop in runtime["crops"]}

    tomato = crops["tomato"]
    assert tomato["planning_supported"] is True
    assert tomato["coverage"]["farmgate"] is True
    assert tomato["coverage"]["retail"] is False
    assert tomato["nccag"]["layer"] == "Vegetables"
    assert tomato["nccag"]["mapping"] == "manual_override"

    cassava = crops["cassava"]
    assert cassava["coverage"]["sua"] is True
    assert cassava["sua_scope"] == "national"
    assert cassava["nccag"]["layer"] == "Cassava"
    assert cassava["nccag"]["mapping"] == "exact_normalized_label"


def test_coverage_matrix_has_required_columns():
    builder = load_builder()
    runtime = {
        "crops": [{
            "crop_id": "tomato",
            "display_name": "Tomato",
            "coverage": {
                "production": True,
                "area": True,
                "farmgate": True,
                "retail": True,
                "sua": True,
                "nccag": True,
            },
            "sua_scope": "national",
            "nccag": {
                "available": True,
                "layer": "Vegetables",
                "specificity": "group_layer",
            },
            "manual_override": {"demo_crop": True},
        }]
    }
    with tempfile.TemporaryDirectory() as directory:
        target = pathlib.Path(directory) / "coverage.csv"
        builder.write_coverage_csv(target, runtime)
        with target.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

    assert len(rows) == 1
    row = rows[0]
    assert row["production"] == "yes"
    assert row["area"] == "yes"
    assert row["farmgate"] == "yes"
    assert row["retail"] == "yes"
    assert row["sua_context"] == "yes"
    assert row["sua_scope"] == "national"
    assert row["nccag_context"] == "yes"
    assert row["nccag_layer"] == "Vegetables"


def test_snapshot_audit_detects_removed_crop():
    builder = load_builder()
    runtime = {"crops": [{
        "crop_id": "tomato",
        "coverage": {"production": True, "area": True},
    }]}
    committed = {"crops": [
        {
            "crop_id": "tomato",
            "coverage": {"production": True, "area": True},
        },
        {
            "crop_id": "eggplant",
            "coverage": {"production": True, "area": True},
        },
    ]}
    with tempfile.TemporaryDirectory() as directory:
        path = pathlib.Path(directory) / "snapshot.json"
        path.write_text(json.dumps(committed), encoding="utf-8")
        try:
            builder.audit_committed_snapshot(runtime, path)
        except RuntimeError as error:
            assert "eggplant" in str(error)
        else:
            raise AssertionError("removed crop was not detected")


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
