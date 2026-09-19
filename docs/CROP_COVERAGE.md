# Explorer crop coverage

Audit date: 2026-09-19.

TANIM currently has 313 Explorer planning entries with safe production and area joins.

| Data context | Explorer entries |
| --- | ---: |
| Production | 313 |
| Area | 313 |
| Farmgate price | 106 |
| Retail price | 9 |
| Supply Utilization Accounts | 39 |
| NCCAG suitability context | 9 |

The full row-by-row matrix is in [crop_coverage.csv](../datasets/generated/crop_coverage.csv).

The machine-readable Explorer catalog is in [crop_registry.generated.json](../datasets/generated/crop_registry.generated.json).

## Reading the matrix

Every Explorer entry has production and area coverage because both are required before TANIM allows a planning entry.

A yes in another column means TANIM found a safe exact normalized source-label join, or a reviewed manual mapping.

A no does not prove that the source has no related data. It means TANIM does not currently have a safe cross-source join for that entry.

Supply Utilization Accounts are national context only. They must not be presented as Luzon demand.

NCCAG context can be a direct layer or a broader reviewed group layer. The matrix records the layer and its specificity.

Source entries can include varieties, forms, and crop products. The 313 entries are not a count of unique biological species.
