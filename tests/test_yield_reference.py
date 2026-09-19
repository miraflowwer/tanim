import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DS = ROOT / "datasets"
GENERATED = DS / "generated"
DOCS = ROOT / "docs"

DETAILED = GENERATED / "yield_reference.csv"
SUMMARY = GENERATED / "yield_summary.csv"
DOCS_PATH = DOCS / "YIELD_REFERENCE.md"

REF_PERIOD = "2021-2025"
REF_YEARS = {"2021", "2022", "2023", "2024", "2025"}
LUZON_IDS = {"NCR", "CAR", "I", "II", "III", "IV-A", "MIMAROPA", "V"}
BANNED = ("Visayas", "Mindanao", "Philippines", "BARMM", "Caraga")


def load_detailed():
    with DETAILED.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def load_summary():
    with SUMMARY.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def test_yield_files_exist_and_schema():
    assert DETAILED.exists()
    assert SUMMARY.exists()
    assert DOCS_PATH.exists()
    fields, detailed = load_detailed()
    assert fields == [
        "crop_id", "display_name", "region_id", "region_label",
        "year", "period", "production_mt", "area_ha",
        "yield_mt_per_ha", "production_table", "area_table",
        "source_id", "data_status",
    ]
    assert detailed
    fields, summary = load_summary()
    assert fields == [
        "crop_id", "display_name", "region_id", "region_label",
        "ref_period", "n_years", "avg_yield_mt_per_ha",
        "min_yield_mt_per_ha", "max_yield_mt_per_ha",
        "unit", "source_id", "data_status",
    ]
    assert summary


def test_yield_math_is_production_divided_by_area():
    _, detailed = load_detailed()
    for row in detailed:
        prod = float(row["production_mt"])
        area = float(row["area_ha"])
        y = float(row["yield_mt_per_ha"])
        assert prod >= 0
        assert area > 0
        assert y >= 0
        assert abs((prod / area) - y) < 0.01


def test_summary_averages_several_complete_years():
    _, detailed = load_detailed()
    _, summary = load_summary()
    annual_by_key = {}
    for row in detailed:
        if row["period"] != "Annual":
            continue
        if row["year"] not in REF_YEARS:
            continue
        annual_by_key.setdefault((row["crop_id"], row["region_id"]), []).append(float(row["yield_mt_per_ha"]))
    assert annual_by_key
    for row in summary:
        assert row["ref_period"] == REF_PERIOD
        assert int(row["n_years"]) == 5
        assert row["unit"] == "mt_per_ha"
        key = (row["crop_id"], row["region_id"])
        values = annual_by_key.get(key, [])
        assert values
        assert int(row["n_years"]) == len(values)
        avg = float(row["avg_yield_mt_per_ha"])
        ymin = float(row["min_yield_mt_per_ha"])
        ymax = float(row["max_yield_mt_per_ha"])
        assert ymin <= avg <= ymax
        assert abs(avg - sum(values) / len(values)) < 0.02
        assert abs(ymin - min(values)) < 0.02
        assert abs(ymax - max(values)) < 0.02


def test_yield_scope_is_luzon_only():
    _, detailed = load_detailed()
    _, summary = load_summary()
    detail_keys = [(r["crop_id"], r["region_id"], r["year"], r["period"]) for r in detailed]
    summary_keys = [(r["crop_id"], r["region_id"]) for r in summary]
    assert len(detail_keys) == len(set(detail_keys))
    assert len(summary_keys) == len(set(summary_keys))
    for row in detailed + summary:
        assert row["region_id"] in LUZON_IDS
    text = DETAILED.read_text(encoding="utf-8") + SUMMARY.read_text(encoding="utf-8")
    for banned in BANNED:
        assert banned not in text
    scope = json.loads((DS / "luzon_scope.json").read_text(encoding="utf-8"))
    scope_ids = {region["id"] for region in scope["regions"]}
    assert LUZON_IDS <= scope_ids


def test_yield_crops_are_valid_registry_crops():
    registry = json.loads((GENERATED / "crop_registry.generated.json").read_text(encoding="utf-8"))
    valid = {crop["crop_id"] for crop in registry["crops"] if crop.get("planning_supported")}
    assert len(valid) == 313
    _, detailed = load_detailed()
    _, summary = load_summary()
    detailed_crops = {row["crop_id"] for row in detailed}
    summary_crops = {row["crop_id"] for row in summary}
    assert detailed_crops <= valid
    assert summary_crops <= valid
    assert summary_crops <= detailed_crops
    assert ("tomato", "IV-A") in {(r["crop_id"], r["region_id"]) for r in summary}
    assert ("eggplant", "IV-A") in {(r["crop_id"], r["region_id"]) for r in summary}


def test_yield_bridge_from_hectares_to_production():
    _, summary = load_summary()
    by_key = {(r["crop_id"], r["region_id"]): r for r in summary}
    tomato = float(by_key[("tomato", "IV-A")]["avg_yield_mt_per_ha"])
    eggplant = float(by_key[("eggplant", "IV-A")]["avg_yield_mt_per_ha"])
    assert tomato > 0 and eggplant > 0
    # Bridge: expected production equals area times average yield.
    assert abs((2.0 * tomato) - 27.89) < 0.05
    assert abs((1.5 * eggplant) - 24.61) < 0.05


def test_yield_docs_use_plain_language():
    text = DOCS_PATH.read_text(encoding="utf-8")
    assert "Yield = Production in metric tons divided by Harvested area in hectares." in text
    assert "five full years" in text
    assert "2021-2025" in text
    assert "Expected production = Area in hectares times Average yield." in text
    assert "not market demand" in text
    assert "not quarter specific" in text
    # Style guard for docs: keep plain formatting.
    assert "—" not in text


def test_yield_numeric_values_are_non_negative():
    _, detailed = load_detailed()
    _, summary = load_summary()
    for row in detailed:
        for field in ("production_mt", "area_ha", "yield_mt_per_ha"):
            assert float(row[field]) >= 0
    for row in summary:
        for field in ("avg_yield_mt_per_ha", "min_yield_mt_per_ha", "max_yield_mt_per_ha"):
            assert float(row[field]) >= 0


if __name__ == "__main__":
    tests = [name for name in globals() if name.startswith("test_")]
    for name in sorted(tests):
        globals()[name]()
    print(f"OK: {len(tests)} yield reference checks passed")
