import ast
import csv
import datetime as dt
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DS = ROOT / "datasets"
DOCS = ROOT / "docs"


def load_csv(name):
    with open(DS / name, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def load_json(name):
    return json.loads((DS / name).read_text(encoding="utf-8"))


def source_catalog():
    items = load_json("sources.json")
    ids = [item["source_id"] for item in items]
    assert len(ids) == len(set(ids)), "duplicate source_id"
    return {item["source_id"]: item for item in items}


def load_fetcher():
    path = ROOT / "scripts" / "fetch_openstat_luzon.py"
    spec = importlib.util.spec_from_file_location("fetch_openstat_luzon", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_catalog():
    catalog = source_catalog()
    required = {
        "source_id", "publisher", "title", "url", "accessed",
        "transformation", "terms_key", "verification",
    }
    for source in catalog.values():
        assert required <= set(source)
        dt.date.fromisoformat(source["accessed"])
    for source_id in {
        "PSA-OPENSTAT-CROPS",
        "PSA-OPENSTAT-FARMGATE",
        "PSA-OPENSTAT-RETAIL",
        "PSA-OPENSTAT-SUA",
        "DA-PM-INDEX",
        "DA-PM-2026-09-07-13",
        "PAGASA-AGRO-2026-08",
        "OPEN-METEO-API",
        "DA-AMIA-NCCAG",
        "DEMO-2026",
    }:
        assert source_id in catalog


def test_concept_note_sources_are_present():
    urls = {item["url"] for item in load_json("sources.json")}
    assert "https://openstat.psa.gov.ph/Metadata/Prices/Farmgate-Prices" in urls
    assert "https://openstat.psa.gov.ph/Metadata/Prices/Retail-Prices" in urls
    assert "https://openstat.psa.gov.ph/Metadata/Agriculture-Forestry-Fisheries/Crops" in urls
    assert "https://www.da.gov.ph/price-monitoring/" in urls
    assert "https://openstat.psa.gov.ph/Metadata/Agricultural-Accounts/Supply-Utilization-Accounts" in urls
    assert "https://open-meteo.com/" in urls
    assert "https://amia.da.gov.ph/national-color-coded-agricultural-guide-nccag-map/" in urls
    assert "https://bagong.pagasa.dost.gov.ph/agri-weather/monthly-agroclimatic-review-and-outlook" in urls


def test_openstat_manifest_has_full_plant_scope():
    manifest = load_json("openstat_tables.json")
    tables = manifest["tables"]
    assert len(tables) == 59
    keys = [table["table_key"] for table in tables]
    paths = [table["path"] for table in tables]
    assert len(keys) == len(set(keys))
    assert len(paths) == len(set(paths))

    families = {}
    for table in tables:
        families.setdefault(table["family"], []).append(table)

    assert {key: len(value) for key, value in families.items()} == {
        "production": 4,
        "area": 4,
        "bearing": 2,
        "farmgate": 18,
        "retail": 24,
        "sua": 7,
    }

    for family in ("production", "area", "bearing", "farmgate", "retail"):
        assert all(table["geo_scope"] == "luzon" for table in families[family])
        assert all(table["expected_luzon_regions"] for table in families[family])
    assert all(table["geo_scope"] == "national" for table in families["sua"])

    assert {table["series_id"] for table in families["farmgate"]} == {
        "farmgate_current_2010_2026",
        "farmgate_legacy_1990_2020",
        "farmgate_legacy_2006_2020",
    }
    assert {table["series_id"] for table in families["retail"]} == {
        "retail_current_2018_2026",
        "retail_revised_2012_2021",
        "retail_legacy_1990_2021",
    }
    assert any("/NFG/" in table["path"] for table in families["farmgate"])
    assert any("/FG/" in table["path"] for table in families["farmgate"])
    assert any("/2018NEW/" in table["path"] for table in families["retail"])
    assert any("/NRP/" in table["path"] for table in families["retail"])
    assert any("/RP/" in table["path"] for table in families["retail"])
    assert all("ESUA" in table["path"] for table in families["sua"])

    titles = " ".join(table["title"].lower() for table in tables)
    for banned in ("livestock", "poultry", "fishery", "fish: retail"):
        assert banned not in titles


def test_manifest_verified_shapes_cover_many_plants():
    tables = load_json("openstat_tables.json")["tables"]
    by_key = {table["table_key"]: table for table in tables}
    assert by_key["PSA-PROD-NONFOOD"]["verified_shape"][0] >= 148
    assert by_key["PSA-PROD-FRUITS"]["verified_shape"][0] >= 83
    assert by_key["PSA-PROD-VEG-ROOT"]["verified_shape"][0] >= 142

    current_farmgate = [
        table for table in tables
        if table.get("series_id") == "farmgate_current_2010_2026"
    ]
    legacy_farmgate = [
        table for table in tables
        if table.get("series_id", "").startswith("farmgate_legacy_")
    ]
    current_retail = [
        table for table in tables
        if table.get("series_id") == "retail_current_2018_2026"
    ]
    revised_retail = [
        table for table in tables
        if table.get("series_id") == "retail_revised_2012_2021"
    ]
    legacy_retail = [
        table for table in tables
        if table.get("series_id") == "retail_legacy_1990_2021"
    ]

    for table in current_farmgate + legacy_farmgate + current_retail + revised_retail + legacy_retail:
        assert table["commodity_count"] > 0

    assert sum(table["commodity_count"] for table in current_farmgate) == 197
    assert sum(table["commodity_count"] for table in legacy_farmgate) == 192
    assert sum(table["commodity_count"] for table in current_retail) == 112
    assert sum(table["commodity_count"] for table in revised_retail) == 74
    assert sum(table["commodity_count"] for table in legacy_retail) == 41


def test_price_series_policy_is_continuous():
    policy = load_json("price_series_policy.json")
    assert policy["farmgate"] == [
        {
            "years": "1990-2009",
            "series_id": "farmgate_legacy_1990_2020",
            "reason": "Only legacy series covers the full pre-2010 period. Cutflowers begin in 2006.",
        },
        {
            "years": "2010-2026",
            "series_id": "farmgate_current_2010_2026",
            "reason": "Current PSA series is preferred where it overlaps the legacy series.",
        },
    ]
    assert [item["series_id"] for item in policy["retail"]] == [
        "retail_legacy_1990_2021",
        "retail_revised_2012_2021",
        "retail_current_2018_2026",
    ]


def test_luzon_scope_aliases_are_complete():
    scope = load_json("luzon_scope.json")
    assert [region["id"] for region in scope["regions"]] == [
        "NCR", "CAR", "I", "II", "III", "IV-A", "MIMAROPA", "V"
    ]
    aliases = {alias for region in scope["regions"] for alias in region["aliases"]}
    assert "REGION I (ILOCOS REGION)" in aliases
    assert "I - ILOCOS REGION" in aliases
    assert "REGION IV-A (CALABARZON)" in aliases
    assert "IV-A - CALABARZON" in aliases
    assert "REGION IV-B (MIMAROPA)" in aliases
    assert "IV-B - MIMAROPA REGION" in aliases
    assert scope["excludes_national_total"] is True


def test_luzon_filter_accepts_old_and_new_psa_labels_without_leakage():
    fetcher = load_fetcher()
    scope = load_json("luzon_scope.json")
    labels = [
        "PHILIPPINES",
        "..NCR - National Capital Region",
        "....City of Manila",
        "..CAR - Cordillera Administrative Region",
        "....Benguet",
        "..I - Ilocos Region",
        "....Pangasinan",
        "..II - Cagayan Valley",
        "....Isabela",
        "..III - Central Luzon",
        "....Bulacan",
        "..IV-A - CALABARZON",
        "....Batangas",
        "..MIMAROPA Region",
        "....Palawan",
        "..V - Bicol Region",
        "....Albay",
        "..VI - Western Visayas",
        "....Iloilo",
        "..X - Northern Mindanao",
        "....Bukidnon",
    ]
    variable = {
        "code": "Geolocation",
        "text": "Geolocation",
        "values": [str(index) for index in range(len(labels))],
        "valueTexts": labels,
    }
    selected = set(fetcher.select_luzon_values(
        variable,
        scope,
        ["NCR", "CAR", "I", "II", "III", "IV-A", "MIMAROPA", "V"],
    ))
    selected_labels = {labels[int(index)] for index in selected}
    assert "..NCR - National Capital Region" in selected_labels
    assert "..V - Bicol Region" in selected_labels
    assert "....Batangas" in selected_labels
    assert "..VI - Western Visayas" not in selected_labels
    assert "....Iloilo" not in selected_labels
    assert "..X - Northern Mindanao" not in selected_labels


def test_da_snapshot_is_complete_but_ncr_only():
    fields, rows = load_csv("da_price_monitoring_ncr_latest.csv")
    assert fields == [
        "period", "category", "commodity", "specification", "region",
        "market_scope", "unit", "weekly_average_price_php",
        "observation_status", "source_id", "data_status",
    ]
    assert len(rows) == 100
    assert len({row["commodity"] for row in rows}) >= 85
    assert {row["region"] for row in rows} == {"NCR"}
    lookup = {(row["category"], row["commodity"]): row for row in rows}
    assert float(lookup[("LOWLAND VEGETABLES", "Eggplant")]["weekly_average_price_php"]) == 156.05
    assert float(lookup[("LOWLAND VEGETABLES", "Tomato")]["weekly_average_price_php"]) == 116.62
    assert float(lookup[("HIGHLAND VEGETABLES", "Carrots, Local")]["weekly_average_price_php"]) == 115.23


def test_demo_stays_fixed():
    _, plans = load_csv("demo_farm_plans.csv")
    totals = {}
    for row in plans:
        totals[row["crop_canonical"]] = totals.get(row["crop_canonical"], 0.0) + float(row["farm_size_ha"])
        assert row["source_id"] == "DEMO-2026"
        assert row["data_status"] == "synthetic"
    assert totals == {"tomato": 40.0, "eggplant": 8.0}

    fields, baseline = load_csv("demo_coordination_baseline.csv")
    assert not (DS / "demo_demand_proxy.csv").exists()
    assert fields == [
        "crop_canonical",
        "reference_period",
        "reference_geography",
        "reference_scope_level",
        "reference_qty_mt",
        "reference_yield_mt_per_ha",
        "reference_area_eq_ha",
        "reference_type",
        "source_id",
        "data_status",
    ]
    assert {row["crop_canonical"] for row in baseline} == {"tomato", "eggplant"}
    assert {row["reference_type"] for row in baseline} == {
        "demo_coordination_baseline"
    }
    assert {row["reference_scope_level"] for row in baseline} == {"region"}
    assert {row["source_id"] for row in baseline} == {"DEMO-2026"}
    assert {row["data_status"] for row in baseline} == {"derived_demo"}


def test_recursive_batching_handles_large_openstat_tables():
    fetcher = load_fetcher()
    selected = [
        ({"code": "crop"}, [str(i) for i in range(148)]),
        ({"code": "geo"}, [str(i) for i in range(110)]),
        ({"code": "year"}, [str(i) for i in range(17)]),
        ({"code": "quarter"}, [str(i) for i in range(7)]),
    ]
    batches = list(fetcher.query_batches(selected))
    assert len(batches) > 1
    for batch in batches:
        cells = 1
        for _, values in batch:
            cells *= len(values)
        assert 0 < cells <= fetcher.SAFE_MAX_CELLS


def test_fetcher_is_stdlib_batched_and_verifiable():
    path = ROOT / "scripts" / "fetch_openstat_luzon.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    assert imports <= {
        "argparse", "csv", "io", "json", "math", "pathlib",
        "re", "time", "urllib"
    }
    text = path.read_text(encoding="utf-8")
    assert "SAFE_MAX_CELLS = 90000" in text
    assert "REQUEST_PAUSE_SECONDS = 1.1" in text
    assert "--verify-only" in text
    assert "verify_shape" in text
    assert "select_luzon_values" in text
    assert "yield from query_batches" in text
    assert "append_csv_text" in text


def test_source_configs_resolve():
    catalog = source_catalog()
    for name in [
        "pagasa_agroclimatic_august_2026.json",
        "weather_api_config.json",
        "nccag_reference.json",
    ]:
        data = load_json(name)
        assert data["source_id"] in catalog
    weather = load_json("weather_api_config.json")
    assert weather["scope"] == "Luzon"
    assert weather["coordinate_mode"] == "caller_provided"
    assert weather["demo_default"]["coordinate_source_id"] in catalog

    nccag = load_json("nccag_reference.json")
    assert nccag["crop_suitability_layer_count"] == 21
    assert len(nccag["crop_suitability_layers"]) == 21
    assert nccag["multi_hazard_count"] == 8

    pagasa = load_json("pagasa_agroclimatic_august_2026.json")
    assert pagasa["region_context"] == "Luzon"
    assert "Ilocos Region" in pagasa["review"]["affected_luzon_regions"]
    assert "MIMAROPA" in pagasa["review"]["affected_luzon_regions"]


def test_markdown_style_guard():
    for path in [ROOT / "README.md", *DS.glob("*.md"), *DOCS.glob("*.md")]:
        text = path.read_text(encoding="utf-8")
        assert "—" not in text, path
        assert "**" not in text, path
        assert all(line.strip() != "---" for line in text.splitlines()), path


if __name__ == "__main__":
    tests = [name for name in globals() if name.startswith("test_")]
    for name in sorted(tests):
        globals()[name]()
    print(f"OK: {len(tests)} dataset checks passed")
