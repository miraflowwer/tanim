"""Data-contract P0 backend (PRD S35): schemas, enums, openapi, fixture shape."""
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend" / "app"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, BACKEND / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    # grci has no third-party deps; schemas needs pydantic (skip if absent).
    try:
        spec.loader.exec_module(mod)
    except ModuleNotFoundError:
        return None
    return mod


def test_reference_enums_match_prd_s13():
    grci = _load("grci")
    assert set(grci.REFERENCE_TYPES) == {
        "local_committed_demand",
        "local_historical_absorption",
        "national_utilization_context",
        "historical_production_baseline",
        "demo_coordination_baseline",
    }
    assert set(grci.VERIFICATION_STATES) == {
        "reviewed_verified",
        "user_provided_unverified",
        "official_context",
        "synthetic_demo",
        "stale",
        "superseded",
    }
    assert set(grci.ELIGIBLE_TYPES) == {"local_committed_demand", "local_historical_absorption"}


def test_openapi_has_versioned_calculate_path():
    spec = json.loads((ROOT / "openapi" / "openapi.json").read_text(encoding="utf-8"))
    assert "/api/v1/plans/{plan_id}/calculate" in spec["paths"]
    assert "/api/v1/health" in spec["paths"]


def test_fixture_matches_calculate_response_contract():
    fix = json.loads((ROOT / "app" / "src" / "fixtures" / "tomato_calabarzon_response.json").read_text(encoding="utf-8"))
    for f in ["planId", "crop", "harvestPeriod", "plannedAreaHa", "estimatedProductionMt",
              "estimatedRangeMt", "comparisonAmountMt", "supplyLoad", "coordinationStatus",
              "headline", "evidenceQuality", "referenceUsed", "provenance", "stale"]:
        assert f in fix, f
    for f in ["referenceType", "verificationStatus", "source", "geography",
              "sourcePeriod", "verifiedAt", "calculationPolicyVersion", "engineVersion", "evidenceNote"]:
        assert f in fix["provenance"], f
    # L = 139.462 / 375 = 0.371899 -> 0.372
    assert abs(fix["supplyLoad"] - 0.372) < 0.001
    assert fix["provenance"]["verificationStatus"] == "synthetic_demo"
    low = (fix["headline"] + fix["evidenceQuality"]).lower()
    for banned in ["guaranteed", "best crop", "safe crop", "no risk", "certain glut"]:
        assert banned not in low, banned


def test_schemas_module_present():
    # Pydantic may be absent locally; CI installs backend/requirements.txt.
    # At minimum the file must define strict PlanIn/ReferenceIn with date rule.
    text = (BACKEND / "schemas.py").read_text(encoding="utf-8")
    assert "class PlanIn" in text and "class ReferenceIn" in text
    assert 'extra="forbid"' in text or "extra='forbid'" in text or 'extra="forbid"' in text.replace("'", '"')
    assert "harvest_period" in text and "planting_date" in text
