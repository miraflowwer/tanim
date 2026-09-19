// Seeded offline display snapshots. Live calculations and aggregates come from FastAPI.
// Synthetic rows are labeled synthetic_demo and never become trusted evidence.
import type {
  ClimateCtx,
  CropEntry,
  DataSourceRow,
  Plan,
  PriceObs,
  ReferenceRecord,
} from "../types";

export const ORG_ID = "org-1";

export const CROPS: CropEntry[] = [
  { code: "tomato", name: "Tomato", supported: true },
  { code: "eggplant", name: "Eggplant", supported: true },
  { code: "ampalaya", name: "Ampalaya", supported: true },
  { code: "upo", name: "Upo", supported: false },
];

export function seedPlans(): Plan[] {
  return [
    {
      id: "plan-tomato-001", crop: "Tomato", cropCode: "tomato", farm: "Brgy. San Isidro",
      areaHa: 12.5, marginHa: 0.5, plantingDate: "2026-09-01", harvestPeriod: "2026-Q4",
      state: "Planned", updatedAt: "2026-09-19", scope: "CALABARZON", synthetic: true,
    },
    {
      id: "plan-eggplant-draft", crop: "Eggplant", cropCode: "eggplant", farm: "Brgy. Malaya",
      areaHa: 2, marginHa: 0.2, plantingDate: "2026-09-10", harvestPeriod: "2026-Q4",
      state: "Draft", updatedAt: "2026-09-18", scope: "CALABARZON", synthetic: true,
    },
    {
      id: "plan-tomato-harv", crop: "Tomato", cropCode: "tomato", farm: "Brgy. San Isidro",
      areaHa: 8, marginHa: 0, plantingDate: "2026-03-01", harvestPeriod: "2026-Q2",
      state: "Harvested", updatedAt: "2026-06-28", scope: "CALABARZON", synthetic: true,
    },
    {
      id: "plan-ampalaya-cancel", crop: "Ampalaya", cropCode: "ampalaya", farm: "Brgy. Malaya",
      areaHa: 1.5, marginHa: 0, plantingDate: "2026-08-01", harvestPeriod: "2026-Q4",
      state: "Cancelled", updatedAt: "2026-08-20", scope: "CALABARZON", synthetic: true,
    },
  ];
}

export function seedReferences(): ReferenceRecord[] {
  return [{
    id: "ref-demo", crop: "Tomato", cropCode: "tomato", amountMt: 375, unit: "MT",
    referenceType: "demo_coordination_baseline", geography: "CALABARZON",
    period: "2026-Q4 demo", source: "Seeded demo snapshot (synthetic_demo)",
    evidenceNote: "Synthetic demo baseline for a fixed offline snapshot. Not market demand.",
    reviewer: "None", verificationStatus: "synthetic_demo",
    effectiveDate: "2026-09-19", expiryState: "synthetic snapshot", version: "v1",
    workflow: "draft", verifiedAt: "", scope: "CALABARZON", synthetic: true,
  }];
}

export function seedPrices(): PriceObs[] {
  return [
    {
      crop: "Tomato", cropCode: "tomato", latestPrice: 42, unit: "PHP/kg",
      date: "2026-09-12", geography: "CALABARZON", source: "PSA farmgate price survey",
      seriesId: "tomato-fresh-calabarzon-monthly", trend: [38, 40, 39, 42],
    },
    {
      crop: "Eggplant", cropCode: "eggplant", latestPrice: 35, unit: "PHP/kg",
      date: "2026-09-12", geography: "CALABARZON", source: "PSA farmgate price survey",
      seriesId: "eggplant-fresh-calabarzon-monthly", trend: [33, 34, 33, 35],
    },
  ];
}

export function seedClimate(): ClimateCtx {
  return {
    source: "PAGASA seasonal outlook",
    issuedAt: "2026-09-10",
    summary: "Near-average rainfall is expected for CALABARZON next season.",
    available: true,
  };
}

export function seedHealth(): DataSourceRow[] {
  return [
    {
      source: "PSA yield reference", lastRefresh: "18 Sep 2026", expected: "Monthly",
      state: "ok", lastError: null, stale: false,
    },
    {
      source: "PSA farmgate prices", lastRefresh: "12 Sep 2026", expected: "Weekly",
      state: "stale", lastError: null, stale: true,
    },
    {
      source: "Weather cache (Open-Meteo)", lastRefresh: "19 Sep 2026", expected: "Every 6 hours",
      state: "error", lastError: "Last fetch failed 19 Sep 2026, 06:10. Showing cached values.", stale: false,
    },
    {
      source: "Seeded demo snapshot", lastRefresh: "19 Sep 2026", expected: "On demo",
      state: "synthetic_demo", lastError: null, stale: false,
    },
  ];
}
