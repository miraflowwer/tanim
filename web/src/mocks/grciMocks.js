// Mock GRCI results. Shape MUST stay identical to scripts/grci.py compute_grci()
// result dict so the UI can switch to Member 1's backend without redesign.
// The UI never computes areas, supply, load, or bands — it only displays
// these precomputed values. See web/openapi-note.md for the live contract.

const DEMO_EVIDENCE =
  "Synthetic DEMO-2026 baseline used only for a reproducible demo. It is not observed local market demand.";

const BASELINE_EVIDENCE =
  "Historical production can show how a plan compares with past supply. It is not market demand.";

const CONTEXT_EVIDENCE =
  "National utilization data provide context only. They are not a Luzon or local demand reference and do not produce a GRCI risk band.";

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

// Custom farmer entry with a ± margin: shows the estimated-range path.
// 2.0 ha ± 0.2 ha -> 1.8 to 2.2 ha; at 13.9462 MT/ha -> ~25.1 to 30.68 MT.
// Reference is a committed local example so market-demand wording IS allowed here.
export const tomatoRangeCommitted = {
  crop: "tomato",
  location: "Tanauan, Batangas",
  harvest_period: "2026-12",
  planned_area_range: [1.8, 2.2],
  reference_yield: 13.9462,
  yield_source: "PSA-OPENSTAT-CROPS 2021-2025 summary",
  planned_supply_range: [25.10316, 30.68164],
  expected_production_range: [25.10316, 30.68164],
  reference_amount: 28.0,
  reference_unit: "MT",
  reference_type: "local_committed_demand",
  reference_geography: "Tanauan, Batangas",
  reference_period: "2026-12",
  reference_label: "Local committed demand",
  reference_evidence_note:
    "Confirmed local buyer, cooperative, or LGU demand for the crop and planning period.",
  reference_quality: "direct",
  reference_scope: "local",
  reference_mode: "risk",
  market_demand_wording_allowed: true,
  supply_load_range: [0.8965414285714286, 1.0957735714285715],
  status: "ok",
  comparison_state: "borderline",
  comparison_band_range: ["low", "watch"],
  risk_state: "borderline",
  risk_band_range: ["low", "watch"],
  borderline: true,
  uncertainty_state: "borderline",
  uncertainty_note:
    "Supply load spans low to watch. The farm-size estimate can change the final band.",
  explanation:
    "Planned area is 1.8 to 2.2 ha. At 13.9462 MT per ha, expected production is " +
    "25.1032 to 30.6816 MT. Compared with Local committed demand of 28 MT, " +
    "supply load is 0.896541 to 1.09577 ratio. Risk state is borderline. " +
    "Confirmed local buyer, cooperative, or LGU demand for the crop and planning period.",
  provenance: {
    yield_source: "PSA-OPENSTAT-CROPS 2021-2025 summary",
    yield_crop_id: "tomato",
    yield_region_id: "IV-A",
    yield_ref_period: "2021-2025",
    yield_n_years: 5,
    yield_unit: "mt_per_ha",
    yield_source_id: "PSA-OPENSTAT-CROPS",
    reference_type: "local_committed_demand",
    reference_amount: 28.0,
    reference_unit: "MT",
    reference_geography: "Tanauan, Batangas",
    reference_period: "2026-12",
    source_labels: ["LGU Tanauan offtake registry 2026-12"],
    reference_label: "Local committed demand",
    reference_evidence_note:
      "Confirmed local buyer, cooperative, or LGU demand for the crop and planning period.",
    reference_quality: "direct",
    reference_mode: "risk",
  },
  source_labels: ["LGU Tanauan offtake registry 2026-12"],
};

// Historical production baseline: must never be called market demand.
export const tomatoBaseline = {
  crop: "tomato",
  location: "Tanauan, Batangas",
  harvest_period: "2026-12",
  planned_area_range: [2.0, 2.0],
  reference_yield: 13.9462,
  yield_source: "PSA-OPENSTAT-CROPS 2021-2025 summary",
  planned_supply_range: [27.8924, 27.8924],
  expected_production_range: [27.8924, 27.8924],
  reference_amount: 300.0,
  reference_unit: "MT",
  reference_type: "historical_production_baseline",
  reference_geography: "CALABARZON (IV-A)",
  reference_period: "2021-2025",
  reference_label: "Historical production baseline (not market demand)",
  reference_evidence_note: BASELINE_EVIDENCE,
  reference_quality: "production_baseline",
  reference_scope: "declared_geography",
  reference_mode: "baseline",
  market_demand_wording_allowed: false,
  supply_load_range: [0.09297466666666667, 0.09297466666666667],
  status: "baseline",
  comparison_state: "low",
  comparison_band_range: ["low", "low"],
  risk_state: null,
  risk_band_range: null,
  borderline: false,
  uncertainty_state: "point",
  uncertainty_note: null,
  explanation:
    "Planned area is 2 ha. At 13.9462 MT per ha, expected production is 27.8924 MT. " +
    "Compared with Historical production baseline (not market demand) of 300 MT, " +
    "supply load is 0.0929747 ratio. Baseline comparison state is low. " +
    BASELINE_EVIDENCE,
  provenance: {
    yield_source: "PSA-OPENSTAT-CROPS 2021-2025 summary",
    yield_crop_id: "tomato",
    yield_region_id: "IV-A",
    yield_ref_period: "2021-2025",
    yield_n_years: 5,
    yield_unit: "mt_per_ha",
    yield_source_id: "PSA-OPENSTAT-CROPS",
    reference_type: "historical_production_baseline",
    reference_amount: 300.0,
    reference_unit: "MT",
    reference_geography: "CALABARZON (IV-A)",
    reference_period: "2021-2025",
    source_labels: ["PSA-OPENSTAT-CROPS"],
    reference_label: "Historical production baseline (not market demand)",
    reference_evidence_note: BASELINE_EVIDENCE,
    reference_quality: "production_baseline",
    reference_mode: "baseline",
  },
  source_labels: ["PSA-OPENSTAT-CROPS"],
};

// National utilization context: context only, no ratio, no band.
export const tomatoNationalContext = {
  crop: "tomato",
  location: "Tanauan, Batangas",
  harvest_period: "2026-12",
  planned_area_range: [2.0, 2.0],
  reference_yield: 13.9462,
  yield_source: "PSA-OPENSTAT-CROPS 2021-2025 summary",
  planned_supply_range: [27.8924, 27.8924],
  expected_production_range: [27.8924, 27.8924],
  reference_amount: 1000000.0,
  reference_unit: "MT",
  reference_type: "national_utilization_context",
  reference_geography: "Philippines",
  reference_period: "2025",
  reference_label: "National utilization context (not Luzon demand)",
  reference_evidence_note: CONTEXT_EVIDENCE,
  reference_quality: "national_context",
  reference_scope: "national",
  reference_mode: "context_only",
  market_demand_wording_allowed: false,
  supply_load_range: null,
  status: "context_only",
  comparison_state: null,
  comparison_band_range: null,
  risk_state: null,
  risk_band_range: null,
  borderline: false,
  uncertainty_state: "point",
  uncertainty_note:
    "This reference is context only. TANIM does not compare local planned supply with a national utilization amount.",
  explanation:
    "Planned area is 2 ha. At 13.9462 MT per ha, expected production is 27.8924 MT. " +
    "National utilization context (not Luzon demand) is shown only as context. " +
    CONTEXT_EVIDENCE,
  provenance: {
    yield_source: "PSA-OPENSTAT-CROPS 2021-2025 summary",
    yield_crop_id: "tomato",
    yield_region_id: "IV-A",
    yield_ref_period: "2021-2025",
    yield_n_years: 5,
    yield_unit: "mt_per_ha",
    yield_source_id: "PSA-OPENSTAT-CROPS",
    reference_type: "national_utilization_context",
    reference_amount: 1000000.0,
    reference_unit: "MT",
    reference_geography: "Philippines",
    reference_period: "2025",
    source_labels: ["PSA-SUA national"],
    reference_label: "National utilization context (not Luzon demand)",
    reference_evidence_note: CONTEXT_EVIDENCE,
    reference_quality: "national_context",
    reference_mode: "context_only",
  },
  source_labels: ["PSA-SUA national"],
};

// Missing yield: engine returns incomplete, no supply shown.
export const incompleteMissingYield = {
  crop: "tomato",
  location: "Tanauan, Batangas",
  harvest_period: "2026-12",
  planned_area_range: [1.8, 2.2],
  reference_yield: null,
  yield_source: null,
  planned_supply_range: null,
  expected_production_range: null,
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
  market_demand_wording_allowed: false,
  supply_load_range: null,
  status: "incomplete",
  comparison_state: null,
  comparison_band_range: null,
  risk_state: null,
  risk_band_range: null,
  borderline: false,
  uncertainty_state: "range",
  uncertainty_note:
    "Missing reference yield. Planned supply cannot be calculated.",
  explanation:
    "No result can be shown. The reference yield is missing, so expected production cannot be calculated.",
  provenance: {
    yield_source: null,
    yield_crop_id: null,
    yield_region_id: null,
    yield_ref_period: null,
    yield_n_years: null,
    yield_unit: null,
    yield_source_id: null,
    reference_type: "demo_coordination_baseline",
    reference_amount: 375.0,
    reference_unit: "MT",
    reference_geography: "CALABARZON (IV-A)",
    reference_period: "2025",
    source_labels: ["DEMO-2026"],
    reference_label: "Demo coordination baseline (not market demand)",
    reference_evidence_note: DEMO_EVIDENCE,
    reference_quality: "synthetic",
    reference_mode: "demo",
  },
  source_labels: ["DEMO-2026"],
};

export const mocksByScenario = {
  "tomato-demo": tomatoDemo,
  "eggplant-demo": eggplantDemo,
  "tomato-range": tomatoRangeCommitted,
  "tomato-baseline": tomatoBaseline,
  "tomato-context": tomatoNationalContext,
  "incomplete-yield": incompleteMissingYield,
};

export function pickMock(planInput = {}) {
  const scenario = planInput.scenario;
  if (scenario && mocksByScenario[scenario]) return mocksByScenario[scenario];
  if (planInput.crop === "eggplant") return eggplantDemo;
  return tomatoDemo;
}
