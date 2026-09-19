# TANIM datasets

This folder contains the source and generated data used by TANIM.

Verified coverage and documentation

- [../docs/VERIFIED_COVERAGE.md](../docs/VERIFIED_COVERAGE.md): audited crop, geography, period, and price coverage
- [../docs/CROP_COVERAGE.md](../docs/CROP_COVERAGE.md): current Explorer crop coverage summary
- [../docs/DATA_DICTIONARY.md](../docs/DATA_DICTIONARY.md): data fields and generated records
- [../docs/LIMITATIONS.md](../docs/LIMITATIONS.md): known data and evidence limits
- [../docs/YIELD_REFERENCE.md](../docs/YIELD_REFERENCE.md): historical yield method and limits

Core source controls

- [openstat_tables.json](openstat_tables.json): 59 verified PSA plant-data tables
- [luzon_scope.json](luzon_scope.json): accepted names for the eight Luzon administrative regions
- [crop_registry.json](crop_registry.json): safe crop-join rules
- [generated/crop_registry.generated.json](generated/crop_registry.generated.json): generated Explorer catalog
- [generated/crop_coverage.csv](generated/crop_coverage.csv): row-by-row Explorer coverage matrix
- [generated/yield_reference.csv](generated/yield_reference.csv): detailed regional historical yield rows
- [generated/yield_summary.csv](generated/yield_summary.csv): regional annual yield summary for planning
- [price_series_policy.json](price_series_policy.json): policy for overlapping PSA price series
- [sources.json](sources.json): source and provenance catalog

Context data

- [da_price_monitoring_ncr_latest.csv](da_price_monitoring_ncr_latest.csv): recent DA NCR market-price snapshot
- [weather_api_config.json](weather_api_config.json): Open-Meteo runtime configuration for Luzon coordinates
- [nccag_reference.json](nccag_reference.json): NCCAG crop-suitability and hazard layer references
- [pagasa_agroclimatic_august_2026.json](pagasa_agroclimatic_august_2026.json): Luzon agroclimatic context

Fixed demo data

- [demo_farm_plans.csv](demo_farm_plans.csv): synthetic tomato and eggplant plans
- [demo_coordination_baseline.csv](demo_coordination_baseline.csv): synthetic demo comparison baseline

The fixed demo uses tomato and eggplant. The Explorer and yield layers are broader.

Farm size can be approximate. Real plans can store a margin so GRCI can use an area range instead of an exact value.
