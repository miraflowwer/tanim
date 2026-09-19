import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_service():
    path = ROOT / "scripts" / "service.py"
    spec = importlib.util.spec_from_file_location("tanim_service_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base_plan(**overrides):
    plan = {
        "crop": "Tomato",
        "region_id": "IV-A",
        "location": "Tanauan, Batangas",
        "farm_size_ha": 2.0,
        "farm_size_margin_ha": 0.2,
        "planting_date": "2026-09-01",
        "harvest_period": "2026-12",
    }
    plan.update(overrides)
    return plan


def historical_baseline():
    return {
        "amount": 100.0,
        "unit": "MT",
        "type": "historical_production_baseline",
        "geography": "CALABARZON (IV-A)",
        "period": "2021-2025",
        "region_id": "IV-A",
    }


def demo_group(crop="Tomato", **overrides):
    is_eggplant = crop.casefold() == "eggplant"
    count = 2 if is_eggplant else 4
    area = 4.0 if is_eggplant else 10.0
    return [
        base_plan(
            crop=crop,
            farm_size_ha=area,
            farm_size_margin_ha=0.0,
            **overrides,
        )
        for _ in range(count)
    ]


def test_fixed_tomato_demo_is_locked():
    service = load_service()
    envelope = service.get_grci_for_plan(
        demo_group("Tomato"),
        use_demo_reference=True,
    )
    assert envelope["error"] is None
    result = envelope["result"]
    assert result["planned_area_range"] == [40.0, 40.0]
    assert result["reference_yield"] == 15.0
    assert result["yield_source"] == "DEMO-2026 synthetic yield"
    assert result["expected_production_range"] == [600.0, 600.0]
    assert result["supply_load_range"] == [1.6, 1.6]
    assert result["risk_state"] == "high"
    assert result["reference_quality"] == "synthetic"
    assert result["evidence_status"] == "fixed_synthetic"
    assert result["evidence_verified"] is False
    assert result["market_demand_wording_allowed"] is False
    assert result["source_labels"] == ["DEMO-2026"]
    assert envelope["lookup"]["yield_record"] is None
    assert envelope["lookup"]["reference_used"]["from_demo"] is True


def test_fixed_eggplant_demo_is_locked():
    service = load_service()
    envelope = service.get_grci_for_plan(
        demo_group("Eggplant"),
        use_demo_reference=True,
    )
    assert envelope["error"] is None
    result = envelope["result"]
    assert result["reference_yield"] == 12.0
    assert result["expected_production_range"] == [96.0, 96.0]
    assert abs(result["supply_load_range"][0] - (96.0 / 180.0)) < 1e-12
    assert result["risk_state"] == "low"


def test_demo_reference_rejects_arbitrary_farmer_plan():
    service = load_service()
    envelope = service.get_grci_for_plan(
        base_plan(farm_size_ha=40.0, farm_size_margin_ha=0.0),
        use_demo_reference=True,
    )
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "invalid_input"
    assert "locked" in envelope["error"]["message"]


def test_non_demo_never_silently_uses_demo_reference():
    service = load_service()
    envelope = service.get_grci_for_plan(base_plan())
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "comparison_required"
    assert "does not substitute synthetic demand" in envelope["error"]["message"]


def test_normal_plan_uses_psa_yield_and_traceable_reference():
    service = load_service()
    envelope = service.get_grci_for_plan(
        base_plan(),
        comparison=historical_baseline(),
        source_labels=["TEST-SOURCE-RECORD"],
    )
    assert envelope["error"] is None
    result = envelope["result"]
    assert abs(result["reference_yield"] - 13.9462) < 1e-9
    assert result["yield_source"].startswith("PSA-OPENSTAT-CROPS")
    assert result["status"] == "unclassified"
    assert result["comparison_state"] is None
    assert result["risk_state"] is None
    assert result["evidence_status"] == "user_provided_unverified"
    assert result["evidence_verified"] is False
    assert result["market_demand_wording_allowed"] is False
    assert result["source_labels"] == ["TEST-SOURCE-RECORD"]
    assert "DEMO-2026" not in result["source_labels"]
    assert result["provenance"]["yield_source_id"] == "PSA-OPENSTAT-CROPS"


def test_non_demo_reference_requires_source_label():
    service = load_service()
    envelope = service.get_grci_for_plan(
        base_plan(),
        comparison=historical_baseline(),
    )
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "invalid_input"
    assert "source_labels" in envelope["error"]["message"]


def test_demo_and_custom_comparison_are_mutually_exclusive():
    service = load_service()
    envelope = service.get_grci_for_plan(
        base_plan(),
        comparison=historical_baseline(),
        source_labels=["TEST"],
        use_demo_reference=True,
    )
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "invalid_input"


def test_runtime_registry_crops_are_resolvable_without_manual_aliases():
    service = load_service()
    context = service.validate_plan(base_plan(crop="Abiu"))
    assert context["crop_id"] == "abiu"


def test_several_farmer_plans_are_aggregated():
    service = load_service()
    plans = [
        base_plan(farm_size_ha=10.0, farm_size_margin_ha=1.0),
        base_plan(farm_size_ha=10.0, farm_size_margin_ha=1.0),
    ]
    envelope = service.get_grci_for_plan(
        plans,
        comparison=historical_baseline(),
        source_labels=["TEST-SOURCE-RECORD"],
    )
    assert envelope["error"] is None
    assert envelope["lookup"]["plan_count"] == 2
    result = envelope["result"]
    assert result["planned_area_range"] == [18.0, 22.0]
    assert abs(result["expected_production_range"][0] - 251.0316) < 1e-9
    assert abs(result["expected_production_range"][1] - 306.8164) < 1e-9


def test_mixed_group_context_fails_closed():
    service = load_service()
    cases = [
        (base_plan(crop="Eggplant"), "same crop"),
        (base_plan(region_id="III"), "same region"),
        (base_plan(location="Lipa, Batangas"), "same location"),
        (base_plan(harvest_period="2027-01"), "same harvest period"),
    ]
    for other, message in cases:
        envelope = service.get_grci_for_plan(
            [base_plan(), other],
            comparison=historical_baseline(),
            source_labels=["TEST"],
        )
        assert envelope["result"] is None
        assert envelope["error"]["code"] == "invalid_input"
        assert message in envelope["error"]["message"]


def test_request_shape_is_unambiguous():
    service = load_service()
    invalid_payloads = [
        {},
        {"plan": base_plan(), "plans": [base_plan()]},
        {"plan": [base_plan()]},
        {"plans": base_plan()},
        {"plans": []},
    ]
    for payload in invalid_payloads:
        envelope = service.build_envelope_from_request(payload)
        assert envelope["result"] is None
        assert envelope["error"]["code"] == "invalid_input"


def test_unknown_crop_fails_closed():
    service = load_service()
    envelope = service.get_grci_for_plan(
        base_plan(crop="not-a-real-crop"),
        comparison=historical_baseline(),
        source_labels=["TEST"],
    )
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "crop_not_found"


def test_missing_crop_region_yield_is_not_guessed():
    service = load_service()
    envelope = service.get_grci_for_plan(
        base_plan(region_id="NCR"),
        comparison={
            **historical_baseline(),
            "region_id": "NCR",
            "geography": "NCR",
        },
        source_labels=["TEST"],
    )
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "yield_not_found"
    assert "never guesses" in envelope["error"]["message"]


def test_bad_dates_and_zero_area_are_rejected():
    service = load_service()
    for plan in (
        base_plan(planting_date="2026-02-30"),
        base_plan(harvest_period="2026-13"),
        base_plan(planting_date="2027-01-01", harvest_period="2026-12"),
        base_plan(farm_size_ha=0),
        base_plan(farm_size_ha=-1),
    ):
        envelope = service.get_grci_for_plan(
            plan,
            comparison=historical_baseline(),
            source_labels=["TEST"],
        )
        assert envelope["result"] is None
        assert envelope["error"]["code"] == "invalid_input"


def test_reference_scope_rules_are_preserved():
    service = load_service()
    local_as_national = {
        "amount": 100,
        "unit": "MT",
        "type": "local_committed_demand",
        "geography": "Philippines",
        "period": "2026-12",
    }
    envelope = service.get_grci_for_plan(
        base_plan(),
        comparison=local_as_national,
        source_labels=["TEST"],
    )
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "invalid_input"

    national = {
        "amount": 1000000,
        "unit": "MT",
        "type": "national_utilization_context",
        "geography": "Philippines",
        "period": "2025",
    }
    envelope = service.get_grci_for_plan(
        base_plan(),
        comparison=national,
        source_labels=["PSA-SUA"],
    )
    assert envelope["error"] is None
    assert envelope["result"]["status"] == "context_only"
    assert envelope["result"]["supply_load_range"] is None
    assert envelope["result"]["risk_state"] is None


def test_explicit_bands_enable_baseline_classification():
    service = load_service()
    bands = [
        (1.0, "low"),
        (1.5, "watch"),
        (float("inf"), "high"),
    ]
    envelope = service.get_grci_for_plan(
        base_plan(),
        comparison=historical_baseline(),
        source_labels=["TEST-SOURCE-RECORD"],
        bands=bands,
    )
    assert envelope["error"] is None
    assert envelope["result"]["status"] == "baseline"
    assert envelope["result"]["comparison_state"] == "low"
    assert envelope["result"]["risk_state"] is None


def test_fixed_demo_rejects_wrong_region_and_overrides():
    service = load_service()

    wrong_region = service.get_grci_for_plan(
        demo_group("Tomato", region_id="III"),
        use_demo_reference=True,
    )
    assert wrong_region["result"] is None
    assert wrong_region["error"]["code"] == "invalid_input"

    custom_bands = service.get_grci_for_plan(
        demo_group("Tomato"),
        bands=[(1.0, "low"), (float("inf"), "high")],
        use_demo_reference=True,
    )
    assert custom_bands["result"] is None
    assert custom_bands["error"]["code"] == "invalid_input"

    custom_sources = service.get_grci_for_plan(
        demo_group("Tomato"),
        source_labels=["NOT-DEMO"],
        use_demo_reference=True,
    )
    assert custom_sources["result"] is None
    assert custom_sources["error"]["code"] == "invalid_input"


def test_custom_comparison_cannot_impersonate_demo_reference():
    service = load_service()
    comparison = {
        "amount": 375,
        "unit": "MT",
        "type": "demo_coordination_baseline",
        "geography": "CALABARZON (IV-A)",
        "period": "2025",
    }
    envelope = service.get_grci_for_plan(
        base_plan(),
        comparison=comparison,
        source_labels=["USER-LABEL"],
    )
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "invalid_input"
    assert "use_demo_reference=true" in envelope["error"]["message"]


def test_source_labels_must_be_non_empty_text():
    service = load_service()
    for labels in ([], [""], [123], ["TEST", " "]):
        envelope = service.get_grci_for_plan(
            base_plan(),
            comparison=historical_baseline(),
            source_labels=labels,
        )
        assert envelope["result"] is None
        assert envelope["error"]["code"] == "invalid_input"


def test_comparison_region_must_match_plan():
    service = load_service()
    comparison = historical_baseline()
    comparison["region_id"] = "III"
    envelope = service.get_grci_for_plan(
        base_plan(),
        comparison=comparison,
        source_labels=["TEST"],
    )
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "invalid_input"
    assert "must match" in envelope["error"]["message"]


def test_non_national_comparison_requires_structured_region():
    service = load_service()
    comparison = historical_baseline()
    comparison.pop("region_id")
    envelope = service.get_grci_for_plan(
        base_plan(),
        comparison=comparison,
        source_labels=["TEST"],
    )
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "invalid_input"
    assert "declare region_id" in envelope["error"]["message"]


def test_local_committed_demand_requires_reviewed_evidence():
    service = load_service()
    comparison = {
        "amount": 100,
        "unit": "MT",
        "type": "local_committed_demand",
        "geography": "Tanauan, Batangas",
        "period": "2026-12",
        "region_id": "IV-A",
    }
    envelope = service.get_grci_for_plan(
        base_plan(),
        comparison=comparison,
        source_labels=["BUYER-CONFIRMATION"],
    )
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "invalid_input"
    assert "reviewed/verified" in envelope["error"]["message"]
    assert "confirmed local demand" in envelope["error"]["message"]


def test_comparison_rejects_unknown_fields():
    service = load_service()
    comparison = historical_baseline()
    comparison["ammount"] = comparison["amount"]
    envelope = service.get_grci_for_plan(
        base_plan(),
        comparison=comparison,
        source_labels=["TEST"],
    )
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "invalid_input"
    assert "unknown field" in envelope["error"]["message"]


def test_request_rejects_unknown_top_level_fields():
    service = load_service()
    payload = {
        "plan": base_plan(),
        "comparison": historical_baseline(),
        "source_labels": ["TEST"],
        "use_demo_refernece": False,
    }
    envelope = service.build_envelope_from_request(payload)
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "invalid_input"
    assert "unknown field" in envelope["error"]["message"]


def test_demo_reference_type_is_pinned():
    service = load_service()
    demo = dict(service.load_demo_references()["tomato"])
    demo["type"] = "local_committed_demand"
    service._DEMO_REFERENCES = {"tomato": demo}
    envelope = service.get_grci_for_plan(
        demo_group("Tomato"),
        use_demo_reference=True,
    )
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "invalid_input"
    assert "demo_coordination_baseline" in envelope["error"]["message"]


def test_options_expose_registry_backed_crop_region_pairs():
    service = load_service()
    options = service.build_options()
    assert len(options["crops"]) > 2
    tomato = next(item for item in options["crops"] if item["id"] == "tomato")
    eggplant = next(item for item in options["crops"] if item["id"] == "eggplant")
    assert "IV-A" in tomato["regions"]
    assert "IV-A" in eggplant["regions"]
    assert tomato["demo_regions"] == ["IV-A"]
    assert eggplant["demo_regions"] == ["IV-A"]
    assert all(item["regions"] for item in options["crops"])
    assert all(
        item["id"] != "demo_coordination_baseline"
        for item in options["reference_types"]
    )
    assert {item["id"] for item in options["reference_types"]} == {
        "historical_production_baseline",
        "local_historical_absorption",
        "national_utilization_context",
    }
    assert "local_committed_demand" not in {
        item["id"] for item in options["reference_types"]
    }


def test_strict_json_rejects_duplicate_keys_and_nonstandard_constants():
    service = load_service()
    for text in (
        '{"plan": {}, "plan": {}}',
        '{"plan": {"farm_size_ha": NaN}}',
        '{"plan": {"farm_size_ha": Infinity}}',
    ):
        try:
            service._strict_json_loads(text)
        except ValueError:
            pass
        else:
            raise AssertionError("strict JSON parser accepted invalid JSON")


def test_envelopes_are_strict_json():
    service = load_service()
    envelope = service.get_grci_for_plan(
        base_plan(farm_size_ha=float("inf")),
        comparison=historical_baseline(),
        source_labels=["TEST"],
    )
    text = json.dumps(envelope, allow_nan=False)
    parsed = json.loads(text)
    assert parsed["error"]["code"] == "invalid_input"


if __name__ == "__main__":
    tests = [name for name in globals() if name.startswith("test_")]
    for name in sorted(tests):
        globals()[name]()
    print(f"OK: {len(tests)} service checks passed")
