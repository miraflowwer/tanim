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

## price_series_policy.json

This file prevents incompatible PSA price vintages from being merged without warning.

Farmgate display precedence is legacy for 1990 to 2009 and current for 2010 onward.

Retail display precedence is legacy for 1990 to 2011, revised for 2012 to 2017, and current for 2018 onward.

All raw source series remain available even when they overlap.

## luzon_scope.json

The file keeps aliases used by different PSA table generations for NCR, CAR, Regions I, II, III, IV-A, MIMAROPA, and Region V.

The filter includes matching region rows and their province or city children. It excludes the national total and all Visayas and Mindanao regions.

## fetch_openstat_luzon.py

Use `--verify-only` first. This checks each selected API path and confirms that its current dimension sizes have not fallen below the audited minimum.

Without `--verify-only`, the script downloads every selected value. Geographic tables are filtered to available Luzon rows. National-only SUA tables remain national.

Large requests are recursively divided below 90,000 cells. CSV batches are streamed to disk so a large table is not held entirely in memory.

## da_price_monitoring_ncr_latest.csv

This file is the complete DA weekly NCR report snapshot for 7 to 13 September 2026. It is supplemental recent-price evidence, not all-Luzon coverage.

## demo files

The fixed demo uses tomato and eggplant synthetic plans. The demo files do not define the supported crop universe.
