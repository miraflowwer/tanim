import { ACCESS_TOKEN_KEY, ServerError, isServerError } from "../../lib/api";

export interface RevisionEntry {
  revisionNumber: number;
  areaHa: number;
  areaMarginHa: number;
  plantingDate: string;
  harvestPeriod: string;
  createdAt: string;
}

export interface CalculationEntry {
  calculationId: string;
  status: string;
  expectedProduction: string;
  coordinationState: string;
  engineVersion: string;
  policyVersion: string;
  yieldReference: string;
  comparisonReference: string;
}

function authed(): HeadersInit {
  const token = window.localStorage.getItem(ACCESS_TOKEN_KEY);
  return token
    ? { "content-type": "application/json", authorization: `Bearer ${token}` }
    : { "content-type": "application/json" };
}

async function getJson(path: string): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(path, { headers: authed() });
  } catch {
    throw new ServerError("SERVICE_UNAVAILABLE", 0);
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ServerError("SERVICE_UNAVAILABLE", response.status);
  return payload;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown, fallback: string): string {
  return typeof value === "string" && value.length > 0 ? value : fallback;
}

function decimal(value: unknown, fallback: string): string {
  return typeof value === "number" && Number.isFinite(value) ? String(value) : fallback;
}

// Plan revisions keep every adjustment. History shows revisions, never edits.
export async function fetchRevisions(planId: string): Promise<RevisionEntry[]> {
  const payload = await getJson(`/api/v1/plans/${encodeURIComponent(planId)}/revisions`);
  if (!isRecord(payload) || !Array.isArray(payload.revisions)) {
    throw new ServerError("SERVICE_UNAVAILABLE", 200);
  }
  return payload.revisions.flatMap((entry): RevisionEntry[] => {
    if (!isRecord(entry)) return [];
    return [{
      revisionNumber: typeof entry.revision_number === "number" ? entry.revision_number : 0,
      areaHa: typeof entry.area_ha === "number" ? entry.area_ha : 0,
      areaMarginHa: typeof entry.area_margin_ha === "number" ? entry.area_margin_ha : 0,
      plantingDate: text(entry.planting_date, "Not set"),
      harvestPeriod: text(entry.harvest_period, "Not set"),
      createdAt: text(entry.created_at, ""),
    }];
  });
}

// One stored calculation with the provenance recorded at calculation time.
// Old calculations keep old provenance even after references change.
export async function fetchCalculation(calculationId: string): Promise<CalculationEntry> {
  const payload = await getJson(`/api/v1/calculations/${encodeURIComponent(calculationId)}`);
  if (!isRecord(payload)) throw new ServerError("SERVICE_UNAVAILABLE", 200);
  const primary = isRecord(payload.primary) ? payload.primary : {};
  const detailed = isRecord(payload.detailed_evidence) ? payload.detailed_evidence : {};
  return {
    calculationId: text(payload.calculation_id, calculationId),
    status: text(primary.coordination_status, "unknown"),
    expectedProduction: decimal(primary.estimated_production_mt, "unavailable"),
    coordinationState: text(primary.coordination_status, "unknown"),
    engineVersion: text(detailed.engine_version, "unknown"),
    policyVersion: text(detailed.calculation_policy_version, "unknown"),
    yieldReference: text(detailed.yield_reference, "unknown"),
    comparisonReference: text(detailed.source, "unknown"),
  };
}

export { isServerError };
