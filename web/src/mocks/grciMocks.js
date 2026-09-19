// Fixed offline fallback for the two committed synthetic demo fixtures.
// The UI never computes areas, supply, load, or bands. See
// web/openapi-note.md for the live service contract.

const DEMO_EVIDENCE =
  "Synthetic DEMO-2026 baseline used only for a reproducible demo. It is not observed local market demand.";

function demoProvenance(overrides) {
  return {
    yield_source: "DEMO-2026 synthetic yield",
    yield_crop_id: null,
    yield_region_id: null,
    yield_ref_period: null,
    yield_n_years: null,
    yield_unit: null,
    yield_source_id: null,
    reference_label: "Demo coordination baseline (not market demand)",
    reference_evidence_note: DEMO_EVIDENCE,
    reference_quality: "synthetic",
    reference_mode: "demo",
    evidence_status: "fixed_synthetic",
    evidence_verified: false,
    ...overrides,
  };
}

export const tomatoDemo = {
  crop: "tomato",
  location: "Tanauan, Batangas",
  harvest_period: "2026-12",
  planned_area_range: [40.0, 40.0],
  reference_yield: 15.0,
  yield_source: "DEMO-2026 synthetic yield",
  planned_supply_range: [600.0, 600.0],
  expected_production_range: [600.0, 600.0],
  reference_amount: 375.0,
  reference_unit: "MT",
  reference_type: "demo_coordination_baseline",
  reference_geography: "CALABARZON (IV-A)",
  reference_period: "2025",
  reference_label: "Demo coordination baseline (not market demand)",
  reference_evidence_note: DEMO_EVIDENCE,
  reference_quality: "synthetic",
  reference_scope: "demo",
  reference_mode: "demo",
  evidence_status: "fixed_synthetic",
  evidence_verified: false,
  market_demand_wording_allowed: false,
  supply_load_range: [1.6, 1.6],
  status: "ok",
  comparison_state: "high",
  comparison_band_range: ["high", "high"],
  risk_state: "high",
  risk_band_range: ["high", "high"],
  borderline: false,
  uncertainty_state: "point",
  uncertainty_note: null,
  explanation:
    "Planned area is 40 ha. At 15 MT per ha, expected production is 600 MT. " +
    "Compared with Demo coordination baseline (not market demand) of 375 MT, " +
    "supply load is 1.6 ratio. Demo risk state is high. " +
    DEMO_EVIDENCE,
  provenance: {
    ...demoProvenance(),
    reference_type: "demo_coordination_baseline",
    reference_amount: 375.0,
    reference_unit: "MT",
    reference_geography: "CALABARZON (IV-A)",
    reference_period: "2025",
    source_labels: ["DEMO-2026"],
  },
  source_labels: ["DEMO-2026"],
};

export const eggplantDemo = {
  crop: "eggplant",
  location: "Tanauan, Batangas",
  harvest_period: "2026-12",
  planned_area_range: [8.0, 8.0],
  reference_yield: 12.0,
  yield_source: "DEMO-2026 synthetic yield",
  planned_supply_range: [96.0, 96.0],
  expected_production_range: [96.0, 96.0],
  reference_amount: 180.0,
  reference_unit: "MT",
  reference_type: "demo_coordination_baseline",
  reference_geography: "CALABARZON (IV-A)",
  reference_period: "2025",
  reference_label: "Demo coordination baseline (not market demand)",
  reference_evidence_note: DEMO_EVIDENCE,
  reference_quality: "synthetic",
  reference_scope: "demo",
  reference_mode: "demo",
  evidence_status: "fixed_synthetic",
  evidence_verified: false,
  market_demand_wording_allowed: false,
  supply_load_range: [0.5333333333333333, 0.5333333333333333],
  status: "ok",
  comparison_state: "low",
  comparison_band_range: ["low", "low"],
  risk_state: "low",
  risk_band_range: ["low", "low"],
  borderline: false,
  uncertainty_state: "point",
  uncertainty_note: null,
  explanation:
    "Planned area is 8 ha. At 12 MT per ha, expected production is 96 MT. " +
    "Compared with Demo coordination baseline (not market demand) of 180 MT, " +
    "supply load is 0.533333 ratio. Demo risk state is low. " +
    DEMO_EVIDENCE,
  provenance: {
    ...demoProvenance(),
    reference_type: "demo_coordination_baseline",
    reference_amount: 180.0,
    reference_unit: "MT",
    reference_geography: "CALABARZON (IV-A)",
    reference_period: "2025",
    source_labels: ["DEMO-2026"],
  },
  source_labels: ["DEMO-2026"],
};

export const mocksByScenario = {
  "tomato-demo": tomatoDemo,
  "eggplant-demo": eggplantDemo,
};

export function pickMock(planInput = {}) {
  const scenario = planInput.scenario;
  const result = scenario ? mocksByScenario[scenario] : null;
  if (!result) {
    throw new Error(
      "Mock fallback only supports the fixed Tomato and Eggplant demo fixtures."
    );
  }
  return result;
}
