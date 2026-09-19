# Data dictionary

This page explains the main TANIM data files and generated records.

## PSA table manifest

[datasets/openstat_tables.json](../datasets/openstat_tables.json) is the authoritative PSA table manifest.

Important fields include:

- `family`: production, area, bearing, farmgate, retail, or SUA
- `geo_scope`: Luzon or national
- `path`: official PSA OpenSTAT API path
- `table_key`: stable TANIM identifier
- `verified_shape`: minimum source dimensions checked on 19 September 2026
- `series_id`: source version for price tables
- `period_start` and `period_end`: source years
- `precedence`: display preference when official price series overlap

The manifest contains 59 plant-data tables.

## Crop registry

[datasets/crop_registry.json](../datasets/crop_registry.json) defines safe crop-name joins.

Automatic joins use exact normalized labels. Similar names, partial names, grades, and varieties are not merged by guesswork.

A planning entry needs both production and area coverage.

Farmgate, retail, Supply Utilization Accounts, and NCCAG context are optional. TANIM adds them only when a safe mapping exists.

The live Explorer catalog is [datasets/generated/crop_registry.generated.json](../datasets/generated/crop_registry.generated.json).

The compact coverage matrix is [datasets/generated/crop_coverage.csv](../datasets/generated/crop_coverage.csv).

## Price series policy

[datasets/price_series_policy.json](../datasets/price_series_policy.json) prevents official PSA price versions from being silently merged.

Raw source series keep their own `series_id`.

## Luzon scope

[datasets/luzon_scope.json](../datasets/luzon_scope.json) stores accepted source labels for NCR, CAR, Regions I, II, III, IV-A, MIMAROPA, and Region V.

The Luzon filter excludes the national total and all Visayas and Mindanao regions.

## OpenSTAT materializer

[scripts/fetch_openstat_luzon.py](../scripts/fetch_openstat_luzon.py) checks and downloads the selected PSA tables.

Use `--verify-only` before a new materialization.

Large requests are split into safe batches. Geographic tables keep available Luzon rows. National-only SUA tables remain national.

## Crop registry builder

[scripts/build_crop_registry.py](../scripts/build_crop_registry.py) builds the runtime Explorer registry from current source metadata.

Use `--check-only` to compare live metadata with the committed registry snapshot.

## Recent DA price snapshot

[datasets/da_price_monitoring_ncr_latest.csv](../datasets/da_price_monitoring_ncr_latest.csv) is the complete DA NCR weekly report snapshot for 7 to 13 September 2026.

It is recent NCR price context. It is not all-Luzon price coverage.

## Fixed demo data

[datasets/demo_farm_plans.csv](../datasets/demo_farm_plans.csv) contains synthetic farmer plans.

`farm_size_ha` is the estimated area. `farm_size_margin_ha` is its plus-or-minus margin.

[datasets/demo_coordination_baseline.csv](../datasets/demo_coordination_baseline.csv) contains the synthetic comparison values for the fixed demo.

Its fields are:

- `crop_canonical`: TANIM crop name
- `reference_period`: period represented by the synthetic baseline
- `reference_geography`: geography represented by the baseline
- `reference_scope_level`: level of that geography
- `reference_qty_mt`: comparison amount in MT
- `reference_yield_mt_per_ha`: synthetic demo yield
- `reference_area_eq_ha`: area equivalent kept for explanation only
- `reference_type`: must be `demo_coordination_baseline`
- `source_id`: `DEMO-2026`
- `data_status`: `derived_demo`

The demo baseline is not observed market demand.

## GRCI reference metadata

GRCI reference types are defined in [scripts/grci.py](../scripts/grci.py).

Only `local_committed_demand` may use direct market-demand wording.

`local_historical_absorption` is a historical proxy.

`national_utilization_context` is national context only.

`historical_production_baseline` is a past-supply comparison.

`demo_coordination_baseline` is synthetic demo data.

See [GRCI_SPEC.md](GRCI_SPEC.md) for the calculation contract.
