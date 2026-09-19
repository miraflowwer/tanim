# ruff: noqa: E701, E702
"""PostgreSQL repository boundary for all production persistence."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, or_, select, text
from sqlalchemy.orm import Session

from ..models import (AuditEvent, CalculationPolicy, CalculationRun, ComparisonReference, ConsentRecord, Crop, DataSource, DataSourceVersion, Farm, Organization, OrganizationMembership, PlantingPlan, PlantingPlanRevision, ReferenceReview, User, YieldReference)
from ..platform_models import ExportRequest, IngestionRun, Invitation, Notification, OrganizationSetting
from .base import Page, RepositoryIdentity

def _uuid(value: str | uuid.UUID) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
def _str(value: Any) -> str | None:
    return str(value) if value is not None else None
def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else _str(value)
def _num(value: Any) -> float | None:
    return float(value) if value is not None else None
def _org_dict(row: Organization) -> dict[str, Any]:
    return {"id": str(row.id), "name": row.name, "slug": row.slug, "default_geography": row.default_geography, "version": row.version, "created_at": _iso(row.created_at), "updated_at": _iso(row.updated_at)}

class PostgresRepository:
    def __init__(self, session: Session, identity: RepositoryIdentity, org_id: str | None = None):
        self.session, self.identity, self.org_id = session, identity, org_id

    @staticmethod
    def resolve_identity(session: Session, provider_subject: str, email: str = "") -> RepositoryIdentity | None:
        user = session.execute(select(User).where(User.provider_subject == provider_subject)).scalar_one_or_none()
        if user is None and email:
            user = session.execute(select(User).where(func.lower(User.email) == email.strip().lower())).scalar_one_or_none()
        if user is None:
            try:
                user = session.get(User, _uuid(provider_subject))
            except (ValueError, AttributeError):
                user = None
        if user is None:
            return None
        session.execute(text("SELECT set_config('app.current_user_id', :user_id, true)"), {"user_id": str(user.id)})
        memberships = session.execute(select(OrganizationMembership.org_id, OrganizationMembership.role).where(OrganizationMembership.user_id == user.id)).all()
        return RepositoryIdentity(str(user.id), user.email or email, {str(org): str(role) for org, role in memberships}, bool(user.is_platform))

    def page(self, rows: list[dict[str, Any]], *, limit: int = 50, cursor: str | None = None) -> Page:
        limit = max(1, min(int(limit), 200))
        try:
            start = max(0, int(cursor)) if cursor else 0
        except ValueError:
            start = 0
        selected = rows[start:start + limit]
        return Page(selected, str(start + limit) if start + limit < len(rows) else None, len(rows))

    def _uid(self) -> uuid.UUID:
        return _uuid(self.identity.user_id)

    def organization(self) -> dict[str, Any] | None:
        row = self.session.get(Organization, _uuid(self.org_id)) if self.org_id else None
        return _org_dict(row) if row else None

    def update_organization(self, values: dict[str, Any]) -> dict[str, Any]:
        row = self.session.get(Organization, _uuid(self.org_id))
        if row is None:
            raise KeyError("organization")
        for key in ("name", "slug", "default_geography"):
            if key in values and values[key] is not None:
                setattr(row, key, values[key])
        row.version = int(row.version or 1) + 1
        row.updated_at = datetime.now(UTC)
        self.session.flush()
        return _org_dict(row)

    def members(self) -> list[dict[str, Any]]:
        rows = self.session.execute(select(OrganizationMembership, User).join(User, User.id == OrganizationMembership.user_id).where(OrganizationMembership.org_id == _uuid(self.org_id)).order_by(User.email)).all()
        return [{"membership_id": str(m.id), "user_id": str(u.id), "email": u.email, "display_name": u.display_name, "role": str(m.role), "created_at": _iso(m.created_at)} for m, u in rows]

    def change_role(self, membership_id: str, role: str) -> dict[str, Any]:
        row = self.session.get(OrganizationMembership, _uuid(membership_id))
        if row is None or str(row.org_id) != str(self.org_id):
            raise KeyError("membership")
        old = str(row.role)
        row.role = role
        self.session.flush()
        return {"membership_id": membership_id, "user_id": str(row.user_id), "from_role": old, "role": role}

    def remove_member(self, membership_id: str) -> None:
        row = self.session.get(OrganizationMembership, _uuid(membership_id))
        if row is None or str(row.org_id) != str(self.org_id):
            raise KeyError("membership")
        self.session.delete(row)
        self.session.flush()

    def settings(self) -> dict[str, Any]:
        rows = self.session.execute(select(OrganizationSetting).where(OrganizationSetting.org_id == _uuid(self.org_id)).order_by(OrganizationSetting.setting_key)).scalars().all()
        return {row.setting_key: row.setting_value for row in rows}

    def put_setting(self, key: str, value: dict[str, Any]) -> dict[str, Any]:
        row = self.session.execute(select(OrganizationSetting).where(OrganizationSetting.org_id == _uuid(self.org_id), OrganizationSetting.setting_key == key)).scalar_one_or_none()
        if row is None:
            row = OrganizationSetting(org_id=_uuid(self.org_id), setting_key=key, setting_value=value, updated_by=self._uid())
            self.session.add(row)
        else:
            row.setting_value, row.updated_by, row.updated_at = value, self._uid(), datetime.now(UTC)
        self.session.flush()
        return {"key": key, "value": value}

    def create_invitation(self, *, email: str, role: str, token_hash: str, expires_at: datetime) -> dict[str, Any]:
        row = Invitation(org_id=_uuid(self.org_id), email=email.strip().lower(), role=role, token_hash=token_hash, invited_by=self._uid(), expires_at=expires_at)
        self.session.add(row)
        self.session.flush()
        return {"id": str(row.id), "email": row.email, "role": row.role, "status": row.status, "expires_at": _iso(row.expires_at), "created_at": _iso(row.created_at)}

    def invitations(self, status: str | None = None) -> list[dict[str, Any]]:
        query = select(Invitation).where(Invitation.org_id == _uuid(self.org_id)).order_by(desc(Invitation.created_at))
        if status:
            query = query.where(Invitation.status == status)
        return [{"id": str(row.id), "email": row.email, "role": row.role, "status": row.status, "expires_at": _iso(row.expires_at), "accepted_at": _iso(row.accepted_at), "created_at": _iso(row.created_at)} for row in self.session.execute(query).scalars().all()]

    @staticmethod
    def farm_dict(row: Farm) -> dict[str, Any]:
        return {"id": str(row.id), "organization_id": str(row.org_id), "owner_user_id": str(row.owner_user_id), "name": row.name, "total_area_ha": _num(row.total_area_ha), "municipality": row.municipality, "region": row.region, "created_at": _iso(row.created_at), "updated_at": _iso(row.updated_at)}
    def create_farm(self, values: dict[str, Any]) -> dict[str, Any]:
        row = Farm(org_id=_uuid(self.org_id), owner_user_id=self._uid(), name=values["name"], total_area_ha=values.get("total_area_ha"), municipality=values.get("municipality"), region=values.get("region"))
        self.session.add(row)
        self.session.flush()
        return self.farm_dict(row)
    def get_farm(self, farm_id: str) -> Farm | None:
        row = self.session.execute(select(Farm).where(Farm.id == _uuid(farm_id), Farm.org_id == _uuid(self.org_id))).scalar_one_or_none()
        if row and self.identity.role_in(self.org_id) == "farmer" and str(row.owner_user_id) != self.identity.user_id:
            return None
        return row
    def list_farms(self) -> list[dict[str, Any]]:
        query = select(Farm).where(Farm.org_id == _uuid(self.org_id)).order_by(Farm.created_at)
        if not self.identity.is_platform and self.identity.role_in(self.org_id) == "farmer":
            query = query.where(Farm.owner_user_id == self._uid())
        return [self.farm_dict(row) for row in self.session.execute(query).scalars().all()]
    def update_farm(self, farm_id: str, values: dict[str, Any]) -> dict[str, Any]:
        row = self.get_farm(farm_id)
        if row is None: raise KeyError("farm")
        for key in ("name", "total_area_ha", "municipality", "region"):
            if key in values: setattr(row, key, values[key])
        row.updated_at = datetime.now(UTC)
        self.session.flush()
        return self.farm_dict(row)
    def delete_farm(self, farm_id: str) -> None:
        row = self.get_farm(farm_id)
        if row is None: raise KeyError("farm")
        self.session.delete(row)
        self.session.flush()

    def list_crops(self) -> list[dict[str, Any]]:
        rows = self.session.execute(select(Crop).where(Crop.is_active.is_(True)).order_by(Crop.code)).scalars().all()
        return [{"code": r.code, "name": r.name, "version": r.version, "is_active": bool(r.is_active)} for r in rows]
    def crop(self, code: str) -> Crop | None:
        return self.session.execute(select(Crop).where(Crop.code == code, Crop.is_active.is_(True))).scalar_one_or_none()

    @staticmethod
    def revision_dict(row: PlantingPlanRevision) -> dict[str, Any]:
        return {"id": str(row.id), "revision_number": row.revision_number, "area_ha": _num(row.area_ha), "area_margin_ha": _num(row.area_margin_ha), "planting_date": _iso(row.planting_date), "harvest_period": _iso(row.harvest_period), "version": row.version, "created_by": _str(row.created_by), "created_at": _iso(row.created_at)}
    def plan_dict(self, plan: PlantingPlan, crop: Crop, revision: PlantingPlanRevision | None = None) -> dict[str, Any]:
        revision = revision or (self.session.get(PlantingPlanRevision, plan.current_revision_id) if plan.current_revision_id else None)
        return {"id": str(plan.id), "organization_id": str(plan.org_id), "farm_id": str(plan.farm_id), "crop_code": crop.code, "crop_name": crop.name, "owner_user_id": str(plan.owner_user_id), "status": str(plan.status), "current_revision": self.revision_dict(revision) if revision else None, "created_at": _iso(plan.created_at), "updated_at": _iso(plan.updated_at)}
    def get_plan_row(self, plan_id: str) -> tuple[PlantingPlan, Crop, PlantingPlanRevision | None] | None:
        row = self.session.execute(select(PlantingPlan, Crop).join(Crop, Crop.id == PlantingPlan.crop_id).where(PlantingPlan.id == _uuid(plan_id), PlantingPlan.org_id == _uuid(self.org_id))).first()
        if row is None: return None
        plan, crop = row
        if self.identity.role_in(self.org_id) == "farmer" and str(plan.owner_user_id) != self.identity.user_id: return None
        revision = self.session.get(PlantingPlanRevision, plan.current_revision_id) if plan.current_revision_id else None
        return plan, crop, revision
    def get_plan(self, plan_id: str) -> dict[str, Any] | None:
        row = self.get_plan_row(plan_id)
        return self.plan_dict(*row) if row else None
    def list_plans(self, status: str | None = None, crop_code: str | None = None) -> list[dict[str, Any]]:
        query = select(PlantingPlan, Crop).join(Crop, Crop.id == PlantingPlan.crop_id).where(PlantingPlan.org_id == _uuid(self.org_id)).order_by(PlantingPlan.created_at)
        if not self.identity.is_platform and self.identity.role_in(self.org_id) == "farmer": query = query.where(PlantingPlan.owner_user_id == self._uid())
        if status: query = query.where(PlantingPlan.status == status)
        if crop_code: query = query.where(Crop.code == crop_code)
        return [self.plan_dict(p, c) for p, c in self.session.execute(query).all()]
    def create_plan(self, values: dict[str, Any]) -> dict[str, Any]:
        farm = self.get_farm(values["farm_id"])
        crop = self.crop(values["crop_code"])
        if farm is None: raise KeyError("farm")
        if crop is None: raise KeyError("crop")
        plan = PlantingPlan(org_id=_uuid(self.org_id), farm_id=farm.id, crop_id=crop.id, owner_user_id=self._uid(), status=values.get("status", "draft"))
        self.session.add(plan); self.session.flush()
        revision = PlantingPlanRevision(org_id=_uuid(self.org_id), plan_id=plan.id, revision_number=1, area_ha=values["area_ha"], area_margin_ha=values.get("area_margin_ha", 0), planting_date=values["planting_date"], harvest_period=values["harvest_period"], created_by=self._uid())
        self.session.add(revision); self.session.flush()
        plan.current_revision_id = revision.id; self.session.flush()
        return self.plan_dict(plan, crop, revision)
    def append_revision(self, plan_id: str, values: dict[str, Any]) -> dict[str, Any]:
        row = self.get_plan_row(plan_id)
        if row is None: raise KeyError("plan")
        plan, crop, _ = row
        latest = self.session.execute(select(func.max(PlantingPlanRevision.revision_number)).where(PlantingPlanRevision.plan_id == plan.id)).scalar() or 0
        rev = PlantingPlanRevision(org_id=_uuid(self.org_id), plan_id=plan.id, revision_number=int(latest) + 1, area_ha=values["area_ha"], area_margin_ha=values.get("area_margin_ha", 0), planting_date=values["planting_date"], harvest_period=values["harvest_period"], created_by=self._uid())
        self.session.add(rev); self.session.flush()
        if values.get("status") is not None: plan.status = values["status"]
        plan.current_revision_id, plan.updated_at = rev.id, datetime.now(UTC); self.session.flush()
        return self.plan_dict(plan, crop, rev)
    def revisions(self, plan_id: str) -> list[dict[str, Any]]:
        if self.get_plan_row(plan_id) is None: return []
        rows = self.session.execute(select(PlantingPlanRevision).where(PlantingPlanRevision.plan_id == _uuid(plan_id)).order_by(PlantingPlanRevision.revision_number)).scalars().all()
        return [self.revision_dict(r) for r in rows]

    @staticmethod
    def calculation_dict(row: CalculationRun) -> dict[str, Any]:
        return {"id": str(row.id), "calculation_id": str(row.id), "organization_id": str(row.org_id), "plan_id": str(row.plan_id), "plan_revision_id": str(row.plan_revision_id), "engine_version": row.engine_version, "policy_id": _str(row.policy_id), "policy_version": row.policy_version, "registry_version": row.registry_version, "yield_reference_id": _str(row.yield_reference_id), "yield_reference_version": row.yield_reference_version, "comparison_reference_id": _str(row.comparison_reference_id), "comparison_reference_version": row.comparison_reference_version, "s_mt": _num(row.s_mt), "s_low_mt": _num(row.s_low_mt), "s_high_mt": _num(row.s_high_mt), "supply_load": _num(row.supply_load), "status": row.status, "request_id": row.request_id, "duration_ms": row.duration_ms, "result": row.result_json, "created_at": _iso(row.created_at)}
    def create_calculation(self, values: dict[str, Any]) -> dict[str, Any]:
        row = CalculationRun(org_id=_uuid(self.org_id), plan_id=_uuid(values["plan_id"]), plan_revision_id=_uuid(values["plan_revision_id"]), engine_version=values["engine_version"], policy_id=_uuid(values["policy_id"]) if values.get("policy_id") else None, policy_version=int(values["policy_version"]), registry_version=int(values.get("registry_version", 1)), yield_reference_id=_uuid(values["yield_reference_id"]) if values.get("yield_reference_id") else None, yield_reference_version=values.get("yield_reference_version"), comparison_reference_id=_uuid(values["comparison_reference_id"]) if values.get("comparison_reference_id") else None, comparison_reference_version=values.get("comparison_reference_version"), s_mt=values.get("s_mt"), s_low_mt=values.get("s_low_mt"), s_high_mt=values.get("s_high_mt"), supply_load=values.get("supply_load"), status=values["status"], request_id=values["request_id"], duration_ms=values.get("duration_ms"), result_json=values.get("result_json"))
        self.session.add(row); self.session.flush()
        return self.calculation_dict(row)
    def get_calculation(self, calc_id: str) -> dict[str, Any] | None:
        row = self.session.execute(select(CalculationRun).where(CalculationRun.id == _uuid(calc_id), CalculationRun.org_id == _uuid(self.org_id))).scalar_one_or_none()
        return self.calculation_dict(row) if row else None
    def calculations_for_plan(self, plan_id: str) -> list[dict[str, Any]]:
        rows = self.session.execute(select(CalculationRun).where(CalculationRun.plan_id == _uuid(plan_id), CalculationRun.org_id == _uuid(self.org_id)).order_by(desc(CalculationRun.created_at))).scalars().all()
        return [self.calculation_dict(r) for r in rows]

    def policies(self) -> list[dict[str, Any]]:
        rows = self.session.execute(select(CalculationPolicy).order_by(desc(CalculationPolicy.version))).scalars().all()
        return [{"id": str(r.id), "version": r.version, "thresholds": r.thresholds, "created_by": _str(r.created_by), "created_at": _iso(r.created_at)} for r in rows]
    def create_policy(self, thresholds: dict[str, Any]) -> dict[str, Any]:
        version = int(self.session.execute(select(func.max(CalculationPolicy.version))).scalar() or 0) + 1
        row = CalculationPolicy(version=version, thresholds=thresholds, created_by=self._uid())
        self.session.add(row); self.session.flush()
        return {"id": str(row.id), "version": row.version, "thresholds": row.thresholds, "created_by": _str(row.created_by), "created_at": _iso(row.created_at)}

    def audit(self, *, action: str, target_kind: str, target_id: str | None = None, metadata: dict[str, Any] | None = None, global_event: bool = False) -> dict[str, Any]:
        row = AuditEvent(org_id=None if global_event else _uuid(self.org_id), actor_user_id=self._uid(), action=action, target_kind=target_kind, target_id=_uuid(target_id) if target_id else None, event_metadata=metadata or {})
        self.session.add(row); self.session.flush()
        return {"id": str(row.id), "org_id": _str(row.org_id), "actor_user_id": _str(row.actor_user_id), "action": row.action, "target_kind": row.target_kind, "target_id": _str(row.target_id), "metadata": row.event_metadata, "created_at": _iso(row.created_at)}
    def audit_events(self, action: str | None = None) -> list[dict[str, Any]]:
        query = select(AuditEvent).where(or_(AuditEvent.org_id == _uuid(self.org_id), AuditEvent.org_id.is_(None))).order_by(desc(AuditEvent.created_at))
        if action: query = query.where(AuditEvent.action == action)
        rows = self.session.execute(query).scalars().all()
        return [{"id": str(r.id), "org_id": _str(r.org_id), "actor_user_id": _str(r.actor_user_id), "action": r.action, "target_kind": r.target_kind, "target_id": _str(r.target_id), "metadata": r.event_metadata, "created_at": _iso(r.created_at)} for r in rows]

    def data_sources(self) -> list[dict[str, Any]]:
        rows = self.session.execute(select(DataSource).order_by(DataSource.key)).scalars().all()
        return [{"id": str(r.id), "key": r.key, "name": r.name, "kind": r.kind, "expected_refresh_interval": r.expected_refresh_interval, "created_at": _iso(r.created_at)} for r in rows]
    def data_source(self, key: str) -> DataSource | None:
        return self.session.execute(select(DataSource).where(DataSource.key == key)).scalar_one_or_none()
    @staticmethod
    def version_dict(row: DataSourceVersion) -> dict[str, Any]:
        return {"id": str(row.id), "source_id": str(row.source_id), "version": row.version, "fetched_at": _iso(row.fetched_at), "promoted_at": _iso(row.promoted_at), "checksum": row.checksum, "payload_ref": row.payload_ref, "period_start": _iso(row.period_start), "period_end": _iso(row.period_end), "row_count": row.row_count, "validation_status": row.validation_status, "validation_errors": row.validation_errors, "normalization_version": row.normalization_version, "staged_at": _iso(row.staged_at), "promoted_by": _str(row.promoted_by), "is_current": bool(row.is_current)}
    def source_versions(self, key: str) -> list[dict[str, Any]]:
        source = self.data_source(key)
        if source is None: return []
        rows = self.session.execute(select(DataSourceVersion).where(DataSourceVersion.source_id == source.id).order_by(desc(DataSourceVersion.version))).scalars().all()
        return [self.version_dict(r) for r in rows]
    def create_source_if_missing(self, *, key: str, name: str, kind: str, expected_refresh_interval: str | None = None) -> DataSource:
        source = self.data_source(key)
        if source is None:
            source = DataSource(key=key, name=name, kind=kind, expected_refresh_interval=expected_refresh_interval)
            self.session.add(source); self.session.flush()
        return source
    def create_source_version(self, *, source: DataSource, values: dict[str, Any]) -> dict[str, Any]:
        checksum = values.get("checksum")
        if not checksum:
            raise ValueError("source_version_checksum_required")
        duplicate = self.session.execute(
            select(DataSourceVersion).where(
                DataSourceVersion.source_id == source.id,
                DataSourceVersion.checksum == checksum,
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise ValueError("duplicate_source_version")
        latest = int(
            self.session.execute(
                select(func.max(DataSourceVersion.version)).where(
                    DataSourceVersion.source_id == source.id
                )
            ).scalar()
            or 0
        ) + 1
        row = DataSourceVersion(
            source_id=source.id,
            version=latest,
            checksum=checksum,
            payload_ref=values.get("payload_ref"),
            period_start=values.get("period_start"),
            period_end=values.get("period_end"),
            row_count=int(values.get("row_count", 0)),
            validation_status=values.get("validation_status", "valid"),
            validation_errors=values.get("validation_errors"),
            normalization_version=values.get("normalization_version"),
            staged_at=datetime.now(UTC),
        )
        self.session.add(row)
        self.session.flush()
        return self.version_dict(row)

    def promote_source_version(self, *, key: str, version: int) -> dict[str, Any]:
        source = self.data_source(key)
        if source is None: raise KeyError("data_source")
        rows = self.session.execute(select(DataSourceVersion).where(DataSourceVersion.source_id == source.id)).scalars().all()
        row = next((item for item in rows if item.version == version), None)
        if row is None: raise KeyError("source_version")
        if row.validation_status != "valid": raise ValueError("source_version_not_valid")
        for item in rows: item.is_current = False
        row.is_current, row.promoted_at, row.promoted_by = True, datetime.now(UTC), self._uid()
        self.session.flush()
        return self.version_dict(row)

    def create_export(self, *, purpose: str, include_individuals: bool, request_id: str) -> dict[str, Any]:
        row = ExportRequest(org_id=_uuid(self.org_id), requested_by=self._uid(), purpose=purpose, include_individuals=include_individuals, request_id=request_id)
        self.session.add(row); self.session.flush()
        return self.export_dict(row)
    @staticmethod
    def export_dict(row: ExportRequest) -> dict[str, Any]:
        return {"id": str(row.id), "organization_id": str(row.org_id), "requested_by": str(row.requested_by), "purpose": row.purpose, "include_individuals": bool(row.include_individuals), "status": row.status, "object_ref": row.object_ref, "error_code": row.error_code, "request_id": row.request_id, "created_at": _iso(row.created_at), "completed_at": _iso(row.completed_at)}
    def exports(self) -> list[dict[str, Any]]:
        rows = self.session.execute(select(ExportRequest).where(ExportRequest.org_id == _uuid(self.org_id)).order_by(desc(ExportRequest.created_at))).scalars().all()
        return [self.export_dict(r) for r in rows]
    def export(self, export_id: str) -> dict[str, Any] | None:
        row = self.session.execute(select(ExportRequest).where(ExportRequest.id == _uuid(export_id), ExportRequest.org_id == _uuid(self.org_id))).scalar_one_or_none()
        return self.export_dict(row) if row else None

    def notifications(self, unread_only: bool = False) -> list[dict[str, Any]]:
        query = select(Notification).where(Notification.org_id == _uuid(self.org_id), or_(Notification.user_id.is_(None), Notification.user_id == self._uid())).order_by(desc(Notification.created_at))
        if unread_only: query = query.where(Notification.read_at.is_(None))
        rows = self.session.execute(query).scalars().all()
        return [{"id": str(r.id), "organization_id": str(r.org_id), "user_id": _str(r.user_id), "kind": r.kind, "title": r.title, "body": r.body, "payload": r.payload, "read_at": _iso(r.read_at), "created_at": _iso(r.created_at)} for r in rows]
    def mark_notification_read(self, notification_id: str) -> dict[str, Any]:
        row = self.session.execute(select(Notification).where(Notification.id == _uuid(notification_id), Notification.org_id == _uuid(self.org_id), or_(Notification.user_id.is_(None), Notification.user_id == self._uid()))).scalar_one_or_none()
        if row is None: raise KeyError("notification")
        row.read_at = datetime.now(UTC); self.session.flush()
        return {"id": str(row.id), "read_at": _iso(row.read_at)}

    @staticmethod
    def ingestion_dict(row: IngestionRun) -> dict[str, Any]:
        return {"id": str(row.id), "source_id": str(row.source_id), "organization_id": _str(row.org_id), "requested_by": str(row.requested_by), "status": row.status, "lifecycle_stage": row.lifecycle_stage, "idempotency_key": row.idempotency_key, "row_count": row.row_count, "validation_errors": row.validation_errors, "validation_summary": row.validation_summary, "source_version_id": _str(row.source_version_id), "error_code": row.error_code, "started_at": _iso(row.started_at), "finished_at": _iso(row.finished_at), "created_at": _iso(row.created_at)}
    def create_ingestion_run(self, *, source: DataSource, idempotency_key: str, org_id: str | None = None) -> dict[str, Any]:
        existing = self.session.execute(select(IngestionRun).where(IngestionRun.idempotency_key == idempotency_key)).scalar_one_or_none()
        if existing: return self.ingestion_dict(existing)
        row = IngestionRun(source_id=source.id, org_id=_uuid(org_id) if org_id else None, requested_by=self._uid(), idempotency_key=idempotency_key, started_at=datetime.now(UTC))
        self.session.add(row); self.session.flush()
        return self.ingestion_dict(row)
    def get_ingestion_run(self, run_id: str) -> IngestionRun | None:
        return self.session.get(IngestionRun, _uuid(run_id))
    def update_ingestion(self, run_id: str, values: dict[str, Any]) -> dict[str, Any]:
        row = self.get_ingestion_run(run_id)
        if row is None: raise KeyError("ingestion_run")
        for key in ("status", "lifecycle_stage", "row_count", "validation_errors", "validation_summary", "source_version_id", "error_code", "finished_at"):
            if key in values: setattr(row, key, values[key])
        self.session.flush(); return self.ingestion_dict(row)
    def ingestion_runs(self, source_key: str | None = None) -> list[dict[str, Any]]:
        query = select(IngestionRun).order_by(desc(IngestionRun.created_at))
        if source_key:
            source = self.data_source(source_key)
            if source is None: return []
            query = query.where(IngestionRun.source_id == source.id)
        return [self.ingestion_dict(r) for r in self.session.execute(query).scalars().all()]
    def consume_rate_limit(self, bucket_key: str, limit: int) -> bool:
        now = datetime.now(UTC); window = now.replace(second=0, microsecond=0)
        count = self.session.execute(text("""
            INSERT INTO rate_limit_buckets (bucket_key, window_start, hit_count)
            VALUES (:bucket_key, :window_start, 1)
            ON CONFLICT (bucket_key) DO UPDATE SET
              hit_count = CASE WHEN rate_limit_buckets.window_start < :window_start THEN 1 ELSE rate_limit_buckets.hit_count + 1 END,
              window_start = CASE WHEN rate_limit_buckets.window_start < :window_start THEN :window_start ELSE rate_limit_buckets.window_start END
            RETURNING hit_count
        """), {"bucket_key": bucket_key[:240], "window_start": window}).scalar_one()
        return int(count) <= int(limit)
    def search(self, query_text: str, *, limit: int = 20) -> list[dict[str, Any]]:
        term = f"%{query_text.strip()}%"
        farms = self.session.execute(select(Farm).where(Farm.org_id == _uuid(self.org_id), Farm.name.ilike(term)).limit(limit)).scalars().all()
        plans = self.session.execute(select(PlantingPlan, Crop).join(Crop, Crop.id == PlantingPlan.crop_id).where(PlantingPlan.org_id == _uuid(self.org_id), Crop.name.ilike(term)).limit(limit)).all()
        return ([{"kind": "farm", "id": str(r.id), "label": r.name} for r in farms] + [{"kind": "plan", "id": str(p.id), "label": c.name, "status": str(p.status)} for p, c in plans])[:limit]
    def calculation_context(self, plan_id: str) -> dict[str, Any] | None:
        row = self.get_plan_row(plan_id)
        if row is None:
            return None
        plan, crop, revision = row
        farm = self.session.get(Farm, plan.farm_id)
        yields = self.session.execute(select(YieldReference).where(YieldReference.org_id == _uuid(self.org_id), YieldReference.crop_id == crop.id, YieldReference.status == "reviewed_verified").order_by(desc(YieldReference.version))).scalars().all()
        comparisons = self.session.execute(select(ComparisonReference).where(ComparisonReference.org_id == _uuid(self.org_id), ComparisonReference.crop_id == crop.id, ComparisonReference.status == "reviewed_verified").order_by(desc(ComparisonReference.version))).scalars().all()
        return {"plan": self.plan_dict(plan, crop, revision), "farm": self.farm_dict(farm) if farm else None, "yield_references": [{"id": str(r.id), "version": r.version, "yield_mt_per_ha": _num(r.yield_mt_per_ha), "geography": r.geography, "period": r.period, "source": _str(r.data_source_version_id)} for r in yields], "comparison_references": [{"id": str(r.id), "version": r.version, "amount_mt": _num(r.amount_mt), "unit": r.unit, "reference_type": str(r.reference_type), "geography": r.geography, "period": r.period, "source": r.source, "evidence_note": r.evidence_note} for r in comparisons]}

    @staticmethod
    def reference_dict(row: ComparisonReference, crop: Crop | None = None) -> dict[str, Any]:
        return {"id": str(row.id), "organization_id": str(row.org_id), "crop_code": crop.code if crop else None, "amount_mt": _num(row.amount_mt), "unit": row.unit, "reference_type": str(row.reference_type), "geography": row.geography, "period": row.period, "source": row.source, "evidence_note": row.evidence_note, "verification_status": str(row.status), "version": row.version, "effective_from": _iso(row.effective_from), "effective_to": _iso(row.effective_to), "supersedes_id": _str(row.supersedes_id), "review": "verified" if str(row.status) == "reviewed_verified" else "draft"}

    def references(self, *, crop_code: str | None = None) -> list[dict[str, Any]]:
        query = select(ComparisonReference, Crop).join(Crop, Crop.id == ComparisonReference.crop_id).where(ComparisonReference.org_id == _uuid(self.org_id)).order_by(desc(ComparisonReference.version))
        if crop_code:
            query = query.where(Crop.code == crop_code)
        return [self.reference_dict(row, crop) for row, crop in self.session.execute(query).all()]

    def create_reference(self, values: dict[str, Any]) -> dict[str, Any]:
        crop = self.crop(values["crop_code"])
        if crop is None:
            raise KeyError("crop")
        latest = int(self.session.execute(select(func.max(ComparisonReference.version)).where(ComparisonReference.org_id == _uuid(self.org_id), ComparisonReference.crop_id == crop.id, ComparisonReference.geography == values["geography"], ComparisonReference.period == values["period"])).scalar() or 0) + 1
        row = ComparisonReference(org_id=_uuid(self.org_id), crop_id=crop.id, reference_type=values["reference_type"], amount_mt=values["amount_mt"], unit=values.get("unit", "MT"), geography=values["geography"], period=values["period"], source=values["source"], evidence_note=values.get("evidence_note"), effective_from=values.get("effective_from") or datetime.now(UTC).date(), effective_to=values.get("effective_to"), version=latest)
        self.session.add(row)
        self.session.flush()
        return self.reference_dict(row, crop)

    def transition_reference(self, reference_id: str, target: str, note: str | None = None) -> dict[str, Any]:
        row = self.session.get(ComparisonReference, _uuid(reference_id))
        if row is None or str(row.org_id) != str(self.org_id):
            raise KeyError("reference")
        current = str(row.status)
        allowed = {"user_provided_unverified": {"verified", "rejected"}, "reviewed_verified": {"superseded", "expired"}, "superseded": set(), "stale": set()}
        if target not in allowed.get(current, set()):
            raise ValueError("invalid_reference_transition")
        row.status = "reviewed_verified" if target == "verified" else ("superseded" if target == "superseded" else ("stale" if target == "expired" else "user_provided_unverified"))
        self.session.add(ReferenceReview(org_id=_uuid(self.org_id), comparison_reference_id=row.id, reviewer_id=self._uid(), from_status="draft" if current != "reviewed_verified" else "verified", to_status="verified" if target == "verified" else target, note=note))
        self.session.flush()
        return self.reference_dict(row, self.session.get(Crop, row.crop_id))

    def consent_records(self) -> list[dict[str, Any]]:
        rows = self.session.execute(select(ConsentRecord).where(ConsentRecord.org_id == _uuid(self.org_id), ConsentRecord.user_id == self._uid()).order_by(desc(ConsentRecord.consented_at))).scalars().all()
        return [{"id": str(r.id), "consent_type": str(r.consent_type), "purpose": r.purpose, "policy_version": r.policy_version, "version": r.version, "consented_at": _iso(r.consented_at), "withdrawn_at": _iso(r.withdrawn_at)} for r in rows]

    def grant_consent(self, values: dict[str, Any]) -> dict[str, Any]:
        latest = int(self.session.execute(select(func.max(ConsentRecord.version)).where(ConsentRecord.org_id == _uuid(self.org_id), ConsentRecord.user_id == self._uid(), ConsentRecord.consent_type == values["consent_type"])).scalar() or 0) + 1
        row = ConsentRecord(org_id=_uuid(self.org_id), user_id=self._uid(), consent_type=values["consent_type"], purpose=values["purpose"], policy_version=values["policy_version"], version=latest)
        self.session.add(row)
        self.session.flush()
        return {"id": str(row.id), "consent_type": str(row.consent_type), "purpose": row.purpose, "policy_version": row.policy_version, "version": row.version, "consented_at": _iso(row.consented_at), "withdrawn_at": None}

    def withdraw_consent(self, consent_type: str) -> dict[str, Any]:
        row = self.session.execute(select(ConsentRecord).where(ConsentRecord.org_id == _uuid(self.org_id), ConsentRecord.user_id == self._uid(), ConsentRecord.consent_type == consent_type, ConsentRecord.withdrawn_at.is_(None)).order_by(desc(ConsentRecord.version))).scalars().first()
        if row is None:
            raise KeyError("consent")
        row.withdrawn_at = datetime.now(UTC)
        self.session.flush()
        return {"id": str(row.id), "consent_type": str(row.consent_type), "withdrawn_at": _iso(row.withdrawn_at)}

    def cancel_plan(self, plan_id: str) -> dict[str, Any]:
        row = self.get_plan_row(plan_id)
        if row is None:
            raise KeyError("plan")
        plan, crop, revision = row
        plan.status = "cancelled"
        plan.updated_at = datetime.now(UTC)
        self.session.flush()
        return self.plan_dict(plan, crop, revision)
    def crop_yield(self, crop_code: str, geography: str | None = None) -> list[dict[str, Any]]:
        crop = self.crop(crop_code)
        if crop is None: return []
        query = select(YieldReference).where(YieldReference.crop_id == crop.id, YieldReference.org_id == _uuid(self.org_id)).order_by(desc(YieldReference.version))
        if geography: query = query.where(YieldReference.geography == geography)
        return [{"id": str(r.id), "crop_code": crop.code, "geography": r.geography, "period": r.period, "yield_mt_per_ha": _num(r.yield_mt_per_ha), "version": r.version, "status": str(r.status), "data_source_version_id": _str(r.data_source_version_id)} for r in self.session.execute(query).scalars().all()]