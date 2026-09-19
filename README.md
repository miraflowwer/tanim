# TANIM

TANIM stands for Timely Agricultural Network for Informed Market. It is a planting coordination prototype for farmer groups.

[![Datasets](https://img.shields.io/badge/data-Luzon%20plant%20coverage-2ea44f)](docs/VERIFIED_COVERAGE.md)
[![Tests](https://img.shields.io/badge/tests-dataset%20audit-2ea44f)](tests/test_datasets.py)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Repository map

- [docs/README.md](docs/README.md): documentation index
- [datasets/README.md](datasets/README.md): dataset and source index
- [scripts/fetch_openstat_luzon.py](scripts/fetch_openstat_luzon.py): PSA OpenSTAT verifier and materializer
- [scripts/build_crop_registry.py](scripts/build_crop_registry.py): crop registry builder
- [scripts/build_yield_reference.py](scripts/build_yield_reference.py): regional historical yield builder
- [scripts/grci.py](scripts/grci.py): deterministic GRCI engine
- [tests/test_datasets.py](tests/test_datasets.py): dataset integrity checks
- [tests/test_crop_registry.py](tests/test_crop_registry.py): crop registry checks
- [tests/test_yield_reference.py](tests/test_yield_reference.py): yield reference checks
- [tests/test_grci.py](tests/test_grci.py): GRCI and fixed demo checks
- [tests/test_mvp_e2e.py](tests/test_mvp_e2e.py): end-to-end demo, edge cases, and safety guards
- [docs/DEMO_RUNBOOK.md](docs/DEMO_RUNBOOK.md): live demo path and backup plan
- [LICENSE](LICENSE): MIT license for TANIM code and original project material
