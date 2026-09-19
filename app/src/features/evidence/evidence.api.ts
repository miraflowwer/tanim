import { ACCESS_TOKEN_KEY, ServerError, isServerError } from "../../lib/api";
import type { CandidateInput, ReferenceDetailModel, ReviewHistoryEntry } from "./evidence.types";

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

function historyOf(value: unknown): ReviewHistoryEntry[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry): ReviewHistoryEntry[] => {
    if (!isRecord(entry)) return [];
    return [{
      action: text(entry.action, "reviewed"),
      actor: text(entry.actor_user_id, text(entry.actor, "Unknown reviewer")),
      at: text(entry.at, text(entry.created_at, "")),
      note: text(entry.note, ""),
    }];
  });
}

function decodeDetail(value: unknown): ReferenceDetailModel {
  if (!isRecord(value)) throw new ServerError("SERVICE_UNAVAILABLE", 200);
  const flags = Array.isArray(value.flags) ? value.flags.flatMap((flag) => {
    if (!isRecord(flag)) return [];
    return [{ by: text(flag.by, "Unknown"), note: text(flag.note, ""), at: text(flag.at, "") }];
  }) : [];
  return {
    id: text(value.id, ""),
    crop: text(value.crop_code, ""),
    cropCode: text(value.crop_code, ""),
    amountMt: typeof value.amount_mt === "number" ? value.amount_mt : 0,
    referenceType: null,
    geography: text(value.geography, ""),
    period: text(value.period, ""),
    source: text(value.source, ""),
    evidenceNote: text(value.evidence_note, ""),
    reviewer: text(value.reviewer_id, "Not reviewed"),
    verificationStatus: text(value.verification_status, ""),
    workflow: text(value.review, ""),
    version: typeof value.version === "number" ? value.version : 1,
    verifiedAt: text(value.verified_at, ""),
    effectiveFrom: text(value.effective_from, "Not set"),
    effectiveTo: text(value.effective_to, "Open ended"),
    predecessorId: typeof value.predecessor_id === "string" ? value.predecessor_id : null,
    successorId: typeof value.successor_id === "string" ? value.successor_id : null,
    flags,
    history: historyOf(value.review_history),
    synthetic: value.reference_type === "demo_coordination_baseline"
      || value.verification_status === "synthetic_demo",
  };
}

export async function fetchReferenceDetail(refId: string): Promise<ReferenceDetailModel> {
  return request("GET", `/api/v1/references/${encodeURIComponent(refId)}`, undefined, decodeDetail);
}

export async function createCandidate(input: CandidateInput & { organizationId: string }): Promise<ReferenceDetailModel> {
  return request("POST", "/api/v1/references", {
    crop_code: input.cropCode,
    organization_id: input.organizationId,
    amount_mt: input.amountMt,
    unit: "MT",
    reference_type: input.referenceType,
    geography: input.geography,
    period: input.period,
    source: input.source,
    evidence_note: input.evidenceNote || null,
    effective_from: input.effectiveFrom || null,
    effective_to: input.effectiveTo || null,
  }, decodeDetail);
}

export async function correctCandidate(refId: string, input: CandidateInput & { organizationId: string }): Promise<ReferenceDetailModel> {
  return request("PATCH", `/api/v1/references/${encodeURIComponent(refId)}`, {
    crop_code: input.cropCode,
    organization_id: input.organizationId,
    amount_mt: input.amountMt,
    unit: "MT",
    reference_type: input.referenceType,
    geography: input.geography,
    period: input.period,
    source: input.source,
    evidence_note: input.evidenceNote || null,
    effective_from: input.effectiveFrom || null,
    effective_to: input.effectiveTo || null,
  }, decodeDetail);
}

export async function supersedeReference(refId: string, input: CandidateInput & { organizationId: string }): Promise<ReferenceDetailModel> {
  return request("POST", `/api/v1/references/${encodeURIComponent(refId)}/supersede`, {
    crop_code: input.cropCode,
    organization_id: input.organizationId,
    amount_mt: input.amountMt,
    unit: "MT",
    reference_type: input.referenceType,
    geography: input.geography,
    period: input.period,
    source: input.source,
    evidence_note: input.evidenceNote || null,
    effective_from: input.effectiveFrom || null,
    effective_to: input.effectiveTo || null,
  }, decodeDetail);
}

export async function flagReference(refId: string, note: string): Promise<void> {
  await request("POST", `/api/v1/references/${encodeURIComponent(refId)}/flag`, { note }, () => undefined);
}

// Review transitions with an optional reviewer note. The server owns every
// transition and rejects illegal moves; this client forwards the request
// and surfaces the server answer.
export async function transitionWithNote(
  refId: string,
  action: "submit" | "verify" | "reject" | "reopen" | "expire",
  note: string,
): Promise<ReferenceDetailModel> {
  const body = { note: note.trim() === "" ? null : note };
  const id = encodeURIComponent(refId);
  switch (action) {
    case "submit":
      return request("POST", `/api/v1/references/${id}/submit`, body, decodeDetail);
    case "verify":
      return request("POST", `/api/v1/references/${id}/verify`, body, decodeDetail);
    case "reject":
      return request("POST", `/api/v1/references/${id}/reject`, body, decodeDetail);
    case "reopen":
      return request("POST", `/api/v1/references/${id}/reopen`, body, decodeDetail);
    case "expire":
      return request("POST", `/api/v1/references/${id}/expire`, body, decodeDetail);
  }
}

export { isServerError };
