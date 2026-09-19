"""API integration: 9-step calculate, auth/RBAC, validation, audit, consent (PRD §§20, 32, 33, 40)."""
import os
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import audit as audit_mod
from app import consent as consent_mod
from app import observability as obs
from app import store as S
from app.auth import dev_token_for
from app.main import app

os.environ["ALLOW_DEV_AUTH"] = "true"

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
TEN_FIELDS = ["calculation_id", "request_id", "engine_version", "policy_version",
              "dataset_version", "reference_version", "organization_id",
              "status", "duration_ms", "timestamp"]


@pytest.fixture(autouse=True)
def _reset():
    S.reset_store()
    audit_mod.reset_audit()
    consent_mod.reset_consents()
    obs.reset_observability()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def _h(user_id: str) -> dict:
    return {"Authorization": f"Bearer {dev_token_for(user_id)}"}


# --- health / identity ---
def test_health_and_readiness_and_request_id(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert UUID_RE.match(r.headers["x-request-id"])
    r2 = client.get("/api/v1/readiness")
    assert r2.status_code == 200 and r2.json()["status"] == "ready"
    r3 = client.get("/api/v1/health", headers={"X-Request-ID": "req-123"})
    assert r3.headers["x-request-id"] == "req-123"


def test_me_and_unauthorized(client):
    assert client.get("/api/v1/me").status_code == 401
    r = client.get("/api/v1/me", headers=_h("farmer-1"))
    assert r.json()["org_roles"] == {"org-1": "farmer"}


# --- 9-step calculate: happy path ---
def test_calculate_happy_path_persists_versions_and_3_levels(client):
    r = client.post("/api/v1/plans/plan-tomato-1/calculate",
                    headers={**_h("farmer-1"), "X-Request-ID": "req-tomato-1"})
    assert r.status_code == 200, r.text
    body = r.json()
    # S = 3.1 × 3.0 = 9.3; L = 9.3 / 25 = 0.372
    assert body["primary"]["estimated_production_mt"] == pytest.approx(9.3)
    assert body["secondary"]["supply_load"] == pytest.approx(0.372)
    assert body["secondary"]["comparison_amount_mt"] == 25.0
    assert body["primary"]["coordination_status"] == "within_reference"
    for level in ("primary", "secondary", "detailed_evidence"):
        assert level in body, level
    assert body["detailed_evidence"]["calculation_policy_version"] == 1
    assert body["detailed_evidence"]["engine_version"] == "0.1.0"
    assert body["request_id"] == "req-tomato-1"
    assert UUID_RE.match(body["calculation_id"])
    assert body["calculation_id"][14] == "7"  # uuid7
    # persisted run: all versions + org + rev + request + duration + timestamp
    run = S.CALCULATIONS[body["calculation_id"]]
    assert (run["org_id"], run["plan_revision"], run["request_id"]) == ("org-1", 1, "req-tomato-1")
    assert run["policy_version"] == 1 and run["registry_version"] == 7
    assert run["yield_reference_version"] == 2 and run["comparison_reference_version"] == 3
    assert run["duration_ms"] >= 0 and "timestamp" in run
    # retrievable + §33 10-field log, no PII
    assert client.get(f"/api/v1/calculations/{body['calculation_id']}",
                      headers=_h("farmer-1")).status_code == 200
    assert len(obs.CALC_LOGS) == 1
    for f in TEN_FIELDS:
        assert f in obs.CALC_LOGS[0], f
    assert "farmer1" not in str(obs.CALC_LOGS[0])


def test_calculate_insufficient_evidence_is_valid_result(client):
    r = client.post("/api/v1/plans/plan-eggplant-1/calculate", headers=_h("farmer-1"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "incomplete"
    assert body["primary"]["coordination_status"] == "insufficient_evidence"
    assert body["primary"]["estimated_production_mt"] == pytest.approx(5.0)  # 2.0 × 2.5
    assert body["secondary"]["supply_load"] is None
    assert obs.COUNTERS.get("missing_evidence", 0) >= 1


def test_calculate_synthetic_never_enters_prod_calc(client):
    # org-2 tomato has ONLY a synthetic demo reference -> must stay insufficient.
    r = client.post("/api/v1/plans/plan-org2-tomato/calculate", headers=_h("farmer-2"))
    assert r.status_code == 200
    assert r.json()["primary"]["coordination_status"] == "insufficient_evidence"


def test_calculate_crop_unsupported_404(client):
    S.PLANS["plan-bad"] = {"id": "plan-bad", "org_id": "org-1", "farm_id": None,
                           "crop_code": "quinoa", "owner_user_id": "farmer-1",
                           "status": "planned",
                           "revisions": [{"revision_number": 1, "area_ha": 1.0,
                                          "area_margin_ha": 0.0, "planting_date": date(2026, 9, 1),
                                          "harvest_period": date(2026, 12, 1),
                                          "created_by": "farmer-1", "created_at": "2026-09-10T00:00:00+00:00"}],
                           "current_revision": 1, "created_at": "2026-09-10T00:00:00+00:00"}
    r = client.post("/api/v1/plans/plan-bad/calculate", headers=_h("farmer-1"))
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "crop_unsupported"


def test_calculate_yield_unavailable_404(client):
    r = client.post("/api/v1/plans", headers=_h("farmer-1"), json={
        "crop_code": "ampalaya", "organization_id": "org-1", "area_ha": 1.0,
        "planting_date": "2026-09-01", "harvest_period": "2026-12-01"})
    assert r.status_code == 201
    pid = r.json()["id"]
    r2 = client.post(f"/api/v1/plans/{pid}/calculate", headers=_h("farmer-1"))
    assert r2.status_code == 404
    assert r2.json()["detail"]["code"] == "yield_unavailable"


# --- authz / RBAC ---
def test_farmer_verify_403_and_permission_denied_metric(client):
    before = obs.COUNTERS.get("permission_denied", 0)
    r = client.post("/api/v1/references/ref-tomato-1/verify",
                    headers=_h("farmer-1"), json={})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "permission_denied"
    assert obs.COUNTERS.get("permission_denied", 0) == before + 1


def test_reviewer_verify_emits_audit(client):
    # create + submit as farmer, verify as reviewer
    r = client.post("/api/v1/references", headers=_h("coord-1"), json={
        "crop_code": "tomato", "organization_id": "org-1", "amount_mt": 50.0,
        "reference_type": "local_committed_demand", "geography": "CALABARZON",
        "period": "2026-H2", "source": "LGU program"})
    assert r.status_code == 201
    assert r.json()["verification_status"] == "user_provided_unverified"  # never auto-verified
    rid = r.json()["id"]
    assert client.post(f"/api/v1/references/{rid}/submit",
                       headers=_h("coord-1"), json={}).status_code == 200
    rv = client.post(f"/api/v1/references/{rid}/verify",
                     headers=_h("reviewer-1"), json={"note": "checked"})
    assert rv.status_code == 200
    assert rv.json()["verification_status"] == "reviewed_verified"
    actions = [e["action"] for e in audit_mod.AUDIT_LOG]
    assert ["reference.created", "reference.submitted", "reference.verified"] == actions


def test_cross_org_tamper_rejected(client):
    # farmer-1 (org-1) calculating org-2's plan -> 403
    r = client.post("/api/v1/plans/plan-org2-tomato/calculate", headers=_h("farmer-1"))
    assert r.status_code == 403
    # ?org_id= mismatch against resource org -> 403
    r2 = client.post("/api/v1/plans/plan-tomato-1/calculate?org_id=org-2", headers=_h("farmer-1"))
    assert r2.status_code == 403
    assert r2.json()["detail"]["code"] == "permission_denied"


def test_audit_events_privileged(client):
    assert client.get("/api/v1/audit-events?org_id=org-1", headers=_h("farmer-1")).status_code == 403
    r = client.get("/api/v1/audit-events?org_id=org-1", headers=_h("reviewer-1"))
    assert r.status_code == 200 and isinstance(r.json()["events"], list)


def test_exports_gated_and_audited(client):
    r = client.post("/api/v1/exports", headers=_h("farmer-1"),
                    json={"organization_id": "org-1", "purpose": "x", "include_individuals": True})
    assert r.status_code == 403
    ok = client.post("/api/v1/exports", headers=_h("admin-1"),
                     json={"organization_id": "org-1", "purpose": "board report",
                           "include_individuals": True})
    assert ok.status_code == 201
    assert any(e["action"] == "export.created" for e in audit_mod.AUDIT_LOG)


# --- validation ---
def test_plan_validation_negatives(client):
    base = {"crop_code": "tomato", "organization_id": "org-1", "area_ha": 2.0,
            "planting_date": "2026-09-01", "harvest_period": "2026-12-01"}
    assert client.post("/api/v1/plans", headers=_h("farmer-1"),
                       json={**base, "area_ha": 0}).status_code == 422
    assert client.post("/api/v1/plans", headers=_h("farmer-1"),
                       json={**base, "harvest_period": "2026-08-01"}).status_code == 422
    # browser-supplied evidence rejected (extra=forbid)
    assert client.post("/api/v1/plans", headers=_h("farmer-1"),
                       json={**base, "reference_type": "local_committed_demand"}).status_code == 422
    assert client.post("/api/v1/plans", headers=_h("farmer-1"),
                       json={**base, "crop_code": "quinoa"}).status_code == 422  # registry


def test_reference_review_window_rejected(client):
    ref = {"crop_code": "tomato", "organization_id": "org-1", "amount_mt": 10.0,
           "reference_type": "local_committed_demand", "geography": "CALABARZON",
           "period": "2026-H2", "source": "LGU",
           "effective_from": "2026-06-01", "effective_to": "2026-01-01"}
    assert client.post("/api/v1/references", headers=_h("coord-1"), json=ref).status_code == 422


def test_payload_too_large_413(client):
    big = {"crop_code": "x" * 1_100_000, "organization_id": "org-1", "area_ha": 1.0,
           "planting_date": "2026-09-01", "harvest_period": "2026-12-01"}
    r = client.post("/api/v1/plans", headers=_h("farmer-1"), json=big)
    assert r.status_code == 413


# --- consent split ---
def test_consent_operational_vs_research_split(client):
    op = client.post("/api/v1/consents?org_id=org-1", headers=_h("farmer-1"), json={
        "consent_type": "operational", "purpose": "coordination", "policy_version": "v1"})
    re = client.post("/api/v1/consents?org_id=org-1", headers=_h("farmer-1"), json={
        "consent_type": "research", "purpose": "model training", "policy_version": "v1"})
    assert op.status_code == 201 and re.status_code == 201
    assert op.json()["version"] == 1 and "consented_at" in op.json()
    w = client.post("/api/v1/consents/withdraw?org_id=org-1", headers=_h("farmer-1"),
                    json={"consent_type": "research"})
    assert w.status_code == 200
    mine = client.get("/api/v1/consents/me?org_id=org-1", headers=_h("farmer-1")).json()["consents"]
    assert {c["consent_type"] for c in mine} == {"operational"}  # research gone, operational kept


# --- misc route groups smoke ---
def test_prd_route_groups_present(client):
    h = _h("coord-1")
    assert client.get("/api/v1/organizations/org-1/aggregates", headers=h).status_code == 200
    assert client.get("/api/v1/crops", headers=h).status_code == 200
    assert client.get("/api/v1/crops/tomato/yield?geography=CALABARZON", headers=h).status_code == 200
    assert client.get("/api/v1/prices", headers=h).status_code == 200
    assert client.get("/api/v1/context/weather?geography=CALABARZON", headers=h).status_code == 200
    assert client.get("/api/v1/context/climate", headers=h).status_code == 200
    assert client.get("/api/v1/context/suitability", headers=h).status_code == 200
    assert client.get("/api/v1/data-sources", headers=h).status_code == 200
    assert client.get("/api/v1/data-sources/psa-yield/freshness", headers=h).status_code == 200
    assert client.get("/api/v1/policies/latest", headers=h).status_code == 200


def test_role_change_and_member_removed_audited(client):
    r = client.put("/api/v1/organizations/org-1/members/farmer-1", headers=_h("admin-1"),
                   json={"role": "coordinator"})
    assert r.status_code == 200 and r.json()["action"] == "role.changed"
    d = client.delete("/api/v1/organizations/org-1/members/farmer-1", headers=_h("admin-1"))
    assert d.status_code == 200 and d.json()["action"] == "member.removed"


@pytest.mark.parametrize("changed", [
    {"org_id": "org-2"},
    {"crop_code": "eggplant"},
    {"geography": "NCR"},
    {"period": "2026-H1"},
    {"effective_from": date(2099, 1, 1)},
    {"effective_to": date(2020, 1, 1)},
    {"review": "superseded"},
    {"verification_status": "synthetic_demo"},
    {"reference_type": "demo_coordination_baseline"},
])
def test_calculation_rejects_reference_outside_exact_scope_and_validity(client, changed):
    # Exercise FastAPI resolution, not a test-side reimplementation of the predicate.
    S.REFERENCES["ref-tomato-1"].update(changed)
    result = client.post(
        "/api/v1/plans/plan-tomato-1/calculate", headers=_h("farmer-1")
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["status"] == "incomplete"
    assert body["primary"]["coordination_status"] == "insufficient_evidence"
    assert body["secondary"]["comparison_amount_mt"] is None
    assert body["secondary"]["supply_load"] is None


def test_active_aggregate_and_calculation_respect_plan_lifecycle(client):
    url = "/api/v1/organizations/org-1/aggregates"
    headers = _h("coord-1")
    S.PLANS["plan-tomato-1"]["status"] = "draft"
    rows = client.get(url, headers=headers).json()["rows"]
    assert any(row["crop_code"] == "tomato" and row["planned_area_ha"] == 3.1
               for row in rows)

    for inactive in ("cancelled", "harvested"):
        S.PLANS["plan-tomato-1"]["status"] = inactive
        rows = client.get(url, headers=headers).json()["rows"]
        assert all(row["crop_code"] != "tomato" for row in rows)
        response = client.post(
            "/api/v1/plans/plan-tomato-1/calculate", headers=_h("farmer-1")
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "plan_inactive"


def test_reference_version_scope_and_supersession_provenance(client):
    candidate = {
        "crop_code": "tomato", "amount_mt": 30.0,
        "reference_type": "local_committed_demand",
        "geography": "CALABARZON", "period": "2026-H2",
        "source": "Reviewed coop record", "effective_from": "2026-01-01",
    }
    other_org = client.post(
        "/api/v1/references", headers=_h("farmer-2"),
        json={**candidate, "organization_id": "org-2"},
    )
    assert other_org.status_code == 201
    assert other_org.json()["version"] == 1

    this_org = client.post(
        "/api/v1/references", headers=_h("coord-1"),
        json={**candidate, "organization_id": "org-1"},
    )
    assert this_org.status_code == 201
    assert this_org.json()["version"] == 4

    predecessor = S.REFERENCES["ref-tomato-1"]
    original_history = [dict(event) for event in predecessor["review_history"]]
    successor = client.post(
        "/api/v1/references/ref-tomato-1/supersede",
        headers=_h("reviewer-1"),
        json={**candidate, "organization_id": "org-1"},
    )
    assert successor.status_code == 200, successor.text
    body = successor.json()
    assert body["version"] == 5
    assert body["predecessor_id"] == "ref-tomato-1"
    assert body["review"] == "draft"
    assert predecessor["successor_id"] == body["id"]
    assert predecessor["review"] == "superseded"
    assert predecessor["review_history"][:len(original_history)] == original_history
    assert client.post(
        "/api/v1/references/ref-tomato-1/verify",
        headers=_h("reviewer-1"), json={},
    ).status_code == 409
    assert client.post(
        f"/api/v1/references/{body['id']}/submit",
        headers=_h("coord-1"), json={},
    ).status_code == 200
    verified = client.post(
        f"/api/v1/references/{body['id']}/verify",
        headers=_h("reviewer-1"), json={"note": "successor checked"},
    )
    assert verified.status_code == 200
    assert verified.json()["verification_status"] == "reviewed_verified"
    assert [event["to"] for event in verified.json()["review_history"]] == [
        "under_review", "verified"
    ]


def test_plan_creation_links_only_an_owned_farm(client):
    created = client.post("/api/v1/farms", headers=_h("farmer-1"), json={
        "organization_id": "org-1", "name": "San Isidro field",
    })
    assert created.status_code == 201, created.text
    farm_id = created.json()["id"]
    plan_input = {
        "crop_code": "tomato", "organization_id": "org-1", "farm_id": farm_id,
        "area_ha": 2.0, "planting_date": "2026-09-20",
        "harvest_period": "2026-10-01",
    }
    plan = client.post("/api/v1/plans", headers=_h("farmer-1"), json=plan_input)
    assert plan.status_code == 201, plan.text
    assert plan.json()["farm_id"] == farm_id
    assert S.PLANS[plan.json()["id"]]["farm_id"] == farm_id

    other_owner = client.post("/api/v1/plans", headers=_h("coord-1"), json=plan_input)
    assert other_owner.status_code == 403
    assert other_owner.json()["detail"]["code"] == "permission_denied"

    missing = client.post("/api/v1/plans", headers=_h("farmer-1"),
                          json={**plan_input, "farm_id": "farm-missing"})
    assert missing.status_code == 404


def test_aggregate_keeps_missing_yield_unknown(client):
    created = client.post("/api/v1/plans", headers=_h("farmer-1"), json={
        "crop_code": "ampalaya", "organization_id": "org-1", "area_ha": 2.0,
        "planting_date": "2026-09-20", "harvest_period": "2026-10-01",
    })
    assert created.status_code == 201
    aggregate = client.get("/api/v1/organizations/org-1/aggregates",
                           headers=_h("farmer-1"))
    assert aggregate.status_code == 200
    row = next(item for item in aggregate.json()["rows"]
               if item["crop_code"] == "ampalaya"
               and item["harvest_period"] == "2026-10-01")
    assert row["planned_area_ha"] == 2.0
    assert row["estimated_production_mt"] is None
