# TANIM datasets

This folder contains the source layer used by TANIM.

Verified source coverage

- [VERIFIED_COVERAGE.md](../docs/VERIFIED_COVERAGE.md): strict audit of crop, geography, period, and price coverage
- [CROP_COVERAGE.md](../docs/CROP_COVERAGE.md): current Explorer crop coverage summary
- [openstat_tables.json](openstat_tables.json): 59 verified PSA plant-data tables
- [luzon_scope.json](luzon_scope.json): accepted names for the eight Luzon administrative regions
- [crop_registry.json](crop_registry.json): rules and manual overrides for safe crop joins
- [generated/crop_registry.generated.json](generated/crop_registry.generated.json): live generated Explorer crop catalog
- [generated/crop_coverage.csv](generated/crop_coverage.csv): row-by-row Explorer coverage matrix
- [price_series_policy.json](price_series_policy.json): precedence for overlapping PSA price series
- [../scripts/fetch_openstat_luzon.py](../scripts/fetch_openstat_luzon.py): verifies and materializes all selected PSA rows
- [../scripts/build_crop_registry.py](../scripts/build_crop_registry.py): builds and audits the live crop registry

Price data

- PSA farmgate: 18 plant tables, including current and legacy series
- PSA retail: 24 plant tables, including current, revised, and legacy series
- [da_price_monitoring_ncr_latest.csv](da_price_monitoring_ncr_latest.csv): complete recent DA NCR report snapshot. It is supplemental because the linked DA reports are not all-Luzon.

Other concept-note sources

- PSA crop production and planted or harvested area
- PSA Supply Utilization Accounts
- [weather_api_config.json](weather_api_config.json): caller-provided Luzon coordinates, with Tanauan only as the demo default
- [nccag_reference.json](nccag_reference.json): all 21 NCCAG Version 2.0 crop-suitability layers and eight hazards
- [pagasa_agroclimatic_august_2026.json](pagasa_agroclimatic_august_2026.json): Luzon-wide August review and September outlook context

Demo-only data

- [demo_farm_plans.csv](demo_farm_plans.csv)
- [demo_demand_proxy.csv](demo_demand_proxy.csv)

The fixed demo uses tomato and eggplant. The source data layer is not restricted to those crops.

Farm size in a real user plan is an estimate. TANIM stores an area margin so the GRCI can work with a range instead of treating the input as exact. The fixed synthetic demo uses a zero margin because its values are controlled demo inputs.
