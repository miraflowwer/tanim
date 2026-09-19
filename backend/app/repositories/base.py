# ruff: noqa: E701, E702`n"""Repository contracts shared by memory and PostgreSQL adapters."""
from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any, Protocol

@dataclass(frozen=True)
class Page:
    items: list[dict[str, Any]]
    next_cursor: str | None = None
    total: int | None = None
    def as_dict(self) -> dict[str, Any]:
        return {"items": self.items, "next_cursor": self.next_cursor, "total": self.total}

@dataclass(frozen=True)
class RepositoryIdentity:
    user_id: str
    email: str
    org_roles: dict[str, str] = field(default_factory=dict)
    is_platform: bool = False
    def role_in(self, org_id: str) -> str | None:
        return "platform_admin" if self.is_platform else self.org_roles.get(org_id)

class Repository(Protocol):
    identity: RepositoryIdentity
    def transaction(self) -> AbstractContextManager[Any]: ...
    def page(self, rows: list[dict[str, Any]], *, limit: int, cursor: str | None = None) -> Page: ...