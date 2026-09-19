"""Mechanism-level PostgreSQL RLS tests.

Set TANIM_TEST_DATABASE_URL to the deployed non-owner application role and
TANIM_RLS_ADMIN_DATABASE_URL to a setup role in a disposable test database.
For CI, DATABASE_URL may point to a disposable admin connection; the test then
creates and SET ROLEs into a non-privileged application role. Without a
configured database URL the tests skip, so a local SQLite run is never reported
as RLS evidence.  CI should run this module after alembic upgrade head.
"""
from __future__ import annotations

import os
import uuid
from contextlib import contextmanager

import pytest

psycopg = pytest.importorskip("psycopg")

APP_URL = (
    os.environ.get("TANIM_TEST_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
)
ADMIN_URL = (
    os.environ.get("TANIM_RLS_ADMIN_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
)
RLS_APP_ROLE = os.environ.get("TANIM_RLS_APP_ROLE", "tanim_rls_app")
pytestmark = pytest.mark.skipif(
    not APP_URL or not ADMIN_URL,
    reason="set DATABASE_URL or TANIM_TEST_DATABASE_URL",
)


def _driver_url(url: str) -> str:
    """Translate SQLAlchemy URLs from CI to psycopg's libpq format."""
    return url.replace("postgresql+psycopg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )


@contextmanager
def connection(url: str):
    with psycopg.connect(_driver_url(url)) as conn:
        yield conn


def _role_identifier() -> str:
    if not RLS_APP_ROLE.replace("_", "").isalnum():
        raise ValueError("TANIM_RLS_APP_ROLE must be a simple identifier")
    return '"' + RLS_APP_ROLE.replace('"', '""') + '"'


@pytest.fixture(scope="session", autouse=True)
def ensure_non_privileged_app_role():
    # CI supplies only a disposable postgres superuser URL.  Create a separate
    # login role and SET ROLE for mechanism tests so the test proves that the
    # deployed application role has neither superuser nor BYPASSRLS powers.
    if APP_URL != ADMIN_URL:
        yield
        return
    created_role = False
    with connection(ADMIN_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s",
                (RLS_APP_ROLE,),
            )
            if cur.fetchone() is None:
                cur.execute(
                    f"CREATE ROLE {_role_identifier()} LOGIN NOSUPERUSER NOBYPASSRLS"
                )
                created_role = True
            cur.execute(
                f"ALTER ROLE {_role_identifier()} NOSUPERUSER NOBYPASSRLS"
            )
            cur.execute(
                f"GRANT USAGE ON SCHEMA public TO {_role_identifier()}"
            )
            tenant_tables = (
                "organizations", "organization_memberships", "farms",
                "farm_locations", "planting_plans", "planting_plan_revisions",
                "yield_references", "comparison_references", "reference_reviews",
                "price_observations", "climate_context", "weather_observations",
                "suitability_references", "calculation_runs", "consent_records",
                "audit_events",
            )
            for table_name in tenant_tables:
                cur.execute(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "
                    f"{table_name} TO {_role_identifier()}"
                )
            # Global registries are readable by the API adapter, but writes stay
            # outside the application role and therefore cannot bypass review.
            for table_name in (
                "data_sources", "data_source_versions", "crops",
                "crop_aliases", "calculation_policies",
            ):
                cur.execute(
                    f"GRANT SELECT ON TABLE {table_name} TO {_role_identifier()}"
                )
            cur.execute(
                f"GRANT REFERENCES ON TABLE users TO {_role_identifier()}"
            )
            cur.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public "
                f"TO {_role_identifier()}"
            )
        conn.commit()
    yield
    if created_role:
        with connection(ADMIN_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(f"DROP OWNED BY {_role_identifier()}")
                cur.execute(f"DROP ROLE IF EXISTS {_role_identifier()}")
            conn.commit()


@contextmanager
def app_connection():
    with psycopg.connect(_driver_url(APP_URL)) as conn:
        if APP_URL == ADMIN_URL:
            with conn.cursor() as cur:
                cur.execute(f"SET ROLE {_role_identifier()}")
            # Commit the session role before tenant-local transactions; a
            # rollback after an expected RLS error must not restore superuser.
            conn.commit()
        yield conn


@pytest.fixture()
def tenant_fixture():
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    farm_a = uuid.uuid4()
    farm_b = uuid.uuid4()

    with connection(ADMIN_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO organizations (id, name, slug, version) "
                "VALUES (%s, %s, %s, 1), (%s, %s, %s, 1)",
                (org_a, "RLS A", f"rls-a-{org_a}", org_b, "RLS B", f"rls-b-{org_b}"),
            )
            cur.execute(
                """
                INSERT INTO users (id, email, display_name, password_hash)
                VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)
                """,
                (
                    user_a,
                    f"rls-a-{user_a}@example.test",
                    "RLS A",
                    "test",
                    user_b,
                    f"rls-b-{user_b}@example.test",
                    "RLS B",
                    "test",
                ),
            )
            cur.execute(
                """
                INSERT INTO organization_memberships (id, org_id, user_id, role)
                VALUES (%s, %s, %s, 'farmer'), (%s, %s, %s, 'farmer')
                """,
                (uuid.uuid4(), org_a, user_a, uuid.uuid4(), org_b, user_b),
            )
            cur.execute(
                """
                INSERT INTO farms
                    (id, org_id, owner_user_id, name, total_area_ha, municipality)
                VALUES (%s, %s, %s, 'A farm', 1, 'A'), (%s, %s, %s, 'B farm', 1, 'B')
                """,
                (farm_a, org_a, user_a, farm_b, org_b, user_b),
            )
        conn.commit()

    yield {
        "org_a": org_a,
        "org_b": org_b,
        "user_a": user_a,
        "user_b": user_b,
        "farm_a": farm_a,
        "farm_b": farm_b,
    }

    with connection(ADMIN_URL) as conn:
        with conn.cursor() as cur:
            # The audit trigger is intentionally immutable; disable only the
            # user trigger for cleanup in this disposable test fixture.
            cur.execute("ALTER TABLE audit_events DISABLE TRIGGER USER")
            cur.execute(
                "DELETE FROM audit_events WHERE org_id IN (%s, %s)",
                (org_a, org_b),
            )
            cur.execute("ALTER TABLE audit_events ENABLE TRIGGER USER")
            # Remove any additional fixture rows created by a write test before
            # deleting users referenced by farm ownership foreign keys.
            cur.execute(
                "DELETE FROM farms WHERE owner_user_id IN (%s, %s)",
                (user_a, user_b),
            )
            cur.execute(
                "DELETE FROM organization_memberships WHERE org_id IN (%s, %s)",
                (org_a, org_b),
            )
            cur.execute("DELETE FROM users WHERE id IN (%s, %s)", (user_a, user_b))
            cur.execute(
                "DELETE FROM organizations WHERE id IN (%s, %s)",
                (org_a, org_b),
            )
        conn.commit()


def set_tenant(conn, org_id, role="farmer", user_id=""):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_org_id', %s, true), "
            "set_config('app.current_role', %s, true), "
            "set_config('app.current_user_id', %s, true)",
            (str(org_id), role, str(user_id)),
        )


def test_rls_is_enabled_and_application_role_cannot_bypass(tenant_fixture):
    with app_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.relrowsecurity, c.relforcerowsecurity,
                       r.rolsuper, r.rolbypassrls
                FROM pg_class c
                JOIN pg_roles r ON r.rolname = current_user
                WHERE c.oid = 'farms'::regclass
                """
            )
            enabled, forced, superuser, bypass = cur.fetchone()
    assert enabled is True
    assert forced is True
    assert superuser is False
    assert bypass is False


def test_wrong_tenant_reads_return_zero_rows(tenant_fixture):
    with app_connection() as conn:
        set_tenant(conn, tenant_fixture["org_a"], user_id=tenant_fixture["user_a"])
        with conn.cursor() as cur:
            cur.execute("SELECT id, org_id FROM farms ORDER BY id")
            rows_a = cur.fetchall()
        set_tenant(conn, tenant_fixture["org_b"], user_id=tenant_fixture["user_b"])
        with conn.cursor() as cur:
            cur.execute("SELECT id, org_id FROM farms ORDER BY id")
            rows_b = cur.fetchall()
    assert [row[1] for row in rows_a] == [tenant_fixture["org_a"]]
    assert [row[1] for row in rows_b] == [tenant_fixture["org_b"]]


def test_wrong_tenant_writes_are_rejected(tenant_fixture):
    with app_connection() as conn:
        set_tenant(conn, tenant_fixture["org_a"], user_id=tenant_fixture["user_a"])
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO farms
                    (id, org_id, owner_user_id, name, total_area_ha, municipality)
                VALUES (%s, %s, %s, 'allowed', 1, 'A')
                """,
                (uuid.uuid4(), tenant_fixture["org_a"], tenant_fixture["user_a"]),
            )
        conn.commit()
        set_tenant(conn, tenant_fixture["org_a"], user_id=tenant_fixture["user_a"])
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO farms
                        (id, org_id, owner_user_id, name, total_area_ha, municipality)
                    VALUES (%s, %s, %s, 'blocked', 1, 'B')
                    """,
                    (uuid.uuid4(), tenant_fixture["org_b"], tenant_fixture["user_b"]),
                )
        conn.rollback()


def test_global_policy_writes_are_denied_to_application_role(tenant_fixture):
    with app_connection() as conn:
        set_tenant(conn, tenant_fixture["org_a"], user_id=tenant_fixture["user_a"])
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.cursor() as cur:
                cur.execute("UPDATE calculation_policies SET version = version")


def test_platform_role_still_requires_explicit_tenant_context(tenant_fixture):
    with app_connection() as conn:
        set_tenant(conn, tenant_fixture["org_a"], role="platform_admin")
        with conn.cursor() as cur:
            cur.execute("SELECT org_id FROM farms")
            rows = cur.fetchall()
        assert {row[0] for row in rows} == {tenant_fixture["org_a"]}


def test_audit_rows_are_append_only_and_tenant_scoped(tenant_fixture):
    event_id = uuid.uuid4()
    with connection(ADMIN_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_events
                    (id, org_id, actor_user_id, action, target_kind)
                VALUES (%s, %s, %s, 'reference.verified', 'reference')
                """,
                (event_id, tenant_fixture["org_a"], tenant_fixture["user_a"]),
            )
        conn.commit()

    with app_connection() as conn:
        set_tenant(conn, tenant_fixture["org_a"], user_id=tenant_fixture["user_a"])
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM audit_events WHERE id = %s", (event_id,))
            assert cur.fetchone()[0] == event_id
        with pytest.raises(psycopg.Error) as update_error:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE audit_events SET target_kind = 'changed' WHERE id = %s",
                    (event_id,),
                )
        assert update_error.value.sqlstate == "55000"
        # The expected trigger exception aborts the transaction; clear it
        # before changing tenant context and continuing the mechanism check.
        conn.rollback()
        set_tenant(conn, tenant_fixture["org_b"], user_id=tenant_fixture["user_b"])
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM audit_events WHERE id = %s", (event_id,))
            assert cur.fetchone() is None
