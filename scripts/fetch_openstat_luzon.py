#!/usr/bin/env python3
import argparse
import csv
import io
import json
import math
import pathlib
import re
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets" / "openstat_tables.json"
SCOPE = ROOT / "datasets" / "luzon_scope.json"
DEFAULT_OUT = ROOT / "datasets" / "openstat"
USER_AGENT = "TANIM/2026 data fetcher"
SAFE_MAX_CELLS = 90000
REQUEST_PAUSE_SECONDS = 1.1


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def post_csv(url, body):
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        return response.read().decode("utf-8-sig")


def normalize_label(label):
    text = label.lstrip(". ").strip().upper()
    text = re.sub(r"\s+\d+/$", "", text)
    return re.sub(r"\s+", " ", text)


def dot_depth(label):
    return len(label) - len(label.lstrip("."))


def alias_map(scope):
    result = {}
    for region in scope["regions"]:
        for alias in region["aliases"]:
            result[normalize_label(alias)] = region["id"]
    return result


def is_geo_variable(variable):
    name = f"{variable.get('code', '')} {variable.get('text', '')}".lower()
    return any(token in name for token in ("geo", "region", "province", "location"))


def select_luzon_values(variable, scope, expected_region_ids=None):
    aliases = alias_map(scope)
    values = variable["values"]
    labels = variable.get("valueTexts", values)
    selected = []
    matched_regions = set()
    active_region = None

    for code, label in zip(values, labels):
        depth = dot_depth(label)
        normalized = normalize_label(label)
        if depth <= 2:
            active_region = aliases.get(normalized)
            if active_region:
                matched_regions.add(active_region)
                selected.append(code)
        elif active_region:
            selected.append(code)

    if not selected:
        raise RuntimeError(f"No Luzon geolocations found in {variable.get('text')}")

    expected = set(expected_region_ids or [])
    missing = expected - matched_regions
    if missing:
        raise RuntimeError(
            f"{variable.get('text')}: missing Luzon regions {sorted(missing)}; "
            f"matched {sorted(matched_regions)}"
        )
    return selected


def verify_shape(metadata, table):
    expected = table.get("verified_shape")
    if not expected:
        return
    actual = [len(variable.get("values", [])) for variable in metadata.get("variables", [])]
    if len(actual) != len(expected):
        raise RuntimeError(
            f"{table['table_key']}: expected {len(expected)} dimensions, got {len(actual)}"
        )
    for index, (current, minimum) in enumerate(zip(actual, expected), start=1):
        if current < minimum:
            raise RuntimeError(
                f"{table['table_key']}: dimension {index} shrank from verified "
                f"minimum {minimum} to {current}"
            )


def chosen_values(metadata, table, scope):
    verify_shape(metadata, table)
    result = []
    for variable in metadata["variables"]:
        values = list(variable["values"])
        if table["geo_scope"] == "luzon" and is_geo_variable(variable):
            values = select_luzon_values(
                variable,
                scope,
                table.get("expected_luzon_regions"),
            )
        result.append((variable, values))
    return result


def chunks(values, size):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def query_batches(selected):
    lengths = [len(values) for _, values in selected]
    if not lengths:
        return
    total = math.prod(lengths)
    if total <= SAFE_MAX_CELLS:
        yield selected
        return

    splittable = [index for index, length in enumerate(lengths) if length > 1]
    if not splittable:
        raise RuntimeError("OpenSTAT query cannot be split below the cell limit")

    split_index = max(splittable, key=lambda index: lengths[index])
    variable, values = selected[split_index]
    midpoint = max(1, len(values) // 2)

    for part in (values[:midpoint], values[midpoint:]):
        if not part:
            continue
        batch = list(selected)
        batch[split_index] = (variable, part)
        yield from query_batches(batch)


def px_body(batch):
    query = []
    for variable, values in batch:
        query.append({
            "code": variable["code"],
            "selection": {"filter": "item", "values": values},
        })
    return {"query": query, "response": {"format": "csv"}}


def append_csv_text(target, text, expected_header):
    reader = csv.reader(io.StringIO(text))
    local_header = next(reader, None)
    if local_header is None:
        return expected_header
    if expected_header is not None and local_header != expected_header:
        raise RuntimeError("OpenSTAT returned inconsistent headers across batches")

    header = expected_header or local_header
    with target.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        if expected_header is None:
            writer.writerow(local_header)
        writer.writerows(reader)
    return header


def table_url(api_base, table):
    return f"{api_base.rstrip('/')}/{table['path']}"


def verify_table(api_base, table, scope):
    metadata = http_json(table_url(api_base, table))
    chosen_values(metadata, table, scope)
    return [len(variable.get("values", [])) for variable in metadata["variables"]]


def fetch_table(api_base, table, scope, out_dir):
    url = table_url(api_base, table)
    metadata = http_json(url)
    selected = chosen_values(metadata, table, scope)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{table['table_key'].lower()}.csv"
    target.unlink(missing_ok=True)

    header = None
    for batch in query_batches(selected):
        text = post_csv(url, px_body(batch))
        header = append_csv_text(target, text, header)
        time.sleep(REQUEST_PAUSE_SECONDS)

    if header is None:
        raise RuntimeError(f"{table['table_key']}: OpenSTAT returned no CSV rows")
    return target


def main():
    manifest = read_json(MANIFEST)
    scope = read_json(SCOPE)
    families = sorted({table["family"] for table in manifest["tables"]})

    parser = argparse.ArgumentParser(
        description="Verify or fetch TANIM plant datasets from PSA OpenSTAT."
    )
    parser.add_argument(
        "--family",
        action="append",
        choices=families,
        help="Limit to one or more families. Default: all.",
    )
    parser.add_argument("--output-dir", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Check every selected table path and verified minimum shape without downloading CSV data.",
    )
    args = parser.parse_args()

    wanted = set(args.family or families)
    tables = [table for table in manifest["tables"] if table["family"] in wanted]

    for index, table in enumerate(tables, start=1):
        if args.verify_only:
            shape = verify_table(manifest["api_base"], table, scope)
            print(f"[{index}/{len(tables)}] OK {table['table_key']} {shape}")
            time.sleep(REQUEST_PAUSE_SECONDS)
        else:
            path = fetch_table(manifest["api_base"], table, scope, args.output_dir)
            print(f"[{index}/{len(tables)}] {table['table_key']} -> {path}")


if __name__ == "__main__":
    main()
