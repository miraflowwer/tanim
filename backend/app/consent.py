"""Tenant scoped consent records.

A consent grant is identified by (user_id, organization_id, consent_type).
Research withdrawal only affects the matching tenant and purpose; operational
consent in another organization remains active.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

CONSENT_TYPES = ("operational", "research")
CONSENTS: list[dict[str, Any]] = []


def reset_consents() -> None:
    CONSENTS.clear()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _validate_scope(user_id: str, org_id: str, consent_type: str) -> None:
    if not user_id or not org_id:
        raise ValueError("user_id and org_id are required")
    if consent_type not in CONSENT_TYPES:
        raise ValueError(f"unknown consent type: {consent_type}")


def grant(
    *,
    user_id: str,
    org_id: str,
    consent_type: str,
    purpose: str,
    policy_version: str,
) -> dict[str, Any]:
    """Grant a consent type, versioned within one tenant."""
    _validate_scope(user_id, org_id, consent_type)
    if not purpose.strip() or not policy_version.strip():
        raise ValueError("purpose and policy_version are required")

    prior = [
        consent
        for consent in CONSENTS
        if consent["user_id"] == user_id
        and consent["org_id"] == org_id
        and consent["consent_type"] == consent_type
        and consent["withdrawn_at"] is None
    ]
    withdrawn_at = _now()
    for consent in prior:
        # A re-grant closes only the active record for this tenant/type.
        consent["withdrawn_at"] = withdrawn_at

    version = (
        max(
            (
                consent["version"]
                for consent in CONSENTS
                if consent["user_id"] == user_id
                and consent["org_id"] == org_id
                and consent["consent_type"] == consent_type
            ),
            default=0,
        )
        + 1
    )
    record = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "org_id": org_id,
        "consent_type": consent_type,
        "purpose": purpose,
        "policy_version": policy_version,
        "version": version,
        "consented_at": _now(),
        "withdrawn_at": None,
    }
    CONSENTS.append(record)
    return dict(record)


def withdraw(*, user_id: str, org_id: str, consent_type: str) -> dict[str, Any] | None:
    """Withdraw active consent in exactly one tenant and type."""
    _validate_scope(user_id, org_id, consent_type)
    active = [
        consent
        for consent in CONSENTS
        if consent["user_id"] == user_id
        and consent["org_id"] == org_id
        and consent["consent_type"] == consent_type
        and consent["withdrawn_at"] is None
    ]
    if not active:
        return None
    timestamp = _now()
    for consent in active:
        consent["withdrawn_at"] = timestamp
    return dict(active[-1])


def active_for(
    user_id: str,
    org_id: str,
    consent_type: str | None = None,
) -> list[dict[str, Any]]:
    """Return active consents for one user in one tenant only."""
    if not user_id or not org_id:
        raise ValueError("user_id and org_id are required")
    if consent_type is not None and consent_type not in CONSENT_TYPES:
        raise ValueError(f"unknown consent type: {consent_type}")
    return [
        dict(consent)
        for consent in CONSENTS
        if consent["user_id"] == user_id
        and consent["org_id"] == org_id
        and consent["withdrawn_at"] is None
        and (consent_type is None or consent["consent_type"] == consent_type)
    ]
