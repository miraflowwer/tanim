# Data dictionary

## openstat_tables.json

This is the authoritative PSA table manifest.

- family: production, area, bearing, farmgate, retail, or sua
- geo_scope: luzon or national
- path: official PXWeb API path below the PSA OpenSTAT API base
- table_key: stable TANIM identifier
- verified_shape: minimum dimension sizes confirmed on 19 September 2026
- series_id: source-vintage identifier for price tables
- period_start and period_end: years exposed by that source series
- precedence: lower value is preferred when a display needs one overlapping price series

The manifest contains 59 plant-data tables.

## crop_registry.json

This file defines safe rules for joining crop names across TANIM sources.

Automatic joins use exact normalized labels only. Similar names, partial names, grades, and varieties are not merged by guesswork.

A crop can support planning when both production and area data resolve to the same normalized crop label.

Farmgate, retail, Supply Utilization Accounts, and NCCAG context are optional. They are attached only when a safe mapping exists.

Tomato and eggplant have manual display overrides for the fixed demo. Their NCCAG mapping points to the general Vegetables layer because NCCAG does not provide separate tomato and eggplant layers in the referenced layer list.

## generated crop registry

[generated/crop_registry.generated.json](generated/crop_registry.generated.json) is the current machine-readable Explorer catalog built from live PSA metadata.

[generated/crop_coverage.csv](generated/crop_coverage.csv) is the compact coverage matrix. Each Explorer row shows whether a safe join exists for production, area, farmgate price, retail price, national SUA context, and NCCAG context.

A no in the matrix means that TANIM has no safe join for that source label. It does not mean that the source has no related data.

The live registry is built by [../scripts/build_crop_registry.py](../scripts/build_crop_registry.py). Use `--check-only` to audit current metadata without replacing the committed snapshot.

## price_series_policy.json

This file prevents incompatible PSA price vintages from being merged without warning.

Farmgate display precedence is legacy for 1990 to 2009 and current for 2010 onward.

Retail display precedence is legacy for 1990 to 2011, revised for 2012 to 2021, and current for 2018 onward.

All raw source series remain available even when they overlap.

## luzon_scope.json

The file keeps aliases used by different PSA table generations for NCR, CAR, Regions I, II, III, IV-A, MIMAROPA, and Region V.

The filter includes matching region rows and their province or city children. It excludes the national total and all Visayas and Mindanao regions.

## fetch_openstat_luzon.py

Use `--verify-only` first. This checks each selected API path and confirms that its current dimension sizes have not fallen below the audited minimum.

Without `--verify-only`, the script downloads every selected value. Geographic tables are filtered to available Luzon rows. National-only SUA tables remain national.

Large requests are recursively divided below 90,000 cells. CSV batches are streamed to disk so a large table is not held entirely in memory.

## build_crop_registry.py

This script reads current OpenSTAT metadata and builds the runtime crop registry.

It only enables planning entries that have both production and area coverage under the same normalized crop label.

It keeps unmatched source labels separate. This reduces the risk of joining different crops, grades, varieties, or product forms by mistake.

The generated catalog can include varieties and product forms. Its entry count is not a count of unique biological species.

## da_price_monitoring_ncr_latest.csv

This file is the complete DA weekly NCR report snapshot for 7 to 13 September 2026. It is supplemental recent-price evidence, not all-Luzon coverage.

## demo files

The fixed demo uses tomato and eggplant synthetic plans. The demo files do not define the supported crop universe.

In `demo_farm_plans.csv`, `farm_size_ha` is the estimated area and `farm_size_margin_ha` is the plus-or-minus margin in hectares.

The synthetic demo uses a margin of 0.0 ha so its fixed scenario stays reproducible. Real user plans should carry a margin when the entered farm size is only an estimate.
