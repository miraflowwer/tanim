"""SQLAlchemy 2 models mirroring alembic 0001 (PRD §§17, 18, 19, 39, 40).

Evidence never overwritten: new version rows supersede old ones; audit /
calculation / plan-revision rows are append-only (see migration trigger+RLS).
Enum value lists for reference type/verification reuse grci.py (read-only).
"""
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from .grci import REFERENCE_TYPES, VERIFICATION_STATES


class Base(DeclarativeBase):
    pass


class Geography(UserDefinedType):
    """PostGIS GEOGRAPHY(Point, 4326); NULL unless consented (§19)."""

    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "GEOGRAPHY(Point, 4326)"


# Platform authority is global and is deliberately excluded from
# organization membership rows. It is resolved from the deployment identity.
OrgRole = Enum("farmer", "coordinator", "reviewer", "org_admin",
               name="org_role")
ReferenceType = Enum(*REFERENCE_TYPES, name="reference_type")
VerificationStatus = Enum(*VERIFICATION_STATES, name="verification_status")
ReviewStatus = Enum("draft", "under_review", "verified", "rejected",
                    "superseded", "expired", name="review_status")
PlanStatus = Enum("draft", "planned", "harvested", "cancelled",
                  name="plan_status")
CalcStatus = Enum("complete", "incomplete", "failed", name="calc_status")
ConsentType = Enum("operational", "research", name="consent_type")

def _pk():
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = _now()


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = _now()


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id",
                                       name="uq_membership_org_user"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"),
                                              index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"),
                                               index=True)
    role: Mapped[str] = mapped_column(OrgRole, server_default="farmer")
    created_at: Mapped[datetime] = _now()


class Farm(Base):
    __tablename__ = "farms"
    __table_args__ = (CheckConstraint(
        "total_area_ha IS NULL OR total_area_ha > 0",
        name="ck_farms_area_pos"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"),
                                              index=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"),
                                                     index=True)
    name: Mapped[str] = mapped_column(Text)
    total_area_ha: Mapped[float | None] = mapped_column(Numeric(12, 3))
    municipality: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = _now()


class FarmLocation(Base):
    __tablename__ = "farm_locations"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"),
                                              index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"),
                                               index=True)
    geom: Mapped[Any | None] = mapped_column(Geography)
    municipality: Mapped[str] = mapped_column(Text)
    is_exact: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = _now()


class Crop(Base):
    __tablename__ = "crops"
    id: Mapped[uuid.UUID] = _pk()
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = _now()


class CropAlias(Base):
    __tablename__ = "crop_aliases"
    __table_args__ = (UniqueConstraint("crop_id", "alias",
                                       name="uq_crop_alias"),)
    id: Mapped[uuid.UUID] = _pk()
    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id"),
                                               index=True)
    alias: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = _now()


class PlantingPlan(Base):
    __tablename__ = "planting_plans"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"),
                                              index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"),
                                               index=True)
    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id"),
                                               index=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"),
                                                     index=True)
    status: Mapped[str] = mapped_column(PlanStatus, server_default="draft")
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = _now()


class PlantingPlanRevision(Base):
    """Append-only revision chain; never UPDATE/DELETE (§17)."""
    __tablename__ = "planting_plan_revisions"
    __table_args__ = (
        UniqueConstraint("plan_id", "revision_number",
                         name="uq_plan_revision"),
        CheckConstraint("area_ha > 0", name="ck_revision_area_pos"),
        CheckConstraint("area_margin_ha >= 0",
                        name="ck_revision_margin_nonneg"),
        CheckConstraint("harvest_period >= planting_date",
                        name="ck_revision_dates"),
    )
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"),
                                              index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("planting_plans.id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    area_ha: Mapped[float] = mapped_column(Numeric(12, 3))
    area_margin_ha: Mapped[float] = mapped_column(Numeric(12, 3),
                                                  server_default="0")
    planting_date: Mapped[date] = mapped_column(Date)
    harvest_period: Mapped[date] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default="now()")


class DataSource(Base):
    __tablename__ = "data_sources"
    id: Mapped[uuid.UUID] = _pk()
    key: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    expected_refresh_interval: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _now()


class DataSourceVersion(Base):
    __tablename__ = "data_source_versions"
    __table_args__ = (UniqueConstraint("source_id", "version",
                                       name="uq_source_version"),)
    id: Mapped[uuid.UUID] = _pk()
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default="now()")
    promoted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True))  # NULL = staged, not yet promoted (§38)
    checksum: Mapped[str | None] = mapped_column(Text)
    payload_ref: Mapped[str | None] = mapped_column(Text)


class _EvidenceMixin:
    """Version + review state + validity window + supersede chain (§17)."""
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(
        VerificationStatus, server_default="user_provided_unverified")
    effective_from: Mapped[date] = mapped_column(
        Date, server_default=text("CURRENT_DATE"))
    effective_to: Mapped[date | None] = mapped_column(Date)
    data_source_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_source_versions.id"))


class YieldReference(_EvidenceMixin, Base):
    __tablename__ = "yield_references"
    __table_args__ = (
        UniqueConstraint("org_id", "crop_id", "geography", "period", "version",
                         name="uq_yield_org_crop_geo_period_ver"),
        CheckConstraint(
            "effective_to IS NULL OR effective_from <= effective_to",
            name="ck_yield_effective_window"),
        CheckConstraint("yield_mt_per_ha > 0", name="ck_yield_pos"),
    )
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"),
                                              index=True)
    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id"),
                                               index=True)
    geography: Mapped[str] = mapped_column(Text)
    period: Mapped[str] = mapped_column(Text)
    yield_mt_per_ha: Mapped[float] = mapped_column(Numeric(12, 4))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("yield_references.id"))


class ComparisonReference(_EvidenceMixin, Base):
    __tablename__ = "comparison_references"
    __table_args__ = (
        UniqueConstraint("org_id", "crop_id", "geography", "period", "version",
                         name="uq_compref_org_crop_geo_period_ver"),
        CheckConstraint(
            "effective_to IS NULL OR effective_from <= effective_to",
            name="ck_compref_effective_window"),
        CheckConstraint("amount_mt > 0", name="ck_compref_amount_pos"),
    )
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"),
                                              index=True)
    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id"),
                                               index=True)
    reference_type: Mapped[str] = mapped_column(ReferenceType)
    amount_mt: Mapped[float] = mapped_column(Numeric(14, 3))
    unit: Mapped[str] = mapped_column(Text, server_default="MT")
    geography: Mapped[str] = mapped_column(Text)
    period: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    evidence_note: Mapped[str | None] = mapped_column(Text)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comparison_references.id"))


class ReferenceReview(Base):
    __tablename__ = "reference_reviews"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"),
                                              index=True)
    comparison_reference_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comparison_references.id"), index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    from_status: Mapped[str] = mapped_column(ReviewStatus)
    to_status: Mapped[str] = mapped_column(ReviewStatus)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default="now()")


class PriceObservation(_EvidenceMixin, Base):
    """Context only — never R (§14.2)."""
    __tablename__ = "price_observations"
    __table_args__ = (CheckConstraint("price > 0", name="ck_price_pos"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"),
                                              index=True)
    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id"),
                                               index=True)
    geography: Mapped[str] = mapped_column(Text)
    observed_on: Mapped[date] = mapped_column(Date)
    price: Mapped[float] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(Text, server_default="PHP")
    series_id: Mapped[str] = mapped_column(Text)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("price_observations.id"))


class ClimateContext(_EvidenceMixin, Base):
    """Context only (§14.4)."""
    __tablename__ = "climate_context"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"),
                                              index=True)
    geography: Mapped[str] = mapped_column(Text)
    period: Mapped[str] = mapped_column(Text)
    outlook: Mapped[str] = mapped_column(Text)
    source_date: Mapped[date] = mapped_column(Date)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("climate_context.id"))


class WeatherObservation(Base):
    """Cached, optional (§14.5)."""
    __tablename__ = "weather_observations"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"),
                                              index=True)
    geography: Mapped[str] = mapped_column(Text, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSONB)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   server_default="now()")
    data_source_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_source_versions.id"))


class SuitabilityReference(_EvidenceMixin, Base):
    """NCCAG layer identity kept (§14.6)."""
    __tablename__ = "suitability_references"
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"),
                                              index=True)
    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id"),
                                               index=True)
    geography: Mapped[str] = mapped_column(Text)
    layer_id: Mapped[str] = mapped_column(Text)
    suitability_class: Mapped[str] = mapped_column(Text)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("suitability_references.id"))


class CalculationPolicy(Base):
    """Global thresholds; change => new version row (§12)."""
    __tablename__ = "calculation_policies"
    id: Mapped[uuid.UUID] = _pk()
    version: Mapped[int] = mapped_column(Integer, unique=True)
    thresholds: Mapped[dict] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default="now()")


class CalculationRun(Base):
    """Append-only; full version bundle + S/L + observability (§§12, 33)."""
    __tablename__ = "calculation_runs"
    __table_args__ = (CheckConstraint(
        "duration_ms IS NULL OR duration_ms >= 0",
        name="ck_calc_duration_nonneg"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"),
                                              index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("planting_plans.id"), index=True)
    plan_revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("planting_plan_revisions.id"))
    engine_version: Mapped[str] = mapped_column(Text)
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("calculation_policies.id"))
    policy_version: Mapped[int] = mapped_column(Integer)
    registry_version: Mapped[int] = mapped_column(Integer)
    yield_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("yield_references.id"))
    yield_reference_version: Mapped[int | None] = mapped_column(Integer)
    comparison_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comparison_references.id"))
    comparison_reference_version: Mapped[int | None] = mapped_column(
        Integer)
    s_mt: Mapped[float | None] = mapped_column(Numeric(14, 3))
    s_low_mt: Mapped[float | None] = mapped_column(Numeric(14, 3))
    s_high_mt: Mapped[float | None] = mapped_column(Numeric(14, 3))
    supply_load: Mapped[float | None] = mapped_column(Numeric(14, 6))
    status: Mapped[str] = mapped_column(CalcStatus)
    request_id: Mapped[str] = mapped_column(Text, unique=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default="now()")


class ConsentRecord(Base):
    """Operational vs research consent split (§8.7)."""
    __tablename__ = "consent_records"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "user_id", "consent_type", "version",
            name="uq_consent_org_user_type_version",
        ),
    )
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"),
                                              index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"),
                                               index=True)
    consent_type: Mapped[str] = mapped_column(ConsentType)
    purpose: Mapped[str] = mapped_column(Text)
    policy_version: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   server_default="now()")
    withdrawn_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True))


class AuditEvent(Base):
    """Immutable: actor + time + target + action (§40)."""
    __tablename__ = "audit_events"
    __table_args__ = (CheckConstraint(
        "action IN ('reference.created','reference.submitted',"
        "'reference.verified','reference.rejected','reference.superseded',"
        "'source.promoted','policy.changed','role.changed',"
        "'member.removed','export.created',"
        "'reference.corrected','reference.reopened','reference.expired')",
        name="ck_audit_action"),)
    id: Mapped[uuid.UUID] = _pk()
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(Text)
    target_kind: Mapped[str] = mapped_column(Text)
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default="now()")
