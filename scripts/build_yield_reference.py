#!/usr/bin/env python3
import argparse
import csv
import io
import json
import math
import pathlib
import re
import time
import unicodedata
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets" / "openstat_tables.json"
SCOPE = ROOT / "datasets" / "luzon_scope.json"
GENERATED_REGISTRY = ROOT / "datasets" / "generated" / "crop_registry.generated.json"
DEFAULT_DETAILED = ROOT / "datasets" / "generated" / "yield_reference.csv"
DEFAULT_SUMMARY = ROOT / "datasets" / "generated" / "yield_summary.csv"
DEFAULT_DOCS = ROOT / "docs" / "YIELD_REFERENCE.md"
USER_AGENT = "TANIM/2026 yield reference builder"
SAFE_MAX_CELLS = 90000
REQUEST_PAUSE_SECONDS = 1.1

REF_YEARS = [2021, 2022, 2023, 2024, 2025]
REF_PERIOD_LABEL = "2021-2025"
SOURCE_ID = "PSA-OPENSTAT-CROPS"
DATA_STATUS = "observed"

TABLE_PAIRS = [
    ("PSA-PROD-PALAY-CORN", "PSA-AREA-PALAY-CORN"),
    ("PSA-PROD-NONFOOD", "PSA-AREA-NONFOOD"),
    ("PSA-PROD-FRUITS", "PSA-AREA-FRUITS"),
    ("PSA-PROD-VEG-ROOT", "PSA-AREA-VEG-ROOT"),
]

PERIOD_ORDER = ["Quarter1", "Quarter2", "Semester1", "Quarter3", "Quarter4", "Semester2", "Annual"]


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


def normalize_crop_label(label):
    text = unicodedata.normalize("NFKC", str(label)).strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_geo_label(label):
    text = label.lstrip(". ").strip().upper()
    text = re.sub(r"\s+\d+/$", "", text)
    return re.sub(r"\s+", " ", text)


def normalize_period_label(label):
    return str(label).replace(" ", "")


def dot_depth(label):
    return len(label) - len(label.lstrip("."))


def alias_map(scope):
    result = {}
    for region in scope["regions"]:
        for alias in region["aliases"]:
            result[normalize_geo_label(alias)] = region["id"]
    return result


def table_url(api_base, table):
    return f"{api_base.rstrip('/')}/{table['path']}"


def find_variable(metadata, tokens):
    for variable in metadata.get("variables", []):
        name = f"{variable.get('code', '')} {variable.get('text', '')}".lower()
        if any(token in name for token in tokens):
            return variable
    return None


def crop_variable(metadata, table):
    variables = metadata.get("variables", [])
    hinted = [
        v for v in variables
        if any(h in f"{v.get('code','')} {v.get('text','')}".lower() for h in ("crop", "commodity", "item", "product", "ecosystem"))
        and not any(s in f"{v.get('code','')} {v.get('text','')}".lower() for s in ("geo", "region", "province", "location", "year", "month", "quarter", "semester", "period", "frequency", "unit", "indicator", "element"))
    ]
    if len(hinted) == 1:
        return hinted[0]
    target = table.get("commodity_count")
    if target:
        matches = [v for v in variables if len(v.get("values", [])) == target]
        if len(matches) == 1:
            return matches[0]
    first_size = (table.get("verified_shape") or [None])[0]
    matches = [v for v in variables if len(v.get("values", [])) == first_size]
    if len(matches) == 1:
        return matches[0]
    raise RuntimeError(f"{table['table_key']}: crop dimension is ambiguous")


def geo_variable(metadata):
    for variable in metadata.get("variables", []):
        name = f"{variable.get('code', '')} {variable.get('text', '')}".lower()
        if any(token in name for token in ("geo", "region", "province", "location")):
            return variable
    raise RuntimeError("geo dimension not found")


def year_variable(metadata):
    variable = find_variable(metadata, ("year",))
    if variable is None:
        raise RuntimeError("year dimension not found")
    return variable


def period_variable(metadata):
    variable = find_variable(metadata, ("period", "quarter", "semester"))
    if variable is None:
        for variable in metadata.get("variables", []):
            texts = " ".join(variable.get("valueTexts", []))
            if "Quarter" in texts or "Semester" in texts or "Annual" in texts:
                return variable
        raise RuntimeError("period dimension not found")
    return variable


def luzon_region_codes(geo_var, scope, expected_ids=None):
    aliases = alias_map(scope)
    values = geo_var["values"]
    labels = geo_var.get("valueTexts", values)
    codes = []
    labels_by_code = {}
    matched = set()
    for code, label in zip(values, labels):
        if dot_depth(label) != 2:
            continue
        normalized = normalize_geo_label(label)
        region_id = aliases.get(normalized)
        if region_id:
            matched.add(region_id)
            codes.append(code)
            labels_by_code[code] = label
    if not codes:
        raise RuntimeError("no Luzon region rows found")
    expected = set(expected_ids or [])
    missing = expected - matched
    if missing:
        raise RuntimeError(f"missing Luzon regions {sorted(missing)}; matched {sorted(matched)}")
    return codes, labels_by_code


def year_codes(year_var, years):
    values = year_var["values"]
    labels = year_var.get("valueTexts", values)
    wanted = {str(y) for y in years}
    codes = [code for code, label in zip(values, labels) if str(label) in wanted]
    if len(codes) != len(wanted):
        found = {str(label) for label in labels}
        raise RuntimeError(f"year selection incomplete; wanted {sorted(wanted)}, found sample {sorted(found)[:5]}")
    return codes


def period_codes(period_var):
    values = period_var["values"]
    labels = period_var.get("valueTexts", values)
    wanted = set(PERIOD_ORDER)
    codes = []
    labels_by_code = {}
    for code, label in zip(values, labels):
        norm = normalize_period_label(label)
        if norm in wanted:
            codes.append(code)
            labels_by_code[code] = norm
    if not codes:
        raise RuntimeError("no usable periods found")
    return codes, labels_by_code


def query_batches(selected):
    lengths = [len(values) for _, values in selected]
    if not lengths:
        return
    total = math.prod(lengths)
    if total <= SAFE_MAX_CELLS:
        yield selected
        return
    splittable = [i for i, n in enumerate(lengths) if n > 1]
    if not splittable:
        raise RuntimeError("query cannot be split below the cell limit")
    idx = max(splittable, key=lambda i: lengths[i])
    variable, values = selected[idx]
    mid = max(1, len(values) // 2)
    for part in (values[:mid], values[mid:]):
        if not part:
            continue
        batch = list(selected)
        batch[idx] = (variable, part)
        yield from query_batches(batch)


def px_body(batch):
    query = []
    for variable, values in batch:
        query.append({"code": variable["code"], "selection": {"filter": "item", "values": values}})
    return {"query": query, "response": {"format": "csv"}}


def fetch_table_values(api_base, table, geo_codes, year_codes_list, period_codes_list):
    url = table_url(api_base, table)
    metadata = http_json(url)
    crop_var = crop_variable(metadata, table)
    geo_var = geo_variable(metadata)
    year_var = year_variable(metadata)
    period_var = period_variable(metadata)
    selected = [
        (crop_var, list(crop_var["values"])),
        (geo_var, list(geo_codes)),
        (year_var, list(year_codes_list)),
        (period_var, list(period_codes_list)),
    ]
    frames = []
    for batch in query_batches(selected):
        text = post_csv(url, px_body(batch))
        frames.append(text)
        time.sleep(REQUEST_PAUSE_SECONDS)
    return frames, metadata


def parse_frames(frames, crop_var, geo_var, year_var, period_var):
    crop_labels = {c: t for c, t in zip(crop_var["values"], crop_var.get("valueTexts", crop_var["values"]))}
    geo_labels = {c: t for c, t in zip(geo_var["values"], geo_var.get("valueTexts", geo_var["values"]))}
    year_labels = {c: t for c, t in zip(year_var["values"], year_var.get("valueTexts", year_var["values"]))}
    period_labels = {c: t for c, t in zip(period_var["values"], period_var.get("valueTexts", period_var["values"]))}
    out = {}
    for text in frames:
        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        if header is None:
            continue
        # Header is Crop, Geolocation, then one column per Year x Period combo.
        data_cols = header[2:]
        for row in reader:
            if len(row) < 3:
                continue
            crop_text = row[0]
            geo_text = row[1]
            for col_name, cell in zip(data_cols, row[2:]):
                # Column names look like "2021 Annual" or "2021 Quarter 1".
                # Year is the first token. Period is the rest.
                tokens = col_name.split()
                if len(tokens) < 2:
                    continue
                year_text = tokens[0].strip()
                period_text = " ".join(tokens[1:])
                period_norm = normalize_period_label(period_text)
                if period_norm not in PERIOD_ORDER:
                    continue
                if year_text not in {str(y) for y in REF_YEARS}:
                    continue
                key = (crop_text, geo_text, year_text, period_norm)
                out[key] = cell.strip()
    return out, {"crop": crop_labels, "geo": geo_labels, "year": year_labels, "period": period_labels}


def to_number(cell):
    if cell is None:
        return None
    text = str(cell).strip()
    if text in ("", "..", ".", "-", "NA", "n.a.", "..."):
        return None
    try:
        value = float(text.replace(",", ""))
    except ValueError:
        return None
    return value


def valid_crops(registry):
    result = {}
    for crop in registry.get("crops", []):
        if not crop.get("planning_supported"):
            continue
        coverage = crop.get("coverage", {})
        if not (coverage.get("production") and coverage.get("area")):
            continue
        result[normalize_crop_label(crop["canonical_label"])] = crop
    if not result:
        raise RuntimeError("no valid crops with production and area")
    return result


def build_yield_tables(manifest, scope, registry):
    crop_index = valid_crops(registry)
    aliases = alias_map(scope)
    by_key = {t["table_key"]: t for t in manifest["tables"]}
    detailed = []
    for prod_key, area_key in TABLE_PAIRS:
        prod_table = by_key[prod_key]
        area_table = by_key[area_key]
        prod_url = table_url(manifest["api_base"], prod_table)
        prod_meta = http_json(prod_url)
        prod_crop = crop_variable(prod_meta, prod_table)
        prod_geo = geo_variable(prod_meta)
        prod_year = year_variable(prod_meta)
        prod_period = period_variable(prod_meta)
        area_url = table_url(manifest["api_base"], area_table)
        area_meta = http_json(area_url)
        area_crop = crop_variable(area_meta, area_table)
        area_geo = geo_variable(area_meta)
        area_year = year_variable(area_meta)
        area_period = period_variable(area_meta)

        prod_geo_codes, _ = luzon_region_codes(
            prod_geo, scope, prod_table.get("expected_luzon_regions")
        )
        area_geo_codes, _ = luzon_region_codes(
            area_geo, scope, area_table.get("expected_luzon_regions")
        )
        prod_year_codes = year_codes(prod_year, REF_YEARS)
        area_year_codes = year_codes(area_year, REF_YEARS)
        prod_period_codes, _ = period_codes(prod_period)
        area_period_codes, _ = period_codes(area_period)

        prod_frames, _ = fetch_table_values(
            manifest["api_base"], prod_table, prod_geo_codes,
            prod_year_codes, prod_period_codes
        )
        time.sleep(REQUEST_PAUSE_SECONDS)
        area_frames, _ = fetch_table_values(
            manifest["api_base"], area_table, area_geo_codes,
            area_year_codes, area_period_codes
        )

        prod_values, _ = parse_frames(
            prod_frames, prod_crop, prod_geo, prod_year, prod_period
        )
        area_values, _ = parse_frames(
            area_frames, area_crop, area_geo, area_year, area_period
        )

        area_index = {}
        for (area_crop_text, area_geo_text, area_year_text, area_period_norm), area_cell in area_values.items():
            area_region_id = aliases.get(normalize_geo_label(area_geo_text))
            if area_region_id is None:
                continue
            key = (
                normalize_crop_label(area_crop_text),
                area_region_id,
                area_year_text,
                area_period_norm,
            )
            if key in area_index:
                raise RuntimeError(f"duplicate area row after normalization: {key}")
            area_index[key] = area_cell

        # Map source crop text to registry crop via exact normalized label.
        for (crop_text, geo_text, year_text, period_norm), prod_cell in prod_values.items():
            norm = normalize_crop_label(crop_text)
            crop = crop_index.get(norm)
            if crop is None:
                continue
            # Require the same crop to exist in the paired area table family.
            # The registry guarantees production and area coverage, but the pair
            # must match the crop group. Skip cross-group matches.
            tables = crop.get("source_tables", {})
            if prod_key not in tables.get("production", []) and prod_table["family"] == "production":
                # Allow when the crop lists a different production table of the same group.
                # Only skip when the crop has no production table in this pair group.
                prod_keys = set(tables.get("production", []))
                if prod_key not in prod_keys:
                    # Check group match by family prefix: keep strict to avoid wrong joins.
                    continue
            if area_key not in tables.get("area", []):
                continue
            region_id = aliases.get(normalize_geo_label(geo_text))
            if region_id is None:
                continue
            area_cell = area_index.get((norm, region_id, year_text, period_norm))
            prod_mt = to_number(prod_cell)
            area_ha = to_number(area_cell)
            if prod_mt is None or area_ha is None or area_ha <= 0:
                continue
            if prod_mt < 0 or area_ha < 0:
                continue
            yield_value = prod_mt / area_ha
            detailed.append({
                "crop_id": crop["crop_id"],
                "display_name": crop["display_name"],
                "canonical_label": crop["canonical_label"],
                "region_id": region_id,
                "region_label": geo_text.lstrip(". "),
                "year": year_text,
                "period": period_norm,
                "production_mt": prod_mt,
                "area_ha": area_ha,
                "yield_mt_per_ha": yield_value,
                "production_table": prod_key,
                "area_table": area_key,
            })
    detailed.sort(key=lambda r: (r["crop_id"], r["region_id"], r["year"], PERIOD_ORDER.index(r["period"]) if r["period"] in PERIOD_ORDER else 99))
    return detailed


def summarize_annual(detailed):
    groups = {}
    for row in detailed:
        if row["period"] != "Annual":
            continue
        key = (row["crop_id"], row["display_name"], row["region_id"], row["region_label"])
        groups.setdefault(key, []).append(row)
    summary = []
    for (crop_id, display_name, region_id, region_label), rows in sorted(groups.items()):
        rows = [r for r in rows if str(r["year"]) in {str(y) for y in REF_YEARS}]
        by_year = {}
        for row in rows:
            year = str(row["year"])
            if year in by_year:
                raise RuntimeError(f"duplicate Annual yield for {crop_id} {region_id} {year}")
            by_year[year] = row
        if set(by_year) != {str(year) for year in REF_YEARS}:
            continue
        rows = [by_year[str(year)] for year in REF_YEARS]
        yields = [r["yield_mt_per_ha"] for r in rows]
        avg = sum(yields) / len(yields)
        summary.append({
            "crop_id": crop_id,
            "display_name": display_name,
            "region_id": region_id,
            "region_label": region_label,
            "ref_period": REF_PERIOD_LABEL,
            "n_years": len(rows),
            "avg_yield_mt_per_ha": avg,
            "min_yield_mt_per_ha": min(yields),
            "max_yield_mt_per_ha": max(yields),
            "unit": "mt_per_ha",
            "source_id": SOURCE_ID,
            "data_status": DATA_STATUS,
        })
    summary.sort(key=lambda r: (r["crop_id"], r["region_id"]))
    return summary


def write_detailed_csv(path, detailed):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["crop_id", "display_name", "region_id", "region_label", "year", "period", "production_mt", "area_ha", "yield_mt_per_ha", "production_table", "area_table", "source_id", "data_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in detailed:
            writer.writerow({
                "crop_id": row["crop_id"],
                "display_name": row["display_name"],
                "region_id": row["region_id"],
                "region_label": row["region_label"],
                "year": row["year"],
                "period": row["period"],
                "production_mt": f"{row['production_mt']:.2f}",
                "area_ha": f"{row['area_ha']:.2f}",
                "yield_mt_per_ha": f"{row['yield_mt_per_ha']:.4f}",
                "production_table": row["production_table"],
                "area_table": row["area_table"],
                "source_id": SOURCE_ID,
                "data_status": DATA_STATUS,
            })


def write_summary_csv(path, summary):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["crop_id", "display_name", "region_id", "region_label", "ref_period", "n_years", "avg_yield_mt_per_ha", "min_yield_mt_per_ha", "max_yield_mt_per_ha", "unit", "source_id", "data_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in summary:
            writer.writerow({
                "crop_id": row["crop_id"],
                "display_name": row["display_name"],
                "region_id": row["region_id"],
                "region_label": row["region_label"],
                "ref_period": row["ref_period"],
                "n_years": row["n_years"],
                "avg_yield_mt_per_ha": f"{row['avg_yield_mt_per_ha']:.4f}",
                "min_yield_mt_per_ha": f"{row['min_yield_mt_per_ha']:.4f}",
                "max_yield_mt_per_ha": f"{row['max_yield_mt_per_ha']:.4f}",
                "unit": row["unit"],
                "source_id": row["source_id"],
                "data_status": row["data_status"],
            })


def lookup_summary(summary, crop_id, region_id):
    for row in summary:
        if row["crop_id"] == crop_id and row["region_id"] == region_id:
            return row
    return None


def write_docs(path, detailed, summary):
    tomato = lookup_summary(summary, "tomato", "IV-A")
    eggplant = lookup_summary(summary, "eggplant", "IV-A")
    if tomato is None or eggplant is None:
        raise RuntimeError("demo crops tomato and eggplant need CALABARZON summary rows")
    tomato_avg = tomato["avg_yield_mt_per_ha"]
    eggplant_avg = eggplant["avg_yield_mt_per_ha"]
    tomato_example = 2.0 * tomato_avg
    eggplant_example = 1.5 * eggplant_avg
    annual_rows = sum(1 for r in detailed if r["period"] == "Annual")
    crop_count = len({r["crop_id"] for r in detailed})
    region_count = len({r["region_id"] for r in detailed})
    lines = [
        "# Yield reference",
        "",
        "This file explains the TANIM yield reference in plain language.",
        "",
        "## What is yield",
        "",
        "Yield shows how much crop you get from one hectare of land.",
        "",
        "The unit is metric tons per hectare.",
        "",
        "The formula is simple:",
        "",
        "Yield = Production in metric tons divided by Harvested area in hectares.",
        "",
        "We use two official PSA measurements that TANIM already keeps:",
        "production volume and harvested area.",
        "",
        "We only join crops with the same exact name in both sources.",
        "We never guess that similar names mean the same crop.",
        "",
        "## Why five years",
        "",
        "One year can be too high or too low.",
        "Rain, pests, or price shifts can change one harvest.",
        "",
        "So we use five full years, not one year.",
        f"Our reference period is {REF_PERIOD_LABEL}.",
        "Year 2026 is not complete yet, so we do not use it.",
        "",
        "For each crop and Luzon region we keep the yearly yields,",
        "then we report the average, the lowest year, and the highest year.",
        "",
        "The average is the main reference for the app.",
        "The lowest and highest years show the range.",
        "",
        f"TANIM now has {annual_rows} yearly Annual yields for {crop_count} crops in {region_count} Luzon regions.",
        "",
        "## How to use it in the app",
        "",
        "Start with the farmer area in hectares.",
        "",
        "Multiply the area by the average yield.",
        "",
        "Expected production = Area in hectares times Average yield.",
        "",
        f"Example: 2 hectares of tomato times {tomato_avg:.2f} is about {tomato_example:.2f} metric tons.",
        f"Example: 1.5 hectares of eggplant times {eggplant_avg:.2f} is about {eggplant_example:.2f} metric tons.",
        "",
        "Show these same words and numbers in the UI so farmers can check the math.",
        "",
        "## Year and quarter",
        "",
        "The detailed file has one row per crop, region, year, and period.",
        "Period can be Quarter1, Quarter2, Semester1, Quarter3, Quarter4, Semester2, or Annual.",
        "",
        "For palay and corn, quarterly area exists, so quarterly yield exists.",
        "For many vegetables and fruits, quarterly area is missing in the source,",
        "so quarterly yield is missing too. We keep it missing. We do not invent it.",
        "",
        "The summary file uses Annual yields only.",
        "It is stable across quarters.",
        "You can use it for any harvest quarter, but note it is not quarter specific.",
        "",
        "## Geography",
        "",
        "Luzon means NCR, CAR, Region I, Region II, Region III, Region IV-A, MIMAROPA, and Region V.",
        "",
        "Some crop tables have no NCR row. We keep every Luzon row that exists.",
        "We never invent a missing region.",
        "",
        "This first version uses region rows only.",
        "Province rows are next. The file format already allows them.",
        "",
        "## Files",
        "",
        "Detailed yearly yields are in datasets/generated/yield_reference.csv.",
        "Five year summary is in datasets/generated/yield_summary.csv.",
        "",
        "Detailed columns keep production, area, yield, source tables, and source id.",
        "Summary columns keep ref period, year count, average yield, min yield, and max yield.",
        "",
        "## Limits",
        "",
        "Yield is a production baseline. It is not market demand.",
        "Do not present it as verified demand.",
        "",
        "A production baseline helps planning. It does not prove a glut or a shortage.",
        "Use it with the GRCI reference rules in docs/GRCI_SPEC.md.",
        "",
        "Source tables can be revised. Rebuild the reference before a new release.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def check_committed_files(detailed_path, summary_path, docs_path):
    if not detailed_path.exists():
        raise RuntimeError("committed detailed yield file is missing")
    if not summary_path.exists():
        raise RuntimeError("committed yield summary is missing")
    if not docs_path.exists():
        raise RuntimeError("committed yield docs are missing")
    with detailed_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        expected_detail = ["crop_id", "display_name", "region_id", "region_label", "year", "period", "production_mt", "area_ha", "yield_mt_per_ha", "production_table", "area_table", "source_id", "data_status"]
        if reader.fieldnames != expected_detail:
            raise RuntimeError(f"detailed yield schema changed: {reader.fieldnames}")
        detailed = list(reader)
    with summary_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        expected_summary = ["crop_id", "display_name", "region_id", "region_label", "ref_period", "n_years", "avg_yield_mt_per_ha", "min_yield_mt_per_ha", "max_yield_mt_per_ha", "unit", "source_id", "data_status"]
        if reader.fieldnames != expected_summary:
            raise RuntimeError(f"yield summary schema changed: {reader.fieldnames}")
        summary = list(reader)
    if not detailed or not summary:
        raise RuntimeError("yield files are empty")
    # Math check: each detailed yield equals production divided by area.
    seen_detail = set()
    for row in detailed:
        detail_key = (row["crop_id"], row["region_id"], row["year"], row["period"])
        if detail_key in seen_detail:
            raise RuntimeError(f"duplicate detailed yield row: {detail_key}")
        seen_detail.add(detail_key)
        prod = float(row["production_mt"])
        area = float(row["area_ha"])
        y = float(row["yield_mt_per_ha"])
        if area <= 0:
            raise RuntimeError("area must be above zero")
        if abs((prod / area) - y) > 0.01:
            raise RuntimeError(f"yield math failed for {row['crop_id']} {row['region_id']} {row['year']} {row['period']}")
    # Summary check: avg, min, max match detailed Annual rows.
    by_key = {}
    for row in detailed:
        if row["period"] != "Annual":
            continue
        if row["year"] not in {str(year) for year in REF_YEARS}:
            continue
        key = (row["crop_id"], row["region_id"])
        by_key.setdefault(key, []).append((row["year"], float(row["yield_mt_per_ha"])))
    for row in summary:
        key = (row["crop_id"], row["region_id"])
        yearly = by_key.get(key, [])
        if not yearly:
            raise RuntimeError(f"summary row has no detailed Annual rows: {key}")
        years = [year for year, _ in yearly]
        if len(years) != len(set(years)):
            raise RuntimeError(f"duplicate Annual year in detailed data: {key}")
        if set(years) != {str(year) for year in REF_YEARS}:
            raise RuntimeError(f"summary row is not backed by five full years: {key}")
        values = [value for _, value in yearly]
        avg = float(row["avg_yield_mt_per_ha"])
        ymin = float(row["min_yield_mt_per_ha"])
        ymax = float(row["max_yield_mt_per_ha"])
        if abs(avg - sum(values) / len(values)) > 0.02:
            raise RuntimeError(f"summary avg failed for {key}")
        if abs(ymin - min(values)) > 0.02:
            raise RuntimeError(f"summary min failed for {key}")
        if abs(ymax - max(values)) > 0.02:
            raise RuntimeError(f"summary max failed for {key}")
        if int(row["n_years"]) != len(REF_YEARS):
            raise RuntimeError(f"summary year count failed for {key}")
        if row["ref_period"] != REF_PERIOD_LABEL:
            raise RuntimeError(f"summary period failed for {key}")
    # Luzon scope check.
    text = detailed_path.read_text(encoding="utf-8") + summary_path.read_text(encoding="utf-8")
    for banned in ("Visayas", "Mindanao", "Philippines", "BARMM", "Caraga"):
        if banned in text:
            raise RuntimeError(f"yield files must stay Luzon-only, found {banned}")
    # Demo crops present.
    keys = {(r["crop_id"], r["region_id"]) for r in summary}
    if ("tomato", "IV-A") not in keys or ("eggplant", "IV-A") not in keys:
        raise RuntimeError("tomato and eggplant CALABARZON summary rows are required")
    print(f"OK: {len(detailed)} detailed yields and {len(summary)} summary rows passed offline checks")


def check_live_sample():
    manifest = read_json(MANIFEST)
    by_key = {t["table_key"]: t for t in manifest["tables"]}
    base = manifest["api_base"]
    # Light live sample: eggplant and tomato, CALABARZON, Annual, 2021-2025.
    prod_table = by_key["PSA-PROD-VEG-ROOT"]
    area_table = by_key["PSA-AREA-VEG-ROOT"]
    prod_url = table_url(base, prod_table)
    prod_meta = http_json(prod_url)
    prod_crop = crop_variable(prod_meta, prod_table)
    prod_geo = geo_variable(prod_meta)
    prod_year = year_variable(prod_meta)
    prod_period = period_variable(prod_meta)
    scope = read_json(SCOPE)
    aliases_for_live = alias_map(scope)
    prod_geo_codes, _ = luzon_region_codes(
        prod_geo, scope, prod_table.get("expected_luzon_regions")
    )
    # Find CALABARZON code.
    calabarzon = None
    for code in prod_geo_codes:
        label = None
        for c, t in zip(prod_geo["values"], prod_geo.get("valueTexts", prod_geo["values"])):
            if c == code:
                label = t
                break
        if label and "IV-A" in label:
            calabarzon = code
            break
    if calabarzon is None:
        raise RuntimeError("CALABARZON region code not found")
    prod_year_codes = year_codes(prod_year, REF_YEARS)
    prod_period_codes, _ = period_codes(prod_period)
    # Keep only Annual period code.
    annual_code = None
    for code in prod_period_codes:
        for c, t in zip(prod_period["values"], prod_period.get("valueTexts", prod_period["values"])):
            if c == code and normalize_period_label(t) == "Annual":
                annual_code = code
                break
    area_meta = http_json(table_url(base, area_table))
    area_crop = crop_variable(area_meta, area_table)
    area_geo = geo_variable(area_meta)
    area_year = year_variable(area_meta)
    area_period = period_variable(area_meta)
    area_geo_codes, _ = luzon_region_codes(
        area_geo, scope, area_table.get("expected_luzon_regions")
    )
    area_calabarzon = None
    for code, label in zip(area_geo["values"], area_geo.get("valueTexts", area_geo["values"])):
        if code in area_geo_codes and aliases_for_live.get(normalize_geo_label(label)) == "IV-A":
            area_calabarzon = code
            break
    if area_calabarzon is None:
        raise RuntimeError("CALABARZON area region code not found")
    area_year_codes = year_codes(area_year, REF_YEARS)
    area_period_codes, area_period_labels = period_codes(area_period)
    area_annual_code = next(
        (code for code in area_period_codes if area_period_labels[code] == "Annual"),
        None,
    )
    if annual_code is None or area_annual_code is None:
        raise RuntimeError("Annual period code not found")

    prod_frames, _ = fetch_table_values(
        base, prod_table, [calabarzon], prod_year_codes, [annual_code]
    )
    area_frames, _ = fetch_table_values(
        base, area_table, [area_calabarzon], area_year_codes, [area_annual_code]
    )
    if not prod_frames or not area_frames:
        raise RuntimeError("live OpenSTAT sample returned no frames")

    prod_values, _ = parse_frames(
        prod_frames, prod_crop, prod_geo, prod_year, prod_period
    )
    area_values, _ = parse_frames(
        area_frames, area_crop, area_geo, area_year, area_period
    )

    def live_index(values):
        index = {}
        for (crop_text, geo_text, year_text, period_norm), cell in values.items():
            if period_norm != "Annual":
                continue
            region_id = aliases_for_live.get(normalize_geo_label(geo_text))
            if region_id != "IV-A":
                continue
            key = (normalize_crop_label(crop_text), year_text)
            if key in index:
                raise RuntimeError(f"duplicate live sample row after normalization: {key}")
            index[key] = cell
        return index

    prod_index = live_index(prod_values)
    area_index = live_index(area_values)
    for crop_name in ("tomato", "eggplant"):
        for year in REF_YEARS:
            key = (crop_name, str(year))
            prod_mt = to_number(prod_index.get(key))
            area_ha = to_number(area_index.get(key))
            if prod_mt is None or prod_mt < 0:
                raise RuntimeError(f"missing live production sample for {key}")
            if area_ha is None or area_ha <= 0:
                raise RuntimeError(f"missing live harvested-area sample for {key}")
            live_yield = prod_mt / area_ha
            if not math.isfinite(live_yield) or live_yield < 0:
                raise RuntimeError(f"invalid live yield sample for {key}")

    print("OK: live OpenSTAT yield sample parsed for tomato and eggplant")


def main():
    parser = argparse.ArgumentParser(description="Build TANIM historical yield reference from PSA production and area.")
    parser.add_argument("--detailed-output", type=pathlib.Path, default=DEFAULT_DETAILED)
    parser.add_argument("--summary-output", type=pathlib.Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--docs-output", type=pathlib.Path, default=DEFAULT_DOCS)
    parser.add_argument("--check-only", action="store_true", help="Audit committed yield files without replacing them.")
    parser.add_argument("--live-sample", action="store_true", help="With check-only, also fetch a light live OpenSTAT sample.")
    args = parser.parse_args()

    if args.check_only:
        check_committed_files(args.detailed_output, args.summary_output, args.docs_output)
        if args.live_sample:
            check_live_sample()
        return

    manifest = read_json(MANIFEST)
    scope = read_json(SCOPE)
    registry = read_json(GENERATED_REGISTRY)
    detailed = build_yield_tables(manifest, scope, registry)
    if not detailed:
        raise RuntimeError("no yields could be computed; check production and area joins")
    summary = summarize_annual(detailed)
    if not summary:
        raise RuntimeError("no summary rows; need all five Annual years per crop and region")
    write_detailed_csv(args.detailed_output, detailed)
    write_summary_csv(args.summary_output, summary)
    write_docs(args.docs_output, detailed, summary)
    print(f"Wrote {len(detailed)} detailed yields to {args.detailed_output}")
    print(f"Wrote {len(summary)} summary rows to {args.summary_output}")
    print(f"Wrote yield docs to {args.docs_output}")


if __name__ == "__main__":
    main()
