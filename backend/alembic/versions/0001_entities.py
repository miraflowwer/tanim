"""Initial PostgreSQL/PostGIS schema plus tenant isolation controls.

The models describe the domain tables; this migration creates them only after
PostGIS is enabled, then installs mechanism-level RLS and append-only
triggers.  The application database role must not own these tables and must
not have BYPASSRLS or superuser privileges.
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

from app.models import Base

revision = "0001_entities"
down_revision = None
branch_labels = None
depends_on = None

_ORG_TABLES = (
    "organization_memberships",
    "farms",
    "farm_locations",
    "planting_plans",
    "planting_plan_revisions",
    "yield_references",
    "comparison_references",
    "reference_reviews",
    "price_observations",
    "climate_context",
    "weather_observations",
    "suitability_references",
    "calculation_runs",
    "consent_records",
    "audit_events",
)


def upgrade() -> None:
    bind = op.get_bind()
    # PostGIS is required for the nullable exact location column.  Municipality
    # and region fields remain usable when no exact GPS has been consented.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    Base.metadata.create_all(bind=bind)

    op.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION tanim_current_org_id()
            RETURNS uuid
            LANGUAGE sql
            STABLE
            AS $$
              SELECT NULLIF(current_setting('app.current_org_id', true), '')::uuid
            $$;

            CREATE OR REPLACE FUNCTION tanim_reject_immutable_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
              RAISE EXCEPTION 'append-only table: %', TG_TABLE_NAME
                USING ERRCODE = '55000';
            END;
            $$;
            """
        )
    )

    # FORCE means table owners are subject to the policy too.  The deployed
    # API role must still be a separate non-owner role without BYPASSRLS.
    for table_name in _ORG_TABLES:
        policy_name = f"tanim_{table_name}_tenant"
        op.execute(
            text(
                f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY'
            )
        )
        op.execute(
            text(
                f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY'
            )
        )
        op.execute(
            text(
                f'''
                CREATE POLICY "{policy_name}" ON "{table_name}"
                USING (org_id = tanim_current_org_id())
                WITH CHECK (org_id = tanim_current_org_id())
                '''
            )
        )

    op.execute("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organizations FORCE ROW LEVEL SECURITY")
    op.execute(
        text(
            """
            CREATE POLICY tanim_organizations_tenant ON organizations
            USING (id = tanim_current_org_id())
            WITH CHECK (id = tanim_current_org_id())
            """
        )
    )

    for table_name in (
        "audit_events",
        "planting_plan_revisions",
        "reference_reviews",
        "calculation_runs",
    ):
        op.execute(
            text(
                f'''
                CREATE TRIGGER tanim_{table_name}_append_only
                BEFORE UPDATE OR DELETE ON "{table_name}"
                FOR EACH ROW
                EXECUTE FUNCTION tanim_reject_immutable_mutation()
                '''
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    # Drop triggers, policies, functions, and metadata through SQLAlchemy's
    # dependency-aware drop_all.  This is a valid full rollback for a fresh
    # TANIM database; shared PostGIS ownership remains if other schemas use it.
    for table_name in (
        "audit_events",
        "planting_plan_revisions",
        "reference_reviews",
        "calculation_runs",
    ):
        op.execute(
            text(
                f'DROP TRIGGER IF EXISTS tanim_{table_name}_append_only '
                f'ON "{table_name}"'
            )
        )

    for table_name in (*_ORG_TABLES, "organizations"):
        op.execute(
            text(
                f'DROP POLICY IF EXISTS tanim_{table_name}_tenant '
                f'ON "{table_name}"'
            )
        )
        op.execute(
            text(
                f'ALTER TABLE IF EXISTS "{table_name}" '
                "DISABLE ROW LEVEL SECURITY"
            )
        )

    Base.metadata.drop_all(bind=bind)
    op.execute("DROP FUNCTION IF EXISTS tanim_current_org_id()")
    op.execute("DROP FUNCTION IF EXISTS tanim_reject_immutable_mutation()")
