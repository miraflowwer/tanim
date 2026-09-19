"""Database-backed FastAPI application for Member 3.

Production routes never import the legacy global store. Every authenticated
operation resolves a durable provider identity, establishes transaction-local
tenant context, and writes through the PostgreSQL repository.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Any, Callable, Iterator

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .db import check_readiness, runtime_mode, session_factory
from .ingestion import STAGES, lifecycle_status, platform_can_promote, safe_retry_allowed, validate_rows
from .ops import bump, metrics_snapshot, metrics_text, monotonic_ms, record_request, safe_log
from .production_auth import ProductionUser, get_current_user
from .repositories.base import RepositoryIdentity
from .repositories.postgres import PostgresRepository

try:
    from scripts import grci
except ImportError:
    grci = None

app = FastAPI(title="TANIM durable API", version="0.3.0", docs_url="/docs", redoc_url="/redoc")

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class FarmPayload(StrictModel):
    organization_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    total_area_ha: float | None = Field(default=None, gt=0, le=100000)
    municipality: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)

class PlanPayload(StrictModel):
    crop_code: str = Field(min_length=1, max_length=64)
    organization_id: str = Field(min_length=1, max_length=64)
    farm_id: str = Field(min_length=1, max_length=64)
    area_ha: float = Field(gt=0, le=10000)
    area_margin_ha: float = Field(default=0, ge=0, le=10000)
    planting_date: date
    harvest_period: date
    status: str = Field(default="draft", pattern="^(draft|planned|harvested|cancelled)$")

class RevisionPayload(StrictModel):
    area_ha: float | None = Field(default=None, gt=0, le=10000)
    area_margin_ha: float | None = Field(default=None, ge=0, le=10000)
    planting_date: date | None = None
    harvest_period: date | None = None
    status: str | None = Field(default=None, pattern="^(draft|planned|harvested|cancelled)$")

class OrganizationPayload(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    default_geography: str | None = Field(default=None, max_length=128)

class RolePayload(StrictModel):
    role: str = Field(pattern="^(farmer|coordinator|reviewer|org_admin)$")

class InvitationPayload(StrictModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(pattern="^(farmer|coordinator|reviewer|org_admin)$")
    expires_in_days: int = Field(default=7, ge=1, le=30)

class SettingPayload(StrictModel):
    key: str = Field(min_length=1, max_length=80)
    value: dict[str, Any]

class ExportPayload(StrictModel):
    organization_id: str = Field(min_length=1, max_length=64)
    purpose: str = Field(min_length=1, max_length=512)
    include_individuals: bool = False

class PolicyPayload(StrictModel):
    elevated_load: float = Field(gt=0, le=100)
    high_load: float = Field(gt=0, le=100)

class ReferencePayload(StrictModel):
    organization_id: str = Field(min_length=1, max_length=64)
    crop_code: str = Field(min_length=1, max_length=64)
    amount_mt: float = Field(gt=0, le=1e9)
    unit: str = Field(default="MT", pattern="^MT$")
    reference_type: str
    geography: str = Field(min_length=1, max_length=128)
    period: str = Field(min_length=1, max_length=64)
    source: str = Field(min_length=1, max_length=256)
    evidence_note: str | None = Field(default=None, max_length=2000)
    effective_from: date | None = None
    effective_to: date | None = None

class ReviewPayload(StrictModel):
    note: str | None = Field(default=None, max_length=2000)

class ConsentPayload(StrictModel):
    consent_type: str = Field(pattern="^(operational|research)$")
    purpose: str = Field(min_length=1, max_length=512)
    policy_version: str = Field(min_length=1, max_length=64)

class WithdrawPayload(StrictModel):
    consent_type: str = Field(pattern="^(operational|research)$")

class IngestionPayload(StrictModel):
    source_key: str = Field(min_length=1, max_length=100)
    name: str = Field(default="TANIM source", min_length=1, max_length=160)
    kind: str = Field(default="managed", min_length=1, max_length=80)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=160)
    rows: list[dict[str, Any]] = Field(min_length=1, max_length=100000)
    promote: bool = False

def api_error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message, **extra})

def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid.uuid4()))

def organization_for(user: ProductionUser, requested: str | None) -> str:
    if requested:
        if user.role_in(requested) is None:
            raise api_error(403, "permission_denied", "You do not have access to this organization.")
        return requested
    if len(user.org_roles) == 1:
        return next(iter(user.org_roles))
    raise api_error(400, "organization_required", "Choose an organization for this request.")

def require_role(user: ProductionUser, org_id: str, roles: set[str]) -> str:
    role = user.role_in(org_id)
    if role is None or (role not in roles and not user.is_platform):
        raise api_error(403, "permission_denied", "You do not have access to this.")
    return role

def identity(user: ProductionUser) -> RepositoryIdentity:
    return RepositoryIdentity(user.user_id, user.email, user.org_roles, user.is_platform)

@contextmanager
def tenant_repo(user: ProductionUser, org_id: str) -> Iterator[PostgresRepository]:
    role = user.role_in(org_id)
    if role is None:
        raise api_error(403, "permission_denied", "You do not have access to this organization.")
    session = session_factory()()
    try:
        session.execute(text("SELECT set_config('app.current_org_id', :org_id, true), set_config('app.current_role', :role, true), set_config('app.current_user_id', :user_id, true)"), {"org_id": org_id, "role": role, "user_id": user.user_id})
        yield PostgresRepository(session, identity(user), org_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

@contextmanager
def platform_repo(user: ProductionUser, org_id: str | None = None) -> Iterator[PostgresRepository]:
    if not platform_can_promote(user.is_platform):
        raise api_error(403, "permission_denied", "Platform authority is required.")
    context_org = org_id or (next(iter(user.org_roles), "") if user.org_roles else "")
    session = session_factory()()
    try:
        session.execute(text("SELECT set_config('app.current_org_id', :org_id, true), set_config('app.current_role', 'platform_admin', true), set_config('app.current_user_id', :user_id, true)"), {"org_id": context_org, "user_id": user.user_id})
        yield PostgresRepository(session, identity(user), org_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def run_db(fn: Callable[[PostgresRepository], Any], *, user: ProductionUser, org_id: str) -> Any:
    try:
        with tenant_repo(user, org_id) as repo:
            return fn(repo)
    except HTTPException:
        raise
    except KeyError as exc:
        raise api_error(404, "not_found", f"The requested {exc.args[0]} was not found.") from exc
    except ValueError as exc:
        code = str(exc).strip() or "domain_validation_failed"
        status = 409 if code in {"duplicate_source_version", "source_version_not_valid", "ingestion_retry_not_safe", "invalid_reference_transition"} else 422
        raise api_error(status, code, "The request could not be applied.") from exc
    except IntegrityError as exc:
        raise api_error(409, "conflict", "The request conflicts with an existing durable record.") from exc
    except (SQLAlchemyError, RuntimeError, OSError) as exc:
        safe_log("database_error", error=type(exc).__name__)
        raise api_error(503, "database_unavailable", "The durable backend is temporarily unavailable.") from exc

def run_platform(fn: Callable[[PostgresRepository], Any], *, user: ProductionUser, org_id: str | None = None) -> Any:
    try:
        with platform_repo(user, org_id) as repo:
            return fn(repo)
    except HTTPException:
        raise
    except KeyError as exc:
        raise api_error(404, "not_found", f"The requested {exc.args[0]} was not found.") from exc
    except ValueError as exc:
        code = str(exc).strip() or "domain_validation_failed"
        status = 409 if code in {"duplicate_source_version", "source_version_not_valid", "ingestion_retry_not_safe", "invalid_reference_transition"} else 422
        raise api_error(status, code, "The request could not be applied.") from exc
    except IntegrityError as exc:
        raise api_error(409, "conflict", "The request conflicts with an existing durable record.") from exc
    except (SQLAlchemyError, RuntimeError, OSError) as exc:
        safe_log("database_error", error=type(exc).__name__)
        raise api_error(503, "database_unavailable", "The durable backend is temporarily unavailable.") from exc

def enforce_rate_limit(request: Request, user: ProductionUser, name: str) -> None:
    limit = int(os.environ.get("TANIM_RATE_LIMIT_PER_MINUTE", "60"))
    host = request.client.host if request.client else "unknown"
    key = f"{name}:{host}:{user.user_id}"
    try:
        session = session_factory()()
        try:
            session.execute(text("SELECT set_config('app.current_user_id', :user_id, true), set_config('app.current_role', :role, true)"), {"user_id": user.user_id, "role": "platform_admin" if user.is_platform else "farmer"})
            allowed = PostgresRepository(session, identity(user)).consume_rate_limit(key, limit)
            session.commit()
        finally:
            session.close()
    except (SQLAlchemyError, RuntimeError, OSError) as exc:
        raise api_error(503, "rate_limit_backend_unavailable", "Request protection is temporarily unavailable.") from exc
    if not allowed:
        bump("rate_limited")
        raise api_error(429, "rate_limited", "Too many requests. Please try again later.", retry_after_seconds=60)

def revision_values(plan: dict[str, Any], patch: RevisionPayload) -> dict[str, Any]:
    current = plan.get("current_revision") or {}
    values = {"area_ha": patch.area_ha if patch.area_ha is not None else current.get("area_ha"), "area_margin_ha": patch.area_margin_ha if patch.area_margin_ha is not None else current.get("area_margin_ha", 0), "planting_date": patch.planting_date if patch.planting_date is not None else date.fromisoformat(current["planting_date"]), "harvest_period": patch.harvest_period if patch.harvest_period is not None else date.fromisoformat(current["harvest_period"]), "status": patch.status}
    if values["harvest_period"] < values["planting_date"]:
        raise api_error(422, "invalid_date_range", "harvest_period must not precede planting_date.")
    return values

def compute_calculation(repo: PostgresRepository, plan_id: str, req_id: str) -> dict[str, Any]:
    if grci is None:
        raise api_error(503, "calculation_backend_missing", "The trusted calculation engine is unavailable.")
    context = repo.calculation_context(plan_id)
    if context is None:
        raise api_error(404, "not_found", "The requested plan was not found.")
    plan = context["plan"]
    revision = plan["current_revision"]
    farm = context.get("farm") or {}
    location = farm.get("municipality") or "organization"
    yield_ref = context["yield_references"][0] if context["yield_references"] else None
    comparison = context["comparison_references"][0] if context["comparison_references"] else None
    policies = repo.policies()
    policy = policies[0] if policies else {"version": 0, "thresholds": {"elevated_load": 1.0, "high_load": 1.5}}
    thresholds = policy["thresholds"]
    bands = [(float(thresholds["elevated_load"]), "low"), (float(thresholds["high_load"]), "medium"), (float("inf"), "high")]
    try:
        result = grci.compute_grci(crop=plan["crop_code"], location=location, harvest_period=revision["harvest_period"], plans=[{"farm_size_ha": revision["area_ha"], "farm_size_margin_ha": revision["area_margin_ha"], "municipality": location, "crop": plan["crop_code"], "harvest_period": revision["harvest_period"]}], reference_yield=yield_ref["yield_mt_per_ha"] if yield_ref else None, yield_source=f"yield_reference:{yield_ref['id']}:v{yield_ref['version']}" if yield_ref else None, reference_amount=comparison["amount_mt"] if comparison else None, reference_unit=comparison["unit"] if comparison else "MT", reference_type=comparison["reference_type"] if comparison else None, reference_geography=comparison["geography"] if comparison else None, reference_period=comparison["period"] if comparison else None, crop_record={"crop_id": plan["crop_code"], "planning_supported": True, "coverage": {"production": True, "area": True}}, bands=bands, source_labels=[comparison["source"]] if comparison else [], yield_record={"crop_id": plan["crop_code"], "avg_yield_mt_per_ha": yield_ref["yield_mt_per_ha"]} if yield_ref else None)
    except (KeyError, TypeError, ValueError) as exc:
        result = {"status": "failed", "error_code": "calculation_invalid", "message": "The calculation inputs could not be evaluated."}
        safe_log("calculation_error", request_id=req_id, error=type(exc).__name__)
    supply = result.get("planned_supply_range") or []
    load = (result.get("supply_load_range") or [None])[-1]
    state = str(result.get("status", "failed"))
    stored_status = "complete" if state in {"ok", "baseline", "context_only"} else ("incomplete" if state in {"incomplete", "unclassified"} else "failed")
    calc = repo.create_calculation({"plan_id": plan_id, "plan_revision_id": revision["id"], "engine_version": getattr(grci, "ENGINE_VERSION", "unknown"), "policy_id": policy.get("id"), "policy_version": policy.get("version", 0), "registry_version": 1, "yield_reference_id": yield_ref.get("id") if yield_ref else None, "yield_reference_version": yield_ref.get("version") if yield_ref else None, "comparison_reference_id": comparison.get("id") if comparison else None, "comparison_reference_version": comparison.get("version") if comparison else None, "s_mt": supply[0] if supply else None, "s_low_mt": supply[0] if supply else None, "s_high_mt": supply[-1] if supply else None, "supply_load": load, "status": stored_status, "request_id": req_id, "duration_ms": None, "result_json": result})
    result["calculation_id"] = calc["calculation_id"]
    return {**calc, "result": result}

def aggregate(plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for plan in plans:
        revision = plan.get("current_revision") or {}
        key = (plan["crop_code"], str(revision.get("harvest_period", "")))
        bucket = buckets.setdefault(key, {"crop_code": key[0], "period": key[1], "planned_area_ha": 0.0, "plan_count": 0, "state": "unavailable", "reason": "missing_verified_reference"})
        bucket["planned_area_ha"] += float(revision.get("area_ha") or 0)
        bucket["plan_count"] += 1
    return list(buckets.values())

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    incoming = request.headers.get("x-request-id", "")
    request_id_value = incoming[:128] if incoming and all(ch.isalnum() or ch in "-_" for ch in incoming[:128]) else str(uuid.uuid4())
    request.state.request_id = request_id_value
    started = time.perf_counter()
    try:
        too_large = int(request.headers.get("content-length", "0")) > int(os.environ.get("TANIM_MAX_BODY_BYTES", "1048576"))
    except ValueError:
        too_large = True
    if too_large:
        response = JSONResponse({"code": "request_too_large", "message": "Request body is too large.", "request_id": request_id_value}, status_code=413)
    else:
        response = await call_next(request)
    response.headers["X-Request-ID"] = request_id_value
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.url.scheme == "https" or os.environ.get("TANIM_FORCE_HSTS") == "true":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    record_request(request_id=request_id_value, method=request.method, route=request.url.path, status=response.status_code, duration_ms=monotonic_ms(started), user_id=getattr(request.state, "user_id", None))
    return response

@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "request_failed", "message": str(exc.detail)}
    body = dict(detail)
    body.setdefault("code", "request_failed")
    body.setdefault("message", "The request could not be completed.")
    body["request_id"] = request_id(request)
    return JSONResponse(body, status_code=exc.status_code, headers=exc.headers)

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse({"code": "validation_error", "message": "The request fields are invalid.", "errors": [{"loc": list(item.get("loc", ())), "type": item.get("type")} for item in exc.errors()], "request_id": request_id(request)}, status_code=422)

@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    safe_log("unhandled_error", request_id=request_id(request), error=type(exc).__name__)
    return JSONResponse({"code": "internal_error", "message": "Something went wrong. Try again later.", "request_id": request_id(request)}, status_code=500)

@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "tanim-api", "runtime_mode": runtime_mode()}

@app.get("/api/v1/readiness")
def readiness():
    ready, details = check_readiness()
    if not ready:
        return JSONResponse({"code": "dependency_unavailable", "message": "TANIM is not ready to serve durable requests.", **details}, status_code=503)
    return {"status": "ready", **details}

@app.get("/api/v1/metrics", response_class=PlainTextResponse)
def metrics():
    return metrics_text()

@app.get("/api/v1/me")
def me(user: ProductionUser = Depends(get_current_user)):
    return {"id": user.user_id, "user_id": user.user_id, "email": user.email, "organizations": user.org_roles, "is_platform": user.is_platform, "auth_provider": "supabase"}

@app.post("/api/v1/auth/session", status_code=405)
def auth_session():
    raise api_error(405, "external_auth_only", "Supabase Auth owns sign-in, refresh, and recovery sessions.")

@app.get("/api/v1/organizations/{org_id}")
def get_organization(org_id: str, user: ProductionUser = Depends(get_current_user)):
    def action(repo: PostgresRepository):
        value = repo.organization()
        if value is None:
            raise KeyError("organization")
        return value
    return run_db(action, user=user, org_id=org_id)

@app.patch("/api/v1/organizations/{org_id}")
def patch_organization(org_id: str, payload: OrganizationPayload, user: ProductionUser = Depends(get_current_user)):
    require_role(user, org_id, {"org_admin"})
    return run_db(lambda repo: (repo.update_organization(payload.model_dump(exclude_none=True)), repo.audit(action="organization.updated", target_kind="organization", target_id=org_id))[0], user=user, org_id=org_id)

@app.get("/api/v1/organizations/{org_id}/members")
def list_members(org_id: str, user: ProductionUser = Depends(get_current_user), limit: int = Query(50, ge=1, le=200), cursor: str | None = None):
    require_role(user, org_id, {"farmer", "coordinator", "reviewer", "org_admin"})
    return run_db(lambda repo: repo.page(repo.members(), limit=limit, cursor=cursor).as_dict(), user=user, org_id=org_id)

@app.patch("/api/v1/organizations/{org_id}/members/{member_id}")
def patch_member(org_id: str, member_id: str, payload: RolePayload, user: ProductionUser = Depends(get_current_user)):
    require_role(user, org_id, {"org_admin"})
    return run_db(lambda repo: (repo.change_role(member_id, payload.role), repo.audit(action="role.changed", target_kind="membership", target_id=member_id, metadata={"role": payload.role}))[0], user=user, org_id=org_id)

@app.delete("/api/v1/organizations/{org_id}/members/{member_id}", status_code=204)
def delete_member(org_id: str, member_id: str, user: ProductionUser = Depends(get_current_user)):
    require_role(user, org_id, {"org_admin"})
    def action(repo: PostgresRepository):
        repo.remove_member(member_id)
        repo.audit(action="member.removed", target_kind="membership", target_id=member_id)
    run_db(action, user=user, org_id=org_id)
    return Response(status_code=204)

@app.get("/api/v1/organizations/{org_id}/settings")
def get_settings(org_id: str, user: ProductionUser = Depends(get_current_user)):
    require_role(user, org_id, {"farmer", "coordinator", "reviewer", "org_admin"})
    return {"organization_id": org_id, "settings": run_db(lambda repo: repo.settings(), user=user, org_id=org_id)}

@app.patch("/api/v1/organizations/{org_id}/settings")
def patch_settings(org_id: str, payload: SettingPayload, user: ProductionUser = Depends(get_current_user)):
    require_role(user, org_id, {"org_admin"})
    return run_db(lambda repo: (repo.put_setting(payload.key, payload.value), repo.audit(action="setting.changed", target_kind="organization_setting", metadata={"key": payload.key}))[0], user=user, org_id=org_id)

@app.get("/api/v1/organizations/{org_id}/invitations")
def list_invitations(org_id: str, status: str | None = None, user: ProductionUser = Depends(get_current_user), limit: int = Query(50, ge=1, le=200), cursor: str | None = None):
    require_role(user, org_id, {"coordinator", "org_admin"})
    return run_db(lambda repo: repo.page(repo.invitations(status), limit=limit, cursor=cursor).as_dict(), user=user, org_id=org_id)

@app.post("/api/v1/organizations/{org_id}/invitations", status_code=201)
def create_invitation(org_id: str, payload: InvitationPayload, request: Request, user: ProductionUser = Depends(get_current_user)):
    require_role(user, org_id, {"org_admin"})
    enforce_rate_limit(request, user, "invitation")
    token_hash = hashlib.sha256(secrets.token_urlsafe(32).encode("utf-8")).hexdigest()
    result = run_db(lambda repo: (repo.create_invitation(email=payload.email, role=payload.role, token_hash=token_hash, expires_at=datetime.now(UTC) + timedelta(days=payload.expires_in_days)), repo.audit(action="invitation.created", target_kind="invitation"))[0], user=user, org_id=org_id)
    return {**result, "delivery": "external_provider_pending", "token_issued": False}

@app.get("/api/v1/farms")
def list_farms(organization_id: str | None = None, user: ProductionUser = Depends(get_current_user), limit: int = Query(50, ge=1, le=200), cursor: str | None = None):
    org_id = organization_for(user, organization_id)
    return run_db(lambda repo: repo.page(repo.list_farms(), limit=limit, cursor=cursor).as_dict(), user=user, org_id=org_id)

@app.post("/api/v1/farms", status_code=201)
def create_farm(payload: FarmPayload, user: ProductionUser = Depends(get_current_user)):
    require_role(user, payload.organization_id, {"farmer", "coordinator", "org_admin"})
    return run_db(lambda repo: repo.create_farm(payload.model_dump(exclude={"organization_id"})), user=user, org_id=payload.organization_id)

@app.get("/api/v1/farms/{farm_id}")
def get_farm(farm_id: str, organization_id: str | None = None, user: ProductionUser = Depends(get_current_user)):
    org_id = organization_for(user, organization_id)
    row = run_db(lambda repo: repo.get_farm(farm_id), user=user, org_id=org_id)
    if row is None:
        raise api_error(404, "not_found", "The farm was not found.")
    return PostgresRepository.farm_dict(row)

@app.patch("/api/v1/farms/{farm_id}")
def patch_farm(farm_id: str, payload: FarmPayload, user: ProductionUser = Depends(get_current_user)):
    require_role(user, payload.organization_id, {"farmer", "coordinator", "org_admin"})
    return run_db(lambda repo: repo.update_farm(farm_id, payload.model_dump(exclude={"organization_id"}, exclude_none=True)), user=user, org_id=payload.organization_id)

@app.delete("/api/v1/farms/{farm_id}", status_code=204)
def delete_farm(farm_id: str, organization_id: str, user: ProductionUser = Depends(get_current_user)):
    require_role(user, organization_id, {"farmer", "coordinator", "org_admin"})
    run_db(lambda repo: repo.delete_farm(farm_id), user=user, org_id=organization_id)
    return Response(status_code=204)

@app.get("/api/v1/crops")
def crops(organization_id: str | None = None, user: ProductionUser = Depends(get_current_user)):
    org_id = organization_for(user, organization_id)
    return {"items": run_db(lambda repo: repo.list_crops(), user=user, org_id=org_id)}

@app.get("/api/v1/crops/{code}/yield")
def crop_yield(code: str, organization_id: str | None = None, geography: str | None = None, user: ProductionUser = Depends(get_current_user)):
    org_id = organization_for(user, organization_id)
    return {"items": run_db(lambda repo: repo.crop_yield(code, geography), user=user, org_id=org_id)}

@app.post("/api/v1/plans", status_code=201)
def create_plan(payload: PlanPayload, user: ProductionUser = Depends(get_current_user)):
    require_role(user, payload.organization_id, {"farmer", "coordinator", "org_admin"})
    return run_db(lambda repo: repo.create_plan(payload.model_dump()), user=user, org_id=payload.organization_id)

@app.get("/api/v1/plans")
def list_plans(organization_id: str | None = None, status: str | None = None, crop_code: str | None = None, user: ProductionUser = Depends(get_current_user), limit: int = Query(50, ge=1, le=200), cursor: str | None = None):
    org_id = organization_for(user, organization_id)
    return run_db(lambda repo: repo.page(repo.list_plans(status, crop_code), limit=limit, cursor=cursor).as_dict(), user=user, org_id=org_id)

@app.get("/api/v1/plans/{plan_id}")
def get_plan(plan_id: str, organization_id: str | None = None, user: ProductionUser = Depends(get_current_user)):
    org_id = organization_for(user, organization_id)
    row = run_db(lambda repo: repo.get_plan(plan_id), user=user, org_id=org_id)
    if row is None:
        raise api_error(404, "not_found", "The plan was not found.")
    return row

@app.patch("/api/v1/plans/{plan_id}")
def patch_plan(plan_id: str, payload: RevisionPayload, organization_id: str, user: ProductionUser = Depends(get_current_user)):
    require_role(user, organization_id, {"farmer", "coordinator", "org_admin"})
    def action(repo: PostgresRepository):
        plan = repo.get_plan(plan_id)
        if plan is None:
            raise KeyError("plan")
        return repo.append_revision(plan_id, revision_values(plan, payload))
    return run_db(action, user=user, org_id=organization_id)

@app.delete("/api/v1/plans/{plan_id}")
def cancel_plan(plan_id: str, organization_id: str, user: ProductionUser = Depends(get_current_user)):
    require_role(user, organization_id, {"farmer", "coordinator", "org_admin"})
    return run_db(lambda repo: repo.cancel_plan(plan_id), user=user, org_id=organization_id)

@app.get("/api/v1/plans/{plan_id}/revisions")
def plan_revisions(plan_id: str, organization_id: str | None = None, user: ProductionUser = Depends(get_current_user), limit: int = Query(50, ge=1, le=200), cursor: str | None = None):
    org_id = organization_for(user, organization_id)
    return run_db(lambda repo: repo.page(repo.revisions(plan_id), limit=limit, cursor=cursor).as_dict(), user=user, org_id=org_id)

@app.post("/api/v1/plans/{plan_id}/calculate", status_code=201)
def calculate_plan(plan_id: str, request: Request, organization_id: str | None = None, user: ProductionUser = Depends(get_current_user)):
    org_id = organization_for(user, organization_id)
    started = time.perf_counter()
    result = run_db(lambda repo: compute_calculation(repo, plan_id, request_id(request)), user=user, org_id=org_id)
    result["duration_ms"] = round(monotonic_ms(started), 2)
    bump("calculations_complete" if result["status"] == "complete" else "calculations_incomplete")
    return result

@app.get("/api/v1/plans/{plan_id}/calculations")
def plan_calculation_history(plan_id: str, organization_id: str | None = None, user: ProductionUser = Depends(get_current_user), limit: int = Query(50, ge=1, le=200), cursor: str | None = None):
    org_id = organization_for(user, organization_id)
    return run_db(lambda repo: repo.page(repo.calculations_for_plan(plan_id), limit=limit, cursor=cursor).as_dict(), user=user, org_id=org_id)

@app.get("/api/v1/calculations/{calculation_id}")
def get_calculation(calculation_id: str, organization_id: str | None = None, user: ProductionUser = Depends(get_current_user)):
    org_id = organization_for(user, organization_id)
    result = run_db(lambda repo: repo.get_calculation(calculation_id), user=user, org_id=org_id)
    if result is None:
        raise api_error(404, "not_found", "The calculation was not found.")
    return result

@app.get("/api/v1/organizations/{org_id}/aggregates")
def aggregates(org_id: str, user: ProductionUser = Depends(get_current_user)):
    require_role(user, org_id, {"farmer", "coordinator", "reviewer", "org_admin"})
    items = run_db(lambda repo: aggregate(repo.list_plans()), user=user, org_id=org_id)
    return {"organization_id": org_id, "items": items, "status": "available" if items else "unavailable"}

@app.get("/api/v1/organizations/{org_id}/geo-aggregates")
def geo_aggregates(org_id: str, user: ProductionUser = Depends(get_current_user)):
    require_role(user, org_id, {"coordinator", "reviewer", "org_admin"})
    return {"organization_id": org_id, "items": run_db(lambda repo: aggregate(repo.list_plans()), user=user, org_id=org_id), "privacy": {"exact_coordinates": False, "minimum_group_size": int(os.environ.get("TANIM_MAP_MIN_GROUP_SIZE", "5"))}}

@app.get("/api/v1/organizations/{org_id}/timeline")
def timeline(org_id: str, user: ProductionUser = Depends(get_current_user)):
    require_role(user, org_id, {"coordinator", "reviewer", "org_admin"})
    plans = run_db(lambda repo: repo.list_plans(), user=user, org_id=org_id)
    return {"organization_id": org_id, "items": [{"plan_id": p["id"], "crop_code": p["crop_code"], "period": (p.get("current_revision") or {}).get("harvest_period"), "status": p["status"]} for p in plans]}

@app.get("/api/v1/organizations/{org_id}/attention-items")
def attention_items(org_id: str, user: ProductionUser = Depends(get_current_user)):
    require_role(user, org_id, {"coordinator", "reviewer", "org_admin"})
    plans = run_db(lambda repo: repo.list_plans(), user=user, org_id=org_id)
    return {"organization_id": org_id, "items": [{"kind": "calculation_required", "plan_id": p["id"], "severity": "info"} for p in plans if p["status"] in {"draft", "planned"}]}

@app.get("/api/v1/organizations/{org_id}/map-data")
def map_data(org_id: str, user: ProductionUser = Depends(get_current_user)):
    require_role(user, org_id, {"coordinator", "reviewer", "org_admin"})
    return {"organization_id": org_id, "available": False, "reason": "privacy_safe_coordinates_not_configured", "features": [], "privacy": {"exact_coordinates": False}}

@app.get("/api/v1/references")
def references(organization_id: str | None = None, crop_code: str | None = None, user: ProductionUser = Depends(get_current_user), limit: int = Query(50, ge=1, le=200), cursor: str | None = None):
    org_id = organization_for(user, organization_id)
    return run_db(lambda repo: repo.page(repo.references(crop_code=crop_code), limit=limit, cursor=cursor).as_dict(), user=user, org_id=org_id)

@app.get("/api/v1/references/{reference_id}")
def get_reference(reference_id: str, organization_id: str, user: ProductionUser = Depends(get_current_user)):
    rows = run_db(lambda repo: repo.references(), user=user, org_id=organization_id)
    value = next((row for row in rows if row["id"] == reference_id), None)
    if value is None:
        raise api_error(404, "not_found", "The reference was not found.")
    return value

@app.post("/api/v1/references", status_code=201)
def create_reference(payload: ReferencePayload, user: ProductionUser = Depends(get_current_user)):
    require_role(user, payload.organization_id, {"coordinator", "reviewer", "org_admin"})
    return run_db(lambda repo: repo.create_reference(payload.model_dump()), user=user, org_id=payload.organization_id)

@app.post("/api/v1/references/{reference_id}/{transition}")
def transition_reference(reference_id: str, transition: str, payload: ReviewPayload, organization_id: str, user: ProductionUser = Depends(get_current_user)):
    require_role(user, organization_id, {"reviewer", "org_admin"})
    if transition not in {"verify", "reject", "supersede", "expire"}:
        raise api_error(404, "not_found", "The reference transition was not found.")
    target = {"verify": "verified", "reject": "rejected", "supersede": "superseded", "expire": "expired"}[transition]
    return run_db(lambda repo: repo.transition_reference(reference_id, target, payload.note), user=user, org_id=organization_id)

@app.get("/api/v1/policies")
def policies(organization_id: str | None = None, user: ProductionUser = Depends(get_current_user)):
    org_id = organization_for(user, organization_id)
    return {"items": run_db(lambda repo: repo.policies(), user=user, org_id=org_id)}

@app.get("/api/v1/policies/latest")
def latest_policy(organization_id: str | None = None, user: ProductionUser = Depends(get_current_user)):
    org_id = organization_for(user, organization_id)
    rows = run_db(lambda repo: repo.policies(), user=user, org_id=org_id)
    return rows[0] if rows else {"status": "unavailable", "reason": "no_policy_promoted"}

@app.post("/api/v1/policies", status_code=201)
def create_policy(payload: PolicyPayload, organization_id: str, user: ProductionUser = Depends(get_current_user)):
    require_role(user, organization_id, {"reviewer", "org_admin"})
    if payload.high_load <= payload.elevated_load:
        raise api_error(422, "invalid_policy", "high_load must exceed elevated_load.")
    return run_db(lambda repo: (repo.create_policy(payload.model_dump()), repo.audit(action="policy.changed", target_kind="calculation_policy"))[0], user=user, org_id=organization_id)

@app.get("/api/v1/data-sources")
def data_sources(organization_id: str | None = None, user: ProductionUser = Depends(get_current_user)):
    org_id = organization_for(user, organization_id)
    return {"items": run_db(lambda repo: repo.data_sources(), user=user, org_id=org_id)}

@app.get("/api/v1/platform/data-sources")
def platform_data_sources(user: ProductionUser = Depends(get_current_user)):
    return {"items": run_platform(lambda repo: repo.data_sources(), user=user)}

@app.get("/api/v1/data-sources/{key}")
def data_source_detail(key: str, organization_id: str | None = None, user: ProductionUser = Depends(get_current_user)):
    org_id = organization_for(user, organization_id)
    def action(repo: PostgresRepository):
        source = repo.data_source(key)
        if source is None:
            raise KeyError("data_source")
        return {"id": str(source.id), "key": source.key, "name": source.name, "kind": source.kind, "expected_refresh_interval": source.expected_refresh_interval, "versions": repo.source_versions(key)}
    return run_db(action, user=user, org_id=org_id)

@app.get("/api/v1/data-sources/{key}/versions")
def data_source_versions(key: str, organization_id: str | None = None, user: ProductionUser = Depends(get_current_user), limit: int = Query(50, ge=1, le=200), cursor: str | None = None):
    org_id = organization_for(user, organization_id)
    return run_db(lambda repo: repo.page(repo.source_versions(key), limit=limit, cursor=cursor).as_dict(), user=user, org_id=org_id)

@app.get("/api/v1/data-sources/{key}/freshness")
def data_source_freshness(key: str, organization_id: str | None = None, user: ProductionUser = Depends(get_current_user)):
    org_id = organization_for(user, organization_id)
    def action(repo: PostgresRepository):
        source = repo.data_source(key)
        if source is None:
            raise KeyError("data_source")
        versions = repo.source_versions(key)
        current = next((v for v in versions if v["is_current"]), None)
        return {"key": key, "status": "fresh" if current else "unavailable", "current_version": current, "reason": None if current else "no_promoted_version"}
    return run_db(action, user=user, org_id=org_id)

@app.post("/api/v1/platform/data-sources/{key}/versions/{version}/promote")
def promote_version(key: str, version: int, organization_id: str | None = None, user: ProductionUser = Depends(get_current_user)):
    return run_platform(lambda repo: (repo.promote_source_version(key=key, version=version), repo.audit(action="source.promoted", target_kind="data_source_version", global_event=True))[0], user=user, org_id=organization_id)

@app.post("/api/v1/data-sources/{key}/promote")
def promote_version_compat(key: str, version: int, organization_id: str | None = None, user: ProductionUser = Depends(get_current_user)):
    return promote_version(key, version, organization_id, user)

@app.post("/api/v1/platform/ingestion", status_code=201)
def run_ingestion(payload: IngestionPayload, request: Request, user: ProductionUser = Depends(get_current_user)):
    enforce_rate_limit(request, user, "ingestion")
    idem = payload.idempotency_key or f"{payload.source_key}:{request_id(request)}"
    def action(repo: PostgresRepository):
        source = repo.create_source_if_missing(key=payload.source_key, name=payload.name, kind=payload.kind)
        run = repo.create_ingestion_run(source=source, idempotency_key=idem)
        if run["status"] not in {"queued", "failed", "validation_failed"}:
            return {"run": run, "stages": STAGES, "replayed": True}
        crops = {item["code"] for item in repo.list_crops()}
        result = validate_rows(payload.rows, crop_codes=crops)
        repo.audit(action="ingestion.started", target_kind="ingestion_run", target_id=run["id"], global_event=True)
        repo.update_ingestion(run["id"], {"lifecycle_stage": "validate", "row_count": len(payload.rows), "validation_errors": result.errors, "validation_summary": result.summary, "status": lifecycle_status(result)})
        repo.audit(action="ingestion.validated", target_kind="ingestion_run", target_id=run["id"], metadata={"valid": result.valid}, global_event=True)
        if not result.valid:
            run_result = repo.update_ingestion(run["id"], {"lifecycle_stage": "monitor", "finished_at": datetime.now(UTC), "error_code": "ingestion_validation_failed"})
            return {"run": run_result, "stages": STAGES, "validation": result.summary, "errors": result.errors, "promoted": False}
        repo.update_ingestion(run["id"], {"lifecycle_stage": "normalize", "status": "validated"})
        repo.update_ingestion(run["id"], {"lifecycle_stage": "version"})
        version = repo.create_source_version(source=source, values={"checksum": result.checksum, "payload_ref": "sha256:" + result.checksum, "row_count": len(result.normalized_rows), "validation_status": "valid", "validation_errors": [], "normalization_version": "crop-aliases-v1"})
        repo.update_ingestion(run["id"], {"lifecycle_stage": "stage", "status": "staged", "source_version_id": version["id"], "finished_at": datetime.now(UTC)})
        promoted = False
        if payload.promote:
            repo.promote_source_version(key=payload.source_key, version=version["version"])
            repo.audit(action="ingestion.promoted", target_kind="data_source_version", global_event=True)
            promoted = True
        final_run = repo.update_ingestion(run["id"], {"lifecycle_stage": "monitor", "status": "promoted" if promoted else "staged"})
        return {"run": final_run, "version": version, "stages": STAGES, "validation": result.summary, "promoted": promoted}
    result = run_platform(action, user=user)
    if result.get("run", {}).get("error_code") == "ingestion_validation_failed":
        return JSONResponse({"code": "ingestion_validation_failed", "message": "The source payload was rejected and the promoted version was unchanged.", "request_id": request_id(request), "details": result}, status_code=422
    return result

@app.get("/api/v1/platform/ingestion")
def ingestion_runs(source_key: str | None = None, user: ProductionUser = Depends(get_current_user), limit: int = Query(50, ge=1, le=200), cursor: str | None = None):
    return run_platform(lambda repo: repo.page(repo.ingestion_runs(source_key), limit=limit, cursor=cursor).as_dict(), user=user)

@app.get("/api/v1/platform/ingestion/{run_id}")
def ingestion_run(run_id: str, user: ProductionUser = Depends(get_current_user)):
    def action(repo: PostgresRepository):
        row = repo.get_ingestion_run(run_id)
        if row is None:
            raise KeyError("ingestion_run")
        return repo.ingestion_dict(row)
    return run_platform(action, user=user)

@app.post("/api/v1/platform/ingestion/{run_id}/retry", status_code=201)
def retry_ingestion(run_id: str, payload: IngestionPayload, request: Request, user: ProductionUser = Depends(get_current_user)):
    enforce_rate_limit(request, user, "ingestion_retry")
    def check(repo: PostgresRepository):
        row = repo.get_ingestion_run(run_id)
        if row is None:
            raise KeyError("ingestion_run")
        if not safe_retry_allowed(row.status):
            raise ValueError("ingestion_retry_not_safe")
    run_platform(check, user=user)
    return run_ingestion(payload, request, user)

@app.get("/api/v1/notifications")
def notifications(organization_id: str | None = None, unread_only: bool = False, user: ProductionUser = Depends(get_current_user), limit: int = Query(50, ge=1, le=200), cursor: str | None = None):
    org_id = organization_for(user, organization_id)
    return run_db(lambda repo: repo.page(repo.notifications(unread_only), limit=limit, cursor=cursor).as_dict(), user=user, org_id=org_id)

@app.post("/api/v1/notifications/{notification_id}/read")
def mark_notification(notification_id: str, organization_id: str, user: ProductionUser = Depends(get_current_user)):
    return run_db(lambda repo: repo.mark_notification_read(notification_id), user=user, org_id=organization_id)

@app.get("/api/v1/search")
def search(request: Request, q: str = Query(min_length=2, max_length=80), organization_id: str | None = None, user: ProductionUser = Depends(get_current_user), limit: int = Query(20, ge=1, le=50)):
    org_id = organization_for(user, organization_id)
    enforce_rate_limit(request, user, "search")
    return run_db(lambda repo: repo.page(repo.search(q, limit=limit), limit=limit).as_dict(), user=user, org_id=org_id)

@app.post("/api/v1/exports", status_code=201)
def create_export(payload: ExportPayload, request: Request, user: ProductionUser = Depends(get_current_user)):
    require_role(user, payload.organization_id, {"coordinator", "org_admin", "reviewer"})
    if payload.include_individuals:
        require_role(user, payload.organization_id, {"reviewer", "org_admin"})
    enforce_rate_limit(request, user, "export")
    return run_db(lambda repo: (repo.create_export(purpose=payload.purpose, include_individuals=payload.include_individuals, request_id=request_id(request)), repo.audit(action="export.created", target_kind="export"))[0], user=user, org_id=payload.organization_id)

@app.get("/api/v1/exports")
def list_exports(organization_id: str | None = None, user: ProductionUser = Depends(get_current_user), limit: int = Query(50, ge=1, le=200), cursor: str | None = None):
    org_id = organization_for(user, organization_id)
    return run_db(lambda repo: repo.page(repo.exports(), limit=limit, cursor=cursor).as_dict(), user=user, org_id=org_id)

@app.get("/api/v1/exports/{export_id}")
def get_export(export_id: str, organization_id: str | None = None, user: ProductionUser = Depends(get_current_user)):
    org_id = organization_for(user, organization_id)
    value = run_db(lambda repo: repo.export(export_id), user=user, org_id=org_id)
    if value is None:
        raise api_error(404, "not_found", "The export was not found.")
    return value

@app.get("/api/v1/audit-events")
def audit_events(organization_id: str | None = None, action: str | None = None, user: ProductionUser = Depends(get_current_user), limit: int = Query(50, ge=1, le=200), cursor: str | None = None):
    org_id = organization_for(user, organization_id)
    require_role(user, org_id, {"reviewer", "org_admin"})
    return run_db(lambda repo: repo.page(repo.audit_events(action), limit=limit, cursor=cursor).as_dict(), user=user, org_id=org_id)

@app.post("/api/v1/consents", status_code=201)
def grant_consent(payload: ConsentPayload, organization_id: str, user: ProductionUser = Depends(get_current_user)):
    return run_db(lambda repo: repo.grant_consent(payload.model_dump()), user=user, org_id=organization_id)

@app.get("/api/v1/consents/me")
def get_consents(organization_id: str, user: ProductionUser = Depends(get_current_user)):
    return {"items": run_db(lambda repo: repo.consent_records(), user=user, org_id=organization_id)}

@app.post("/api/v1/consents/withdraw")
def withdraw_consent(payload: WithdrawPayload, organization_id: str, user: ProductionUser = Depends(get_current_user)):
    return run_db(lambda repo: repo.withdraw_consent(payload.consent_type), user=user, org_id=organization_id)

@app.get("/api/v1/context/{kind}")
def context(kind: str, organization_id: str | None = None, user: ProductionUser = Depends(get_current_user)):
    if kind not in {"weather", "climate", "suitability"}:
        raise api_error(404, "not_found", "The context endpoint was not found.")
    organization_for(user, organization_id)
    return {"status": "unavailable", "kind": kind, "items": [], "reason": "no_promoted_source"}

@app.get("/api/v1/prices")
def prices(organization_id: str | None = None, user: ProductionUser = Depends(get_current_user)):
    organization_for(user, organization_id)
    return {"status": "unavailable", "items": [], "reason": "no_promoted_source"}

@app.get("/api/v1/observability/calculations")
def calculation_observability(user: ProductionUser = Depends(get_current_user)):
    if not user.is_platform:
        raise api_error(403, "permission_denied", "Platform authority is required.")
    return metrics_snapshot()