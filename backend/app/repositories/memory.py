# ruff: noqa: E701, E702
"""Isolated in-memory repository used only by explicit unit/demo services."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterator

from .base import Page, RepositoryIdentity

@dataclass
class MemoryRepository:
    identity: RepositoryIdentity
    tables: dict[str, dict[str, Any]]
    @contextmanager
    def transaction(self) -> Iterator["MemoryRepository"]:
        snapshot = deepcopy(self.tables)
        try:
            yield self
        except Exception:
            self.tables.clear()
            self.tables.update(snapshot)
            raise
    def page(self, rows: list[dict[str, Any]], *, limit: int = 50, cursor: str | None = None) -> Page:
        limit = max(1, min(int(limit), 200))
        start = 0
        if cursor:
            try:
                start = int(cursor)
            except ValueError:
                start = 0
        selected = rows[start:start + limit]
        return Page(selected, str(start + limit) if start + limit < len(rows) else None, len(rows))
    def get(self, table: str, key: str) -> dict[str, Any] | None:
        row = self.tables.get(table, {}).get(key)
        return deepcopy(row) if row is not None else None
    def put(self, table: str, key: str, value: dict[str, Any]) -> dict[str, Any]:
        self.tables.setdefault(table, {})[key] = deepcopy(value)
        return deepcopy(value)
    def list(self, table: str) -> list[dict[str, Any]]:
        return [deepcopy(row) for row in self.tables.get(table, {}).values()]