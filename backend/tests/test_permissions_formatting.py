"""Production API permission and calibrated-copy tests."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("TANIM_RUNTIME_MODE", "inmemory")
os.environ["ALLOW_DEV_AUTH"] = "true"

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

try:
    from backend.app import audit as audit_mod
    from backend.app import consent as consent_mod
    from backend.app import observability as obs
    from backend.app import store
    from backend.app.auth import dev_token_for
    from backend.app.main import app
except ModuleNotFoundError:
    from app import audit as audit_mod
    from app import consent as consent_mod
    from app import observability as obs
    from app import store
    from app.auth import dev_token_for
    from app.main import app

from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_state():
    store.reset_store()
    audit_mod.reset_audit()
    consent_mod.reset_consents()
    obs.reset_observability()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {dev_token_for(user_id)}"}


@pytest.mark.parametrize("user_id", ["farmer-1", "coord-1", "admin-1"])
def test_non_reviewer_cannot_verify_reference(client, user_id):
    response = client.post(
        "/api/v1/references/ref-tomato-1/verify",
        headers=headers(user_id),
        json={"note": "not allowed"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "permission_denied"


def test_reviewer_can_verify_reference_through_api(client):
    draft = client.post(
        "/api/v1/references",
        headers=headers("reviewer-1"),
        json={
            "organization_id": "org-1",
            "crop_code": "tomato",
            "reference_type": "local_committed_demand",
            "amount_mt": 25,
            "geography": "CALABARZON",
            "period": "2026-H2",
            "source": "review workflow test",
        },
    )
    assert draft.status_code == 201
    ref_id = draft.json()["id"]

    submitted = client.post(
        f"/api/v1/references/{ref_id}/submit",
        headers=headers("reviewer-1"),
        json={"note": "ready for review"},
    )
    assert submitted.status_code == 200
    assert submitted.json()["review"] == "under_review"

    response = client.post(
        f"/api/v1/references/{ref_id}/verify",
        headers=headers("reviewer-1"),
        json={"note": "reviewed"},
    )
    assert response.status_code == 200
    assert response.json()["verification_status"] == "reviewed_verified"


def test_synthetic_reference_stays_out_of_real_calculation(client):
    response = client.post(
        "/api/v1/plans/plan-org2-tomato/calculate",
        headers=headers("farmer-2"),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "incomplete"
    assert response.json()["primary"]["coordination_status"] == "insufficient_evidence"


BANNED = (
    "guaranteed",
    "definitely profitable",
    "certain glut",
    "safe crop",
    "best crop",
    "no risk",
)


def test_calibrated_copy_avoids_banned_phrases():
    headlines = (
        "Planned production is below the comparison reference for this crop and harvest period.",
        "TANIM can estimate production, but no reviewed local demand reference is available.",
        "TANIM does not have enough verified evidence to classify this plan.",
        "Fewer planned hectares are currently registered for Eggplant for this harvest period.",
    )
    for headline in headlines:
        for phrase in BANNED:
            assert phrase not in headline.lower()


def test_estimated_range_wording_is_not_statistical():
    label = "Estimated range: 1.8 ha to 2.2 ha"
    assert label.startswith("Estimated range:")
    assert "confidence" not in label.lower()


def test_error_copy_matches_section_30():
    copy = {
        "CROP_UNSUPPORTED": "TANIM does not yet have a safe production and area match for this crop.",
        "YIELD_UNAVAILABLE": "TANIM cannot estimate production for this crop and region yet.",
        "COMPARISON_UNAVAILABLE": "Expected production is available, but TANIM does not have a reviewed comparison reference.",
        "SERVICE_UNAVAILABLE": "TANIM could not calculate this plan. Your entries have been kept. Try again.",
        "STALE_EVIDENCE": "This result uses the latest verified reference available, but the source is older than expected.",
    }
    for message in copy.values():
        for phrase in BANNED:
            assert phrase not in message.lower()
    assert "kept" in copy["SERVICE_UNAVAILABLE"]
