import csv
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DS = ROOT / "datasets"

# These bands are only for the fixed demo fixture tests.
# They are not final product thresholds.
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
    with open(DS / "demo_farm_plans.csv", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_demo_demand():
    with open(DS / "demo_demand_proxy.csv", encoding="utf-8", newline="") as handle:
        return {
            row["crop_canonical"]: row
            for row in csv.DictReader(handle)
        }


def supported_crop_record():
    return {
        "planning_supported": True,
        "coverage": {"production": True, "area": True},
    }


def demo_result(grci, crop_id):
    all_plans = load_demo_plans()
    rows = [row for row in all_plans if row["crop_canonical"] == crop_id]
    plans = [
        {
            "farm_size_ha": float(row["farm_size_ha"]),
            "farm_size_margin_ha": float(row["farm_size_margin_ha"]),
        }
        for row in rows
    ]
    demand = load_demo_demand()[crop_id]

    return grci.compute_grci(
        crop=crop_id,
        location=rows[0]["municipality"],
        harvest_period=rows[0]["harvest_period"],
        plans=plans,
        reference_yield=float(demand["demo_yield_mt_per_ha"]),
        yield_source="DEMO-2026 synthetic yield",
        reference_amount=float(demand["demo_qty_mt"]),
        reference_type="demo_coordination_baseline",
        crop_record=supported_crop_record(),
        bands=TEST_BANDS,
        source_labels=[demand["source_id"]],
    )


def approx(first, second, tol=1e-9):
    return abs(first - second) <= tol


def expect_value_error(callback):
    try:
        callback()
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_demo_fixture_is_reproducible_and_labelled():
    grci = load_grci()
    plans = load_demo_plans()
    demand = load_demo_demand()

    assert {row["source_id"] for row in plans} == {"DEMO-2026"}
    assert {row["data_status"] for row in plans} == {"synthetic"}
    assert {row["source_id"] for row in demand.values()} == {"DEMO-2026"}
    assert {row["data_status"] for row in demand.values()} == {"derived_demo"}

    totals = {}
    for row in plans:
        crop = row["crop_canonical"]
        totals[crop] = totals.get(crop, 0.0) + float(row["farm_size_ha"])
    assert totals == {"tomato": 40.0, "eggplant": 8.0}

    tomato = demo_result(grci, "tomato")
    eggplant = demo_result(grci, "eggplant")

    assert tomato["status"] == "ok"
    assert tomato["planned_area_range"] == [40.0, 40.0]
    assert tomato["planned_supply_range"] == [600.0, 600.0]
    assert approx(tomato["supply_load_range"][0], 1.6)
    assert approx(tomato["supply_load_range"][1], 1.6)
    assert tomato["risk_state"] == "high"
    assert tomato["risk_band_range"] == ["high", "high"]
    assert tomato["borderline"] is False

    assert eggplant["status"] == "ok"
    assert eggplant["planned_area_range"] == [8.0, 8.0]
    assert eggplant["planned_supply_range"] == [96.0, 96.0]
    assert approx(eggplant["supply_load_range"][0], 96.0 / 180.0)
    assert approx(eggplant["supply_load_range"][1], 96.0 / 180.0)
    assert eggplant["risk_state"] == "low"
    assert eggplant["risk_band_range"] == ["low", "low"]
    assert eggplant["borderline"] is False

    for result in (tomato, eggplant):
        assert result["reference_type"] == "demo_coordination_baseline"
        assert result["reference_label"] == "Demo coordination baseline (not market demand)"
        assert "not observed local market demand" in result["reference_evidence_note"]
        assert "market demand" not in result["reference_label"].lower().replace("not market demand", "")
        assert result["source_labels"] == ["DEMO-2026"]

    assert demo_result(grci, "tomato") == tomato
    assert demo_result(grci, "eggplant") == eggplant


def test_approximate_farm_area_produces_range():
    grci = load_grci()

    low, high = grci.area_range(2.0, 0.2)
    assert approx(low, 1.8)
    assert approx(high, 2.2)

    low, high = grci.collective_area_range([
        {"farm_size_ha": 10.0, "farm_size_margin_ha": 1.0},
        {"farm_size_ha": 10.0, "farm_size_margin_ha": 1.0},
    ])
    assert (low, high) == (18.0, 22.0)

    result = grci.compute_grci(
        crop="tomato",
        location="Tanauan, Batangas",
        harvest_period="2026-12",
        plans=[
            {"farm_size_ha": 10.0, "farm_size_margin_ha": 1.0},
            {"farm_size_ha": 10.0, "farm_size_margin_ha": 1.0},
        ],
        reference_yield=15.0,
        yield_source="test source",
        reference_amount=300.0,
        reference_type="local_committed_demand",
        crop_record=supported_crop_record(),
        bands=TEST_BANDS,
        source_labels=["TEST"],
    )

    assert result["status"] == "ok"
    assert result["planned_area_range"] == [18.0, 22.0]
    assert result["planned_supply_range"] == [270.0, 330.0]
    assert approx(result["supply_load_range"][0], 0.9)
    assert approx(result["supply_load_range"][1], 1.1)
    assert result["risk_state"] == "borderline"
    assert result["borderline"] is True


def test_missing_reference_yield_is_incomplete():
    grci = load_grci()
    result = grci.compute_grci(
        crop="tomato",
        location="Tanauan, Batangas",
        harvest_period="2026-12",
        plans=[{"farm_size_ha": 10.0, "farm_size_margin_ha": 0.0}],
        reference_yield=None,
        yield_source=None,
        reference_amount=375.0,
        reference_type="local_committed_demand",
        crop_record=supported_crop_record(),
        bands=TEST_BANDS,
        source_labels=["TEST"],
    )

    assert result["status"] == "incomplete"
    assert result["risk_state"] is None
    assert result["planned_supply_range"] is None
    assert result["supply_load_range"] is None
    assert "yield" in result["uncertainty_note"].lower()


def test_unsupported_or_missing_crop_registry_record():
    grci = load_grci()
    production_only = {
        "planning_supported": False,
        "coverage": {"production": True, "area": False},
    }

    for crop_record in (production_only, None):
        result = grci.compute_grci(
            crop="eggplant",
            location="Tanauan, Batangas",
            harvest_period="2026-12",
            plans=[{"farm_size_ha": 8.0, "farm_size_margin_ha": 0.0}],
            reference_yield=12.0,
            yield_source="test source",
            reference_amount=180.0,
            reference_type="local_committed_demand",
            crop_record=crop_record,
            bands=TEST_BANDS,
            source_labels=["TEST"],
        )
        assert result["status"] == "unsupported"
        assert result["risk_state"] is None
        assert result["planned_supply_range"] is None

    assert grci.is_planning_supported(supported_crop_record()) is True
    assert grci.is_planning_supported(production_only) is False
    assert grci.is_planning_supported(None) is False


def test_missing_location_or_harvest_period():
    grci = load_grci()

    cases = [
        {"location": "", "harvest_period": "2026-12", "message": "location"},
        {"location": "Tanauan, Batangas", "harvest_period": "", "message": "harvest"},
    ]

    for case in cases:
        result = grci.compute_grci(
            crop="tomato",
            location=case["location"],
            harvest_period=case["harvest_period"],
            plans=[{"farm_size_ha": 10.0, "farm_size_margin_ha": 0.0}],
            reference_yield=15.0,
            yield_source="test source",
            reference_amount=375.0,
            reference_type="local_committed_demand",
            crop_record=supported_crop_record(),
            bands=TEST_BANDS,
            source_labels=["TEST"],
        )
        assert result["status"] == "incomplete"
        assert result["risk_state"] is None
        assert case["message"] in result["uncertainty_note"].lower()


def test_zero_reference_amount_is_invalid():
    grci = load_grci()
    assert grci.supply_load_range(600.0, 600.0, 0) is None

    result = grci.compute_grci(
        crop="tomato",
        location="Tanauan, Batangas",
        harvest_period="2026-12",
        plans=[{"farm_size_ha": 40.0, "farm_size_margin_ha": 0.0}],
        reference_yield=15.0,
        yield_source="test source",
        reference_amount=0,
        reference_type="local_committed_demand",
        crop_record=supported_crop_record(),
        bands=TEST_BANDS,
        source_labels=["TEST"],
    )

    assert result["status"] == "invalid"
    assert result["risk_state"] is None
    assert result["planned_supply_range"] == [600.0, 600.0]
    assert result["supply_load_range"] is None
    assert "greater than zero" in result["uncertainty_note"].lower()


def test_invalid_farm_area_returns_invalid_result():
    grci = load_grci()
    for plan in (
        {"farm_size_ha": -1.0, "farm_size_margin_ha": 0.0},
        {"farm_size_ha": 1.0, "farm_size_margin_ha": -0.2},
        {"farm_size_ha": "not-a-number", "farm_size_margin_ha": 0.0},
    ):
        result = grci.compute_grci(
            crop="tomato",
            location="Tanauan, Batangas",
            harvest_period="2026-12",
            plans=[plan],
            reference_yield=15.0,
            yield_source="test source",
            reference_amount=375.0,
            reference_type="local_committed_demand",
            crop_record=supported_crop_record(),
            bands=TEST_BANDS,
            source_labels=["TEST"],
        )
        assert result["status"] == "invalid"
        assert result["risk_state"] is None
        assert result["planned_area_range"] is None


def test_grci_range_crossing_risk_boundary():
    grci = load_grci()
    result = grci.compute_grci(
        crop="tomato",
        location="Tanauan, Batangas",
        harvest_period="2026-12",
        plans=[{"farm_size_ha": 10.0, "farm_size_margin_ha": 5.0}],
        reference_yield=10.0,
        yield_source="test source",
        reference_amount=100.0,
        reference_type="local_committed_demand",
        crop_record=supported_crop_record(),
        bands=TEST_BANDS,
        source_labels=["TEST"],
    )

    assert result["status"] == "ok"
    assert result["planned_area_range"] == [5.0, 15.0]
    assert result["planned_supply_range"] == [50.0, 150.0]
    assert approx(result["supply_load_range"][0], 0.5)
    assert approx(result["supply_load_range"][1], 1.5)
    assert result["risk_state"] == "borderline"
    assert result["risk_band_range"] == ["low", "watch"]
    assert result["borderline"] is True


def test_reference_quality_labels_change_with_evidence():
    grci = load_grci()

    assert set(grci.valid_reference_types()) == {
        "local_committed_demand",
        "local_historical_absorption",
        "national_utilization_context",
        "historical_production_baseline",
        "demo_coordination_baseline",
    }

    labels = {
        reference: grci.describe_reference(reference)
        for reference in grci.valid_reference_types()
    }
    assert labels["local_committed_demand"][0] == "Local committed demand"
    assert labels["local_historical_absorption"][0] == "Local historical absorption"
    assert labels["national_utilization_context"][0] == (
        "National utilization context (not Luzon demand)"
    )
    assert labels["historical_production_baseline"][0] == (
        "Historical production baseline (not market demand)"
    )
    assert labels["demo_coordination_baseline"][0] == (
        "Demo coordination baseline (not market demand)"
    )

    assert grci.is_market_demand_reference("local_committed_demand") is True
    assert grci.is_market_demand_reference("local_historical_absorption") is True
    assert grci.is_market_demand_reference("national_utilization_context") is False
    assert grci.is_market_demand_reference("historical_production_baseline") is False
    assert grci.is_market_demand_reference("demo_coordination_baseline") is False

    for reference in (
        "national_utilization_context",
        "historical_production_baseline",
        "demo_coordination_baseline",
    ):
        label, note = labels[reference]
        assert "not " in label.lower() or "not " in note.lower()
        bare_label = label.lower().replace("(not market demand)", "").replace(
            "(not luzon demand)", ""
        )
        assert "market demand" not in bare_label


def test_historical_production_is_never_market_demand():
    grci = load_grci()
    result = grci.compute_grci(
        crop="tomato",
        location="Tanauan, Batangas",
        harvest_period="2026-12",
        plans=[{"farm_size_ha": 10.0, "farm_size_margin_ha": 0.0}],
        reference_yield=15.0,
        yield_source="test source",
        reference_amount=300.0,
        reference_type="historical_production_baseline",
        crop_record=supported_crop_record(),
        bands=TEST_BANDS,
        source_labels=["TEST"],
    )

    assert result["status"] == "ok"
    assert result["reference_type"] == "historical_production_baseline"
    assert result["reference_label"] == (
        "Historical production baseline (not market demand)"
    )
    assert "not market demand" in result["reference_evidence_note"].lower()
    assert "luzon demand" not in result["reference_evidence_note"].lower()


def test_national_utilization_is_not_luzon_demand():
    grci = load_grci()
    result = grci.compute_grci(
        crop="tomato",
        location="Tanauan, Batangas",
        harvest_period="2026-12",
        plans=[{"farm_size_ha": 10.0, "farm_size_margin_ha": 0.0}],
        reference_yield=15.0,
        yield_source="test source",
        reference_amount=300.0,
        reference_type="national_utilization_context",
        crop_record=supported_crop_record(),
        bands=TEST_BANDS,
        source_labels=["TEST"],
    )

    assert result["status"] == "ok"
    assert result["reference_label"] == (
        "National utilization context (not Luzon demand)"
    )
    assert "not luzon demand" in result["reference_evidence_note"].lower()


def test_unknown_reference_type_is_incomplete():
    grci = load_grci()
    for bad_type in ("test_reference", "demo_market_absorption_proxy", "  "):
        result = grci.compute_grci(
            crop="tomato",
            location="Tanauan, Batangas",
            harvest_period="2026-12",
            plans=[{"farm_size_ha": 10.0, "farm_size_margin_ha": 0.0}],
            reference_yield=15.0,
            yield_source="test source",
            reference_amount=375.0,
            reference_type=bad_type,
            crop_record=supported_crop_record(),
            bands=TEST_BANDS,
            source_labels=["TEST"],
        )
        assert result["status"] == "incomplete"
        assert result["risk_state"] is None
        assert result["supply_load_range"] is None
        assert result["reference_label"] is None
        assert result["reference_evidence_note"] is None


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
    ]
    for bands in bad_bands:
        expect_value_error(lambda bands=bands: grci.validate_bands(bands))


if __name__ == "__main__":
    tests = [name for name in globals() if name.startswith("test_")]
    for name in sorted(tests):
        globals()[name]()
    print(f"OK: {len(tests)} GRCI checks passed")
