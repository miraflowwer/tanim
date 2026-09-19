# Glut Risk Coordination Indicator

Status: MVP specification. Risk thresholds are not final yet.

The Glut Risk Coordination Indicator, or GRCI, is TANIM's main coordination measure.

It compares the supply that farmers plan to produce with a reference for the same crop, place, and harvest period.

The MVP uses fixed rules and source data. It does not use machine learning to decide the result. AI tools may help the team build and audit the software, but they do not produce the GRCI result.

## Inputs

A farmer plan should include:

- crop
- location
- estimated farm size in hectares
- farm size margin in hectares
- planting date
- expected harvest period

The crop must resolve through the TANIM crop registry before it can be used in a cross-source calculation.

## Farm size uncertainty

Farm size can be an estimate. TANIM must not treat every user-entered area as exact.

Let:

- A = estimated farm size in hectares
- M = margin in hectares

The lower area is:

`max(0, A - M)`

The upper area is:

`A + M`

Example:

A farmer enters 2.0 ha with a margin of 0.2 ha.

TANIM treats the area as 1.8 ha to 2.2 ha.

For a group of farmers, TANIM adds the lower values together and adds the upper values together. This gives a collective planned-area range.

The fixed synthetic demo uses a margin of 0 because its farm sizes are controlled demo values. This does not mean real farm sizes are exact.

TANIM does not set a default real-world margin yet. A default should only be added after pilot evidence supports it. Until then, the user or organization should provide the margin when the farm size is estimated.

## Planned supply

When a reference yield is available, TANIM converts the planned-area range into a planned-supply range.

`planned supply = planned area x reference yield`

If the group has an area range, the output is also a range.

Example:

If planned area is 18 ha to 22 ha and reference yield is 15 MT/ha, planned supply is 270 MT to 330 MT.

## Supply load

When a valid market or absorption reference is available, TANIM compares planned supply with that reference.

`supply load = planned supply / reference amount`

Because planned supply can be a range, supply load can also be a range.

TANIM should show this range instead of giving false precision.

If the lower and upper values fall in different risk bands, the result should be marked as borderline or uncertain. The interface should explain that the farm-size estimate can change the final band.

## Reference quality

The GRCI result must state which reference it uses.

Preferred references are:

1. committed buyer, cooperative, or LGU demand for the crop and period
2. local historical sold or accepted volume
3. broader official utilization data used only with its real geographic scope
4. historical production used as a coordination baseline, not as market demand

A production baseline must not be presented as verified market demand.

## Crop coverage

TANIM uses exact normalized crop labels for automatic cross-source joins.

A crop can support planning when it has both production and area coverage. Price, supply-utilization, and suitability data are added only when a safe mapping exists.

The crop registry must keep unmatched labels separate instead of guessing that similar names mean the same crop.

## Output contract

A GRCI result should include:

- crop
- location
- harvest period
- planned area range
- reference yield and source
- planned supply range
- reference amount and reference type
- supply-load range
- risk state
- uncertainty note when needed
- source labels used in the calculation

The result must be reproducible from the stored inputs and source data.
