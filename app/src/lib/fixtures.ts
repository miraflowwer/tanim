import tomatoSnapshot from "../fixtures/tomato_calabarzon_response.json";
import type { CalculateResponse, CoordinationStatus, Plan, ReferenceType, VerificationStatus } from "../types";

function coordinationStatus(value: string): CoordinationStatus {
  switch (value) {
    case "low_coordination_load":
    case "elevated_coordination_load":
    case "high_coordination_load":
    case "historical_baseline_only":
    case "more_evidence_needed":
      return value;
    default:
      throw new Error("Invalid committed snapshot coordination status.");
  }
}

function referenceType(value: string): ReferenceType {
  switch (value) {
    case "demo_coordination_baseline":
      return value;
    default:
      throw new Error("Offline snapshot must use the synthetic demo reference.");
  }
}

function verificationStatus(value: string): VerificationStatus {
  if (value === "synthetic_demo") return value;
  throw new Error("Offline snapshot must be marked synthetic_demo.");
}

// Fixed synthetic evidence is a display snapshot for the exact seeded plan only.
export const TOMATO_SYNTHETIC_SNAPSHOT: CalculateResponse = {
  ...tomatoSnapshot,
  coordinationStatus: coordinationStatus(tomatoSnapshot.coordinationStatus),
  provenance: {
    ...tomatoSnapshot.provenance,
    referenceType: referenceType(tomatoSnapshot.provenance.referenceType),
    verificationStatus: verificationStatus(tomatoSnapshot.provenance.verificationStatus),
  },
};

export function offlineSnapshotFor(plan: Plan): CalculateResponse | null {
  if (
    !plan.synthetic ||
    plan.id !== TOMATO_SYNTHETIC_SNAPSHOT.planId ||
    plan.marginHa !== 0.5 ||
    plan.plantingDate !== "2026-09-01" ||
    plan.cropCode !== "tomato" ||
    plan.crop !== TOMATO_SYNTHETIC_SNAPSHOT.crop ||
    plan.areaHa !== TOMATO_SYNTHETIC_SNAPSHOT.plannedAreaHa ||
    plan.harvestPeriod !== TOMATO_SYNTHETIC_SNAPSHOT.harvestPeriod ||
    plan.scope !== TOMATO_SYNTHETIC_SNAPSHOT.provenance.geography
  ) return null;
  return TOMATO_SYNTHETIC_SNAPSHOT;
}
