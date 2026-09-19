import type { ReferenceType } from "../../types";

export interface CandidateInput {
  cropCode: string;
  amountMt: number;
  referenceType: ReferenceType;
  geography: string;
  period: string;
  source: string;
  evidenceNote: string;
  effectiveFrom: string;
  effectiveTo: string;
}

export interface ReviewHistoryEntry {
  action: string;
  actor: string;
  at: string;
  note: string;
}

export interface ReferenceVersionEntry {
  version: number;
  review: string;
  verificationStatus: string;
  amountMt: number;
  predecessorId: string | null;
  successorId: string | null;
}

export interface ReferenceDetailModel {
  id: string;
  crop: string;
  cropCode: string;
  amountMt: number;
  referenceType: ReferenceType | null;
  geography: string;
  period: string;
  source: string;
  evidenceNote: string;
  reviewer: string;
  verificationStatus: string;
  workflow: string;
  version: number;
  verifiedAt: string;
  effectiveFrom: string;
  effectiveTo: string;
  predecessorId: string | null;
  successorId: string | null;
  flags: Array<{ by: string; note: string; at: string }>;
  history: ReviewHistoryEntry[];
  synthetic: boolean;
}
