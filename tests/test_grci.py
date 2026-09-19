import ast
import csv
import importlib.util
import pathlib
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
DS = ROOT / "datasets"

TEST_BANDS = [
    (1.0, "low"),
    (1.5, "watch"),
    (float("inf"), "high"),
]


def load_grci():
    path = ROOT / "scripts" / "grci.py"
    spec = importlib.util.spec_from_file_location("grci", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_demo_plans():
    with open(
        DS / "demo_farm_plans.csv",
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def load_demo_baseline():
    with open(
        DS / "demo_coordination_baseline.csv",
        encoding="utf-8",
        newline="",
    ) as handle:
        return {
            row["crop_canonical"]: row
            for row in csv.DictReader(handle)
        }


def supported_crop_record():
    return {
        "planning_supported": True,
        "coverage": {"production": True, "area": True},
    }


def base_kwargs():
    return {
        "crop": "tomato",
        "location": "Tanauan, Batangas",
        "harvest_period": "2026-12",
        "plans": [{
            "crop_canonical": "tomato",
            "municipality": "Tanauan, Batangas",
            "harvest_period": "2026-12",
            "farm_size_ha": 10.0,
            "farm_size_margin_ha": 0.0,
        }],
        "reference_yield": 15.0,
        "yield_source": "test source",
        "reference_amount": 150.0,
        "reference_unit": "MT",
        "reference_type": "local_committed_demand",
        "reference_geography": "Tanauan, Batangas",
        "reference_period": "2026-12",
        "crop_record": supported_crop_record(),
        "bands": TEST_BANDS,
        "source_labels": ["TEST"],
    }


def demo_result(grci, crop_id):
    rows = [
        row
        for row in load_demo_plans()
        if row["crop_canonical"] == crop_id
    ]
    baseline = load_demo_baseline()[crop_id]

    return grci.compute_grci(
        crop=crop_id,
        location=rows[0]["municipality"],
        harvest_period=rows[0]["harvest_period"],
        plans=rows,
        reference_yield=float(
            baseline["reference_yield_mt_per_ha"]
        ),
        yield_source="DEMO-2026 synthetic yield",
        reference_amount=float(baseline["reference_qty_mt"]),
        reference_unit="MT",
        reference_type=baseline["reference_type"],
        reference_geography=baseline["reference_geography"],
        reference_period=baseline["reference_period"],
        crop_record=supported_crop_record(),
        bands=TEST_BANDS,
        source_labels=[baseline["source_id"]],
    )


def approx(first, second, tol=1e-9):
    return abs(first - second) <= tol


def expect_value_error(callback):
    try:
        callback()
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_demo_fixture_is_reproducible_and_explicit():
    grci = load_grci()
    plans = load_demo_plans()
    baseline = load_demo_baseline()

    assert {row["source_id"] for row in plans} == {"DEMO-2026"}
    assert {row["data_status"] for row in plans} == {"synthetic"}
    assert {row["source_id"] for row in baseline.values()} == {"DEMO-2026"}
    assert {row["data_status"] for row in baseline.values()} == {
        "derived_demo"
    }
    assert {row["reference_type"] for row in baseline.values()} == {
        "demo_coordination_baseline"
    }

    totals = {}
    for row in plans:
        crop = row["crop_canonical"]
        totals[crop] = (
            totals.get(crop, 0.0)
            + float(row["farm_size_ha"])
        )
    assert totals == {"tomato": 40.0, "eggplant": 8.0}

    tomato = demo_result(grci, "tomato")
    eggplant = demo_result(grci, "eggplant")

    assert tomato["status"] == "ok"
    assert tomato["planned_area_range"] == [40.0, 40.0]
    assert tomato["planned_supply_range"] == [600.0, 600.0]
    assert tomato["expected_production_range"] == [600.0, 600.0]
    assert approx(tomato["supply_load_range"][0], 1.6)
    assert tomato["risk_state"] == "high"
    assert tomato["uncertainty_state"] == "point"

    assert eggplant["status"] == "ok"
    assert eggplant["planned_area_range"] == [8.0, 8.0]
    assert eggplant["planned_supply_range"] == [96.0, 96.0]
    assert eggplant["expected_production_range"] == [96.0, 96.0]
    assert approx(
        eggplant["supply_load_range"][0],
        96.0 / 180.0,
    )
    assert eggplant["risk_state"] == "low"

    for result in (tomato, eggplant):
        assert result["reference_quality"] == "synthetic"
        assert result["reference_mode"] == "demo"
        assert result["market_demand_wording_allowed"] is False
        assert result["reference_unit"] == "MT"
        assert result["reference_label"] == (
            "Demo coordination baseline (not market demand)"
        )
        assert "not observed local market demand" in (
            result["reference_evidence_note"]
        )
        assert "Demo risk state" in result["explanation"]
        assert result["source_labels"] == ["DEMO-2026"]
        assert result["provenance"]["reference_type"] == (
            "demo_coordination_baseline"
        )

    assert demo_result(grci, "tomato") == tomato
    assert demo_result(grci, "eggplant") == eggplant


def test_approximate_farm_area_produces_range():
    grci = load_grci()
    low, high = grci.area_range(2.0, 0.2)
    assert approx(low, 1.8)
    assert approx(high, 2.2)

    kwargs = base_kwargs()
    kwargs["plans"] = [
        {
            "crop_canonical": "tomato",
            "municipality": "Tanauan, Batangas",
            "harvest_period": "2026-12",
            "farm_size_ha": 10.0,
            "farm_size_margin_ha": 1.0,
        },
        {
            "crop_canonical": "tomato",
            "municipality": "Tanauan, Batangas",
            "harvest_period": "2026-12",
            "farm_size_ha": 10.0,
            "farm_size_margin_ha": 1.0,
        },
    ]
    kwargs["reference_amount"] = 300.0

    result = grci.compute_grci(**kwargs)
    assert result["status"] == "ok"
    assert result["planned_area_range"] == [18.0, 22.0]
    assert result["planned_supply_range"] == [270.0, 330.0]
    assert approx(result["supply_load_range"][0], 0.9)
    assert approx(result["supply_load_range"][1], 1.1)
    assert result["risk_state"] == "borderline"
    assert result["uncertainty_state"] == "borderline"
    assert "270" in result["explanation"]
    assert "330" in result["explanation"]


def test_missing_reference_yield_is_incomplete():
    grci = load_grci()
    kwargs = base_kwargs()
    kwargs["reference_yield"] = None
    kwargs["yield_source"] = None
    result = grci.compute_grci(**kwargs)

    assert result["status"] == "incomplete"
    assert result["planned_supply_range"] is None
    assert result["risk_state"] is None
    assert "yield" in result["uncertainty_note"].lower()
    assert "No result can be shown" in result["explanation"]


def test_unsupported_crop_is_not_calculated():
    grci = load_grci()
    for crop_record in (
        {
            "planning_supported": False,
            "coverage": {"production": True, "area": False},
        },
        {
            "planning_supported": True,
            "coverage": {"production": "true", "area": "true"},
        },
    ):
        kwargs = base_kwargs()
        kwargs["crop_record"] = crop_record
        result = grci.compute_grci(**kwargs)

        assert result["status"] == "unsupported"
        assert result["planned_supply_range"] is None
        assert result["risk_state"] is None


def test_missing_location_or_harvest_period():
    grci = load_grci()
    for field in ("location", "harvest_period"):
        kwargs = base_kwargs()
        kwargs[field] = ""
        result = grci.compute_grci(**kwargs)
        assert result["status"] == "incomplete"
        assert result["risk_state"] is None


def test_invalid_farm_area_returns_invalid_result():
    grci = load_grci()
    for field, value in (
        ("farm_size_ha", -1.0),
        ("farm_size_ha", "not-a-number"),
        ("farm_size_ha", True),
        ("farm_size_margin_ha", -0.1),
        ("farm_size_margin_ha", "nan"),
        ("farm_size_margin_ha", False),
    ):
        kwargs = base_kwargs()
        kwargs["plans"][0][field] = value
        result = grci.compute_grci(**kwargs)
        assert result["status"] == "invalid"
        assert result["planned_area_range"] is None


def test_mixed_plan_context_is_rejected():
    grci = load_grci()

    kwargs = base_kwargs()
    kwargs["plans"].append({
        "crop_canonical": "eggplant",
        "municipality": "Tanauan, Batangas",
        "harvest_period": "2026-12",
        "farm_size_ha": 1.0,
        "farm_size_margin_ha": 0.0,
    })
    result = grci.compute_grci(**kwargs)
    assert result["status"] == "invalid"
    assert "different crop" in result["uncertainty_note"].lower()

    kwargs = base_kwargs()
    kwargs["plans"][0]["municipality"] = "Lipa, Batangas"
    result = grci.compute_grci(**kwargs)
    assert result["status"] == "invalid"
    assert "different location" in result["uncertainty_note"].lower()

    kwargs = base_kwargs()
    kwargs["plans"][0]["harvest_period"] = "2027-01"
    result = grci.compute_grci(**kwargs)
    assert result["status"] == "invalid"
    assert "different harvest period" in (
        result["uncertainty_note"].lower()
    )


def test_reference_amount_and_unit_are_strict():
    grci = load_grci()

    for value in (0, -1, "nan", "inf", "bad"):
        kwargs = base_kwargs()
        kwargs["reference_amount"] = value
        result = grci.compute_grci(**kwargs)
        assert result["status"] == "invalid"
        assert result["supply_load_range"] is None

    kwargs = base_kwargs()
    kwargs["reference_unit"] = "kg"
    result = grci.compute_grci(**kwargs)
    assert result["status"] == "invalid"
    assert "must use mt" in result["uncertainty_note"].lower()


def test_reference_quality_metadata_is_safe():
    grci = load_grci()

    assert set(grci.valid_reference_types()) == {
        "local_committed_demand",
        "local_historical_absorption",
        "national_utilization_context",
        "historical_production_baseline",
        "demo_coordination_baseline",
    }

    assert grci.allows_market_demand_wording(
        "local_committed_demand"
    ) is True
    for reference in (
        "local_historical_absorption",
        "national_utilization_context",
        "historical_production_baseline",
        "demo_coordination_baseline",
    ):
        assert grci.allows_market_demand_wording(reference) is False

    label, note = grci.describe_reference(
        "local_historical_absorption"
    )
    assert "not committed demand" in label.lower()
    assert "historical absorption" in note.lower()

    label, note = grci.describe_reference(
        "historical_production_baseline"
    )
    assert "not market demand" in label.lower()
    assert "not market demand" in note.lower()


def test_historical_production_is_baseline_not_risk():
    grci = load_grci()
    kwargs = base_kwargs()
    kwargs.update({
        "reference_type": "historical_production_baseline",
        "reference_geography": "CALABARZON (IV-A)",
        "reference_period": "2025",
        "reference_amount": 300.0,
    })
    result = grci.compute_grci(**kwargs)

    assert result["status"] == "baseline"
    assert result["comparison_state"] == "low"
    assert result["comparison_band_range"] == ["low", "low"]
    assert result["risk_state"] is None
    assert result["risk_band_range"] is None
    assert result["market_demand_wording_allowed"] is False
    assert "Baseline comparison state" in result["explanation"]
    assert "not market demand" in result["explanation"]


def test_national_utilization_is_context_only():
    grci = load_grci()
    kwargs = base_kwargs()
    kwargs.update({
        "reference_type": "national_utilization_context",
        "reference_geography": "Philippines",
        "reference_period": "2025",
        "reference_amount": 1000000.0,
    })
    result = grci.compute_grci(**kwargs)

    assert result["status"] == "context_only"
    assert result["reference_scope"] == "national"
    assert result["planned_supply_range"] == [150.0, 150.0]
    assert result["supply_load_range"] is None
    assert result["comparison_state"] is None
    assert result["risk_state"] is None
    assert "shown only as context" in result["explanation"]
    assert "does not compare local" in (
        result["uncertainty_note"].lower()
    )


def test_unknown_reference_type_is_invalid_but_missing_is_incomplete():
    grci = load_grci()

    kwargs = base_kwargs()
    kwargs["reference_type"] = "made_up_reference"
    result = grci.compute_grci(**kwargs)
    assert result["status"] == "invalid"
    assert result["reference_label"] is None

    kwargs = base_kwargs()
    kwargs["reference_type"] = " "
    result = grci.compute_grci(**kwargs)
    assert result["status"] == "incomplete"


def test_comparison_reference_requires_source_label():
    grci = load_grci()
    kwargs = base_kwargs()
    kwargs["source_labels"] = [" ", ""]
    result = grci.compute_grci(**kwargs)
    assert result["status"] == "incomplete"
    assert "source label" in result["uncertainty_note"].lower()
    assert result["risk_state"] is None


def test_reference_scope_metadata_is_required():
    grci = load_grci()

    kwargs = base_kwargs()
    kwargs["reference_geography"] = ""
    result = grci.compute_grci(**kwargs)
    assert result["status"] == "incomplete"

    kwargs = base_kwargs()
    kwargs["reference_period"] = ""
    result = grci.compute_grci(**kwargs)
    assert result["status"] == "incomplete"

    kwargs = base_kwargs()
    kwargs["reference_geography"] = "Philippines"
    result = grci.compute_grci(**kwargs)
    assert result["status"] == "invalid"

    kwargs = base_kwargs()
    kwargs["reference_type"] = "national_utilization_context"
    kwargs["reference_geography"] = "CALABARZON"
    result = grci.compute_grci(**kwargs)
    assert result["status"] == "invalid"


def test_source_labels_are_normalized():
    grci = load_grci()
    kwargs = base_kwargs()
    kwargs["source_labels"] = [" TEST ", "TEST", "", "OTHER"]
    result = grci.compute_grci(**kwargs)
    assert result["source_labels"] == ["TEST", "OTHER"]
    assert result["provenance"]["source_labels"] == [
        "TEST",
        "OTHER",
    ]


def test_risk_band_configuration_is_strict():
    grci = load_grci()

    assert grci.classify_range(1.6, 1.6, TEST_BANDS) == (
        "high",
        "high",
        False,
    )

    bad_bands = [
        [],
        [(1.5, "watch"), (1.0, "low"), (float("inf"), "high")],
        [(1.0, "low"), (float("inf"), "low")],
        [(1.0, "low"), (1.5, "watch")],
        [(float("nan"), "low"), (float("inf"), "high")],
        [(True, "low"), (float("inf"), "high")],
    ]
    for bands in bad_bands:
        expect_value_error(
            lambda bands=bands: grci.validate_bands(bands)
        )

    expect_value_error(
        lambda: grci.classify_range(1.5, 1.0, TEST_BANDS)
    )


def test_numeric_range_helpers_reject_invalid_bounds():
    grci = load_grci()

    for callback in (
        lambda: grci.planned_supply_range(2.0, 1.0, 10.0),
        lambda: grci.planned_supply_range(-1.0, 1.0, 10.0),
        lambda: grci.planned_supply_range(True, 1.0, 10.0),
        lambda: grci.supply_load_range(20.0, 10.0, 100.0),
        lambda: grci.supply_load_range(-1.0, 10.0, 100.0),
        lambda: grci.supply_load_range(False, 10.0, 100.0),
    ):
        expect_value_error(callback)


def test_estimated_range_wording_is_not_statistical():
    grci = load_grci()

    assert grci.format_estimated_range(1.8, 2.2, "ha") == (
        "Estimated range: 1.8 ha to 2.2 ha"
    )
    assert grci.format_estimated_range(27.0, 33.0, "MT") == (
        "Estimated range: 27 MT to 33 MT"
    )

    label = grci.format_estimated_range(1.8, 2.2, "ha")
    assert "confidence" not in label.lower()

    for callback in (
        lambda: grci.format_estimated_range(2.2, 1.8, "ha"),
        lambda: grci.format_estimated_range(-1.0, 2.0, "ha"),
        lambda: grci.format_estimated_range(
            "not-a-number",
            2.0,
            "ha",
        ),
        lambda: grci.format_estimated_range(1.0, 2.0, ""),
    ):
        expect_value_error(callback)


def test_reference_yield_lookup_uses_validated_summary():
    grci = load_grci()
    index = grci.load_yield_summary(
        DS / "generated" / "yield_summary.csv"
    )

    tomato = grci.reference_yield_for(
        index,
        "tomato",
        "IV-A",
    )
    assert tomato is not None
    assert tomato["ref_period"] == "2021-2025"
    assert tomato["n_years"] == 5
    assert abs(
        tomato["avg_yield_mt_per_ha"] - 13.9462
    ) < 0.0001

    eggplant = grci.reference_yield_for(
        index,
        "eggplant",
        "IV-A",
    )
    assert eggplant is not None
    assert abs(
        eggplant["avg_yield_mt_per_ha"] - 16.4048
    ) < 0.0001

    assert grci.reference_yield_for(
        index,
        "tomato",
        "NCR",
    ) is None
    assert grci.reference_yield_for(
        index,
        "unknown-crop",
        "IV-A",
    ) is None
    assert grci.reference_yield_for(index, "", "IV-A") is None


def test_reference_yield_loader_rejects_wrong_year_count_and_metadata():
    grci = load_grci()
    header = ",".join(grci.YIELD_SUMMARY_FIELDS)
    bad_rows = [
        "tomato,Tomato,IV-A,REGION IV-A (CALABARZON),2021-2025,4,13.9462,12.1046,16.0314,mt_per_ha,PSA-OPENSTAT-CROPS,observed",
        "tomato,Tomato,IV-A,REGION IV-A (CALABARZON),2020-2024,5,13.9462,12.1046,16.0314,mt_per_ha,PSA-OPENSTAT-CROPS,observed",
        "tomato,Tomato,IV-A,REGION IV-A (CALABARZON),2021-2025,5,13.9462,12.1046,16.0314,mt_per_ha,WRONG,observed",
        "tomato,Tomato,IV-A,REGION IV-A (CALABARZON),2021-2025,5,13.9462,12.1046,16.0314,mt_per_ha,PSA-OPENSTAT-CROPS,synthetic",
        "tomato,Tomato,ZZ,Unknown Region,2021-2025,5,13.9462,12.1046,16.0314,mt_per_ha,PSA-OPENSTAT-CROPS,observed",
        "tomato,,IV-A,REGION IV-A (CALABARZON),2021-2025,5,13.9462,12.1046,16.0314,mt_per_ha,PSA-OPENSTAT-CROPS,observed",
        "tomato,Tomato,IV-A,,2021-2025,5,13.9462,12.1046,16.0314,mt_per_ha,PSA-OPENSTAT-CROPS,observed",
    ]
    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "summary.csv"
        for row in bad_rows:
            path.write_text(header + "\n" + row + "\n", encoding="utf-8")
            expect_value_error(lambda: grci.load_yield_summary(path))


def test_reference_yield_loader_rejects_duplicate_keys():
    grci = load_grci()
    header = ",".join(grci.YIELD_SUMMARY_FIELDS)
    row = (
        "tomato,Tomato,IV-A,REGION IV-A (CALABARZON),"
        "2021-2025,5,13.9462,12.1046,16.0314,"
        "mt_per_ha,PSA-OPENSTAT-CROPS,observed"
    )

    with tempfile.TemporaryDirectory() as temp:
        path = pathlib.Path(temp) / "summary.csv"
        path.write_text(
            header + "\n" + row + "\n" + row + "\n",
            encoding="utf-8",
        )
        expect_value_error(lambda: grci.load_yield_summary(path))


def test_yield_provenance_must_match_reference_yield():
    grci = load_grci()
    index = grci.load_yield_summary(
        DS / "generated" / "yield_summary.csv"
    )
    record = grci.reference_yield_for(
        index,
        "tomato",
        "IV-A",
    )

    kwargs = base_kwargs()
    kwargs["reference_yield"] = record["avg_yield_mt_per_ha"]
    kwargs["yield_source"] = "PSA-OPENSTAT-CROPS 2021-2025 summary"
    kwargs["yield_record"] = record
    result = grci.compute_grci(**kwargs)

    assert result["status"] == "ok"
    provenance = result["provenance"]
    assert provenance["yield_crop_id"] == "tomato"
    assert provenance["yield_region_id"] == "IV-A"
    assert provenance["yield_ref_period"] == "2021-2025"
    assert provenance["yield_n_years"] == 5
    assert provenance["yield_unit"] == "mt_per_ha"
    assert provenance["yield_source_id"] == "PSA-OPENSTAT-CROPS"

    kwargs = base_kwargs()
    kwargs["reference_yield"] = (
        record["avg_yield_mt_per_ha"] + 1.0
    )
    kwargs["yield_source"] = "PSA-OPENSTAT-CROPS 2021-2025 summary"
    kwargs["yield_record"] = record
    result = grci.compute_grci(**kwargs)
    assert result["status"] == "invalid"
    assert "does not match" in result["uncertainty_note"].lower()

    bad_record = dict(record)
    bad_record["region_id"] = "ZZ"
    kwargs = base_kwargs()
    kwargs["reference_yield"] = record["avg_yield_mt_per_ha"]
    kwargs["yield_source"] = "PSA-OPENSTAT-CROPS 2021-2025 summary"
    kwargs["yield_record"] = bad_record
    result = grci.compute_grci(**kwargs)
    assert result["status"] == "invalid"
    assert "region id" in result["uncertainty_note"].lower()

    bad_record = dict(record)
    bad_record["data_status"] = "synthetic"
    kwargs["yield_record"] = bad_record
    result = grci.compute_grci(**kwargs)
    assert result["status"] == "invalid"
    assert "observed" in result["uncertainty_note"].lower()


def test_output_contract_has_explanation_and_provenance():
    grci = load_grci()
    result = demo_result(grci, "tomato")

    required = {
        "crop",
        "location",
        "harvest_period",
        "planned_area_range",
        "expected_production_range",
        "reference_amount",
        "reference_unit",
        "reference_type",
        "reference_label",
        "reference_evidence_note",
        "supply_load_range",
        "status",
        "comparison_state",
        "risk_state",
        "explanation",
        "uncertainty_state",
        "provenance",
    }
    assert required <= set(result)
    assert "600" in result["explanation"]
    assert "high" in result["explanation"].lower()
    assert result["provenance"]["reference_amount"] == 375.0


def test_engine_is_independent_from_ui_and_stdlib_only():
    source = (
        ROOT / "scripts" / "grci.py"
    ).read_text(encoding="utf-8")
    assert "react" not in source.lower()

    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(
                alias.name.split(".")[0]
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])

    assert imports <= {"csv", "datetime", "math", "pathlib", "re"}


if __name__ == "__main__":
    tests = [
        name
        for name in globals()
        if name.startswith("test_")
    ]
    for name in sorted(tests):
        globals()[name]()
    print(f"OK: {len(tests)} GRCI checks passed")
