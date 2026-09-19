import assert from "node:assert/strict";
import test from "node:test";
import { toBackendPayload } from "./grciPayload.js";

const plan = {
  crop: "tomato",
  regionId: "IV-A",
  location: "Tanauan, Batangas",
  farmSizeHa: 2,
  farmSizeMarginHa: 0.2,
  plantingDate: "2026-09-01",
  harvestPeriod: "2026-12",
};

test("maps one farmer plan without inventing a comparison", () => {
  assert.deepEqual(toBackendPayload({ ...plan }), {
    use_demo_reference: false,
    plan: {
      crop: "tomato",
      region_id: "IV-A",
      location: "Tanauan, Batangas",
      farm_size_ha: 2,
      farm_size_margin_ha: 0.2,
      planting_date: "2026-09-01",
      harvest_period: "2026-12",
    },
  });
});

test("keeps traceable normal comparison evidence", () => {
  const comparison = {
    amount: 100,
    unit: "MT",
    type: "historical_production_baseline",
    geography: "CALABARZON (IV-A)",
    period: "2021-2025",
    region_id: "IV-A",
  };
  const payload = toBackendPayload({
    ...plan,
    useDemoReference: false,
    comparison,
    sourceLabels: ["PSA-OPENSTAT-CROPS"],
  });
  assert.deepEqual(payload.comparison, comparison);
  assert.deepEqual(payload.source_labels, ["PSA-OPENSTAT-CROPS"]);
});

test("fixed demo groups never send a custom comparison", () => {
  const payload = toBackendPayload({
    ...plan,
    useDemoReference: true,
    plans: [plan, plan],
    comparison: { amount: 1 },
    sourceLabels: ["SHOULD-NOT-LEAK"],
  });
  assert.equal(payload.use_demo_reference, true);
  assert.equal(payload.plans.length, 2);
  assert.equal("comparison" in payload, false);
  assert.equal("source_labels" in payload, false);
});
