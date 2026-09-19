import { ACCESS_TOKEN_KEY, ServerError, isServerError } from "../../lib/api";

export interface MemberRow {
  id: string;
  role: string;
  state: string;
}

export interface InvitationRow {
  id: string;
  role: string;
  created: string;
  expiry: string;
  status: string;
}

export interface AuditRow {
  id: string;
  time: string;
  actor: string;
  action: string;
  target: string;
  summary: string;
}

export interface ExportRecord {
  id: string;
  purpose: string;
  includeIndividuals: boolean;
  planCount: number;
  createdAt: string;
}

export interface PolicyRecord {
  id: string;
  version: number;
  elevatedLoad: number;
  highLoad: number;
  createdBy: string;
  createdAt: string;
}

function authed(): HeadersInit {
  const token = window.localStorage.getItem(ACCESS_TOKEN_KEY);
  return token
    ? { "content-type": "application/json", authorization: `Bearer ${token}` }
    : { "content-type": "application/json" };
}

async function request<T>(method: string, path: string, body: unknown, decode: (value: unknown) => T): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers: authed(),
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch {
    throw new ServerError("SERVICE_UNAVAILABLE", 0);
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ServerError("SERVICE_UNAVAILABLE", response.status);
  return decode(payload);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown, fallback: string): string {
  return typeof value === "string" && value.length > 0 ? value : fallback;
}

function decodeAudit(value: unknown): AuditRow[] {
  if (!isRecord(value) || !Array.isArray(value.events)) {
    throw new ServerError("SERVICE_UNAVAILABLE", 200);
  }
  return value.events.flatMap((entry): AuditRow[] => {
    if (!isRecord(entry)) return [];
    const metadata = isRecord(entry.metadata) ? entry.metadata : {};
    return [{
      id: text(entry.id, ""),
      time: text(entry.created_at, ""),
      actor: text(entry.actor_user_id, "Unknown"),
      action: text(entry.action, ""),
      target: `${text(entry.target_kind, "")}:${text(entry.target_id, "")}`,
      summary: text(metadata.purpose, text(metadata.role, text(metadata.note, ""))),
    }];
  });
}

export async function fetchAudit(orgId: string, action?: string): Promise<AuditRow[]> {
  const query = action
    ? `?org_id=${encodeURIComponent(orgId)}&action=${encodeURIComponent(action)}`
    : `?org_id=${encodeURIComponent(orgId)}`;
  return request("GET", `/api/v1/audit-events${query}`, undefined, decodeAudit);
}

export async function changeMemberRole(orgId: string, memberId: string, role: string): Promise<void> {
  await request(
    "PUT",
    `/api/v1/organizations/${encodeURIComponent(orgId)}/members/${encodeURIComponent(memberId)}`,
    { role },
    () => undefined,
  );
}

export async function removeMember(orgId: string, memberId: string): Promise<void> {
  await request(
    "DELETE",
    `/api/v1/organizations/${encodeURIComponent(orgId)}/members/${encodeURIComponent(memberId)}`,
    undefined,
    () => undefined,
  );
}

export async function createExport(orgId: string, purpose: string, includeIndividuals: boolean): Promise<ExportRecord> {
  return request("POST", "/api/v1/exports", {
    organization_id: orgId,
    purpose,
    include_individuals: includeIndividuals,
  }, (value): ExportRecord => {
    if (!isRecord(value)) throw new ServerError("SERVICE_UNAVAILABLE", 200);
    return {
      id: text(value.id, ""),
      purpose: text(value.purpose, purpose),
      includeIndividuals: value.include_individuals === true,
      planCount: typeof value.plan_count === "number" ? value.plan_count : 0,
      createdAt: text(value.created_at, ""),
    };
  });
}

export async function fetchExport(exportId: string): Promise<ExportRecord> {
  return request("GET", `/api/v1/exports/${encodeURIComponent(exportId)}`, undefined, (value): ExportRecord => {
    if (!isRecord(value)) throw new ServerError("SERVICE_UNAVAILABLE", 200);
    return {
      id: text(value.id, exportId),
      purpose: text(value.purpose, ""),
      includeIndividuals: value.include_individuals === true,
      planCount: typeof value.plan_count === "number" ? value.plan_count : 0,
      createdAt: text(value.created_at, ""),
    };
  });
}

export async function fetchPolicy(): Promise<PolicyRecord> {
  return request("GET", "/api/v1/policies/latest", undefined, (value): PolicyRecord => {
    if (!isRecord(value)) throw new ServerError("SERVICE_UNAVAILABLE", 200);
    const thresholds = isRecord(value.thresholds) ? value.thresholds : {};
    return {
      id: text(value.id, ""),
      version: typeof value.version === "number" ? value.version : 0,
      elevatedLoad: typeof thresholds.elevated_load === "number" ? thresholds.elevated_load : 0,
      highLoad: typeof thresholds.high_load === "number" ? thresholds.high_load : 0,
      createdBy: text(value.created_by, ""),
      createdAt: text(value.created_at, ""),
    };
  });
}

export { isServerError };
