# TANIM interface rules

This is the small design guide for the Step 7 farmer interface.

## Main rules

1. Keep text clear on a phone and projector.
2. Show the reference type and evidence status beside each result.
3. A manual source label is user-provided. It is not proof that the amount is
   reviewed or verified.
4. Direct local committed demand is reserved for a reviewed source
   integration. The farmer form must not create it from free text.
5. Historical production is a baseline, not market demand.
6. National utilization is context only.
7. Synthetic demo values must always say synthetic and not observed demand.
8. The browser only displays values returned by the Python service.

## Layout

Use one main column. Use large buttons and form fields. Keep base text at
18 px. Use system fonts so the demo does not need a font download.

Color tokens and spacing values are in `src/styles.css`.

## Form

The form uses this order:

1. crop
2. Luzon region
3. municipality or location
4. farm size
5. farm-size margin
6. planting date
7. expected harvest month
8. comparison evidence fields

Farm size must be greater than 0. Crop and region choices come from the
backend. They only expose crop-region pairs with a committed five-year yield
row.

The normal form uses the safe reference types returned by `GET /api/options`:
historical production baseline, local historical absorption, and national
utilization context. It does not offer the synthetic demo or
`local_committed_demand`. A normal response carries
`evidence_status: user_provided_unverified`.

## Demo buttons

Show only the two committed fixtures:

- Tomato demo (high)
- Eggplant demo (low)

The demo response carries `evidence_status: fixed_synthetic`. Do not add a
fake buyer, fake committed demand, or fake national value to show another
state.

## Evidence display

Map the engine evidence quality to a short badge:

- synthetic: SYNTHETIC
- historical_proxy: HISTORICAL PROXY
- national_context: NATIONAL CONTEXT
- production_baseline: HISTORICAL BASELINE

Show the engine reference label and evidence note unchanged. Also show the
evidence status. Only `reviewed_verified` evidence may use market-demand
wording. The current farmer form never produces that status.

## Result card

Show these items in order:

1. state
2. planned area
3. estimated area range, when there is a range
4. reference yield and source
5. expected production
6. comparison reference
7. reference type and evidence badge
8. evidence status
9. evidence note
10. supply load and comparison state
11. uncertainty
12. explanation
13. plan summary
14. provenance details

For an `ok` result, the state banner uses the engine risk state. Baseline and
context-only results keep their safe wording.

## Copy rules

Use English for the main text. Keep only the approved short Tagalog hints that
already appear in the form.

Do not rewrite the engine explanation, evidence note, or uncertainty note.
Render them as returned by the backend.

## Not in this MVP

Do not add a municipality geocoder, login system, charts, price dashboard, or
multi-farmer account system yet.
