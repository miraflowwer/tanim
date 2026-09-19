"""Authentication helpers for the production API and explicit development auth.

Production requests must carry a signed JWT.  The development token format is
available only in an explicitly selected development/in-memory runtime with
ALLOW_DEV_AUTH=true; it is never a fallback when production JWT settings are
missing or invalid.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, Request

from . import store as S

ROLES = ("farmer", "coordinator", "reviewer", "org_admin", "platform_admin")
_DEV_MODES = frozenset({"development", "dev", "inmemory", "test"})
_JWKS_CACHE: dict[str, Any] = {"keys": {}, "fetched_at": 0.0, "url": ""}


@dataclass(frozen=True)
class UserContext:
    """Authenticated identity plus server-resolved organization memberships."""

    user_id: str
    email: str = ""
    org_roles: dict[str, str] = field(default_factory=dict)
    is_platform: bool = False

    def role_in(self, org_id: str) -> str | None:
        if self.is_platform:
            return "platform_admin"
        return self.org_roles.get(org_id)


def _unauthorized(msg: str = "Sign in required.") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"code": "unauthorized", "message": msg},
        headers={"WWW-Authenticate": "Bearer"},
    )


VALID_MODES = frozenset(
    {"postgres", "production", "prod", "inmemory", "development", "dev", "test"}
)


def runtime_mode() -> str:
    """Resolve and validate the runtime mode using the database signal."""
    configured = (
        os.environ.get("TANIM_RUNTIME_MODE")
        or os.environ.get("RUNTIME_MODE")
        or ""
    ).strip().lower()
    if not configured:
        return "postgres"  # fail closed unless development mode is explicit
    if configured not in VALID_MODES:
        raise RuntimeError(
            f"unknown TANIM runtime mode {configured!r}; choose postgres or inmemory"
        )
    if configured in {"production", "prod"}:
        return "postgres"
    if configured in {"development", "dev", "test"}:
        return "inmemory"
    return configured


def dev_auth_enabled() -> bool:
    """Development auth requires both an explicit mode and an explicit opt-in."""
    return (
        runtime_mode() in _DEV_MODES
        and os.environ.get("ALLOW_DEV_AUTH", "").strip().lower() == "true"
    )


def _supabase_configured() -> bool:
    return bool(
        os.environ.get("SUPABASE_JWT_SECRET")
        or os.environ.get("SUPABASE_JWKS_URL")
    )


def _jwt_kwargs(*, audience: str | None, issuer: str | None) -> dict[str, Any]:
    """Build strict PyJWT options while allowing issuer/audience to be optional."""
    options: dict[str, Any] = {
        "require": ["exp", "sub"],
        "verify_aud": bool(audience),
        "verify_iss": bool(issuer),
    }
    kwargs: dict[str, Any] = {"options": options}
    if audience:
        kwargs["audience"] = audience
    if issuer:
        kwargs["issuer"] = issuer
    return kwargs


def _supabase_user(token: str) -> UserContext:
    """Validate a signed Supabase JWT and map sub to seeded memberships.

    Memberships are resolved server-side.  A valid signature never creates a
    user or grants organization access on its own.
    """
    try:
        import jwt
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail={
                "code": "auth_backend_missing",
                "message": "TANIM could not verify this sign-in. Your entries have been kept. Try again.",
            },
        ) from exc

    secret = os.environ.get("SUPABASE_JWT_SECRET")
    try:
        if secret:
            claims = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                **_jwt_kwargs(
                    audience=os.environ.get("SUPABASE_JWT_AUDIENCE") or None,
                    issuer=os.environ.get("SUPABASE_JWT_ISSUER") or None,
                ),
            )
        else:
            claims = _decode_with_jwks(token, jwt)
    except Exception as exc:  # noqa: BLE001 - decode failures are intentionally uniform
        raise _unauthorized(
            "This sign-in is invalid or expired. Please sign in again."
        ) from exc

    sub = str(claims.get("sub", ""))
    email = str(claims.get("email", ""))
    user = S.USERS.get(sub)
    if user is None:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "unknown_user",
                "message": "This account is not a member of any TANIM organization yet.",
            },
        )
    return UserContext(
        user_id=sub,
        email=email or user.get("email", ""),
        org_roles=dict(user.get("org_roles", {})),
        is_platform=bool(user.get("is_platform", False)),
    )


def _decode_with_jwks(token: str, jwt: Any) -> dict[str, Any]:
    jwks_url = os.environ.get("SUPABASE_JWKS_URL")
    if not jwks_url:
        raise ValueError("SUPABASE_JWKS_URL is not configured")
    parsed_url = urlparse(jwks_url)
    loopback_http = (
        parsed_url.scheme == "http"
        and parsed_url.hostname in {"127.0.0.1", "localhost", "::1"}
        and runtime_mode() in _DEV_MODES
    )
    if parsed_url.scheme != "https" and not loopback_http:
        raise ValueError(
            "SUPABASE_JWKS_URL must use HTTPS outside development loopback"
        )

    now = time.time()
    if (
        now - float(_JWKS_CACHE["fetched_at"]) > 600
        or not _JWKS_CACHE["keys"]
        or _JWKS_CACHE["url"] != jwks_url
    ):
        # The URL is operator-configured and restricted to HTTP(S) above.
        with urllib.request.urlopen(jwks_url, timeout=10) as response:  # nosec B310
            jwks = json.loads(response.read().decode("utf-8"))
        _JWKS_CACHE["keys"] = {
            key["kid"]: key for key in jwks.get("keys", []) if key.get("kid")
        }
        _JWKS_CACHE["fetched_at"] = now
        _JWKS_CACHE["url"] = jwks_url

    kid = jwt.get_unverified_header(token).get("kid")
    key = _JWKS_CACHE["keys"].get(kid)
    if key is None:
        raise ValueError("unknown key id")
    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
    return jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        **_jwt_kwargs(
            audience=os.environ.get("SUPABASE_JWT_AUDIENCE") or None,
            issuer=os.environ.get("SUPABASE_JWT_ISSUER") or None,
        ),
    )


def _dev_user(token: str) -> UserContext:
    """Resolve a development token against exact server-side memberships.

    Token syntax is dev:<user_id>:<role>:<org_id>[,<org_id>...].  The role and
    every claimed organization must already match the seeded membership.  A
    platform role is only valid for a server-marked platform user.
    """
    if not dev_auth_enabled():
        raise _unauthorized("Development sign-in is disabled.")

    try:
        scheme, user_id, role, orgs = token.split(":", 3)
    except ValueError as exc:
        raise _unauthorized(
            "This sign-in is invalid or expired. Please sign in again."
        ) from exc

    claimed_orgs = {org.strip() for org in orgs.split(",") if org.strip()}
    if (
        scheme != "dev"
        or role not in ROLES
        or not user_id
        or not claimed_orgs
    ):
        raise _unauthorized("This sign-in is invalid or expired. Please sign in again.")

    user = S.USERS.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "unknown_user",
                "message": "This account is not a member of any TANIM organization yet.",
            },
        )

    is_platform = bool(user.get("is_platform", False))
    if role == "platform_admin":
        if not is_platform:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "permission_denied",
                    "message": "You do not have access to this.",
                },
            )
        # Platform authority is a server-side identity property, never an org role.
        return UserContext(
            user_id=user_id,
            email=user.get("email", ""),
            org_roles={org: "platform_admin" for org in claimed_orgs},
            is_platform=True,
        )

    memberships = dict(user.get("org_roles", {}))
    if any(memberships.get(org) != role for org in claimed_orgs):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "permission_denied",
                "message": "You do not have access to this organization.",
            },
        )
    return UserContext(
        user_id=user_id,
        email=user.get("email", ""),
        org_roles={org: memberships[org] for org in claimed_orgs},
        is_platform=False,
    )


def dev_token_for(user_id: str) -> str:
    """Mint a development bearer token for a seeded user.

    This helper is intentionally unavailable in production mode so a route
    cannot accidentally expose a production token minting path.
    """
    if not dev_auth_enabled():
        raise RuntimeError("Development auth is disabled")
    user = S.USERS.get(user_id)
    if user is None:
        raise KeyError(user_id)
    if user.get("is_platform"):
        return f"dev:{user_id}:platform_admin:org-1,org-2"
    org_roles = dict(user.get("org_roles", {}))
    if not org_roles:
        raise ValueError("user has no organization membership")
    role = next(iter(org_roles.values()))
    same_role_orgs = [org for org, member_role in org_roles.items() if member_role == role]
    return f"dev:{user_id}:{role}:{','.join(same_role_orgs)}"


async def get_current_user(request: Request) -> UserContext:
    """FastAPI dependency: strict bearer validation -> UserContext."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer ") or len(auth) < 12:
        from . import observability as obs

        obs.bump("auth_failures")
        raise _unauthorized("Sign in required.")

    token = auth[7:].strip()
    if token.startswith("dev:"):
        return _dev_user(token)
    if not _supabase_configured():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "auth_not_configured",
                "message": "Sign-in is not configured for this runtime.",
            },
        )
    return _supabase_user(token)
