// TANIM frontend contracts.
// API payloads stay snake_case at the boundary. UI view models use camelCase so
// serialization and deserialization happen in one place (lib/api.ts).

export type ReferenceType =
  | "local_committed_demand"
  | "local_historical_absorption"
  | "national_utilization_context"
  | "historical_production_baseline"
  | "demo_coordination_baseline";

export type VerificationStatus =
  | "reviewed_verified"
  | "user_provided_unverified"
  | "official_context"
  | "synthetic_demo"
  | "stale"
  | "superseded";

export type CoordinationStatus =
  | "low_coordination_load"
  | "elevated_coordination_load"
  | "high_coordination_load"
  | "historical_baseline_only"
  | "more_evidence_needed";

export type ErrorCode =
  | "CROP_UNSUPPORTED"
  | "YIELD_UNAVAILABLE"
  | "COMPARISON_UNAVAILABLE"
  | "SERVICE_UNAVAILABLE"
  | "STALE_EVIDENCE"
  | "VALIDATION_ERROR"
  | "UNAUTHORIZED"
  | "PERMISSION_DENIED"
  | "PLAN_INACTIVE"
  | "REFERENCE_TRANSITION";

export interface EvidenceProvenance {
  referenceType: ReferenceType | null;
  verificationStatus: VerificationStatus | null;
  source: string;
  geography: string;
  sourcePeriod: string;
  verifiedAt: string | null;
  calculationPolicyVersion: string;
  engineVersion: string;
  evidenceNote: string;
}

export interface CalculateResponse {
  calculationId: string;
  planId: string;
  crop: string;
  harvestPeriod: string;
  plannedAreaHa: number;
  estimatedProductionMt: number;
  estimatedRangeMt: { low: number; high: number };
  comparisonAmountMt: number | null;
  supplyLoad: number | null;
  coordinationStatus: CoordinationStatus;
  headline: string;
  evidenceQuality: string;
  referenceUsed: string;
  provenance: EvidenceProvenance;
  stale: boolean;
  synthetic: boolean;
}

export interface ApiErrorIssue {
  loc: Array<string | number>;
  msg: string;
  type: string;
}

export interface ApiError {
  code: ErrorCode;
  message: string;
  field?: string;
  issues?: ApiErrorIssue[];
}

export const ERROR_COPY: Record<ErrorCode, string> = {
  CROP_UNSUPPORTED:
    "TANIM does not yet have a safe production and area match for this crop.",
  YIELD_UNAVAILABLE:
    "TANIM cannot estimate production for this crop and region yet.",
  COMPARISON_UNAVAILABLE:
    "Expected production is available, but TANIM does not have a reviewed comparison reference.",
  SERVICE_UNAVAILABLE:
    "TANIM could not calculate this plan. Your entries have been kept. Try again.",
  STALE_EVIDENCE:
    "This result uses the latest verified reference available, but the source is older than expected.",
  VALIDATION_ERROR: "Check the highlighted fields and try again.",
  UNAUTHORIZED: "Sign in to continue.",
  PERMISSION_DENIED: "You do not have access to this record.",
  PLAN_INACTIVE: "This plan is no longer active.",
  REFERENCE_TRANSITION: "This reference cannot make that review transition.",
};

export interface ApiPlanResource {
  id: string;
  organizationId: string;
  farmId: string | null;
  cropCode: string;
  ownerUserId: string;
  status: "draft" | "planned" | "harvested" | "cancelled";
  revisionNumber: number;
  areaHa: number;
  areaMarginHa: number;
  plantingDate: string;
  harvestPeriod: string;
}

export interface Plan {
  id: string;
  crop: string;
  cropCode: string;
  farm: string;
  areaHa: number;
  marginHa: number;
  plantingDate: string;
  harvestPeriod: string;
  state: PlanState;
  updatedAt: string;
  scope: string;
  synthetic?: boolean;
}

export type PlanState = "Draft" | "Planned" | "Harvested" | "Cancelled";
export type Role = "farmer" | "reviewer";

export interface CropEntry {
  code: string;
  name: string;
  supported: boolean;
}

export type RefWorkflow = "draft" | "under_review" | "verified" | "rejected" | "superseded" | "expired";

export interface ReferenceRecord {
  id: string;
  crop: string;
  cropCode: string;
  amountMt: number;
  unit: "MT";
  referenceType: ReferenceType;
  geography: string;
  period: string;
  source: string;
  evidenceNote: string;
  reviewer: string;
  verificationStatus: VerificationStatus;
  effectiveDate: string;
  expiryState: string;
  version: string;
  workflow: RefWorkflow;
  verifiedAt: string;
  scope: string;
  synthetic: boolean;
}

export interface AggregateRow {
  cropCode: string;
  harvestPeriod: string;
  farmers: number;
  plannedAreaHa: number;
  estimatedProductionMt: number | null;
  plans: number;
}

export interface PriceObs {
  crop: string;
  cropCode: string;
  latestPrice: number;
  unit: string;
  date: string;
  geography: string;
  source: string;
  seriesId: string;
  trend: number[];
}

export interface ClimateCtx {
  source: string;
  issuedAt: string;
  summary: string;
  available: boolean;
}

export interface DataSourceRow {
  source: string;
  lastRefresh: string;
  expected: string;
  state: string;
  lastError: string | null;
  stale: boolean;
}

export interface NewPlanInput {
  cropCode: string;
  farm: string;
  areaHa: number;
  marginHa: number;
  plantingDate: string;
  harvestPeriod: string;
}
