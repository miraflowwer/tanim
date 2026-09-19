# Backend contract note (`POST /api/grci`)

Member 1: implement this endpoint so the UI flips with
`VITE_USE_MOCK=false` and no redesign.

## Request (JSON)

```json
{
  "crop": "tomato",
  "location": "Tanauan, Batangas",
  "harvest_period": "2026-12",
  "plans": [
    {
      "crop_canonical": "tomato",
      "municipality": "Tanauan, Batangas",
      "harvest_period": "2026-12",
      "farm_size_ha": 10.0,
      "farm_size_margin_ha": 0.0
    }
  ],
  "planting_date": "2026-09-01",
  "region_id": "IV-A"
}
```

Backend responsibilities (UI does none of this):

- Validate crop against the registry (`planning_supported` + production/area).
- Look up `reference_yield` + `yield_record` from `yield_summary.csv`
  (or DEMO-2026 synthetic yield for the fixed demo).
- Choose `reference_type`, `reference_amount` (MT), `reference_geography`,
  `reference_period`, `source_labels`.
- Call `scripts/grci.py → compute_grci(...)` with caller bands.

Suggested temporary demo bands (not production thresholds):
`[[1.0, "low"], [1.5, "watch"], [Infinity, "high"]]`.

## Response (JSON)

Return the `compute_grci()` result dict verbatim. Required keys the UI
reads (see `src/mocks/grciMocks.js` for full examples):

`crop, location, harvest_period, planned_area_range, reference_yield,
yield_source, planned_supply_range, expected_production_range,
reference_amount, reference_unit, reference_type, reference_geography,
reference_period, reference_label, reference_evidence_note,
reference_quality, reference_scope, reference_mode,
market_demand_wording_allowed, supply_load_range, status,
comparison_state, comparison_band_range, risk_state, risk_band_range,
borderline, uncertainty_state, uncertainty_note, explanation, provenance,
source_labels`

Rules the UI depends on:

- `reference_unit` is always `"MT"`.
- `risk_state` is set only when `status === "ok"`.
  `status === "baseline"` sets only `comparison_state`.
  `status === "context_only"` sets neither and leaves
  `supply_load_range` null.
- `explanation`, `reference_evidence_note`, `uncertainty_note` are
  user-facing and rendered verbatim.
