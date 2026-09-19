import {
  ERROR_COPY,
  type ApiErrorIssue,
  type ApiPlanResource,
  type AggregateRow,
  type CalculationRun,
  type ConsentRecord,
  type ConsentType,
  type CropDetail,
  type Farm,
  type NewFarmInput,
  type PlanRevision,
  type ReferenceRecord,
  type RefWorkflow,
  type CalculateResponse,
  type CoordinationStatus,
  type ErrorCode,
  type NewPlanInput,
} from "../types";

export const ACCESS_TOKEN_KEY = "tanim.access_token";

export class ServerError extends Error {
  readonly code: ErrorCode;
  readonly field?: string;
  readonly status: number;
  readonly issues: ApiErrorIssue[];

  constructor(code: ErrorCode, status: number, message = ERROR_COPY[code], field?: string, issues: ApiErrorIssue[] = []) {
    super(message);
    this.name = "ServerError";
    this.code = code;
    this.status = status;
    this.field = field;
    this.issues = issues;
  }
}

export function isServerError(error: unknown): error is ServerError {
  return error instanceof ServerError;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function nullableNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function apiErrorCode(value: unknown): ErrorCode {
  switch (value) {
    case "crop_unsupported": return "CROP_UNSUPPORTED";
    case "yield_unavailable": return "YIELD_UNAVAILABLE";
    case "comparison_unavailable": return "COMPARISON_UNAVAILABLE";
    case "stale_evidence": return "STALE_EVIDENCE";
    case "unauthorized": return "UNAUTHORIZED";
    case "permission_denied": return "PERMISSION_DENIED";
    case "plan_inactive": return "PLAN_INACTIVE";
    case "invalid_reference_transition": return "REFERENCE_TRANSITION";
    case "validation_error":
    case "bad_request":
    case "payload_too_large": return "VALIDATION_ERROR";
    default: return "SERVICE_UNAVAILABLE";
  }
}

function parseIssues(value: unknown): ApiErrorIssue[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry): ApiErrorIssue[] => {
    if (!isRecord(entry)) return [];
    const loc = Array.isArray(entry.loc)
      ? entry.loc.filter((item): item is string | number => typeof item === "string" || typeof item === "number")
      : [];
    return [{
      loc,
      msg: stringValue(entry.msg, "Check this field."),
      type: stringValue(entry.type, "validation_error"),
    }];
  });
}

function parseServerError(payload: unknown, status: number): ServerError {
  const root = isRecord(payload) ? payload : {};
  const detail = isRecord(root.detail) ? root.detail : root;
  const issues = parseIssues(detail.errors);
  const firstLoc = issues[0]?.loc;
  const fields = firstLoc?.filter((part): part is string => typeof part === "string") ?? [];
  const field = fields[fields.length - 1];
  const code = apiErrorCode(detail.code);
  const message = stringValue(detail.message, ERROR_COPY[code]);
  return new ServerError(code, status, message, field, issues);
}

function authHeaders(): HeadersInit {
  const token = window.localStorage.getItem(ACCESS_TOKEN_KEY);
  return token
    ? { "content-type": "application/json", authorization: `Bearer ${token}` }
    : { "content-type": "application/json" };
}

async function apiRequest<T>(
  method: "GET" | "POST" | "PATCH" | "DELETE",
  path: string,
  body: unknown,
  decode: (value: unknown) => T,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers: authHeaders(),
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch {
    throw new ServerError("SERVICE_UNAVAILABLE", 0);
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) throw parseServerError(payload, response.status);
  return decode(payload);
}

function post<T>(path: string, body: unknown, decode: (value: unknown) => T): Promise<T> {
  return apiRequest("POST", path, body, decode);
}

function get<T>(path: string, decode: (value: unknown) => T): Promise<T> {
  return apiRequest("GET", path, undefined, decode);
}

function patch<T>(path: string, body: unknown, decode: (value: unknown) => T): Promise<T> {
  return apiRequest("PATCH", path, body, decode);
}

function del<T>(path: string, decode: (value: unknown) => T): Promise<T> {
  return apiRequest("DELETE", path, undefined, decode);
}

function dateForApi(value: string): string {
  const quarter = /^(\d{4})-Q([1-4])$/.exec(value.trim());
  if (quarter) {
    const month = (Number(quarter[2]) - 1) * 3 + 1;
    return `${quarter[1]}-${String(month).padStart(2, "0")}-01`;
  }
  return value;
}

function planStatus(value: unknown): ApiPlanResource["status"] {
  switch (value) {
    case "draft":
    case "planned":
    case "harvested":
    case "cancelled":
      return value;
    default:
      throw new ServerError("SERVICE_UNAVAILABLE", 200, "The API returned an unknown plan status.");
  }
}

function decodePlan(value: unknown): ApiPlanResource {
  const root = requiredRecord(value, "plan");
  const revision = requiredRecord(root.revision, "plan revision");
  const id = requiredString(root.id, "plan ID");
  return {
    id,
    organizationId: requiredString(root.org_id, "plan organization"),
    farmId: typeof root.farm_id === "string" ? root.farm_id : null,
    cropCode: requiredString(root.crop_code, "plan crop"),
    ownerUserId: requiredString(root.owner_user_id, "plan owner"),
    status: planStatus(root.status),
    revisionNumber: requiredNumber(revision.revision_number, "revision number"),
    areaHa: requiredNumber(revision.area_ha, "plan area"),
    areaMarginHa: requiredNumber(revision.area_margin_ha, "plan uncertainty"),
    plantingDate: requiredString(revision.planting_date, "planting date"),
    harvestPeriod: requiredString(revision.harvest_period, "harvest period"),
  };
}

function parseCoordinationStatus(value: unknown): CoordinationStatus {
  switch (value) {
    case "within_reference": return "low_coordination_load";
    case "elevated_coordination_load": return "elevated_coordination_load";
    case "high_coordination_load": return "high_coordination_load";
    case "historical_baseline_only": return "historical_baseline_only";
    case "insufficient_evidence": return "more_evidence_needed";
    default: throw new ServerError("SERVICE_UNAVAILABLE", 200, "The API returned an unknown coordination status.");
  }
}

function referenceType(value: unknown) {
  switch (value) {
    case "local_committed_demand":
    case "local_historical_absorption":
    case "national_utilization_context":
    case "historical_production_baseline":
    case "demo_coordination_baseline":
      return value;
    case null:
    case undefined:
      return null;
    default:
      throw new ServerError("SERVICE_UNAVAILABLE", 200, "The API returned an unknown reference type.");
  }
}

function decodeCalculation(value: unknown, context: { crop: string; harvestPeriod: string }): CalculateResponse {
  const root = requiredRecord(value, "calculation");
  const primary = requiredRecord(root.primary, "calculation summary");
  const secondary = requiredRecord(root.secondary, "calculation detail");
  const detailed = requiredRecord(root.detailed_evidence, "calculation evidence");
  const range = secondary.estimated_range_mt;
  if (!Array.isArray(range) || range.length !== 2) {
    throw new ServerError("SERVICE_UNAVAILABLE", 200, "The API returned an invalid production range.");
  }
  const low = requiredNumber(range[0], "lower production estimate");
  const high = requiredNumber(range[1], "upper production estimate");
  const provenanceStatus = detailed.verification_date ? "reviewed_verified" : null;
  const provenanceType = referenceType(detailed.reference_type);
  const evidenceQuality = stringValue(secondary.evidence_quality, "none");
  return {
    calculationId: requiredString(root.calculation_id, "calculation ID"),
    planId: requiredString(root.plan_id, "calculation plan ID"),
    crop: context.crop,
    harvestPeriod: context.harvestPeriod,
    plannedAreaHa: requiredNumber(primary.planned_area_ha, "planned area"),
    estimatedProductionMt: requiredNumber(primary.estimated_production_mt, "production estimate"),
    estimatedRangeMt: { low, high },
    comparisonAmountMt: nullableNumber(secondary.comparison_amount_mt),
    supplyLoad: nullableNumber(secondary.supply_load),
    coordinationStatus: parseCoordinationStatus(primary.coordination_status),
    headline: stringValue(primary.message, ERROR_COPY.COMPARISON_UNAVAILABLE),
    evidenceQuality,
    referenceUsed: stringValue(primary.reference_used, "No reviewed reference"),
    provenance: {
      referenceType: provenanceType,
      verificationStatus: provenanceStatus,
      source: stringValue(detailed.source, "No reviewed reference"),
      geography: stringValue(detailed.geography),
      sourcePeriod: stringValue(detailed.source_period),
      verifiedAt: typeof detailed.verification_date === "string" ? detailed.verification_date : null,
      calculationPolicyVersion: typeof detailed.calculation_policy_version === "string" || typeof detailed.calculation_policy_version === "number"
        ? detailed.calculation_policy_version.toString()
        : "unknown",
      engineVersion: stringValue(detailed.engine_version),
      evidenceNote: stringValue(detailed.evidence_note, "No reviewed comparison reference."),
    },
    stale: isRecord(detailed.freshness) && detailed.freshness.state === "stale",
    synthetic: provenanceType === "demo_coordination_baseline" || evidenceQuality === "synthetic_demo",
  };
}

export async function createFarm(organizationId: string, name: string): Promise<{ id: string }> {
  return post("/api/v1/farms", { organization_id: organizationId, name }, (payload) => {
    const root = requiredRecord(payload, "farm");
    return { id: requiredString(root.id, "farm ID") };
  });
}

export async function createPlan(input: NewPlanInput & { organizationId: string; farmId: string }): Promise<ApiPlanResource> {
  return post("/api/v1/plans", {
    crop_code: input.cropCode,
    organization_id: input.organizationId,
    farm_id: input.farmId,
    area_ha: input.areaHa,
    area_margin_ha: input.marginHa,
    planting_date: input.plantingDate,
    harvest_period: dateForApi(input.harvestPeriod),
  }, decodePlan);
}

export async function calculatePlan(
  planId: string,
  context: { crop: string; harvestPeriod: string },
): Promise<CalculateResponse> {
  return post(
    `/api/v1/plans/${encodeURIComponent(planId)}/calculate`,
    {},
    (value) => decodeCalculation(value, context),
  );
}

export async function signIn(userId: string): Promise<void> {
  const response = await post(
    "/api/v1/auth/session",
    { user_id: userId },
    (value) => {
      const root = isRecord(value) ? value : {};
      const token = stringValue(root.access_token);
      if (!token) throw new ServerError("SERVICE_UNAVAILABLE", 200, "The API returned no access token.");
      return { access_token: token };
    },
  );
  window.localStorage.setItem(ACCESS_TOKEN_KEY, response.access_token);
  window.dispatchEvent(new Event("tanim:auth-changed"));
}

export function clearSession(): void {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.dispatchEvent(new Event("tanim:auth-changed"));
}

export async function fetchMyRole(organizationId: string): Promise<"farmer" | "reviewer"> {
  return get("/api/v1/me", (payload) => {
    const root = requiredRecord(payload, "identity");
    const roles = requiredRecord(root.org_roles, "organization roles");
    return roles[organizationId] === "reviewer" || root.is_platform === true ? "reviewer" : "farmer";
  });
}

function requiredRecord(value: unknown, name: string): Record<string, unknown> {
  if (!isRecord(value)) throw new ServerError("SERVICE_UNAVAILABLE", 200, `The API returned an invalid ${name}.`);
  return value;
}

function requiredString(value: unknown, name: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new ServerError("SERVICE_UNAVAILABLE", 200, `The API returned an invalid ${name}.`);
  }
  return value;
}

function requiredNumber(value: unknown, name: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new ServerError("SERVICE_UNAVAILABLE", 200, `The API returned an invalid ${name}.`);
  }
  return value;
}

export async function updatePlan(
  planId: string,
  input: { areaHa: number; plantingDate: string; harvestPeriod: string },
): Promise<ApiPlanResource> {
  return patch(`/api/v1/plans/${encodeURIComponent(planId)}`, {
    area_ha: input.areaHa,
    planting_date: input.plantingDate,
    harvest_period: dateForApi(input.harvestPeriod),
  }, decodePlan);
}

export async function fetchAggregates(organizationId: string): Promise<AggregateRow[]> {
  return get(`/api/v1/organizations/${encodeURIComponent(organizationId)}/aggregates`, (payload) => {
    const root = requiredRecord(payload, "aggregate response");
    if (!Array.isArray(root.rows)) throw new ServerError("SERVICE_UNAVAILABLE", 200, "The API returned invalid aggregate rows.");
    return root.rows.map((item): AggregateRow => {
      const row = requiredRecord(item, "aggregate row");
      return {
        cropCode: requiredString(row.crop_code, "aggregate crop"),
        harvestPeriod: requiredString(row.harvest_period, "aggregate period"),
        farmers: requiredNumber(row.farmers, "farmer count"),
        plannedAreaHa: requiredNumber(row.planned_area_ha, "planned area"),
        estimatedProductionMt: row.estimated_production_mt === null ? null
          : requiredNumber(row.estimated_production_mt, "production estimate"),
        plans: requiredNumber(row.plans, "plan count"),
      };
    });
  });
}

function reviewState(value: unknown): RefWorkflow {
  switch (value) {
    case "draft":
    case "under_review":
    case "verified":
    case "rejected":
    case "superseded":
    case "expired":
      return value;
    default:
      throw new ServerError("SERVICE_UNAVAILABLE", 200, "The API returned an unknown review state.");
  }
}

function decodeReference(value: unknown): ReferenceRecord {
  const row = requiredRecord(value, "reference");
  const kind = referenceType(row.reference_type);
  if (kind === null) throw new ServerError("SERVICE_UNAVAILABLE", 200, "The API returned an unknown reference type.");
  const verification = stringValue(row.verification_status);
  const knownVerification = [
    "reviewed_verified", "user_provided_unverified", "official_context",
    "synthetic_demo", "stale", "superseded",
  ];
  if (!knownVerification.includes(verification)) {
    throw new ServerError("SERVICE_UNAVAILABLE", 200, "The API returned an unknown verification state.");
  }
  // The server owns review and verification. This view model never upgrades evidence.
  return {
    id: requiredString(row.id, "reference ID"),
    crop: requiredString(row.crop_code, "reference crop"),
    cropCode: requiredString(row.crop_code, "reference crop"),
    amountMt: requiredNumber(row.amount_mt, "reference amount"),
    unit: "MT",
    referenceType: kind,
    geography: requiredString(row.geography, "reference geography"),
    period: requiredString(row.period, "reference period"),
    source: requiredString(row.source, "reference source"),
    evidenceNote: stringValue(row.evidence_note),
    reviewer: stringValue(row.reviewer_id, "Not reviewed"),
    verificationStatus: verification === "reviewed_verified" ? "reviewed_verified"
      : verification === "official_context" ? "official_context"
      : verification === "synthetic_demo" ? "synthetic_demo"
      : verification === "stale" ? "stale"
      : verification === "superseded" ? "superseded"
      : "user_provided_unverified",
    effectiveDate: stringValue(row.effective_from, "Not set"),
    expiryState: stringValue(row.effective_to, "Open ended"),
    version: String(requiredNumber(row.version, "reference version")),
    workflow: reviewState(row.review),
    verifiedAt: stringValue(row.verified_at),
    scope: requiredString(row.geography, "reference geography"),
    synthetic: kind === "demo_coordination_baseline" || verification === "synthetic_demo",
  };
}

export async function fetchReferences(organizationId: string): Promise<ReferenceRecord[]> {
  return get(`/api/v1/references?org_id=${encodeURIComponent(organizationId)}`, (payload) => {
    const root = requiredRecord(payload, "reference list");
    if (!Array.isArray(root.references)) throw new ServerError("SERVICE_UNAVAILABLE", 200, "The API returned an invalid reference list.");
    return root.references.map(decodeReference);
  });
}

// --- Member 1 Wave A: farms / plans / calculations / crops / consent ---
// All wrappers hit the real versioned API. Anything the backend does not
// offer yet is filed in docs/implementation/API_REQUESTS.md, never faked here.

function decodeFarm(value: unknown): Farm {
  const root = requiredRecord(value, "farm");
  const total = root.total_area_ha;
  return {
    id: requiredString(root.id, "farm ID"),
    organizationId: requiredString(root.org_id ?? root.organization_id, "farm organization"),
    name: requiredString(root.name, "farm name"),
    municipality: typeof root.municipality === "string" ? root.municipality : null,
    region: typeof root.region === "string" ? root.region : null,
    totalAreaHa: typeof total === "number" && Number.isFinite(total) ? total : null,
    mine: true, // list endpoint already scopes farmers to their own farms
  };
}

export async function fetchFarms(organizationId: string): Promise<Farm[]> {
  return get(`/api/v1/farms?org_id=${encodeURIComponent(organizationId)}`, (payload) => {
    const root = requiredRecord(payload, "farm list");
    if (!Array.isArray(root.farms)) throw new ServerError("SERVICE_UNAVAILABLE", 200, "The API returned an invalid farm list.");
    return root.farms.map(decodeFarm);
  });
}

export async function fetchFarm(farmId: string): Promise<Farm> {
  return get(`/api/v1/farms/${encodeURIComponent(farmId)}`, decodeFarm);
}

export async function createFarmFull(organizationId: string, input: NewFarmInput): Promise<Farm> {
  return post("/api/v1/farms", {
    organization_id: organizationId,
    name: input.name,
    municipality: input.municipality || null,
    region: input.region || null,
    total_area_ha: input.totalAreaHa,
  }, decodeFarm);
}

export async function updateFarm(farmId: string, organizationId: string, input: NewFarmInput): Promise<Farm> {
  return patch(`/api/v1/farms/${encodeURIComponent(farmId)}`, {
    organization_id: organizationId,
    name: input.name,
    municipality: input.municipality || null,
    region: input.region || null,
    total_area_ha: input.totalAreaHa,
  }, decodeFarm);
}

export async function fetchPlans(organizationId: string): Promise<ApiPlanResource[]> {
  return get(`/api/v1/plans?org_id=${encodeURIComponent(organizationId)}`, (payload) => {
    const root = requiredRecord(payload, "plan list");
    if (!Array.isArray(root.plans)) throw new ServerError("SERVICE_UNAVAILABLE", 200, "The API returned an invalid plan list.");
    return root.plans.map(decodePlan);
  });
}

export async function fetchPlan(planId: string): Promise<ApiPlanResource> {
  return get(`/api/v1/plans/${encodeURIComponent(planId)}`, decodePlan);
}

export async function cancelPlan(planId: string): Promise<void> {
  await del(`/api/v1/plans/${encodeURIComponent(planId)}`, () => undefined);
}

function decodeRevision(value: unknown): PlanRevision {
  const root = requiredRecord(value, "plan revision");
  return {
    revisionNumber: requiredNumber(root.revision_number, "revision number"),
    areaHa: requiredNumber(root.area_ha, "revision area"),
    areaMarginHa: requiredNumber(root.area_margin_ha ?? 0, "revision uncertainty"),
    plantingDate: stringValue(root.planting_date),
    harvestPeriod: stringValue(root.harvest_period),
    createdBy: stringValue(root.created_by),
    createdAt: stringValue(root.created_at),
  };
}

export async function fetchRevisions(planId: string): Promise<PlanRevision[]> {
  return get(`/api/v1/plans/${encodeURIComponent(planId)}/revisions`, (payload) => {
    const root = requiredRecord(payload, "revision list");
    if (!Array.isArray(root.revisions)) throw new ServerError("SERVICE_UNAVAILABLE", 200, "The API returned invalid revisions.");
    return root.revisions.map(decodeRevision);
  });
}

export async function fetchCalculation(
  calculationId: string,
  context: { crop: string; harvestPeriod: string },
): Promise<CalculateResponse> {
  return get(`/api/v1/calculations/${encodeURIComponent(calculationId)}`, (value) =>
    decodeCalculation(value, context));
}

export function toCalculationRuns(
  revisions: PlanRevision[],
  latest: CalculateResponse | undefined,
): CalculationRun[] {
  return revisions.map((rev) => ({
    calculationId: latest && rev.revisionNumber === revisions.length ? latest.calculationId : `rev-${rev.revisionNumber}`,
    revisionNumber: rev.revisionNumber,
    timestamp: rev.createdAt,
    engineVersion: latest?.provenance.engineVersion ?? "unknown",
    policyVersion: latest?.provenance.calculationPolicyVersion ?? "unknown",
    status: latest && rev.revisionNumber === revisions.length ? latest.coordinationStatus : "more_evidence_needed",
    expectedProductionMt: latest && rev.revisionNumber === revisions.length ? latest.estimatedProductionMt : null,
    coordinationState: latest && rev.revisionNumber === revisions.length ? latest.headline : "No calculation recorded for this revision yet.",
  }));
}

export async function fetchCrops(): Promise<CropDetail[]> {
  return get("/api/v1/crops", (payload) => {
    const root = requiredRecord(payload, "crop list");
    if (!Array.isArray(root.crops)) throw new ServerError("SERVICE_UNAVAILABLE", 200, "The API returned an invalid crop list.");
    return root.crops.map((item): CropDetail => {
      const row = requiredRecord(item, "crop");
      const code = requiredString(row.code ?? row.crop_code, "crop code");
      return {
        code,
        name: stringValue(row.name, code),
        supported: row.is_active !== false,
        yieldMtPerHa: nullableNumber(row.yield_mt_per_ha),
        yieldGeography: typeof row.geography === "string" ? row.geography : null,
        priceNote: "Market price is context only — never the reviewed comparison reference.",
        climateNote: "Suitability and climate are context only, not planting recommendations.",
        suitabilityNote: "Suitability is contextual information, not an automatic planting recommendation.",
      };
    });
  });
}

export async function fetchCropYield(code: string, geography: string): Promise<number | null> {
  try {
    const row = await get(
      `/api/v1/crops/${encodeURIComponent(code)}/yield?geography=${encodeURIComponent(geography)}`,
      (payload) => requiredRecord(payload, "yield reference"),
    );
    return nullableNumber(row.yield_mt_per_ha);
  } catch (error: unknown) {
    if (isServerError(error) && (error.code === "YIELD_UNAVAILABLE" || error.status === 404)) return null;
    throw error;
  }
}

export interface PriceRow {
  cropCode: string;
  price: number;
  unit: string;
  date: string;
  geography: string;
  source: string;
}

export async function fetchPrices(cropCode?: string): Promise<PriceRow[]> {
  const query = cropCode ? `?crop_code=${encodeURIComponent(cropCode)}` : "";
  return get(`/api/v1/prices${query}`, (payload) => {
    const root = requiredRecord(payload, "price list");
    if (!Array.isArray(root.prices)) return [];
    return root.prices.map((item): PriceRow => {
      const row = requiredRecord(item, "price");
      return {
        cropCode: stringValue(row.crop_code),
        price: nullableNumber(row.price ?? row.latest_price) ?? 0,
        unit: stringValue(row.unit, "PHP/kg"),
        date: stringValue(row.date),
        geography: stringValue(row.geography),
        source: stringValue(row.source),
      };
    });
  });
}

export async function fetchClimateNote(geography?: string): Promise<string> {
  const query = geography ? `?geography=${encodeURIComponent(geography)}` : "";
  const rows = await get(`/api/v1/context/climate${query}`, (payload) => {
    const root = requiredRecord(payload, "climate");
    return Array.isArray(root.climate) ? root.climate : [];
  });
  if (rows.length === 0) return "Weather context is not available right now. Your coordination result does not depend on it.";
  const first = requiredRecord(rows[0], "climate row");
  return stringValue(first.summary ?? first.outlook, "Seasonal outlook available. Context only — not part of the coordination result.");
}

export async function fetchMyConsents(organizationId: string): Promise<ConsentRecord[]> {
  return get(`/api/v1/consents/me?org_id=${encodeURIComponent(organizationId)}`, (payload) => {
    const root = requiredRecord(payload, "consent list");
    if (!Array.isArray(root.consents)) return [];
    return root.consents.map((item): ConsentRecord => {
      const row = requiredRecord(item, "consent");
      const kind = stringValue(row.consent_type);
      return {
        consentType: kind === "research" ? "research" : "operational",
        purpose: stringValue(row.purpose),
        policyVersion: stringValue(row.policy_version),
        active: row.active !== false,
      };
    });
  });
}

export async function grantConsent(
  organizationId: string,
  consentType: ConsentType,
  purpose: string,
  policyVersion: string,
): Promise<void> {
  await post(`/api/v1/consents?org_id=${encodeURIComponent(organizationId)}`, {
    consent_type: consentType,
    purpose,
    policy_version: policyVersion,
  }, () => undefined);
}

export async function withdrawConsent(organizationId: string, consentType: ConsentType): Promise<void> {
  await post(`/api/v1/consents/withdraw?org_id=${encodeURIComponent(organizationId)}`, {
    consent_type: consentType,
  }, () => undefined);
}

export async function transitionReference(
  referenceId: string,
  next: "under_review" | "verified" | "rejected" | "draft" | "expired",
): Promise<ReferenceRecord> {
  const suffix = {
    under_review: "submit",
    verified: "verify",
    rejected: "reject",
    draft: "reopen",
    expired: "expire",
  }[next];
  return post(`/api/v1/references/${encodeURIComponent(referenceId)}/${suffix}`, {}, decodeReference);
}
