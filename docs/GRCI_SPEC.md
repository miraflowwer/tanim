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

The GRCI result must state which reference it uses.

Preferred reference order is:

1. committed buyer, cooperative, or LGU demand for the crop and period
2. local historical sold or accepted volume
3. broader official utilization data used only with its real geographic scope
4. historical production used as a coordination baseline, not as market demand

A production baseline must not be presented as verified market demand.

PSA Supply Utilization Accounts remain national context. They must not be presented as Luzon demand.

## Fixed demo fixture

The fixed demo is synthetic and reproducible.

Tomato uses 40 ha of planned area. The demo yield is 15 MT/ha, so planned supply is 600 MT. The demo reference amount is 375 MT. The supply load is 1.60.

Eggplant uses 8 ha of planned area. The demo yield is 12 MT/ha, so planned supply is 96 MT. The demo reference amount is 180 MT. The supply load is about 0.53.

With the test-only bands above, tomato is high and eggplant is low.

The plan rows come from [../datasets/demo_farm_plans.csv](../datasets/demo_farm_plans.csv). The reference rows come from [../datasets/demo_demand_proxy.csv](../datasets/demo_demand_proxy.csv).

Both files are marked as demo data. The 375 MT and 180 MT values are not observed local market demand and must not be presented that way.

## Output contract

A GRCI result includes crop, location, harvest period, planned-area range, reference yield and source, planned-supply range, reference amount and type, supply-load range, calculation status, risk state, risk-band range, uncertainty note, and source labels.

The result must be reproducible from the stored inputs and source data.
