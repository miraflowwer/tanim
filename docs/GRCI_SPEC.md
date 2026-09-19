# Glut Risk Coordination Indicator

Status: MVP specification. Product risk thresholds are not final yet.

The Glut Risk Coordination Indicator, or GRCI, is TANIM's main coordination measure.

It compares planned crop supply with a reference for the same planning context. The MVP uses fixed rules and source data. It does not use machine learning to produce the result.

The current implementation is in [../scripts/grci.py](../scripts/grci.py). The fixed demo and edge cases are checked in [../tests/test_grci.py](../tests/test_grci.py).

## Inputs

A farmer plan should include crop, location, estimated farm size, farm-size margin, planting date, and expected harvest period.

The crop must resolve through the TANIM crop registry before a GRCI calculation is allowed. A planning crop needs both production and area coverage.

## Farm-size uncertainty

Farm size can be an estimate. TANIM must not treat every entered area as exact.

Let A be the estimated farm size in hectares. Let M be the plus-or-minus margin in hectares.

The lower area is:

`max(0, A - M)`

The upper area is:

`A + M`

For example, 2.0 ha with a margin of 0.2 ha becomes an estimated range of 1.8 ha to 2.2 ha.

For several farmers, TANIM adds the lower values together and adds the upper values together. This gives one collective planned-area range.

The fixed synthetic demo uses a margin of 0 because its inputs are controlled. Real user plans can use a non-zero margin.

TANIM does not set a default real-world margin yet. A default should only be added after pilot evidence supports it.

## Planned supply

When a valid reference yield is available, TANIM converts the planned-area range into a planned-supply range.

`planned supply = planned area x reference yield`

If planned area is 18 ha to 22 ha and reference yield is 15 MT/ha, planned supply is 270 MT to 330 MT.

The result also needs the source of the reference yield. A value without its source is incomplete.

## Supply load

When a valid reference amount is available, TANIM compares planned supply with that amount.

`supply load = planned supply / reference amount`

Supply load can also be a range.

A supply load of 1.0 means planned supply is equal to the reference amount. A value above 1.0 means planned supply is higher than the reference. A value below 1.0 means it is lower.

This ratio does not prove that a glut will happen. Its meaning depends on the quality and geographic scope of the reference amount.

## Risk classification

Risk bands are supplied by the caller. The calculation module does not store final product thresholds.

The fixed demo tests currently use test-only bands:

- low: supply load up to 1.0
- watch: above 1.0 and up to 1.5
- high: above 1.5

These values lock the demo fixture for testing. They are not approved production thresholds.

If the lower and upper supply-load values fall in different bands, TANIM marks the result as borderline. The interface should show that the farm-size estimate can change the final band.

## Result status

Data quality and risk level are separate.

`status` describes whether TANIM could complete the calculation:

- `ok`: calculation completed and a risk state was assigned
- `unclassified`: supply load is available but risk bands are not configured
- `incomplete`: a required input or source value is missing
- `invalid`: an input or reference value is not usable
- `unsupported`: the crop does not have a safe production and area join

`risk_state` is only used for the risk result. It is normally low, watch, high, or borderline. It stays empty when the calculation is not complete.

## Reference quality

The GRCI result must state which reference it uses. The engine accepts only these reference types, defined in scripts/grci.py as REFERENCE_TYPES:

1. local_committed_demand: committed buyer, cooperative, or LGU demand for the crop and period. User label: Local committed demand. This is market demand.
2. local_historical_absorption: local historical sold or accepted volume. User label: Local historical absorption. This is market demand history, not a forward commitment.
3. national_utilization_context: broader official utilization data used only with its real geographic scope. User label: National utilization context (not Luzon demand). This is not Luzon demand.
4. historical_production_baseline: historical production used as a coordination baseline. User label: Historical production baseline (not market demand). This is never market demand.
5. demo_coordination_baseline: synthetic demo baseline. User label: Demo coordination baseline (not market demand). This is never market demand.

Preferred evidence order is local_committed_demand, then local_historical_absorption, then national_utilization_context, then historical_production_baseline. We still do not have verified Luzon-local market demand for every crop, so callers must select the tier that matches the evidence.

Rules:

- Historical production must never be labelled as market demand in code, docs, or UI. Use describe_reference() for user wording.
- Only local_committed_demand and local_historical_absorption may use the words market demand. The other three tiers must use their not-demand labels.
- PSA Supply Utilization Accounts remain national context. They must use national_utilization_context and must not be presented as Luzon demand.
- An unknown or missing reference type returns incomplete. Supply load is not calculated for display until the tier is known.

## Fixed demo fixture

The fixed demo is synthetic and reproducible.

Tomato uses 40 ha of planned area. The demo yield is 15 MT/ha, so planned supply is 600 MT. The demo reference amount is 375 MT. The supply load is 1.60.

Eggplant uses 8 ha of planned area. The demo yield is 12 MT/ha, so planned supply is 96 MT. The demo reference amount is 180 MT. The supply load is about 0.53.

With the test-only bands above, tomato is high and eggplant is low.

The plan rows come from [../datasets/demo_farm_plans.csv](../datasets/demo_farm_plans.csv). The reference rows come from [../datasets/demo_demand_proxy.csv](../datasets/demo_demand_proxy.csv).

Both files are marked as demo data. The 375 MT and 180 MT values use reference type demo_coordination_baseline. They are not observed local market demand and must not be presented that way. The demo user label is Demo coordination baseline (not market demand).

## Output contract

A GRCI result includes crop, location, harvest period, planned-area range, reference yield and source, planned-supply range, reference amount and type, reference label and evidence note, supply-load range, calculation status, risk state, risk-band range, uncertainty note, and source labels.

The interface must show reference_label and reference_evidence_note, not only the raw reference_type code. The result must be reproducible from the stored inputs and source data.
