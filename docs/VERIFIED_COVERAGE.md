# Verified coverage

Audit date: 19 September 2026.

The earlier dataset package was not complete enough for the stated Luzon scope.

The concept note requires historical crop production, planted area, farmgate prices, recent price monitoring, Supply Utilization Accounts, weather, NCCAG crop suitability, and PAGASA climate context.

## Production and area

The PSA crop tables cover palay and corn plus non-food and industrial crops, fruit crops, vegetables, and root crops.

Detailed crop tables use Luzon regional and province or city rows where the source publishes them.

The current source tables expose 148 non-food and industrial crop entries, 83 fruit crop entries, and 142 vegetable and root-crop entries for production. Area tables expose 126, 83, and 120 crop entries in the same groups.

The detailed OpenSTAT crop series begins in 2010. PSA notes that annual 1990 to 2009 data for crops other than palay and corn remain available from the Crops Statistics Division, but those older rows are not exposed by the linked OpenSTAT tables. TANIM does not invent them.

## Explorer crop registry

The live audit currently resolves 313 Explorer planning entries with safe production and area joins.

The committed [Explorer crop coverage](CROP_COVERAGE.md) reports 106 entries with a safe farmgate-price join, 9 with a safe retail-price join, 39 with national SUA context, and 9 with NCCAG context.

These are source entries, not unique biological species. An entry can be a crop, variety, form, or crop product.

A yes means TANIM has a safe exact normalized source-label join or a reviewed manual mapping. A no means no safe join is registered yet. It does not prove that the official source has no related data.

The full machine-readable matrix is [crop_coverage.csv](../datasets/generated/crop_coverage.csv).

The scheduled live audit rebuilds the registry in memory and compares it with the committed snapshot. New, removed, or changed source joins make the audit fail until the snapshot is reviewed and refreshed.

## Prices

Price coverage keeps every plant-focused PSA series exposed by the linked price databases.

Farmgate has 18 plant tables. The current series covers 2010 to 2026 and exposes 197 commodity entries across nine categories. The legacy series covers 1990 to 2020 and exposes 192 commodity entries across the same plant categories. Legacy cutflowers begin in 2006.

Retail has 24 plant tables. The current series covers 2018 to 2026 and exposes 112 commodity entries across eight categories. A revised series covers 2012 to 2021 with 74 entries. The legacy series covers 1990 to 2021 with 41 entries.

These counts are source commodity entries, not unique biological species. A crop can occur in several grades, varieties, forms, or source vintages.

Overlapping PSA price series are never silently merged. The raw series retain their own series_id. For one continuous TANIM display, [price_series_policy.json](../datasets/price_series_policy.json) defines which official series is preferred by year.

The linked DA weekly reports cover monitored NCR markets. They are a recent market pulse, not complete Luzon coverage. PSA farmgate and retail tables provide the geographic Luzon price history.

## Climate and suitability

Open-Meteo is configured for caller-provided coordinates anywhere in the TANIM Luzon scope. Tanauan remains only the fixed demo default.

NCCAG Version 2.0 is not limited to a generic vegetables layer. TANIM references all 21 official crop-suitability layers and the eight climate-change-induced multi-hazards. The map itself is nationwide; TANIM uses it for Luzon locations.

The PAGASA August 2026 summary keeps Luzon-wide rainfall, soil-moisture, temperature, crop-stage, and September outlook context instead of a CALABARZON-only summary.

## Supply utilization

The PSA Supply Utilization Accounts are national tables. TANIM keeps the seven plant groups in full: rice and corn, rootcrops, vegetables, nuts, fruits, commercial crops, and non-food crops.

These data must not be presented as Luzon demand.

## Scope rule

Luzon means NCR, CAR, Region I, Region II, Region III, Region IV-A, MIMAROPA, and Region V.

Some production tables do not publish an NCR row. TANIM keeps every available Luzon row and never invents a missing region.

## Repository rule

The selected official tables contain millions of source cells. The full OpenSTAT corpus is therefore not hand-copied into small CSV files in main.

Instead, main contains the audited 59-table manifest, Luzon filter, crop registry, generated Explorer catalog, coverage matrix, price-series policy, tests, and deterministic materializers.

## Demo rule

Tomato and eggplant remain the fixed demonstration pair. They are not the only crops supported by the source layer.

The fixed demo uses exact synthetic farm sizes with a zero margin so the scenario stays reproducible. Real user plans can carry a farm-size margin, and GRCI should report a range when that margin affects the result.
