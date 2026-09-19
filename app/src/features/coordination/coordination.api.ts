import { ACCESS_TOKEN_KEY, ServerError, isServerError } from "../../lib/api";

export interface CoordinatorPlanDetail {
  id: string;
  cropCode: string;
  status: string;
  revisionNumber: number;
  areaHa: number;
  areaMarginHa: number;
  plantingDate: string;
  harvestPeriod: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown, fallback: string): string {
  return typeof value === "string" && value.length > 0 ? value : fallback;
}

function decimal(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

async function getJson(path: string): Promise<unknown> {
  const token = window.localStorage.getItem(ACCESS_TOKEN_KEY);
  let response: Response;
  try {
    response = await fetch(path, {
      headers: token
        ? { "content-type": "application/json", authorization: `Bearer ${token}` }
        : { "content-type": "application/json" },
    });
  } catch {
    throw new ServerError("SERVICE_UNAVAILABLE", 0);
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ServerError("SERVICE_UNAVAILABLE", response.status);
  return payload;
}

// Server-authorized plan fields only. The server decides visibility;
// this client only displays returned fields.
export async function fetchCoordinatorPlan(planId: string): Promise<CoordinatorPlanDetail> {
  const payload = await getJson(`/api/v1/plans/${encodeURIComponent(planId)}`);
  if (!isRecord(payload)) throw new ServerError("SERVICE_UNAVAILABLE", 200);
  const revision = isRecord(payload.revision) ? payload.revision : {};
  return {
    id: text(payload.id, planId),
    cropCode: text(payload.crop_code, "unknown"),
    status: text(payload.status, "unknown"),
    revisionNumber: decimal(revision.revision_number, 1),
    areaHa: decimal(revision.area_ha, 0),
    areaMarginHa: decimal(revision.area_margin_ha, 0),
    plantingDate: text(revision.planting_date, "Not set"),
    harvestPeriod: text(revision.harvest_period, "Not set"),
  };
}

export { isServerError };
