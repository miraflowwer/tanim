# ruff: noqa: E701, E702
"""Supabase Auth/JWKS boundary for the database-backed API.

A valid provider token is necessary but not sufficient: the subject must map to
a pre-provisioned durable user and server-resolved memberships. Development
tokens are rejected unconditionally by this module.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlparse
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from .db import session_factory, runtime_mode
from .repositories.postgres import PostgresRepository
from .repositories.base import RepositoryIdentity

_JWKS_CACHE: dict[str, Any] = {"keys": {}, "fetched_at": 0.0, "url": ""}

@dataclass(frozen=True)
class ProductionUser:
    user_id: str
    email: str
    org_roles: dict[str, str] = field(default_factory=dict)
    is_platform: bool = False
    def role_in(self, org_id: str) -> str | None:
        return "platform_admin" if self.is_platform else self.org_roles.get(org_id)

def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})

def _jwt_kwargs() -> dict[str, Any]:
    audience = os.environ.get("SUPABASE_JWT_AUDIENCE") or None
    issuer = os.environ.get("SUPABASE_JWT_ISSUER") or None
    options = {"require": ["exp", "sub"], "verify_aud": bool(audience), "verify_iss": bool(issuer)}
    result: dict[str, Any] = {"options": options}
    if audience: result["audience"] = audience
    if issuer: result["issuer"] = issuer
    return result

def _decode_with_jwks(token: str, jwt: Any) -> dict[str, Any]:
    jwks_url = os.environ.get("SUPABASE_JWKS_URL")
    if not jwks_url:
        raise ValueError("SUPABASE_JWKS_URL is not configured")
    parsed = urlparse(jwks_url)
    loopback = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"} and runtime_mode() == "inmemory"
    if parsed.scheme != "https" and not loopback:
        raise ValueError("SUPABASE_JWKS_URL must use HTTPS")
    now = time.time()
    if now - float(_JWKS_CACHE["fetched_at"]) > 600 or not _JWKS_CACHE["keys"] or _JWKS_CACHE["url"] != jwks_url:
        with urllib.request.urlopen(jwks_url, timeout=10) as response:  # nosec B310
            payload = json.loads(response.read().decode("utf-8"))
        _JWKS_CACHE["keys"] = {item["kid"]: item for item in payload.get("keys", []) if item.get("kid")}
        _JWKS_CACHE["fetched_at"] = now
        _JWKS_CACHE["url"] = jwks_url
    kid = jwt.get_unverified_header(token).get("kid")
    key = _JWKS_CACHE["keys"].get(kid)
    if key is None:
        raise ValueError("unknown key id")
    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
    return jwt.decode(token, public_key, algorithms=["RS256"], **_jwt_kwargs())

def decode_supabase_claims(token: str) -> dict[str, Any]:
    try:
        import jwt
    except ImportError as exc:
        raise _error(503, "auth_backend_missing", "Sign-in verification is temporarily unavailable.") from exc
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret and not os.environ.get("SUPABASE_JWKS_URL"):
        raise _error(503, "auth_not_configured", "Sign-in is not configured for this runtime.")
    try:
        if secret:
            return jwt.decode(token, secret, algorithms=["HS256"], **_jwt_kwargs())
        return _decode_with_jwks(token, jwt)
    except Exception as exc:
        raise _error(401, "unauthorized", "This sign-in is invalid or expired. Please sign in again.") from exc

def _to_user(identity: RepositoryIdentity) -> ProductionUser:
    return ProductionUser(identity.user_id, identity.email, dict(identity.org_roles), identity.is_platform)

async def get_current_user(request: Request) -> ProductionUser:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer ") or len(header) < 12:
        raise _error(401, "unauthorized", "Sign in required.")
    token = header[7:].strip()
    if not token or token.startswith("dev:") or len(token) > 8192:
        raise _error(401, "unauthorized", "This sign-in is invalid or expired. Please sign in again.")
    claims = decode_supabase_claims(token)
    subject = str(claims.get("sub", "")).strip()
    email = str(claims.get("email", "")).strip()
    if not subject:
        raise _error(401, "unauthorized", "This sign-in is invalid or expired. Please sign in again.")
    try:
        session = session_factory()()
        try:
            identity = PostgresRepository.resolve_identity(session, subject, email)
        finally:
            session.close()
    except (SQLAlchemyError, RuntimeError, OSError) as exc:
        raise _error(503, "auth_backend_unavailable", "Sign-in verification is temporarily unavailable.") from exc
    if identity is None:
        raise _error(403, "unknown_user", "This account is not provisioned for TANIM.")
    user = _to_user(identity)
    request.state.user_id = user.user_id
    return user