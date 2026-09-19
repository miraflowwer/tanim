"""Server-side authorization helpers.

Every protected route must authorize the resource organization first.  A
farmer's organization membership does not grant access to another farmer's
individual resource; owner checks are explicit and use the resource owner id.
"""
from __future__ import annotations

from fastapi import HTTPException

from . import observability as obs
from .auth import UserContext

ROLES = ("farmer", "coordinator", "reviewer", "org_admin", "platform_admin")
REVIEW_ROLES = ("reviewer", "platform_admin")
AUDIT_ROLES = ("reviewer", "org_admin", "platform_admin")
OWNER_BYPASS_ROLES = ("coordinator", "reviewer", "org_admin", "platform_admin")


def _denied(
    msg: str = "You do not have access to this. Contact your organization admin.",
) -> HTTPException:
    obs.bump("permission_denied")
    return HTTPException(
        status_code=403,
        detail={"code": "permission_denied", "message": msg},
    )


def authorize(user: UserContext, org_id: str, *allowed: str) -> str:
    """Return the server-resolved role in org_id or raise a structured 403."""
    if not org_id:
        raise _denied("Organization scope is required.")
    role = user.role_in(org_id)
    if role is None:
        raise _denied("You do not have access to this organization.")
    if allowed and role not in allowed:
        raise _denied()
    return role


def require_owner_or_role(
    user: UserContext,
    org_id: str,
    owner_user_id: str,
    *allowed_roles: str,
) -> str:
    """Authorize an individual resource for its owner or explicit role."""
    role = authorize(user, org_id)
    if user.user_id == owner_user_id:
        return role
    if role in (allowed_roles or OWNER_BYPASS_ROLES):
        return role
    raise _denied("You do not have access to this individual record.")


def check_query_org(resource_org: str, query_org: str | None) -> None:
    """Reject cross-organization query tampering."""
    if query_org is not None and query_org != resource_org:
        raise _denied("Organization scope mismatch.")


def require_target_org(user: UserContext, target_org: str, supplied_org: str | None) -> str:
    """Authorize a target organization and reject mismatched query scope."""
    check_query_org(target_org, supplied_org)
    return authorize(user, target_org)
