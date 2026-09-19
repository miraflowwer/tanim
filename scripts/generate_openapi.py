#!/usr/bin/env python3
"""Generate the checked-in contract from the actual FastAPI application.

Run from the repository root:
    python scripts/generate_openapi.py
    python scripts/generate_openapi.py --check
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "openapi" / "openapi.json"
sys.path.insert(0, str(ROOT))
# The checked-in contract must describe the durable production adapter, never the in-memory demo.
os.environ["TANIM_RUNTIME_MODE"] = "postgres"

from backend.app.main import app  # noqa: E402


def schema_text() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when committed schema differs")
    args = parser.parse_args()
    generated = schema_text()
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != generated:
            print("openapi/openapi.json differs from FastAPI app.openapi(); regenerate and commit it.")
            return 1
        print("OpenAPI matches FastAPI.")
        return 0
    OUT.write_text(generated, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} from FastAPI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
