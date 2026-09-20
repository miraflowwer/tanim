"""SQLAlchemy engine/session helpers for explicit development and production modes.

The in-memory API adapter requires TANIM_RUNTIME_MODE=inmemory.
An unspecified mode fails closed as PostgreSQL, including when DATABASE_URL
is accidentally missing. Production deployments must configure DATABASE_URL.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "")
VALID_MODES = frozenset({"postgres", "production", "prod", "inmemory", "development", "dev", "test"})
PRODUCTION_MODES = frozenset({"postgres", "production", "prod"})
INMEMORY_MODES = frozenset({"inmemory", "development", "dev", "test"})


def runtime_mode() -> str:
    """Resolve and validate the runtime mode.

    With no explicit mode, fail closed as PostgreSQL. Development must opt in
    to the in-memory adapter explicitly.
    """
    configured = (
        os.environ.get("TANIM_RUNTIME_MODE")
        or os.environ.get("RUNTIME_MODE")
        or ""
    ).strip().lower()
    if not configured:
        return "postgres"
    if configured not in VALID_MODES:
        raise RuntimeError(
            f"unknown TANIM runtime mode {configured!r}; "
            "choose postgres or inmemory"
        )
    if configured in {"production", "prod"}:
        return "postgres"
    if configured in {"development", "dev", "test"}:
        return "inmemory"
    return configured


def is_production_mode() -> bool:
    return runtime_mode() in PRODUCTION_MODES


def is_inmemory_mode() -> bool:
    return runtime_mode() in INMEMORY_MODES


def configured_database_url() -> str:
    return os.environ.get("DATABASE_URL", "").strip()


def get_engine(url: str | None = None) -> Engine:
    """Build a pre-ping engine; production requires a PostgreSQL URL."""
    resolved = (url or configured_database_url()).strip()
    if not resolved:
        raise RuntimeError("DATABASE_URL is required for database-backed runtime")
    if is_production_mode() and not resolved.startswith(
        ("postgresql://", "postgresql+", "postgres://")
    ):
        raise RuntimeError(
            "database-backed production runtime requires PostgreSQL/PostGIS"
        )
    return create_engine(resolved, pool_pre_ping=True)


def session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine or get_engine(),
        class_=Session,
        expire_on_commit=False,
    )


SessionLocal = sessionmaker(class_=Session, expire_on_commit=False)


def check_readiness() -> tuple[bool, dict[str, Any]]:
    """Check dependencies required by the configured runtime mode."""
    if is_inmemory_mode():
        return True, {"mode": "inmemory", "database": "not_required"}

    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            postgis_version = connection.execute(
                text("SELECT PostGIS_Version()")
            ).scalar_one()
            migration = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
            expected = "0002_platform_durability"
            if migration != expected:
                return False, {
                    "mode": "postgres",
                    "database": "not_ready",
                    "postgis": str(postgis_version),
                    "migration": str(migration or "missing"),
                    "expected_migration": expected,
                }
        return True, {
            "mode": "postgres",
            "database": "ok",
            "postgis": str(postgis_version),
            "migration": "0002_platform_durability",
            "repository": "postgresql",
        }
    except (SQLAlchemyError, RuntimeError, OSError) as exc:
        return False, {
            "mode": "postgres",
            "database": "unavailable",
            "error": type(exc).__name__,
        }


@contextmanager
def tenant_session(
    org_id: str,
    role: str = "farmer",
    user_id: str = "",
    *,
    engine: Engine | None = None,
) -> Iterator[Session]:
    """Open a transaction with tenant context for PostgreSQL RLS policies."""
    if not is_production_mode():
        raise RuntimeError("tenant_session requires the PostgreSQL runtime")
    if not org_id:
        raise ValueError("org_id is required for tenant_session")

    session = session_factory(engine)()
    try:
        session.execute(
            text(
                "SELECT set_config('app.current_org_id', :org_id, true), "
                "set_config('app.current_role', :role, true), "
                "set_config('app.current_user_id', :user_id, true)"
            ),
            {"org_id": org_id, "role": role, "user_id": user_id},
        )
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = [
    "DATABASE_URL",
    "Base",
    "SessionLocal",
    "VALID_MODES",
    "PRODUCTION_MODES",
    "INMEMORY_MODES",
    "runtime_mode",
    "is_production_mode",
    "is_inmemory_mode",
    "configured_database_url",
    "get_engine",
    "session_factory",
    "check_readiness",
    "tenant_session",
]
