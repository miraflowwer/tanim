# Glut Risk Coordination Indicator

Status: MVP specification. Product risk thresholds are not final.

The Glut Risk Coordination Indicator, or GRCI, is TANIM's planting coordination measure.

It compares planned crop supply with a clearly named reference. The reference quality must always be visible. The MVP uses fixed rules and source data. It does not use machine learning.

The implementation is in [../scripts/grci.py](../scripts/grci.py). The fixed demo and edge cases are checked in [../tests/test_grci.py](../tests/test_grci.py).

## Inputs

A farmer plan should include crop, location, estimated farm size, farm-size margin, planting date, and expected harvest period.

The crop must pass the TANIM crop registry. Production and area coverage are both required.

All plans in one calculation must belong to the same crop, location, and harvest period. The engine rejects a plan row when it clearly belongs to another context.

## Farm-size uncertainty

Farm size can be an estimate.

Let $A$ be the estimated farm size in hectares. Let $M$ be the plus-or-minus margin.

$$
A_{low} = \max(0, A - M)
$$

$$
A_{high} = A + M
$$

For example, 2.0 ha with a margin of 0.2 ha becomes 1.8 ha to 2.2 ha.

For several farmers, TANIM adds the lower values and the upper values separately. This gives one collective planned-area range.

The fixed demo uses a zero margin because its inputs are controlled. TANIM does not set a default real-world margin yet.

## Historical yield reference

TANIM can load a regional historical yield from [../datasets/generated/yield_summary.csv](../datasets/generated/yield_summary.csv).

The reference window is 2021 to 2025. A crop-region row needs all five Annual years. The `n_years` field is 5 in the committed summary.

The loader validates the file schema, duplicate crop-region keys, finite numbers, year count, unit, and source fields before it returns a record.

A missing crop-region yield stays missing. TANIM does not copy a value from another crop or region.

Historical yield is a production reference. It is not market demand.

See [YIELD_REFERENCE.md](YIELD_REFERENCE.md) for the source method and limits.

## Planned supply

TANIM converts planned area to planned supply when a valid reference yield is available.

$$
\text{Planned supply} = \text{Planned area} \times \text{Reference yield}
$$

Planned supply is measured in metric tons, or MT.

If planned area is 18 ha to 22 ha and reference yield is 15 MT/ha, planned supply is 270 MT to 330 MT.

The result must include the source of the reference yield.

When a validated yield-summary record is supplied, the engine also checks that its crop, unit, average yield, reference period, and source are consistent with the numeric yield used in the calculation.

## Estimated range wording

Every value that depends on an approximate farm size is shown as an estimated range.

For example:

Estimated range: 1.8 ha to 2.2 ha

At 15 MT/ha:

Estimated range: 27 MT to 33 MT

This is not a statistical confidence interval. The range comes from the farm-size margin supplied with the plan.

Use `format_estimated_range` so interfaces use the same wording.

## Reference amount

The comparison amount must also use MT. TANIM rejects another unit because the ratio would be invalid.

Every reference must state:

- reference type
- reference geography
- reference period
- source label or source record
- evidence note

These fields make the limits of the comparison visible.

## Supply load

For a reference that can be compared with planned supply:

$$
\text{Supply load} = \frac{\text{Planned supply in MT}}{\text{Reference amount in MT}}
$$

A value of 1.0 means planned supply equals the reference amount.

This ratio does not prove that a glut will happen. Its meaning depends on the reference type.

## Reference types

TANIM accepts five reference types.

1. `local_committed_demand` is confirmed local buyer, cooperative, or LGU demand. It is the only reference that may be directly described as market demand.
2. `local_historical_absorption` is past local sold or accepted volume. It is a historical absorption proxy, not current or committed demand.
3. `national_utilization_context` is national context only. TANIM does not divide local planned supply by this national amount and does not produce a GRCI risk band from it.
4. `historical_production_baseline` compares a plan with past production. It can produce a baseline comparison, but it must not be shown as market demand or as a demand-based glut result.
5. `demo_coordination_baseline` is synthetic data for the fixed demo. It can produce the fixed demo GRCI result, but it must always be labelled as synthetic and not observed market demand.

The machine-readable reference metadata is defined in `REFERENCE_TYPES` in [../scripts/grci.py](../scripts/grci.py).

## Risk and baseline states

Risk bands are supplied by the caller. The engine does not store final product thresholds.

The fixed demo tests use temporary bands:

- low: supply load up to 1.0
- watch: above 1.0 and up to 1.5
- high: above 1.5

These values keep the demo reproducible. They are not approved production thresholds.

`comparison_state` stores the band from any valid comparison.

`risk_state` is used only when the reference mode supports a risk interpretation. Historical production keeps `risk_state` empty and uses only `comparison_state`.

National utilization context produces neither state.

If a range crosses two bands, the state is `borderline`.

## Result status

`status` describes what the engine could safely produce.

- `ok`: a risk or proxy-risk comparison is available
- `baseline`: a historical production comparison is available, but it is not a demand-based risk result
- `context_only`: the reference is shown as context and is not used for a local ratio
- `unclassified`: a valid ratio exists but comparison bands are not configured
- `incomplete`: a required value is missing
- `invalid`: a value, unit, reference type, geography, provenance record, or plan context is not usable
- `unsupported`: the crop does not have a safe production and area join

Data quality and risk level are separate.

## Explanation and provenance

Each result includes a plain-language `explanation` and machine-readable `provenance`.

The explanation must follow the reference mode.

A historical production baseline is described as a baseline comparison, not as market demand.

National utilization is described as context only.

A local historical absorption reference is identified as a proxy.

The synthetic demo is identified as a demo result.

When a yield-summary record is passed, provenance can include crop, region, reference window, number of years, unit, source id, and the exact yield source used.

## Fixed demo fixture

The fixed demo is synthetic and reproducible.

Tomato uses 40 ha. At 15 MT/ha, planned supply is 600 MT. The demo coordination baseline is 375 MT. The supply load is 1.60.

Eggplant uses 8 ha. At 12 MT/ha, planned supply is 96 MT. The demo coordination baseline is 180 MT. The supply load is about 0.53.

With the temporary demo bands, tomato is high and eggplant is low.

The plan rows are in [../datasets/demo_farm_plans.csv](../datasets/demo_farm_plans.csv).

The synthetic reference rows are in [../datasets/demo_coordination_baseline.csv](../datasets/demo_coordination_baseline.csv).

The baseline file states its reference type, geography, period, and synthetic status. Its 375 MT and 180 MT values are not observed local market demand.

## Output contract

A result includes the plan context, planned-area range, reference yield and source, planned-supply range, expected-production range, reference amount and unit, reference type, geography, period, reference label, evidence note, reference quality, reference mode, supply-load range when allowed, calculation status, comparison state, risk state when allowed, uncertainty state, uncertainty note, plain-language explanation, provenance, and source labels.

The interface must show the reference label and evidence note. It must not infer stronger evidence than the result provides.
