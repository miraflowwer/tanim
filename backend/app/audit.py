"""Append-only audit event helpers.

Tenant events carry their organization id.  Platform/global events explicitly
use org_id=None and are never silently assigned to an arbitrary organization.
The production database migration enforces append-only behavior with a trigger;
the in-memory list is a deterministic development adapter.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

AUDIT_ACTIONS = frozenset(
    {
        "reference.created",
        "reference.submitted",
        "reference.verified",
        "reference.rejected",
        "reference.corrected",
        "reference.reopened",
        "reference.expired",
        "reference.superseded",
        "source.promoted",
        "policy.changed",
        "role.changed",
        "member.removed",
        "export.created",
    }
)
GLOBAL_ACTIONS = frozenset({"source.promoted", "policy.changed"})
AUDIT_LOG: list[dict[str, Any]] = []


def reset_audit() -> None:
    """Reset the development adapter between isolated tests."""
    AUDIT_LOG.clear()


def emit(
    action: str,
    *,
    org_id: str | None,
    actor_user_id: str | None,
    target_kind: str,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one event, rejecting unknown or incorrectly scoped actions."""
    if action not in AUDIT_ACTIONS:
        raise ValueError(f"unknown audit action: {action}")
    if org_id is None and action not in GLOBAL_ACTIONS:
        raise ValueError(f"{action} must be scoped to an organization")
    event = {
        "id": str(uuid.uuid4()),
        "org_id": org_id,
        "actor_user_id": actor_user_id,
        "action": action,
        "target_kind": target_kind,
        "target_id": target_id,
        "metadata": dict(metadata or {}),
        "created_at": datetime.now(UTC).isoformat(),
    }
    AUDIT_LOG.append(event)
    return dict(event)


def events_for(
    org_id: str,
    *,
    action: str | None = None,
    include_global: bool = False,
) -> list[dict[str, Any]]:
    """Return copies scoped to one organization."""
    rows = [
        event
        for event in AUDIT_LOG
        if event["org_id"] == org_id
        or (include_global and event["org_id"] is None)
    ]
    if action:
        rows = [event for event in rows if event["action"] == action]
    return [dict(event, metadata=dict(event.get("metadata") or {})) for event in rows]
