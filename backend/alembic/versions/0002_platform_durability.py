"""Durable platform tables, provider identity, ingestion metadata, and RLS."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app import platform_models

revision = "0002_platform_durability"
down_revision = "0001_entities"
branch_labels = None
depends_on = None
_ORG_TABLES = ("organization_settings", "invitations", "notifications", "exports")

def _policy(table: str, name: str, using: str, check: str | None = None) -> None:
    op.execute(text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    suffix = f" WITH CHECK ({check})" if check else ""
    op.execute(text(f'CREATE POLICY "{name}" ON "{table}" USING ({using}){suffix}'))

def upgrade() -> None:
    op.add_column("users", sa.Column("provider_subject", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_users_provider_subject", "users", ["provider_subject"])
    op.add_column("users", sa.Column("is_platform", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=True)
    op.add_column("organizations", sa.Column("default_geography", sa.Text(), nullable=True))
    op.add_column("calculation_runs", sa.Column("result_json", JSONB(), nullable=True))
    op.add_column("data_source_versions", sa.Column("period_start", sa.Date(), nullable=True))
    op.add_column("data_source_versions", sa.Column("period_end", sa.Date(), nullable=True))
    op.add_column("data_source_versions", sa.Column("row_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("data_source_versions", sa.Column("validation_status", sa.Text(), server_default="pending", nullable=False))
    op.add_column("data_source_versions", sa.Column("validation_errors", JSONB(), nullable=True))
    op.add_column("data_source_versions", sa.Column("normalization_version", sa.Text(), nullable=True))
    op.add_column("data_source_versions", sa.Column("staged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("data_source_versions", sa.Column("promoted_by", UUID(as_uuid=True), nullable=True))
    op.add_column("data_source_versions", sa.Column("is_current", sa.Boolean(), server_default=sa.false(), nullable=False))
    platform_models.Base.metadata.create_all(bind=op.get_bind())
    op.execute(text("""
        CREATE OR REPLACE FUNCTION tanim_current_user_id()
        RETURNS uuid LANGUAGE sql STABLE AS $$
          SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid
        $$;
        CREATE TABLE IF NOT EXISTS rate_limit_buckets (
            bucket_key text PRIMARY KEY,
            window_start timestamptz NOT NULL,
            hit_count integer NOT NULL DEFAULT 0
        )
    """))
    op.execute(text('DROP POLICY IF EXISTS "tanim_organization_memberships_tenant" ON organization_memberships'))
    _policy("organization_memberships", "tanim_organization_memberships_tenant", "org_id = tanim_current_org_id() OR user_id = tanim_current_user_id()", "org_id = tanim_current_org_id()")
    _policy("user_sessions", "tanim_user_sessions_user", "user_id = tanim_current_user_id()", "user_id = tanim_current_user_id()")
    for table in _ORG_TABLES:
        _policy(table, f"tanim_{table}_tenant", "org_id = tanim_current_org_id()", "org_id = tanim_current_org_id()")
    _policy("ingestion_runs", "tanim_ingestion_platform_or_tenant", "org_id = tanim_current_org_id() OR current_setting('app.current_role', true) = 'platform_admin'", "org_id = tanim_current_org_id() OR current_setting('app.current_role', true) = 'platform_admin'")
    op.execute(text("ALTER TABLE data_source_versions ADD CONSTRAINT fk_data_source_versions_promoted_by FOREIGN KEY (promoted_by) REFERENCES users(id)"))
    op.execute(text("ALTER TABLE ingestion_runs ADD CONSTRAINT fk_ingestion_runs_requested_by FOREIGN KEY (requested_by) REFERENCES users(id)"))
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", "action IN ('reference.created','reference.submitted','reference.verified','reference.rejected','reference.superseded','source.promoted','policy.changed','role.changed','member.removed','export.created','reference.corrected','reference.reopened','reference.expired','invitation.created','invitation.revoked','notification.created','organization.updated','setting.changed','ingestion.started','ingestion.validated','ingestion.promoted','session.revoked')")

def downgrade() -> None:
    op.drop_constraint("ck_audit_action", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_action", "audit_events", "action IN ('reference.created','reference.submitted','reference.verified','reference.rejected','reference.superseded','source.promoted','policy.changed','role.changed','member.removed','export.created','reference.corrected','reference.reopened','reference.expired')")
    for table in ("ingestion_runs", *reversed(_ORG_TABLES), "user_sessions"):
        op.execute(text(f'DROP POLICY IF EXISTS "tanim_{table}_tenant" ON "{table}"'))
        op.execute(text(f'ALTER TABLE IF EXISTS "{table}" DISABLE ROW LEVEL SECURITY'))
    op.execute(text("ALTER TABLE data_source_versions DROP CONSTRAINT IF EXISTS fk_data_source_versions_promoted_by"))
    op.execute(text("ALTER TABLE ingestion_runs DROP CONSTRAINT IF EXISTS fk_ingestion_runs_requested_by"))
    op.drop_table("rate_limit_buckets")
    op.drop_table("ingestion_runs")
    for table in reversed(_ORG_TABLES):
        op.drop_table(table)
    op.drop_table("user_sessions")
    for column in ("is_current", "promoted_by", "staged_at", "normalization_version", "validation_errors", "validation_status", "row_count", "period_end", "period_start"):
        op.drop_column("data_source_versions", column)
    op.drop_column("calculation_runs", "result_json")
    op.drop_column("organizations", "default_geography")
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=False)
    op.drop_column("users", "is_platform")
    op.drop_constraint("uq_users_provider_subject", "users", type_="unique")
    op.drop_column("users", "provider_subject")