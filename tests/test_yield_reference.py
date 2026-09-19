import csv
import importlib.util
import json
import math
import pathlib
import tempfile


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
PERIODS = {
    "Quarter1",
    "Quarter2",
    "Semester1",
    "Quarter3",
    "Quarter4",
    "Semester2",
    "Annual",
}
TABLE_PAIRS = {
    ("PSA-PROD-PALAY-CORN", "PSA-AREA-PALAY-CORN"),
    ("PSA-PROD-NONFOOD", "PSA-AREA-NONFOOD"),
    ("PSA-PROD-FRUITS", "PSA-AREA-FRUITS"),
    ("PSA-PROD-VEG-ROOT", "PSA-AREA-VEG-ROOT"),
}


def load_builder():
    path = ROOT / "scripts" / "build_yield_reference.py"
    spec = importlib.util.spec_from_file_location(
        "build_yield_reference",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_detailed():
    with DETAILED.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def load_summary():
    with SUMMARY.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def finite(value):
    return math.isfinite(float(value))


def test_yield_files_exist_and_schema():
    assert DETAILED.exists()
    assert SUMMARY.exists()
    assert DOCS_PATH.exists()

    fields, detailed = load_detailed()
    assert fields == [
        "crop_id",
        "display_name",
        "region_id",
        "region_label",
        "year",
        "period",
        "production_mt",
        "area_ha",
        "yield_mt_per_ha",
        "production_table",
        "area_table",
        "source_id",
        "data_status",
    ]
    assert detailed

    fields, summary = load_summary()
    assert fields == [
        "crop_id",
        "display_name",
        "region_id",
        "region_label",
        "ref_period",
        "n_years",
        "avg_yield_mt_per_ha",
        "min_yield_mt_per_ha",
        "max_yield_mt_per_ha",
        "unit",
        "source_id",
        "data_status",
    ]
    assert summary


def test_detailed_rows_are_unique_finite_and_traceable():
    _, detailed = load_detailed()
    keys = set()

    for row in detailed:
        key = (
            row["crop_id"],
            row["region_id"],
            row["year"],
            row["period"],
        )
        assert key not in keys
        keys.add(key)

        assert row["crop_id"]
        assert row["display_name"]
        assert row["region_id"] in LUZON_IDS
        assert row["year"] in REF_YEARS
        assert row["period"] in PERIODS
        assert (
            row["production_table"],
            row["area_table"],
        ) in TABLE_PAIRS
        assert row["source_id"] == "PSA-OPENSTAT-CROPS"
        assert row["data_status"] == "observed"

        production = float(row["production_mt"])
        area = float(row["area_ha"])
        yield_value = float(row["yield_mt_per_ha"])
        assert finite(production)
        assert finite(area)
        assert finite(yield_value)
        assert production >= 0
        assert area > 0
        assert yield_value >= 0
        assert abs((production / area) - yield_value) <= 0.01


def test_summary_matches_unique_annual_years():
    _, detailed = load_detailed()
    _, summary = load_summary()

    annual = {}
    for row in detailed:
        if row["period"] != "Annual":
            continue
        key = (row["crop_id"], row["region_id"])
        year_map = annual.setdefault(key, {})
        assert row["year"] not in year_map
        year_map[row["year"]] = float(row["yield_mt_per_ha"])

    summary_keys = set()
    for row in summary:
        key = (row["crop_id"], row["region_id"])
        assert key not in summary_keys
        summary_keys.add(key)

        assert row["ref_period"] == REF_PERIOD
        assert row["unit"] == "mt_per_ha"
        assert row["source_id"] == "PSA-OPENSTAT-CROPS"
        assert row["data_status"] == "observed"

        n_years = int(row["n_years"])
        assert 3 <= n_years <= 5

        values = list(annual[key].values())
        assert len(values) == n_years

        avg = float(row["avg_yield_mt_per_ha"])
        low = float(row["min_yield_mt_per_ha"])
        high = float(row["max_yield_mt_per_ha"])
        assert all(finite(value) for value in (avg, low, high))
        assert avg > 0
        assert 0 <= low <= avg <= high
        assert abs(avg - sum(values) / len(values)) <= 0.02
        assert abs(low - min(values)) <= 0.02
        assert abs(high - max(values)) <= 0.02


def test_yield_scope_is_luzon_only():
    _, detailed = load_detailed()
    _, summary = load_summary()

    for row in detailed + summary:
        assert row["region_id"] in LUZON_IDS
        upper = row["region_label"].upper()
        for banned in ("VISAYAS", "MINDANAO", "BARMM", "CARAGA", "PHILIPPINES"):
            assert banned not in upper

    scope = json.loads(
        (DS / "luzon_scope.json").read_text(encoding="utf-8")
    )
    scope_ids = {region["id"] for region in scope["regions"]}
    assert LUZON_IDS <= scope_ids


def test_yield_crops_are_safe_registry_crops():
    registry = json.loads(
        (GENERATED / "crop_registry.generated.json").read_text(
            encoding="utf-8"
        )
    )
    valid = {
        crop["crop_id"]
        for crop in registry["crops"]
        if crop.get("planning_supported")
        and crop.get("coverage", {}).get("production")
        and crop.get("coverage", {}).get("area")
    }
    assert valid

    _, detailed = load_detailed()
    _, summary = load_summary()
    detailed_crops = {row["crop_id"] for row in detailed}
    summary_crops = {row["crop_id"] for row in summary}

    assert detailed_crops <= valid
    assert summary_crops <= valid
    assert summary_crops <= detailed_crops


def test_tomato_and_eggplant_bridge_is_present():
    _, summary = load_summary()
    by_key = {
        (row["crop_id"], row["region_id"]): row
        for row in summary
    }

    tomato = float(
        by_key[("tomato", "IV-A")]["avg_yield_mt_per_ha"]
    )
    eggplant = float(
        by_key[("eggplant", "IV-A")]["avg_yield_mt_per_ha"]
    )

    assert abs(tomato - 13.9462) < 0.0001
    assert abs(eggplant - 16.4048) < 0.0001

    assert abs((2.0 * tomato) - 27.8924) < 0.001
    assert abs((1.5 * eggplant) - 24.6060) < 0.01


def test_docs_state_evidence_limits_and_partial_year_rule():
    text = DOCS_PATH.read_text(encoding="utf-8")
    assert (
        "Yield = Production in metric tons divided by "
        "Harvested area in hectares."
    ) in text
    assert "reference window is 2021-2025" in text
    assert "all five Annual years" in text
    assert "n_years" in text
    assert "not market demand" in text
    assert "not quarter specific" in text
    assert "GRCI still needs a separate" in text
    assert "—" not in text
    assert "**" not in text


def test_builder_offline_check_accepts_committed_snapshot():
    builder = load_builder()
    builder.check_committed_files(
        DETAILED,
        SUMMARY,
        DOCS_PATH,
    )


def test_builder_uses_table_specific_region_codes():
    builder = load_builder()
    scope = json.loads(
        (DS / "luzon_scope.json").read_text(encoding="utf-8")
    )

    production_geo = {
        "text": "Geolocation",
        "values": ["p1", "p2"],
        "valueTexts": [
            "..I - Ilocos Region",
            "..IV-A - CALABARZON",
        ],
    }
    area_geo = {
        "text": "Geolocation",
        "values": ["a9", "a3"],
        "valueTexts": [
            "..I - Ilocos Region",
            "..IV-A - CALABARZON",
        ],
    }

    production_codes, _, _ = builder.luzon_region_codes(
        production_geo,
        scope,
        ["I", "IV-A"],
    )
    area_codes, _, _ = builder.luzon_region_codes(
        area_geo,
        scope,
        ["I", "IV-A"],
    )

    assert production_codes["IV-A"] == "p2"
    assert area_codes["IV-A"] == "a3"
    assert production_codes["IV-A"] != area_codes["IV-A"]


def test_builder_rejects_non_finite_source_numbers():
    builder = load_builder()
    for value in ("nan", "NaN", "inf", "-inf", "not-a-number"):
        assert builder.to_number(value) is None


def test_summary_requires_all_five_distinct_annual_years():
    builder = load_builder()

    def row(year, value):
        return {
            "crop_id": "sample",
            "display_name": "Sample",
            "region_id": "IV-A",
            "region_label": "REGION IV-A (CALABARZON)",
            "year": str(year),
            "period": "Annual",
            "production_mt": value * 10,
            "area_ha": 10,
            "yield_mt_per_ha": value,
            "production_table": "PSA-PROD-VEG-ROOT",
            "area_table": "PSA-AREA-VEG-ROOT",
            "source_id": "PSA-OPENSTAT-CROPS",
            "data_status": "observed",
        }

    four_years = [row(year, float(year - 2020)) for year in range(2021, 2025)]
    assert builder.summarize_annual(four_years) == []

    five_years = [row(year, float(year - 2020)) for year in range(2021, 2026)]
    summary = builder.summarize_annual(five_years)
    assert len(summary) == 1
    assert summary[0]["n_years"] == 5
    assert summary[0]["avg_yield_mt_per_ha"] == 3.0

def test_builder_check_fails_on_stale_docs():
    builder = load_builder()
    with tempfile.TemporaryDirectory() as temp:
        target = pathlib.Path(temp)
        detail = target / "yield_reference.csv"
        summary = target / "yield_summary.csv"
        docs = target / "YIELD_REFERENCE.md"

        detail.write_bytes(DETAILED.read_bytes())
        summary.write_bytes(SUMMARY.read_bytes())
        docs.write_text("stale", encoding="utf-8")

        try:
            builder.check_committed_files(detail, summary, docs)
        except RuntimeError as error:
            assert "stale" in str(error).lower()
        else:
            raise AssertionError("stale yield documentation was accepted")


if __name__ == "__main__":
    tests = [
        name
        for name in globals()
        if name.startswith("test_")
    ]
    for name in sorted(tests):
        globals()[name]()
    print(f"OK: {len(tests)} yield reference checks passed")
