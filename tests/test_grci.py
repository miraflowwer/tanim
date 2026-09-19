import csv
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DS = ROOT / "datasets"

TEST_BANDS = [(1.0, "low"), (1.5, "watch"), (float("inf"), "high")]


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
        return {row["crop_canonical"]: row for row in csv.DictReader(handle)}


def demo_result(grci, crop_id):
    plans = [
        {
            "farm_size_ha": float(row["farm_size_ha"]),
            "farm_size_margin_ha": float(row["farm_size_margin_ha"]),
        }
        for row in load_demo_plans()
        if row["crop_canonical"] == crop_id
    ]
    demand = load_demo_demand()[crop_id]
    rows = [row for row in load_demo_plans() if row["crop_canonical"] == crop_id]
    return grci.compute_grci(
        crop=crop_id,
        location=rows[0]["municipality"],
        harvest_period=rows[0]["harvest_period"],
        plans=plans,
        reference_yield=float(demand["demo_yield_mt_per_ha"]),
        yield_source="DEMO-2026 demo yield",
        reference_amount=float(demand["demo_qty_mt"]),
        reference_type="demo_proxy",
        crop_record={"planning_supported": True},
        bands=TEST_BANDS,
        source_labels=["DEMO-2026"],
    )


def approx(first, second, tol=1e-9):
    return abs(first - second) <= tol


def test_demo_fixture_is_reproducible():
    grci = load_grci()
    plans = load_demo_plans()
    totals = {}
    for row in plans:
        totals[row["crop_canonical"]] = totals.get(row["crop_canonical"], 0.0) + float(
            row["farm_size_ha"]
        )
    assert totals == {"tomato": 40.0, "eggplant": 8.0}

    tomato = demo_result(grci, "tomato")
    eggplant = demo_result(grci, "eggplant")

    assert tomato["planned_area_range"] == [40.0, 40.0]
    assert tomato["planned_supply_range"] == [600.0, 600.0]
    assert approx(tomato["supply_load_range"][0], 1.6)
    assert approx(tomato["supply_load_range"][1], 1.6)
    assert tomato["risk_state"] == "high"
    assert tomato["borderline"] is False

    assert eggplant["planned_area_range"] == [8.0, 8.0]
    assert eggplant["planned_supply_range"] == [96.0, 96.0]
    assert approx(eggplant["supply_load_range"][0], 96.0 / 180.0)
    assert approx(eggplant["supply_load_range"][1], 96.0 / 180.0)
    assert eggplant["risk_state"] == "low"
    assert eggplant["borderline"] is False

    for result in (tomato, eggplant):
        for key in (
            "crop",
            "location",
            "harvest_period",
            "planned_area_range",
            "reference_yield",
            "yield_source",
            "planned_supply_range",
            "reference_amount",
            "reference_type",
            "supply_load_range",
            "risk_state",
            "borderline",
            "uncertainty_note",
            "source_labels",
        ):
            assert key in result

    assert demo_result(grci, "tomato") == tomato
    assert demo_result(grci, "eggplant") == eggplant


def test_approximate_farm_area_produces_range():
    grci = load_grci()
    assert grci.area_range(2.0, 0.2) == (1.8, 2.2)
    assert grci.area_range(1.0, 5.0) == (0.0, 6.0)

    low, high = grci.collective_area_range(
        [
            {"farm_size_ha": 10.0, "farm_size_margin_ha": 1.0},
            {"farm_size_ha": 10.0, "farm_size_margin_ha": 1.0},
        ]
    )
    assert (low, high) == (18.0, 22.0)

    supply = grci.planned_supply_range(low, high, 15.0)
    assert supply == (270.0, 330.0)

    load = grci.supply_load_range(supply[0], supply[1], 300.0)
    assert approx(load[0], 0.9)
    assert approx(load[1], 1.1)

    result = grci.compute_grci(
        crop="tomato",
        location="Tanauan, Batangas",
        harvest_period="2026-12",
        plans=[
            {"farm_size_ha": 10.0, "farm_size_margin_ha": 1.0},
            {"farm_size_ha": 10.0, "farm_size_margin_ha": 1.0},
        ],
        reference_yield=15.0,
        yield_source="test",
        reference_amount=300.0,
        reference_type="demo_proxy",
        crop_record={"planning_supported": True},
        bands=TEST_BANDS,
        source_labels=["DEMO-2026"],
    )
    assert result["planned_area_range"] == [18.0, 22.0]
    assert result["planned_supply_range"] == [270.0, 330.0]
    assert result["supply_load_range"][0] < result["supply_load_range"][1]


def test_missing_historical_yield():
    grci = load_grci()
    result = grci.compute_grci(
        crop="tomato",
        location="Tanauan, Batangas",
        harvest_period="2026-12",
        plans=[{"farm_size_ha": 10.0, "farm_size_margin_ha": 0.0}],
        reference_yield=None,
        yield_source=None,
        reference_amount=375.0,
        reference_type="demo_proxy",
        crop_record={"planning_supported": True},
        bands=TEST_BANDS,
        source_labels=["DEMO-2026"],
    )
    assert result["planned_supply_range"] is None
    assert result["supply_load_range"] is None
    assert result["risk_state"] == "unknown"
    assert "yield" in (result["uncertainty_note"] or "").lower()


def test_unsupported_crop_join():
    grci = load_grci()
    production_only = {
        "crop_id": "eggplant",
        "coverage": {"production": True, "area": False},
        "planning_supported": False,
    }
    result = grci.compute_grci(
        crop="eggplant",
        location="Tanauan, Batangas",
        harvest_period="2026-12",
        plans=[{"farm_size_ha": 8.0, "farm_size_margin_ha": 0.0}],
        reference_yield=12.0,
        yield_source="test",
        reference_amount=180.0,
        reference_type="demo_proxy",
        crop_record=production_only,
        bands=TEST_BANDS,
        source_labels=["DEMO-2026"],
    )
    assert result["risk_state"] == "unsupported"
    assert result["planned_supply_range"] is None
    assert result["supply_load_range"] is None
    assert result["uncertainty_note"]

    assert grci.is_planning_supported({"planning_supported": True}) is True
    assert grci.is_planning_supported(production_only) is False
    assert grci.is_planning_supported(None) is False


def test_missing_geography():
    grci = load_grci()
    for bad_location in (None, "", "   "):
        result = grci.compute_grci(
            crop="tomato",
            location=bad_location,
            harvest_period="2026-12",
            plans=[{"farm_size_ha": 10.0, "farm_size_margin_ha": 0.0}],
            reference_yield=15.0,
            yield_source="test",
            reference_amount=375.0,
            reference_type="demo_proxy",
            crop_record={"planning_supported": True},
            bands=TEST_BANDS,
            source_labels=["DEMO-2026"],
        )
        assert result["risk_state"] == "incomplete"
        assert "location" in (result["uncertainty_note"] or "").lower()


def test_zero_reference_values():
    grci = load_grci()
    assert grci.supply_load_range(600.0, 600.0, 0) is None
    assert grci.supply_load_range(600.0, 600.0, None) is None

    result = grci.compute_grci(
        crop="tomato",
        location="Tanauan, Batangas",
        harvest_period="2026-12",
        plans=[{"farm_size_ha": 40.0, "farm_size_margin_ha": 0.0}],
        reference_yield=15.0,
        yield_source="test",
        reference_amount=0,
        reference_type="demo_proxy",
        crop_record={"planning_supported": True},
        bands=TEST_BANDS,
        source_labels=["DEMO-2026"],
    )
    assert result["planned_supply_range"] == [600.0, 600.0]
    assert result["supply_load_range"] is None
    assert result["risk_state"] == "unknown"
    assert "reference amount" in (result["uncertainty_note"] or "").lower()


def test_grci_range_crossing_risk_boundary():
    grci = load_grci()
    result = grci.compute_grci(
        crop="tomato",
        location="Tanauan, Batangas",
        harvest_period="2026-12",
        plans=[{"farm_size_ha": 10.0, "farm_size_margin_ha": 5.0}],
        reference_yield=10.0,
        yield_source="test",
        reference_amount=100.0,
        reference_type="demo_proxy",
        crop_record={"planning_supported": True},
        bands=TEST_BANDS,
        source_labels=["DEMO-2026"],
    )
    assert result["planned_area_range"] == [5.0, 15.0]
    assert result["planned_supply_range"] == [50.0, 150.0]
    assert approx(result["supply_load_range"][0], 0.5)
    assert approx(result["supply_load_range"][1], 1.5)
    assert result["borderline"] is True
    assert result["risk_state"] == "borderline"
    assert "farm-size estimate" in (result["uncertainty_note"] or "")

    low_band, high_band, borderline = grci.classify_range(0.5, 1.5, TEST_BANDS)
    assert (low_band, high_band, borderline) == ("low", "watch", True)
    assert grci.classify_range(1.6, 1.6, TEST_BANDS) == ("high", "high", False)


if __name__ == "__main__":
    tests = [name for name in globals() if name.startswith("test_")]
    for name in sorted(tests):
        globals()[name]()
    print(f"OK: {len(tests)} GRCI checks passed")
