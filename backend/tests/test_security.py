"""Production API authorization tests.

These tests call FastAPI routes and the real authentication/RBAC/consent/audit
helpers.  They deliberately do not model RLS with SQLite; PostgreSQL
mechanism tests live in test_postgres_rls.py and skip unless a test database is
configured.
"""
from __future__ import annotations

import asyncio
import os
import time

import pytest

os.environ.setdefault("TANIM_RUNTIME_MODE", "inmemory")
os.environ["ALLOW_DEV_AUTH"] = "true"

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

try:
    from backend.app import audit as audit_mod
    from backend.app import consent as consent_mod
    from backend.app import db as db_mod
    from backend.app import observability as obs
    from backend.app import store as store
    from backend.app import auth as auth_mod
    from backend.app.auth import dev_token_for
    from backend.app.main import app
except ModuleNotFoundError:
    from app import audit as audit_mod
    from app import consent as consent_mod
    from app import db as db_mod
    from app import observability as obs
    from app import store
    from app import auth as auth_mod
    from app.auth import dev_token_for
    from app.main import app

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

jwt = pytest.importorskip("jwt")


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


def test_farmer_cannot_read_another_organization_plan(client):
    response = client.get("/api/v1/plans/plan-org2-tomato", headers=headers("farmer-1"))
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "permission_denied"


def test_farmer_cannot_verify_reference_through_api(client):
    response = client.post(
        "/api/v1/references/ref-tomato-1/verify",
        headers=headers("farmer-1"),
        json={"note": "attempted"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "permission_denied"


def test_farmer_is_owner_scoped_for_private_resources(client):
    # A second farmer in the same organization must not inherit access to
    # another farmer's individual records through shared membership.
    from datetime import date

    store.USERS["farmer-1b"] = {
        "id": "farmer-1b",
        "email": "farmer1b@example.ph",
        "org_roles": {"org-1": "farmer"},
    }
    store.FARMS["farm-private-2"] = {
        "id": "farm-private-2",
        "org_id": "org-1",
        "owner_user_id": "farmer-1b",
        "name": "Private farm",
        "total_area_ha": 1.0,
        "municipality": "Calamba",
        "region": "CALABARZON",
    }
    store.PLANS["plan-private-2"] = {
        "id": "plan-private-2",
        "org_id": "org-1",
        "farm_id": "farm-private-2",
        "crop_code": "tomato",
        "owner_user_id": "farmer-1b",
        "status": "planned",
        "revisions": [{
            "revision_number": 1,
            "area_ha": 1.0,
            "area_margin_ha": 0.0,
            "planting_date": date(2026, 9, 1),
            "harvest_period": date(2026, 12, 1),
            "created_by": "farmer-1b",
            "created_at": "2026-09-19T00:00:00+00:00",
        }],
        "current_revision": 1,
        "created_at": "2026-09-19T00:00:00+00:00",
    }
    store.CALCULATIONS["calc-private-2"] = {
        "calculation_id": "calc-private-2",
        "org_id": "org-1",
        "plan_id": "plan-private-2",
        "result": {"calculation_id": "calc-private-2"},
    }

    for url in (
        "/api/v1/farms/farm-private-2",
        "/api/v1/plans/plan-private-2",
        "/api/v1/plans/plan-private-2/revisions",
        "/api/v1/calculations/calc-private-2",
    ):
        response = client.get(url, headers=headers("farmer-1"))
        assert response.status_code == 403, url
        assert response.json()["detail"]["code"] == "permission_denied"

    created = client.post(
        "/api/v1/exports",
        headers=headers("admin-1"),
        json={
            "organization_id": "org-1",
            "purpose": "individual review",
            "include_individuals": True,
        },
    )
    assert created.status_code == 201
    exported = client.get(
        f"/api/v1/exports/{created.json()['id']}",
        headers=headers("farmer-1"),
    )
    assert exported.status_code == 403
    assert exported.json()["detail"]["code"] == "permission_denied"


def test_forged_development_role_is_rejected(client):
    response = client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer dev:farmer-1:org_admin:org-1"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "permission_denied"


def test_platform_authority_is_server_side(client):
    response = client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer dev:admin-1:platform_admin:org-1"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "permission_denied"


def test_consent_withdrawal_is_scoped_to_one_organization(client):
    # The same user can have independent records in two organizations in this
    # adapter; withdrawing research consent in org-1 cannot affect org-2.
    store.USERS["farmer-1"]["org_roles"]["org-2"] = "farmer"
    assert client.post(
        "/api/v1/consents?org_id=org-1",
        headers=headers("farmer-1"),
        json={
            "consent_type": "operational",
            "purpose": "coordination",
            "policy_version": "v1",
        },
    ).status_code == 201
    assert client.post(
        "/api/v1/consents?org_id=org-2",
        headers=headers("farmer-1"),
        json={
            "consent_type": "research",
            "purpose": "research",
            "policy_version": "v1",
        },
    ).status_code == 201

    withdrawn = client.post(
        "/api/v1/consents/withdraw?org_id=org-1",
        headers=headers("farmer-1"),
        json={"consent_type": "operational"},
    )
    assert withdrawn.status_code == 200
    assert client.get(
        "/api/v1/consents/me?org_id=org-2",
        headers=headers("farmer-1"),
    ).json()["consents"][0]["consent_type"] == "research"


def test_audit_rejects_unknown_and_unscoped_tenant_events():
    with pytest.raises(ValueError):
        audit_mod.emit(
            "not-a-real-action",
            org_id="org-1",
            actor_user_id="admin-1",
            target_kind="test",
        )
    with pytest.raises(ValueError):
        audit_mod.emit(
            "reference.verified",
            org_id=None,
            actor_user_id="admin-1",
            target_kind="reference",
        )

    event = audit_mod.emit(
        "policy.changed",
        org_id=None,
        actor_user_id="platform-1",
        target_kind="policy",
    )
    assert event["org_id"] is None


def _jwt_token(secret: str = "test-secret", **overrides) -> str:
    now = int(time.time())
    claims = {
        "sub": "farmer-1",
        "iat": now,
        "exp": now + 60,
        "iss": "https://issuer.example",
        "aud": "tanim-api",
    }
    claims.update(overrides)
    return jwt.encode(claims, secret, algorithm="HS256")


@pytest.mark.parametrize(
    ("name", "secret", "claims"),
    [
        ("invalid signature", "wrong-secret", {}),
        ("expired token", "test-secret", {"exp": int(time.time()) - 1}),
        ("wrong issuer", "test-secret", {"iss": "https://other.example"}),
        ("wrong audience", "test-secret", {"aud": "other-api"}),
    ],
)
def test_supabase_jwt_rejects_invalid_signature_or_claims(
    client, monkeypatch, name, secret, claims
):
    monkeypatch.setenv("TANIM_RUNTIME_MODE", "inmemory")
    monkeypatch.setenv("ALLOW_DEV_AUTH", "false")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", "https://issuer.example")
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", "tanim-api")

    response = client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {_jwt_token(secret, **claims)}"},
    )
    assert response.status_code == 401, name
    assert response.json()["detail"]["code"] == "unauthorized"


def test_dev_token_is_rejected_when_postgres_mode_is_selected(monkeypatch):
    monkeypatch.setenv("TANIM_RUNTIME_MODE", "postgres")
    monkeypatch.setenv("ALLOW_DEV_AUTH", "true")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/me",
            "headers": [
                (b"authorization", b"Bearer dev:farmer-1:farmer:org-1"),
            ],
        }
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(auth_mod.get_current_user(request))
    assert error.value.status_code == 401
    assert error.value.detail["code"] == "unauthorized"


def test_postgres_readiness_is_503_when_database_is_unavailable(
    client, monkeypatch
):
    monkeypatch.setenv("TANIM_RUNTIME_MODE", "postgres")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:1/tanim"
    )

    def unavailable_engine():
        raise OSError("database unavailable")

    monkeypatch.setattr(db_mod, "get_engine", unavailable_engine)
    response = client.get("/api/v1/readiness")
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "dependency_unavailable"
    assert body["database"] == "unavailable"


def test_production_jwks_requires_https(monkeypatch):
    monkeypatch.setenv("TANIM_RUNTIME_MODE", "postgres")
    monkeypatch.setenv("SUPABASE_JWKS_URL", "http://keys.example.test/jwks.json")
    with pytest.raises(ValueError, match="HTTPS"):
        auth_mod._decode_with_jwks("not-a-token", jwt)


def test_missing_runtime_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("TANIM_RUNTIME_MODE", raising=False)
    monkeypatch.delenv("RUNTIME_MODE", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("ALLOW_DEV_AUTH", "true")
    assert db_mod.runtime_mode() == "postgres"
    request = Request({
        "type": "http", "method": "GET", "path": "/api/v1/me",
        "headers": [(b"authorization", b"Bearer dev:farmer-1:farmer:org-1")],
    })
    with pytest.raises(HTTPException) as error:
        asyncio.run(auth_mod.get_current_user(request))
    assert error.value.status_code == 401
