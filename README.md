# TANIM

TANIM stands for Timely Agricultural Network for Informed Market. It is a planting coordination prototype for farmer groups.

[![Datasets](https://img.shields.io/badge/data-Luzon%20plant%20coverage-2ea44f)](docs/VERIFIED_COVERAGE.md)
[![Tests](https://img.shields.io/badge/tests-dataset%20audit-2ea44f)](tests/test_datasets.py)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Repository map

- [datasets/README.md](datasets/README.md): dataset index
- [datasets/crop_registry.json](datasets/crop_registry.json): safe cross-source crop join rules
- [docs/CROP_COVERAGE.md](docs/CROP_COVERAGE.md): generated Explorer crop coverage summary
- [docs/VERIFIED_COVERAGE.md](docs/VERIFIED_COVERAGE.md): audited crop, geography, and price coverage
- [docs/GRCI_SPEC.md](docs/GRCI_SPEC.md): Glut Risk Coordination Indicator data and uncertainty contract
- [scripts/fetch_openstat_luzon.py](scripts/fetch_openstat_luzon.py): PSA OpenSTAT verifier and materializer
- [scripts/build_crop_registry.py](scripts/build_crop_registry.py): live Explorer crop registry builder
- [tests/test_datasets.py](tests/test_datasets.py): dataset integrity and scope checks
- [tests/test_crop_registry.py](tests/test_crop_registry.py): crop join and farm-size uncertainty checks
- [LICENSE](LICENSE): MIT license for TANIM code and original project material
