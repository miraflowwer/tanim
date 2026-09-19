import type { AggregateRow, ReferenceRecord } from "../../types";

export interface AttentionItem {
  id: string;
  crop: string;
  period: string;
  geography: string;
  reason: string;
  severity: "high" | "watch" | "info";
  evidenceState: string;
  nextAction: string;
  nextHref: string;
}

function verifiedRefFor(references: ReferenceRecord[], cropCode: string, period: string): ReferenceRecord | null {
  const match = references.find(
    (reference) => reference.cropCode === cropCode
      && (reference.period === period || reference.period.startsWith(period.slice(0, 4)))
      && reference.workflow === "verified",
  );
  return match ?? null;
}

// Display-only attention list built from server aggregates and reference
// records. This never computes a coordination result; it points at rows
// that need a human look.
export function buildAttentionItems(
  aggregates: AggregateRow[],
  references: ReferenceRecord[],
): AttentionItem[] {
  const items: AttentionItem[] = [];
  for (const row of aggregates) {
    const verified = verifiedRefFor(references, row.cropCode, row.harvestPeriod);
    if (!verified) {
      items.push({
        id: `missing-ref-${row.cropCode}-${row.harvestPeriod}`,
        crop: row.cropCode,
        period: row.harvestPeriod,
        geography: "Organization scope",
        reason: "No verified comparison reference for this crop and period.",
        severity: "watch",
        evidenceState: "More evidence needed",
        nextAction: "Open references",
        nextHref: "#/references",
      });
    }
    if (row.estimatedProductionMt === null) {
      items.push({
        id: `missing-yield-${row.cropCode}-${row.harvestPeriod}`,
        crop: row.cropCode,
        period: row.harvestPeriod,
        geography: "Organization scope",
        reason: "Yield evidence unavailable, so production cannot be estimated.",
        severity: "info",
        evidenceState: "Yield unavailable",
        nextAction: "Open crop detail",
        nextHref: `#/crop/${row.cropCode}`,
      });
    }
    const stale = references.find(
      (reference) => reference.cropCode === row.cropCode
        && reference.verificationStatus === "stale",
    );
    if (stale) {
      items.push({
        id: `stale-ref-${row.cropCode}-${row.harvestPeriod}`,
        crop: row.cropCode,
        period: row.harvestPeriod,
        geography: stale.geography,
        reason: `Reference ${stale.version} is stale.`,
        severity: "watch",
        evidenceState: "Stale",
        nextAction: "Open review queue",
        nextHref: "#/review",
      });
    }
  }
  const totalArea = aggregates.reduce((sum, row) => sum + row.plannedAreaHa, 0);
  for (const row of aggregates) {
    if (totalArea > 0 && row.plannedAreaHa / totalArea >= 0.5 && aggregates.length > 1) {
      items.push({
        id: `concentrated-${row.cropCode}-${row.harvestPeriod}`,
        crop: row.cropCode,
        period: row.harvestPeriod,
        geography: "Organization scope",
        reason: "Half or more of planned area sits in one crop and period.",
        severity: "high",
        evidenceState: "Concentrated harvest",
        nextAction: "Open timeline",
        nextHref: "#/timeline",
      });
    }
  }
  return items;
}

export interface HarvestBucket {
  period: string;
  areaHa: number;
  productionMt: number | null;
}

// Display buckets grouped by harvest period. Production stays null when any
// contributing row lacks yield evidence; a missing value is never zero.
export function harvestBuckets(aggregates: AggregateRow[]): HarvestBucket[] {
  const byPeriod = new Map<string, HarvestBucket>();
  for (const row of aggregates) {
    const bucket = byPeriod.get(row.harvestPeriod) ?? {
      period: row.harvestPeriod, areaHa: 0, productionMt: 0,
    };
    bucket.areaHa += row.plannedAreaHa;
    if (row.estimatedProductionMt === null || bucket.productionMt === null) {
      bucket.productionMt = null;
    } else {
      bucket.productionMt += row.estimatedProductionMt;
    }
    byPeriod.set(row.harvestPeriod, bucket);
  }
  return [...byPeriod.values()].sort((a, b) => a.period.localeCompare(b.period));
}
