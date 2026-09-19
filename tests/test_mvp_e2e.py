import csv
import importlib.util
import json
import pathlib
import socket

ROOT = pathlib.Path(__file__).resolve().parents[1]
DS = ROOT / "datasets"

# Test-only risk bands. These are not final product thresholds.
TEST_BANDS = [
    (1.0, "low"),
    (1.5, "watch"),
    (float("inf"), "high"),
]

# Canonical engine output keys the UI contract depends on.
# Backend and UI must use the same names with the same meanings.
CONTRACT_KEYS = {
    "crop", "location", "harvest_period",
    "planned_area_range", "reference_yield", "yield_source",
    "planned_supply_range", "expected_production_range",
    "reference_amount", "reference_unit", "reference_type",
    "reference_geography", "reference_period",
    "reference_label", "reference_evidence_note",
    "supply_load_range", "status",
    "comparison_state", "comparison_band_range",
    "risk_state", "risk_band_range", "borderline",
    "uncertainty_state", "uncertainty_note", "explanation",
    "provenance", "source_labels",
}


def load_grci():
    path = ROOT / "scripts" / "grci.py"
    spec = importlib.util.spec_from_file_location("grci_e2e", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_demo_plans():
    with open(DS / "demo_farm_plans.csv", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_demo_baseline():
    with open(DS / "demo_coordination_baseline.csv", encoding="utf-8", newline="") as handle:
        return {row["crop_canonical"]: row for row in csv.DictReader(handle)}


def supported_crop_record():
    return {
        "planning_supported": True,
        "coverage": {"production": True, "area": True},
    }


def unsupported_crop_record():
    return {
        "planning_supported": False,
        "coverage": {"production": True, "area": False},
    }


def base_kwargs(**overrides):
    kwargs = {
        "crop": "tomato",
        "location": "Tanauan, Batangas",
        "harvest_period": "2026-12",
        "plans": [{"farm_size_ha": 10.0, "farm_size_margin_ha": 0.0}],
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
    kwargs.update(overrides)
    return kwargs


def demo_result(grci, crop_id):
    rows = [r for r in load_demo_plans() if r["crop_canonical"] == crop_id]
    baseline = load_demo_baseline()[crop_id]
    plans = [
        {
            "farm_size_ha": float(r["farm_size_ha"]),
            "farm_size_margin_ha": float(r["farm_size_margin_ha"]),
        }
        for r in rows
    ]
    return grci.compute_grci(
        crop=crop_id,
        location=rows[0]["municipality"],
        harvest_period=rows[0]["harvest_period"],
        plans=plans,
        reference_yield=float(baseline["reference_yield_mt_per_ha"]),
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


def test_e2e_tomato_fixed_demo():
    grci = load_grci()
    result = demo_result(grci, "tomato")
    assert result["status"] == "ok"
    assert result["planned_area_range"] == [40.0, 40.0]
    assert result["expected_production_range"] == [600.0, 600.0]
    assert approx(result["supply_load_range"][0], 1.6)
    assert result["risk_state"] == "high"
    assert result["uncertainty_state"] == "point"
    assert "600" in result["explanation"]


def test_e2e_eggplant_fixed_demo():
    grci = load_grci()
    result = demo_result(grci, "eggplant")
    assert result["status"] == "ok"
    assert result["planned_area_range"] == [8.0, 8.0]
    assert result["expected_production_range"] == [96.0, 96.0]
    assert approx(result["supply_load_range"][0], 96.0 / 180.0)
    assert result["risk_state"] == "low"
    assert result["uncertainty_state"] == "point"


def test_e2e_one_farmer():
    grci = load_grci()
    result = grci.compute_grci(**base_kwargs(
        plans=[{"farm_size_ha": 2.0, "farm_size_margin_ha": 0.0}],
    ))
    assert result["status"] == "ok"
    assert result["planned_area_range"] == [2.0, 2.0]
    assert result["expected_production_range"] == [30.0, 30.0]
    assert result["uncertainty_state"] == "point"


def test_e2e_several_farmers():
    grci = load_grci()
    result = grci.compute_grci(**base_kwargs(
        plans=[
            {"farm_size_ha": 10.0, "farm_size_margin_ha": 1.0},
            {"farm_size_ha": 10.0, "farm_size_margin_ha": 1.0},
        ],
    ))
    assert result["status"] == "ok"
    assert result["planned_area_range"] == [18.0, 22.0]
    assert result["expected_production_range"] == [270.0, 330.0]


def test_e2e_exact_farm_area():
    grci = load_grci()
    result = grci.compute_grci(**base_kwargs(
        plans=[{"farm_size_ha": 5.0, "farm_size_margin_ha": 0.0}],
    ))
    assert result["uncertainty_state"] == "point"
    assert result["borderline"] is False


def test_e2e_farm_area_with_margin():
    grci = load_grci()
    result = grci.compute_grci(**base_kwargs(
        plans=[{"farm_size_ha": 2.0, "farm_size_margin_ha": 0.2}],
        reference_amount=1000.0,
    ))
    assert result["planned_area_range"] == [1.8, 2.2]
    assert result["expected_production_range"] == [27.0, 33.0]
    assert result["uncertainty_state"] == "range"
    assert grci.format_estimated_range(1.8, 2.2, "ha") == (
        "Estimated range: 1.8 ha to 2.2 ha"
    )
    assert grci.format_estimated_range(27.0, 33.0, "MT") == (
        "Estimated range: 27 MT to 33 MT"
    )


def test_e2e_missing_yield_reference():
    grci = load_grci()
    result = grci.compute_grci(**base_kwargs(
        reference_yield=None, yield_source=None,
    ))
    assert result["status"] == "incomplete"
    assert result["planned_supply_range"] is None
    assert result["expected_production_range"] is None
    assert result["supply_load_range"] is None
    assert "yield" in result["uncertainty_note"].lower()


def test_e2e_unsupported_crop_region_pair():
    grci = load_grci()
    result = grci.compute_grci(**base_kwargs(
        crop="unknown-crop",
        crop_record=unsupported_crop_record(),
    ))
    assert result["status"] == "unsupported"
    assert result["risk_state"] is None
    assert result["planned_supply_range"] is None
    assert result["expected_production_range"] is None


def test_e2e_invalid_or_negative_farm_area():
    grci = load_grci()
    for plans in (
        [{"farm_size_ha": -1.0, "farm_size_margin_ha": 0.0}],
        [{"farm_size_ha": 1.0, "farm_size_margin_ha": -0.2}],
        [{"farm_size_ha": "not-a-number", "farm_size_margin_ha": 0.0}],
    ):
        result = grci.compute_grci(**base_kwargs(plans=plans))
        assert result["status"] == "invalid"
        assert result["risk_state"] is None
        assert result["planned_area_range"] is None


def test_e2e_missing_location():
    grci = load_grci()
    result = grci.compute_grci(**base_kwargs(location=""))
    assert result["status"] == "incomplete"
    assert result["risk_state"] is None
    assert "location" in result["uncertainty_note"].lower()


def test_e2e_missing_harvest_period():
    grci = load_grci()
    result = grci.compute_grci(**base_kwargs(harvest_period=""))
    assert result["status"] == "incomplete"
    assert result["risk_state"] is None
    assert "harvest" in result["uncertainty_note"].lower()


def test_e2e_local_committed_demand():
    grci = load_grci()
    result = grci.compute_grci(**base_kwargs(
        reference_type="local_committed_demand",
    ))
    assert result["status"] == "ok"
    assert result["risk_state"] == "low"
    assert result["market_demand_wording_allowed"] is True
    assert result["reference_label"] == "Local committed demand"


def test_e2e_historical_absorption():
    grci = load_grci()
    result = grci.compute_grci(**base_kwargs(
        reference_type="local_historical_absorption",
    ))
    assert result["status"] == "ok"
    assert result["supply_load_range"] == [1.0, 1.0]
    assert result["market_demand_wording_allowed"] is False
    assert "not committed demand" in result["reference_label"].lower()


def test_e2e_historical_production_baseline():
    grci = load_grci()
    result = grci.compute_grci(**base_kwargs(
        reference_type="historical_production_baseline",
        reference_geography="CALABARZON (IV-A)",
    ))
    assert result["status"] == "baseline"
    assert result["risk_state"] is None
    assert result["supply_load_range"] == [1.0, 1.0]
    assert result["market_demand_wording_allowed"] is False


def test_e2e_national_utilization_context():
    grci = load_grci()
    result = grci.compute_grci(**base_kwargs(
        reference_type="national_utilization_context",
        reference_geography="Philippines",
    ))
    assert result["status"] == "context_only"
    assert result["risk_state"] is None
    assert result["supply_load_range"] is None
    assert "not luzon demand" in result["reference_label"].lower()


def test_e2e_synthetic_demo_reference():
    grci = load_grci()
    result = demo_result(grci, "tomato")
    assert result["reference_quality"] == "synthetic"
    assert result["market_demand_wording_allowed"] is False
    assert result["reference_label"] == (
        "Demo coordination baseline (not market demand)"
    )
    assert "not observed local market demand" in result["reference_evidence_note"].lower()


def test_e2e_borderline_from_uncertainty():
    grci = load_grci()
    result = grci.compute_grci(**base_kwargs(
        plans=[
            {"farm_size_ha": 10.0, "farm_size_margin_ha": 1.0},
            {"farm_size_ha": 10.0, "farm_size_margin_ha": 1.0},
        ],
        reference_amount=300.0,
    ))
    assert result["status"] == "ok"
    assert result["planned_area_range"] == [18.0, 22.0]
    assert result["expected_production_range"] == [270.0, 330.0]
    assert approx(result["supply_load_range"][0], 0.9)
    assert approx(result["supply_load_range"][1], 1.1)
    assert result["uncertainty_state"] == "borderline"
    assert result["risk_state"] == "borderline"
    assert result["risk_band_range"] == ["low", "watch"]


def test_contract_result_keys_match_documented_output():
    grci = load_grci()
    result = demo_result(grci, "tomato")
    assert CONTRACT_KEYS <= set(result)
    assert isinstance(result["planned_area_range"], list)
    assert isinstance(result["expected_production_range"], list)
    assert isinstance(result["supply_load_range"], list)
    assert isinstance(result["provenance"], dict)
    assert isinstance(result["explanation"], str) and result["explanation"]


def test_guard_historical_production_never_market_demand():
    grci = load_grci()
    assert grci.allows_market_demand_wording("historical_production_baseline") is False
    result = grci.compute_grci(**base_kwargs(
        reference_type="historical_production_baseline",
        reference_geography="CALABARZON (IV-A)",
    ))
    assert result["market_demand_wording_allowed"] is False
    assert "not market demand" in result["reference_label"].lower()
    label, _ = grci.describe_reference("historical_production_baseline")
    assert "market demand" not in label.lower().replace("not market demand", "")


def test_guard_national_never_local_demand():
    grci = load_grci()
    result = grci.compute_grci(**base_kwargs(
        reference_type="national_utilization_context",
        reference_geography="Philippines",
    ))
    assert result["status"] == "context_only"
    assert result["supply_load_range"] is None
    assert result["risk_state"] is None
    assert "luzon" not in result["reference_geography"].lower()
    assert "philipp" in result["reference_geography"].casefold()


def test_guard_synthetic_never_observed():
    plans = load_demo_plans()
    baseline = load_demo_baseline()
    assert {r["data_status"] for r in plans} == {"synthetic"}
    assert {r["data_status"] for r in baseline.values()} == {"derived_demo"}
    assert "observed" not in {r["data_status"] for r in plans}
    assert "observed" not in {r["data_status"] for r in baseline.values()}

    grci = load_grci()
    for crop_id in ("tomato", "eggplant"):
        result = demo_result(grci, crop_id)
        assert result["reference_quality"] == "synthetic"
        assert "not observed" in result["reference_evidence_note"].lower()


def test_guard_missing_never_guessed():
    grci = load_grci()
    missing_yield = grci.compute_grci(**base_kwargs(
        reference_yield=None, yield_source=None,
    ))
    assert missing_yield["planned_supply_range"] is None
    assert missing_yield["expected_production_range"] is None

    unsupported = grci.compute_grci(**base_kwargs(
        crop="unknown-crop",
        crop_record=unsupported_crop_record(),
    ))
    assert unsupported["planned_area_range"] is None
    assert unsupported["planned_supply_range"] is None

    missing_amount = grci.compute_grci(**base_kwargs(reference_amount=None))
    assert missing_amount["supply_load_range"] is None


def test_offline_demo_needs_no_network():
    real_socket = socket.socket

    def blocked_socket(*args, **kwargs):
        raise AssertionError("network use is not allowed in the offline demo")

    grci = load_grci()
    socket.socket = blocked_socket
    try:
        tomato = demo_result(grci, "tomato")
        eggplant = demo_result(grci, "eggplant")
    finally:
        socket.socket = real_socket
    assert tomato["status"] == "ok"
    assert eggplant["status"] == "ok"
    assert (DS / "generated" / "yield_summary.csv").exists()
    assert (DS / "demo_farm_plans.csv").exists()
    assert (DS / "demo_coordination_baseline.csv").exists()


if __name__ == "__main__":
    tests = [name for name in globals() if name.startswith("test_")]
    for name in sorted(tests):
        globals()[name]()
    print(f"OK: {len(tests)} MVP end-to-end checks passed")
