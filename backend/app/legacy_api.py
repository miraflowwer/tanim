"""TANIM P0 production API (PRD ??10.2, 12, 13, 20, 32, 33, 40).

Calculation flow POST /api/v1/plans/{plan_id}/calculate (PRD ?20):
  1. load plan revision  2. authorize  3. resolve crop  4. resolve yield
  5. resolve eligible evidence  6. resolve policy  7. run S=A?Y, L=S/R
  8. persist calculation_runs  9. return 3-level presentation result.
The browser never builds trusted evidence: PlanIn carries no evidence fields.
"""
import os
import time
import uuid
from datetime import UTC, date, datetime

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.utils import generate_unique_id

from . import audit as audit_mod
from . import consent as consent_mod
from . import db as db_mod
from . import store as S
from .auth import UserContext, dev_token_for, get_current_user
from .grci import (
    ENGINE_VERSION,
    active_plans,
    classify_coordination_load,
    estimate_production,
    next_reference_version,
    period_matches,
    select_eligible_reference,
    supply_load,
    transition_reference,
)
from .observability import (
    CALC_LOGS,
    bump,
    log_calculation,
    new_calculation_id,
    new_request_id,
    utcnow_iso,
)
from .rbac import AUDIT_ROLES, REVIEW_ROLES, authorize, check_query_org
from .schemas import (
    ConsentIn,
    ConsentWithdrawIn,
    ExportIn,
    FarmIn,
    PlanIn,
    PlanPatchIn,
    PolicyIn,
    ReferenceIn,
    ReviewNoteIn,
    RoleChangeIn,
    SessionIn,
)

MAX_BODY_BYTES = 1_000_000  # ?32 request-size limit

COPY = {  # ?30 + ?10.3 calibrated copy; never use banned certainty words
    "crop_unsupported": "TANIM does not yet have a safe production and area match for this crop.",
    "yield_unavailable": "TANIM cannot estimate production for this crop and region yet.",
    "comparison_unavailable": "Expected production is available, but TANIM does not have a reviewed comparison reference.",
    "service_unavailable": "TANIM could not calculate this plan. Your entries have been kept. Try again.",
    "stale_evidence": "This result uses the latest verified reference available, but the source is older than expected.",
    "high_load": "Planned production is above the reviewed reference for this crop and harvest period.",
    "approaching": "Planned production is approaching the reviewed reference for this crop and harvest period.",
    "within": "Planned production is below the comparison reference for this crop and harvest period.",
    "insufficient": "TANIM can estimate production, but no reviewed local demand reference is available for this crop and period.",
}

app = FastAPI(title="TANIM API", version="0.1.0",
              generate_unique_id_function=generate_unique_id)


# --- middleware: X-Request-ID (?33) + request-size limit (?32) ---
@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or new_request_id()
    request.state.request_id = request_id
    cl = request.headers.get("content-length")
    try:
        if cl is not None and int(cl) > MAX_BODY_BYTES:
            return JSONResponse(status_code=413, content={"detail": {
                "code": "payload_too_large",
                "message": "This submission is too large. Keep entries under 1 MB."}})
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": {
            "code": "bad_request", "message": "Unrecognized request."}})
    if (request.url.path.startswith("/api/v1/")
            and request.url.path not in ("/api/v1/health", "/api/v1/readiness")
            and db_mod.is_production_mode()):
        return JSONResponse(
            status_code=503,
            content={"detail": {
                "code": "database_not_wired",
                "message": "Production routes require the PostgreSQL repository adapter.",
            }},
            headers={"X-Request-ID": request_id},
        )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": {
        "code": "validation_error",
        "message": "Some entries need fixing. Check each field and try again.",
        "errors": [{k: v for k, v in e.items() if k in ("loc", "msg", "type")}
                    for e in exc.errors()]}})


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _plan_geo(plan: dict) -> str:
    if plan.get("farm_id") and plan["farm_id"] in S.FARMS:
        return S.FARMS[plan["farm_id"]].get("region") or S.ORGS[plan["org_id"]]["default_geography"]
    return S.ORGS[plan["org_id"]]["default_geography"]


def _today() -> date:
    return datetime.now(UTC).date()


def _eligible_refs(crop_code: str, org_id: str, geography: str,
                   planning_period: date) -> list[dict]:
    """Resolve only evidence matching the exact tenant, context, and validity window."""
    ref = select_eligible_reference(
        S.REFERENCES, organization_id=org_id, crop_code=crop_code,
        geography=geography, planning_period=planning_period,
        calculation_date=_today())
    return [ref] if ref is not None else []


def _has_stale_verified(crop_code: str, org_id: str, geography: str,
                        planning_period: date) -> bool:
    today = _today()
    return any(
        ref.get("org_id") == org_id
        and ref.get("crop_code") == crop_code
        and ref.get("geography") == geography
        and period_matches(ref.get("period"), planning_period)
        and ref.get("reference_type") in
            ("local_committed_demand", "local_historical_absorption")
        and (
            ref.get("verification_status") in ("stale", "superseded")
            or (ref.get("review") == "verified"
                and ref.get("effective_to") is not None
                and ref["effective_to"] < today)
        )
        for ref in S.REFERENCES.values()
    )


# --- health / readiness (?33) ---
@app.get("/api/v1/health")
def health():
    return {"status": "ok", "engine_version": ENGINE_VERSION}


@app.get("/api/v1/readiness")
def readiness():
    dependencies_ready, details = db_mod.check_readiness()
    if not dependencies_ready:
        return JSONResponse(status_code=503, content={
            "status": "not_ready", "code": "dependency_unavailable",
            "engine_version": ENGINE_VERSION, **details})
    if db_mod.is_production_mode():
        return JSONResponse(status_code=503, content={
            "status": "not_ready", "code": "database_not_wired",
            "engine_version": ENGINE_VERSION, **details})
    return {"status": "ready", "engine_version": ENGINE_VERSION, **details}


# --- auth / me ---
@app.post("/api/v1/auth/session")
def create_session(body: SessionIn):
    """DEV ONLY login helper: exchange a seeded user id for a bearer token."""
    if os.environ.get("ALLOW_DEV_AUTH") != "true" or body.user_id not in S.USERS:
        raise _err(401, "unauthorized", "Sign in required.")
    # Reviewed B105: bearer names the OAuth token scheme; it is not a password.
    return {"access_token": dev_token_for(body.user_id), "token_type": "bearer"}  # nosec B105


@app.get("/api/v1/me")
def me(user: UserContext = Depends(get_current_user)):
    return {"user_id": user.user_id, "email": user.email,
            "org_roles": user.org_roles, "is_platform": user.is_platform}


# --- organizations / aggregates ---
@app.get("/api/v1/organizations/{org_id}/aggregates")
def aggregates(org_id: str, harvest_period: str | None = None,
               user: UserContext = Depends(get_current_user)):
    authorize(user, org_id)
    rows: dict = {}
    for plan in active_plans(S.PLANS):
        if plan["org_id"] != org_id:
            continue
        rev = plan["revisions"][-1]
        if rev["harvest_period"] < _today():
            continue
        if harvest_period and str(rev["harvest_period"]) != harvest_period:
            continue
        key = (plan["crop_code"], str(rev["harvest_period"]))
        row = rows.setdefault(key, {"crop_code": plan["crop_code"],
                                    "harvest_period": str(rev["harvest_period"]),
                                    "farmers": set(), "planned_area_ha": 0.0,
                                    "estimated_production_mt": 0.0, "plans": 0})
        row["farmers"].add(plan["owner_user_id"])
        row["planned_area_ha"] += rev["area_ha"]
        row["plans"] += 1
        y = S.YIELDS.get((plan["crop_code"], _plan_geo(plan)))
        if y and row["estimated_production_mt"] is not None:
            row["estimated_production_mt"] += estimate_production(
                rev["area_ha"], y["yield_mt_per_ha"], rev["area_margin_ha"]
            )["s_mt"]
        elif y is None:
            row["estimated_production_mt"] = None
    return {"organization_id": org_id,
            "rows": [{**r, "farmers": len(r["farmers"])} for r in rows.values()]}


@app.put("/api/v1/organizations/{org_id}/members/{member_id}")
def change_role(org_id: str, member_id: str, body: RoleChangeIn,
                user: UserContext = Depends(get_current_user)):
    authorize(user, org_id, "org_admin", "platform_admin")
    if member_id not in S.USERS or org_id not in S.ORGS:
        raise _err(404, "not_found", "Member or organization not found.")
    if body.role == "platform_admin":
        raise _err(422, "invalid_role", "Platform authority cannot be assigned through an organization.")
    S.USERS[member_id].setdefault("org_roles", {})[org_id] = body.role
    return audit_mod.emit("role.changed", org_id=org_id, actor_user_id=user.user_id,
                          target_kind="membership", target_id=member_id,
                          metadata={"role": body.role})


@app.delete("/api/v1/organizations/{org_id}/members/{member_id}")
def remove_member(org_id: str, member_id: str, user: UserContext = Depends(get_current_user)):
    authorize(user, org_id, "org_admin", "platform_admin")
    S.USERS.get(member_id, {}).get("org_roles", {}).pop(org_id, None)
    return audit_mod.emit("member.removed", org_id=org_id, actor_user_id=user.user_id,
                          target_kind="membership", target_id=member_id)


# --- farms CRUD ---
@app.post("/api/v1/farms", status_code=201)
def create_farm(body: FarmIn, org_id: str | None = None,
                user: UserContext = Depends(get_current_user)):
    if body.organization_id not in S.ORGS:
        raise _err(404, "not_found", "Organization not found.")
    check_query_org(body.organization_id, org_id)
    authorize(user, body.organization_id)
    fid = f"farm-{uuid.uuid4().hex[:8]}"
    farm = {"id": fid, "org_id": body.organization_id, "owner_user_id": user.user_id,
            "name": body.name, "total_area_ha": body.total_area_ha,
            "municipality": body.municipality, "region": body.region}
    S.FARMS[fid] = farm
    return farm


@app.get("/api/v1/farms")
def list_farms(org_id: str, user: UserContext = Depends(get_current_user)):
    authorize(user, org_id)
    role = user.role_in(org_id)
    farms = [f for f in S.FARMS.values() if f["org_id"] == org_id]
    if role == "farmer":  # farmers see only their own farms
        farms = [f for f in farms if f["owner_user_id"] == user.user_id]
    return {"farms": farms}


@app.get("/api/v1/farms/{farm_id}")
def get_farm(farm_id: str, user: UserContext = Depends(get_current_user)):
    farm = S.FARMS.get(farm_id)
    if farm is None:
        raise _err(404, "not_found", "Farm not found.")
    authorize(user, farm["org_id"])
    if user.role_in(farm["org_id"]) == "farmer" and farm["owner_user_id"] != user.user_id:
        raise _err(403, "permission_denied", "You do not have access to this farm.")
    return farm


@app.patch("/api/v1/farms/{farm_id}")
def update_farm(farm_id: str, body: FarmIn, user: UserContext = Depends(get_current_user)):
    farm = S.FARMS.get(farm_id)
    if farm is None:
        raise _err(404, "not_found", "Farm not found.")
    authorize(user, farm["org_id"])
    if body.organization_id != farm["org_id"]:
        raise _err(403, "permission_denied", "Organization scope mismatch.")
    if user.role_in(farm["org_id"]) == "farmer" and farm["owner_user_id"] != user.user_id:
        raise _err(403, "permission_denied", "You do not have access to this farm.")
    farm.update({"name": body.name, "total_area_ha": body.total_area_ha,
                 "municipality": body.municipality, "region": body.region})
    return farm


@app.delete("/api/v1/farms/{farm_id}")
def delete_farm(farm_id: str, user: UserContext = Depends(get_current_user)):
    farm = S.FARMS.get(farm_id)
    if farm is None:
        raise _err(404, "not_found", "Farm not found.")
    authorize(user, farm["org_id"], "coordinator", "org_admin", "platform_admin")
    del S.FARMS[farm_id]
    return {"deleted": farm_id}


# --- crops + yield ---
@app.get("/api/v1/crops")
def list_crops(user: UserContext = Depends(get_current_user)):
    return {"registry_version": S.REGISTRY_VERSION,
            "crops": [c for c in S.CROPS.values() if c["is_active"]]}


@app.get("/api/v1/crops/{code}")
def get_crop(code: str, user: UserContext = Depends(get_current_user)):
    crop = S.CROPS.get(code)
    if crop is None or not crop["is_active"]:
        raise _err(404, "crop_unsupported", COPY["crop_unsupported"])
    return {**crop, "registry_version": S.REGISTRY_VERSION}


@app.get("/api/v1/crops/{code}/yield")
def crop_yield(code: str, geography: str, user: UserContext = Depends(get_current_user)):
    y = S.YIELDS.get((code, geography))
    if y is None:
        raise _err(404, "yield_unavailable", COPY["yield_unavailable"])
    return y


# --- plans CRUD + revisions ---
def _plan_out(plan: dict) -> dict:
    rev = plan["revisions"][-1]
    return {**plan, "revision": {**rev, "planting_date": str(rev["planting_date"]),
                                 "harvest_period": str(rev["harvest_period"])}}


@app.post("/api/v1/plans", status_code=201)
def create_plan(body: PlanIn, org_id: str | None = None,
                user: UserContext = Depends(get_current_user)):
    if body.organization_id not in S.ORGS:
        raise _err(404, "not_found", "Organization not found.")
    check_query_org(body.organization_id, org_id)
    authorize(user, body.organization_id)
    crop = S.CROPS.get(body.crop_code)
    if crop is None or not crop["is_active"]:
        raise _err(422, "crop_unsupported", COPY["crop_unsupported"])
    if body.farm_id is not None:
        farm = S.FARMS.get(body.farm_id)
        if farm is None:
            raise _err(404, "not_found", "Farm not found.")
        if farm["org_id"] != body.organization_id or farm["owner_user_id"] != user.user_id:
            raise _err(403, "permission_denied", "You do not have access to this farm.")
    pid = f"plan-{uuid.uuid4().hex[:8]}"
    S.PLANS[pid] = {"id": pid, "org_id": body.organization_id, "farm_id": body.farm_id,
                    "crop_code": body.crop_code, "owner_user_id": user.user_id,
                    "status": "draft", "revisions": [{
                        "revision_number": 1, "area_ha": body.area_ha,
                        "area_margin_ha": body.area_margin_ha,
                        "planting_date": body.planting_date, "harvest_period": body.harvest_period,
                        "created_by": user.user_id, "created_at": utcnow_iso()}],
                    "current_revision": 1, "created_at": utcnow_iso()}
    return _plan_out(S.PLANS[pid])


@app.get("/api/v1/plans")
def list_plans(org_id: str, user: UserContext = Depends(get_current_user)):
    authorize(user, org_id)
    plans = [p for p in S.PLANS.values() if p["org_id"] == org_id]
    if user.role_in(org_id) == "farmer":
        plans = [p for p in plans if p["owner_user_id"] == user.user_id]
    return {"plans": [_plan_out(p) for p in plans]}


@app.get("/api/v1/plans/{plan_id}")
def get_plan(plan_id: str, org_id: str | None = None,
             user: UserContext = Depends(get_current_user)):
    plan = S.PLANS.get(plan_id)
    if plan is None:
        raise _err(404, "plan_not_found", "Planting plan not found.")
    check_query_org(plan["org_id"], org_id)
    authorize(user, plan["org_id"])
    if user.role_in(plan["org_id"]) == "farmer" and plan["owner_user_id"] != user.user_id:
        raise _err(403, "permission_denied", "You do not have access to this plan.")
    return _plan_out(plan)


@app.patch("/api/v1/plans/{plan_id}")
def update_plan(plan_id: str, body: PlanPatchIn, user: UserContext = Depends(get_current_user)):
    plan = S.PLANS.get(plan_id)
    if plan is None:
        raise _err(404, "plan_not_found", "Planting plan not found.")
    authorize(user, plan["org_id"])
    if user.role_in(plan["org_id"]) == "farmer" and plan["owner_user_id"] != user.user_id:
        raise _err(403, "permission_denied", "You do not have access to this plan.")
    last = dict(plan["revisions"][-1])
    patch = body.model_dump(exclude_unset=True)
    status = patch.pop("status", None)
    if plan["status"] in ("cancelled", "harvested"):
        raise _err(409, "plan_inactive", "Cancelled and harvested plans cannot be changed.")
    if any(value is None for value in patch.values()):
        raise _err(422, "validation_error", "Plan fields cannot be cleared.")
    candidate = {**last, **patch}
    if candidate["harvest_period"] < candidate["planting_date"]:
        raise _err(422, "validation_error", "harvest_period must not precede planting_date.")
    if status:
        plan["status"] = status
    if not patch:
        return _plan_out(plan)
    last = candidate
    last["revision_number"] = len(plan["revisions"]) + 1
    last["created_by"] = user.user_id
    last["created_at"] = utcnow_iso()
    plan["revisions"].append(last)
    plan["current_revision"] = last["revision_number"]
    return _plan_out(plan)


@app.delete("/api/v1/plans/{plan_id}")
def delete_plan(plan_id: str, user: UserContext = Depends(get_current_user)):
    plan = S.PLANS.get(plan_id)
    if plan is None:
        raise _err(404, "plan_not_found", "Planting plan not found.")
    authorize(user, plan["org_id"])
    if user.role_in(plan["org_id"]) == "farmer" and plan["owner_user_id"] != user.user_id:
        raise _err(403, "permission_denied", "You do not have access to this plan.")
    if plan["status"] == "harvested":
        raise _err(409, "plan_inactive", "Harvested plans cannot be cancelled.")
    plan["status"] = "cancelled"  # history preserved, never hard-deleted
    return {"cancelled": plan_id}


@app.get("/api/v1/plans/{plan_id}/revisions")
def plan_revisions(plan_id: str, user: UserContext = Depends(get_current_user)):
    plan = S.PLANS.get(plan_id)
    if plan is None:
        raise _err(404, "plan_not_found", "Planting plan not found.")
    authorize(user, plan["org_id"])
    if user.role_in(plan["org_id"]) == "farmer" and plan["owner_user_id"] != user.user_id:
        raise _err(403, "permission_denied", "You do not have access to this plan.")
    return {"plan_id": plan_id, "revisions": [
        {**r, "planting_date": str(r["planting_date"]), "harvest_period": str(r["harvest_period"])}
        for r in plan["revisions"]]}


# --- 9-step calculation (PRD ?20) ---
@app.post("/api/v1/plans/{plan_id}/calculate")
def calculate_plan(plan_id: str, request: Request, org_id: str | None = None,
                   user: UserContext = Depends(get_current_user)):
    t0 = time.perf_counter()
    request_id = getattr(request.state, "request_id", new_request_id())
    calculation_id = new_calculation_id()
    policy = S.POLICIES[-1]

    def finish(status: str, run: dict, exc: HTTPException | None = None):
        duration_ms = int((time.perf_counter() - t0) * 1000)
        run.update({"calculation_id": calculation_id, "request_id": request_id,
                    "duration_ms": duration_ms, "timestamp": utcnow_iso()})
        S.CALCULATIONS[calculation_id] = run
        log_calculation(calculation_id=calculation_id, request_id=request_id,
                        engine_version=ENGINE_VERSION, policy_version=policy["version"],
                        dataset_version="psa-2021-2025-v1",
                        reference_version=run.get("comparison_reference_version"),
                        organization_id=run["org_id"], status=status, duration_ms=duration_ms)
        bump("calc_complete" if status == "complete" else
             "calc_incomplete" if status == "incomplete" else "calc_failed")
        if exc is not None:
            raise exc
        return run["result"]

    # 1. load plan revision
    plan = S.PLANS.get(plan_id)
    if plan is None:
        raise _err(404, "plan_not_found", "Planting plan not found.")
    rev = plan["revisions"][-1]
    # 2. authorize (server-side; tamper-proof)
    check_query_org(plan["org_id"], org_id)
    authorize(user, plan["org_id"])
    if user.role_in(plan["org_id"]) == "farmer" and plan["owner_user_id"] != user.user_id:
        from .rbac import _denied
        raise _denied("You do not have access to this plan.")
    if plan["status"] not in ("draft", "planned"):
        raise _err(409, "plan_inactive", "Cancelled and harvested plans cannot be recalculated.")
    base_run = {"org_id": plan["org_id"], "plan_id": plan_id,
                "plan_revision": rev["revision_number"], "engine_version": ENGINE_VERSION,
                "policy_version": policy["version"], "registry_version": S.REGISTRY_VERSION,
                "yield_reference_id": None, "yield_reference_version": None,
                "comparison_reference_id": None, "comparison_reference_version": None,
                "s_mt": None, "s_low_mt": None, "s_high_mt": None, "supply_load": None}
    # 3. resolve crop (registry check)
    crop = S.CROPS.get(plan["crop_code"])
    if crop is None or not crop["is_active"]:
        bump("missing_evidence")
        return finish("failed", base_run,
                      _err(404, "crop_unsupported", COPY["crop_unsupported"]))
    # 4. resolve crop-region yield
    geo = _plan_geo(plan)
    y = S.YIELDS.get((plan["crop_code"], geo))
    if y is None:
        bump("missing_yield")
        return finish("failed", base_run,
                      _err(404, "yield_unavailable", COPY["yield_unavailable"]))
    base_run.update({"yield_reference_id": y["id"], "yield_reference_version": y["version"]})
    # 5. resolve eligible evidence (fresh reviewed_verified local only)
    refs = _eligible_refs(plan["crop_code"], plan["org_id"], geo,
                          rev["harvest_period"])
    # 6. resolve policy (latest calculation_policies)
    thresholds = policy["thresholds"]
    # 7. run S = A ? Y (+ range) and L = S / R
    prod = estimate_production(rev["area_ha"], y["yield_mt_per_ha"], rev["area_margin_ha"])
    base_run.update({"s_mt": prod["s_mt"], "s_low_mt": prod["s_low_mt"], "s_high_mt": prod["s_high_mt"]})
    primary = {"planned_area_ha": rev["area_ha"],
               "estimated_production_mt": round(prod["s_mt"], 3)}
    secondary = {"estimated_range_mt": [round(prod["s_low_mt"], 3), round(prod["s_high_mt"], 3)],
                 "area_range_ha": [round(max(0.0, rev["area_ha"] - rev["area_margin_ha"]), 3),
                                   round(rev["area_ha"] + rev["area_margin_ha"], 3)]}
    if not refs:
        # Valid result: production known, comparison missing (?10.3 third state).
        bump("missing_evidence")
        stale = _has_stale_verified(plan["crop_code"], plan["org_id"], geo,
                                    rev["harvest_period"])
        if stale:
            bump("stale_evidence")
        primary.update({"coordination_status": "insufficient_evidence",
                        "reference_used": None, "message": COPY["comparison_unavailable"]})
        secondary.update({"comparison_amount_mt": None, "supply_load": None,
                          "evidence_quality": "none"})
        detailed = {"reference_type": None, "source": None, "geography": geo,
                    "source_period": None, "verification_date": None,
                    "calculation_policy_version": policy["version"],
                    "engine_version": ENGINE_VERSION, "evidence_note": None,
                    "freshness": {"state": "stale" if stale else "missing",
                                  "note": COPY["stale_evidence"] if stale else None}}
        base_run["result"] = _present("incomplete", calculation_id, plan, rev, primary,
                                      secondary, detailed, request_id)
        return finish("incomplete", base_run)
    ref = refs[0]
    load = supply_load(prod["s_mt"], ref["amount_mt"])
    base_run.update({"comparison_reference_id": ref["id"],
                     "comparison_reference_version": ref["version"], "supply_load": round(load, 6)})
    status_label = classify_coordination_load(load, thresholds)
    message = {
        "high_coordination_load": COPY["high_load"],
        "elevated_coordination_load": COPY["approaching"],
        "within_reference": COPY["within"],
    }[status_label]
    primary.update({"coordination_status": status_label,
                    "reference_used": f"{ref['source']} ? {ref['geography']} ? {ref['period']}",
                    "message": message})
    secondary.update({"comparison_amount_mt": ref["amount_mt"], "supply_load": round(load, 6),
                      "evidence_quality": ref["verification_status"]})
    detailed = {"reference_type": ref["reference_type"], "source": ref["source"],
                "geography": ref["geography"], "source_period": ref["period"],
                "verification_date": ref.get("verified_at"),
                "calculation_policy_version": policy["version"],
                "engine_version": ENGINE_VERSION, "evidence_note": ref.get("evidence_note"),
                "freshness": {"state": "fresh", "verified_at": ref.get("verified_at"),
                              "expected_refresh": "annual"}}
    # 8. persist  9. return presentation result (3 disclosure levels)
    base_run["result"] = _present("complete", calculation_id, plan, rev, primary,
                                  secondary, detailed, request_id)
    return finish("complete", base_run)


def _present(status: str, calculation_id: str, plan: dict, rev: dict,
             primary: dict, secondary: dict, detailed: dict, request_id: str) -> dict:
    return {"calculation_id": calculation_id, "plan_id": plan["id"],
            "revision_number": rev["revision_number"], "organization_id": plan["org_id"],
            "status": status, "primary": primary, "secondary": secondary,
            "detailed_evidence": detailed, "request_id": request_id,
            "timestamp": utcnow_iso()}


@app.get("/api/v1/calculations/{calculation_id}")
def get_calculation(calculation_id: str, user: UserContext = Depends(get_current_user)):
    run = S.CALCULATIONS.get(calculation_id)
    if run is None:
        raise _err(404, "not_found", "Calculation not found.")
    authorize(user, run["org_id"])
    plan = S.PLANS.get(run["plan_id"])
    if (user.role_in(run["org_id"]) == "farmer"
            and (plan is None or plan["owner_user_id"] != user.user_id)):
        raise _err(403, "permission_denied", "You do not have access to this calculation.")
    return run["result"]


# --- references + review workflow (?11.3, audit ?40) ---
@app.post("/api/v1/references", status_code=201)
def create_reference(body: ReferenceIn, user: UserContext = Depends(get_current_user)):
    if body.organization_id not in S.ORGS:
        raise _err(404, "not_found", "Organization not found.")
    authorize(user, body.organization_id)
    if S.CROPS.get(body.crop_code) is None:
        raise _err(422, "crop_unsupported", COPY["crop_unsupported"])
    rid = f"ref-{uuid.uuid4().hex[:8]}"
    version = next_reference_version(
        S.REFERENCES, organization_id=body.organization_id,
        crop_code=body.crop_code, geography=body.geography,
        planning_period=body.period)
    ref = {"id": rid, "org_id": body.organization_id, "crop_code": body.crop_code,
           "reference_type": body.reference_type, "amount_mt": body.amount_mt, "unit": body.unit,
           "geography": body.geography, "period": body.period, "source": body.source,
           "evidence_note": body.evidence_note,
           "verification_status": "user_provided_unverified",  # never auto-verified
           "review": "draft", "reviewer_id": None,
           "effective_from": body.effective_from, "effective_to": body.effective_to,
           "version": version, "predecessor_id": None, "successor_id": None,
           "verified_at": None, "flags": [], "review_history": []}
    S.REFERENCES[rid] = ref
    audit_mod.emit("reference.created", org_id=ref["org_id"], actor_user_id=user.user_id,
                   target_kind="reference", target_id=rid)
    return ref


@app.get("/api/v1/references")
def list_references(org_id: str, user: UserContext = Depends(get_current_user)):
    authorize(user, org_id)
    return {"references": [r for r in S.REFERENCES.values() if r["org_id"] == org_id]}


@app.get("/api/v1/references/{ref_id}")
def get_reference(ref_id: str, user: UserContext = Depends(get_current_user)):
    ref = S.REFERENCES.get(ref_id)
    if ref is None:
        raise _err(404, "not_found", "Reference not found.")
    authorize(user, ref["org_id"])
    return ref


def _transition(ref_id: str, user: UserContext, to: str, action: str,
                note: str | None) -> dict:
    ref = S.REFERENCES.get(ref_id)
    if ref is None:
        raise _err(404, "not_found", "Reference not found.")
    authorize(user, ref["org_id"], *REVIEW_ROLES)
    if to == "verified" and ref["reference_type"] == "demo_coordination_baseline":
        raise _err(422, "synthetic_reference", "Synthetic demo evidence cannot be verified for production.")
    try:
        transition_reference(ref, to, actor_user_id=user.user_id, note=note)
    except ValueError as exc:
        raise _err(409, "invalid_reference_transition", str(exc)) from exc
    audit_mod.emit(action, org_id=ref["org_id"], actor_user_id=user.user_id,
                   target_kind="reference", target_id=ref_id,
                   metadata={"note": note} if note else {})
    return ref


@app.post("/api/v1/references/{ref_id}/submit")
def submit_reference(ref_id: str, body: ReviewNoteIn,
                     user: UserContext = Depends(get_current_user)):
    ref = S.REFERENCES.get(ref_id)
    if ref is None:
        raise _err(404, "not_found", "Reference not found.")
    authorize(user, ref["org_id"])
    try:
        transition_reference(ref, "under_review", actor_user_id=user.user_id,
                             note=body.note)
    except ValueError as exc:
        raise _err(409, "invalid_reference_transition", str(exc)) from exc
    audit_mod.emit("reference.submitted", org_id=ref["org_id"],
                   actor_user_id=user.user_id, target_kind="reference",
                   target_id=ref_id, metadata={"note": body.note} if body.note else {})
    return ref


@app.post("/api/v1/references/{ref_id}/verify")
def verify_reference(ref_id: str, body: ReviewNoteIn,
                     user: UserContext = Depends(get_current_user)):
    return _transition(ref_id, user, "verified", "reference.verified", body.note)


@app.post("/api/v1/references/{ref_id}/reject")
def reject_reference(ref_id: str, body: ReviewNoteIn,
                     user: UserContext = Depends(get_current_user)):
    return _transition(ref_id, user, "rejected", "reference.rejected", body.note)


@app.post("/api/v1/references/{ref_id}/reopen")
def reopen_reference(ref_id: str, body: ReviewNoteIn,
                     user: UserContext = Depends(get_current_user)):
    return _transition(ref_id, user, "draft", "reference.reopened", body.note)


@app.patch("/api/v1/references/{ref_id}")
def correct_reference(ref_id: str, body: ReferenceIn,
                      user: UserContext = Depends(get_current_user)):
    ref = S.REFERENCES.get(ref_id)
    if ref is None:
        raise _err(404, "not_found", "Reference not found.")
    authorize(user, ref["org_id"], *REVIEW_ROLES)
    if ref["review"] != "draft":
        raise _err(409, "invalid_reference_transition",
                   "Only draft references can be corrected.")
    if (body.organization_id != ref["org_id"]
            or body.crop_code != ref["crop_code"]
            or body.geography != ref["geography"]
            or not period_matches(body.period, ref["period"])):
        raise _err(422, "reference_scope_mismatch",
                   "Correction must retain organization, crop, geography, and planning period.")
    ref.update({
        "reference_type": body.reference_type,
        "amount_mt": body.amount_mt,
        "unit": body.unit,
        "source": body.source,
        "evidence_note": body.evidence_note,
        "effective_from": body.effective_from,
        "effective_to": body.effective_to,
    })
    audit_mod.emit("reference.corrected", org_id=ref["org_id"],
                   actor_user_id=user.user_id, target_kind="reference",
                   target_id=ref_id)
    return ref


@app.post("/api/v1/references/{ref_id}/supersede")
def supersede_reference(ref_id: str, body: ReferenceIn,
                        user: UserContext = Depends(get_current_user)):
    old = S.REFERENCES.get(ref_id)
    if old is None:
        raise _err(404, "not_found", "Reference not found.")
    authorize(user, old["org_id"], *REVIEW_ROLES)
    if (body.organization_id != old["org_id"]
            or body.crop_code != old["crop_code"]
            or body.geography != old["geography"]
            or not period_matches(body.period, old["period"])):
        raise _err(422, "reference_scope_mismatch",
                   "Successor must retain organization, crop, geography, and planning period.")
    if old["review"] != "verified":
        raise _err(409, "invalid_reference_transition",
                   "Only verified references can be superseded.")
    version = next_reference_version(
        S.REFERENCES, organization_id=old["org_id"],
        crop_code=old["crop_code"], geography=old["geography"],
        planning_period=old["period"])
    nid = f"ref-{uuid.uuid4().hex[:8]}"
    new = {
        "id": nid, "org_id": old["org_id"], "crop_code": old["crop_code"],
        "reference_type": body.reference_type, "amount_mt": body.amount_mt,
        "unit": body.unit, "geography": old["geography"],
        "period": old["period"], "source": body.source,
        "evidence_note": body.evidence_note,
        "effective_from": body.effective_from, "effective_to": body.effective_to,
        "version": version, "review": "draft",
        "verification_status": "user_provided_unverified",
        "reviewer_id": None, "verified_at": None, "flags": [],
        "predecessor_id": ref_id, "successor_id": None,
        "review_history": [],
    }
    transition_reference(old, "superseded", actor_user_id=user.user_id,
                         note=f"successor: {nid}")
    old["successor_id"] = nid
    S.REFERENCES[nid] = new
    audit_mod.emit("reference.superseded", org_id=old["org_id"],
                   actor_user_id=user.user_id, target_kind="reference",
                   target_id=ref_id, metadata={"successor_id": nid})
    return new


@app.post("/api/v1/references/{ref_id}/expire")
def expire_reference(ref_id: str, user: UserContext = Depends(get_current_user)):
    return _transition(ref_id, user, "expired", "reference.expired", None)


@app.post("/api/v1/references/{ref_id}/flag")
def flag_reference(ref_id: str, body: ReviewNoteIn,
                   user: UserContext = Depends(get_current_user)):
    ref = S.REFERENCES.get(ref_id)
    if ref is None:
        raise _err(404, "not_found", "Reference not found.")
    authorize(user, ref["org_id"])
    ref["flags"].append({"by": user.user_id, "note": body.note, "at": utcnow_iso()})
    return ref


# --- prices / context (??14.2, 14.4?14.6: context only, never R) ---
@app.get("/api/v1/prices")
def list_prices(crop_code: str | None = None, user: UserContext = Depends(get_current_user)):
    rows = [p for p in S.PRICES if crop_code is None or p["crop_code"] == crop_code]
    return {"prices": rows, "note": "Market context only ? never a demand reference."}


@app.get("/api/v1/context/weather")
def weather(geography: str, user: UserContext = Depends(get_current_user)):
    return S.WEATHER


@app.get("/api/v1/context/climate")
def climate(geography: str | None = None, user: UserContext = Depends(get_current_user)):
    rows = [c for c in S.CLIMATE if geography is None or c["geography"] == geography]
    return {"climate": rows, "note": "Context only ? not part of the coordination result."}


@app.get("/api/v1/context/suitability")
def suitability(crop_code: str | None = None, user: UserContext = Depends(get_current_user)):
    rows = [s for s in S.SUITABILITY if crop_code is None or s["crop_code"] == crop_code]
    return {"suitability": rows, "note": "Context only ? not part of the coordination result."}


# --- data sources + freshness/promote (??38, 39) ---
@app.get("/api/v1/data-sources")
def list_sources(user: UserContext = Depends(get_current_user)):
    return {"sources": list(S.DATA_SOURCES.values())}


@app.get("/api/v1/data-sources/{key}/freshness")
def source_freshness(key: str, user: UserContext = Depends(get_current_user)):
    src = S.DATA_SOURCES.get(key)
    if src is None:
        raise _err(404, "not_found", "Data source not found.")
    return {"key": key, "last_verified": src["last_verified"],
            "expected_refresh": src["expected_refresh"],
            "dataset_version": src["dataset_version"]}


def _has_global_role(user: UserContext, *allowed: str) -> bool:
    """Global datasets/policies: reviewer+ in any member org, or platform."""
    if user.is_platform:
        return True
    return any(role in allowed for role in user.org_roles.values())


@app.post("/api/v1/data-sources/{key}/promote")
def promote_source(key: str, user: UserContext = Depends(get_current_user)):
    src = S.DATA_SOURCES.get(key)
    if src is None:
        raise _err(404, "not_found", "Data source not found.")
    if not user.is_platform:  # global source promotion is a platform action
        from .rbac import _denied
        raise _denied()
    staged = [v for v in src["versions"] if v.get("promoted_at") is None]
    if not staged:
        raise _err(409, "nothing_to_promote", "No staged version awaiting promotion.")
    staged[-1]["promoted_at"] = utcnow_iso()
    src["last_verified"] = _today().isoformat()
    audit_mod.emit("source.promoted", org_id=None, actor_user_id=user.user_id,
                   target_kind="data_source", target_id=key)
    return src


# --- policies (threshold change => new version, ?12) ---
@app.get("/api/v1/policies/latest")
def latest_policy(user: UserContext = Depends(get_current_user)):
    return S.POLICIES[-1]


@app.post("/api/v1/policies", status_code=201)
def create_policy(body: PolicyIn, user: UserContext = Depends(get_current_user)):
    if not user.is_platform:
        from .rbac import _denied
        raise _denied("Only platform operators may change calculation policy.")
    nxt = {"id": f"policy-v{len(S.POLICIES) + 1}", "version": len(S.POLICIES) + 1,
           "thresholds": {"elevated_load": body.elevated_load, "high_load": body.high_load},
           "created_by": user.user_id, "created_at": utcnow_iso()}
    S.POLICIES.append(nxt)
    audit_mod.emit("policy.changed", org_id=None, actor_user_id=user.user_id,
                   target_kind="policy", target_id=nxt["id"],
                   metadata={"version": nxt["version"]})
    return nxt


# --- exports (gated, logged ?8.8) ---
@app.post("/api/v1/exports", status_code=201)
def create_export(body: ExportIn, user: UserContext = Depends(get_current_user)):
    if body.include_individuals:
        authorize(user, body.organization_id, "org_admin", "platform_admin")
    else:
        authorize(user, body.organization_id)
    eid = f"export-{uuid.uuid4().hex[:8]}"
    plans = [p for p in S.PLANS.values() if p["org_id"] == body.organization_id]
    if user.role_in(body.organization_id) == "farmer":
        plans = [p for p in plans if p["owner_user_id"] == user.user_id]
    S.EXPORTS[eid] = {"id": eid, "org_id": body.organization_id, "created_by": user.user_id,
                      "purpose": body.purpose, "include_individuals": body.include_individuals,
                      "plan_count": len(plans), "created_at": utcnow_iso()}
    audit_mod.emit("export.created", org_id=body.organization_id, actor_user_id=user.user_id,
                   target_kind="export", target_id=eid,
                   metadata={"purpose": body.purpose,
                             "include_individuals": body.include_individuals})
    return S.EXPORTS[eid]


@app.get("/api/v1/exports/{export_id}")
def get_export(export_id: str, user: UserContext = Depends(get_current_user)):
    exp = S.EXPORTS.get(export_id)
    if exp is None:
        raise _err(404, "not_found", "Export not found.")
    authorize(user, exp["org_id"])
    if exp["include_individuals"] and user.role_in(exp["org_id"]) not in ("org_admin", "platform_admin"):
        raise _err(403, "permission_denied", "Individual exports require administrator access.")
    if user.role_in(exp["org_id"]) == "farmer" and exp["created_by"] != user.user_id:
        raise _err(403, "permission_denied", "You do not have access to this export.")
    return exp


# --- audit events (privileged, ?40) ---
@app.get("/api/v1/audit-events")
def list_audit_events(org_id: str, action: str | None = None,
                      user: UserContext = Depends(get_current_user)):
    authorize(user, org_id, *AUDIT_ROLES)
    events = [e for e in audit_mod.AUDIT_LOG if e["org_id"] == org_id]
    if action:
        events = [e for e in events if e["action"] == action]
    return {"events": events}


# --- consent (operational vs research split, ?8.7) ---
@app.post("/api/v1/consents", status_code=201)
def give_consent(body: ConsentIn, org_id: str, user: UserContext = Depends(get_current_user)):
    authorize(user, org_id)
    return consent_mod.grant(user_id=user.user_id, org_id=org_id,
                             consent_type=body.consent_type, purpose=body.purpose,
                             policy_version=body.policy_version)


@app.post("/api/v1/consents/withdraw")
def withdraw_consent(body: ConsentWithdrawIn, org_id: str,
                     user: UserContext = Depends(get_current_user)):
    authorize(user, org_id)
    rec = consent_mod.withdraw(user_id=user.user_id, org_id=org_id,
                               consent_type=body.consent_type)
    if rec is None:
        raise _err(404, "no_active_consent", "No active consent of this type to withdraw.")
    return rec


@app.get("/api/v1/consents/me")
def my_consents(org_id: str, user: UserContext = Depends(get_current_user)):
    authorize(user, org_id)
    return {"consents": consent_mod.active_for(user.user_id, org_id=org_id)}


# --- observability self-view (no PII) ---
@app.get("/api/v1/observability/calculations")
def recent_calculations(org_id: str, user: UserContext = Depends(get_current_user)):
    authorize(user, org_id, *AUDIT_ROLES)
    rows = [row for row in CALC_LOGS if row["organization_id"] == org_id]
    counts = {state: sum(row["status"] == state for row in rows)
              for state in ("complete", "incomplete", "failed")}
    return {"calculations": rows[-50:], "counters": counts}
