"""Production boundary, error-envelope, and privacy telemetry checks."""
from __future__ import annotations

import ast
import asyncio
import inspect

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.app import production_api, production_auth
from backend.app.ops import safe_log


def test_production_routes_do_not_import_legacy_store():
    tree = ast.parse(inspect.getsource(production_api))
    imports = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    ]
    assert ".store" not in imports
    assert "backend.app.store" not in imports


def test_production_health_and_openapi_use_durable_contract(monkeypatch):
    monkeypatch.setenv("TANIM_RUNTIME_MODE", "postgres")
    client = TestClient(production_api.app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["runtime_mode"] == "postgres"
    schema = production_api.app.openapi()
    assert "/api/v1/platform/ingestion" in schema["paths"]
    assert "/api/v1/auth/session" in schema["paths"]


def test_production_error_envelope_and_security_headers(monkeypatch):
    monkeypatch.setenv("TANIM_FORCE_HSTS", "true")
    client = TestClient(production_api.app)
    response = client.post("/api/v1/auth/session")
    assert response.status_code == 405
    body = response.json()
    assert body["code"] == "external_auth_only"
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "max-age=31536000" in response.headers["Strict-Transport-Security"]


def test_production_auth_rejects_development_tokens(monkeypatch):
    monkeypatch.setenv("TANIM_RUNTIME_MODE", "postgres")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/me",
            "headers": [(b"authorization", b"Bearer dev:farmer-1:farmer:org-1")],
        }
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(production_auth.get_current_user(request))
    assert error.value.status_code == 401
    assert error.value.detail["code"] == "unauthorized"


def test_safe_logs_redact_secrets_and_coordinates():
    payload = safe_log(
        "test",
        token="bearer-secret",
        password="password-secret",
        coordinates={"latitude": 14.2, "longitude": 121.1},
        body={"token": "nested-secret"},
    )
    assert payload["token"] == "[REDACTED]"
    assert payload["password"] == "[REDACTED]"
    assert payload["coordinates"] == "[REDACTED]"
    assert "body" not in payload