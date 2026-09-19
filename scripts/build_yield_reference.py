#!/usr/bin/env python3
"""Build and audit TANIM's regional historical yield reference."""

import argparse
import csv
import io
import json
import math
import pathlib
import re
import time
import unicodedata
import urllib.error
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets" / "openstat_tables.json"
SCOPE = ROOT / "datasets" / "luzon_scope.json"
GENERATED_REGISTRY = (
    ROOT / "datasets" / "generated" / "crop_registry.generated.json"
)
DEFAULT_DETAILED = ROOT / "datasets" / "generated" / "yield_reference.csv"
DEFAULT_SUMMARY = ROOT / "datasets" / "generated" / "yield_summary.csv"
DEFAULT_DOCS = ROOT / "docs" / "YIELD_REFERENCE.md"

USER_AGENT = "TANIM/2026 yield reference builder"
SAFE_MAX_CELLS = 90000
REQUEST_PAUSE_SECONDS = 1.1
RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0)

REF_YEARS = [2021, 2022, 2023, 2024, 2025]
REF_YEAR_TEXT = {str(year) for year in REF_YEARS}
REF_PERIOD_LABEL = "2021-2025"
SOURCE_ID = "PSA-OPENSTAT-CROPS"
DATA_STATUS = "observed"
MIN_SUMMARY_YEARS = len(REF_YEARS)

LUZON_IDS = {"NCR", "CAR", "I", "II", "III", "IV-A", "MIMAROPA", "V"}
BANNED_GEO_WORDS = ("VISAYAS", "MINDANAO", "BARMM", "CARAGA", "PHILIPPINES")

TABLE_PAIRS = [
    ("PSA-PROD-PALAY-CORN", "PSA-AREA-PALAY-CORN"),
    ("PSA-PROD-NONFOOD", "PSA-AREA-NONFOOD"),
    ("PSA-PROD-FRUITS", "PSA-AREA-FRUITS"),
    ("PSA-PROD-VEG-ROOT", "PSA-AREA-VEG-ROOT"),
]

PAIR_BY_PRODUCTION = dict(TABLE_PAIRS)
PAIR_SET = set(TABLE_PAIRS)

PERIOD_ORDER = [
    "Quarter1",
    "Quarter2",
    "Semester1",
    "Quarter3",
    "Quarter4",
    "Semester2",
    "Annual",
]

DETAILED_FIELDS = [
    "crop_id",
    "display_name",
    "region_id",
    "region_label",
    "year",
    "period",
    "production_mt",
    "area_ha",
    "yield_mt_per_ha",
    "production_table",
    "area_table",
    "source_id",
    "data_status",
]

SUMMARY_FIELDS = [
    "crop_id",
    "display_name",
    "region_id",
    "region_label",
    "ref_period",
    "n_years",
    "avg_yield_mt_per_ha",
    "min_yield_mt_per_ha",
    "max_yield_mt_per_ha",
    "unit",
    "source_id",
    "data_status",
]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _request_bytes(request, timeout):
    last_error = None
    for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            last_error = error
            retryable = error.code == 429 or 500 <= error.code < 600
            if not retryable or attempt >= len(RETRY_DELAYS_SECONDS):
                raise
        except urllib.error.URLError as error:
            last_error = error
            if attempt >= len(RETRY_DELAYS_SECONDS):
                raise
        time.sleep(RETRY_DELAYS_SECONDS[attempt])
    raise last_error


def http_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    payload = _request_bytes(request, timeout=60)
    return json.loads(payload.decode("utf-8"))


def post_csv(url, body):
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    return _request_bytes(request, timeout=180).decode("utf-8-sig")


def normalize_crop_label(label):
    text = unicodedata.normalize("NFKC", str(label)).strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_geo_label(label):
    text = str(label).lstrip(". ").strip().upper()
    text = re.sub(r"\s+\d+/$", "", text)
    return re.sub(r"\s+", " ", text)


def normalize_period_label(label):
    return re.sub(r"\s+", "", str(label).strip())


def alias_map(scope):
    result = {}
    for region in scope["regions"]:
        for alias in region["aliases"]:
            normalized = normalize_geo_label(alias)
            previous = result.get(normalized)
            if previous is not None and previous != region["id"]:
                raise RuntimeError(
                    f"geography alias maps to two regions: {alias}"
                )
            result[normalized] = region["id"]
    return result


def table_url(api_base, table):
    return f"{api_base.rstrip('/')}/{table['path']}"


def _variable_name(variable):
    return f"{variable.get('code', '')} {variable.get('text', '')}".lower()


def find_variable(metadata, tokens):
    for variable in metadata.get("variables", []):
        name = _variable_name(variable)
        if any(token in name for token in tokens):
            return variable
    return None


def crop_variable(metadata, table):
    variables = metadata.get("variables", [])
    hinted = []
    for variable in variables:
        name = _variable_name(variable)
        if not any(
            token in name
            for token in ("crop", "commodity", "item", "product", "ecosystem")
        ):
            continue
        if any(
            token in name
            for token in (
                "geo",
                "region",
                "province",
                "location",
                "year",
                "month",
                "quarter",
                "semester",
                "period",
                "frequency",
                "unit",
                "indicator",
                "element",
            )
        ):
            continue
        hinted.append(variable)

    if len(hinted) == 1:
        return hinted[0]

    target = table.get("commodity_count")
    if target:
        matches = [
            variable
            for variable in variables
            if len(variable.get("values", [])) == target
        ]
        if len(matches) == 1:
            return matches[0]

    first_size = (table.get("verified_shape") or [None])[0]
    matches = [
        variable
        for variable in variables
        if len(variable.get("values", [])) == first_size
    ]
    if len(matches) == 1:
        return matches[0]

    raise RuntimeError(f"{table['table_key']}: crop dimension is ambiguous")


def geo_variable(metadata):
    variable = find_variable(
        metadata,
        ("geo", "region", "province", "location"),
    )
    if variable is None:
        raise RuntimeError("geography dimension not found")
    return variable


def year_variable(metadata):
    variable = find_variable(metadata, ("year",))
    if variable is None:
        raise RuntimeError("year dimension not found")
    return variable


def period_variable(metadata):
    variable = find_variable(
        metadata,
        ("period", "quarter", "semester"),
    )
    if variable is not None:
        return variable

    for candidate in metadata.get("variables", []):
        texts = " ".join(candidate.get("valueTexts", []))
        if "Quarter" in texts or "Semester" in texts or "Annual" in texts:
            return candidate

    raise RuntimeError("period dimension not found")


def verify_shape(metadata, table):
    expected = table.get("verified_shape")
    if not expected:
        return
    actual = [
        len(variable.get("values", []))
        for variable in metadata.get("variables", [])
    ]
    if len(actual) != len(expected):
        raise RuntimeError(
            f"{table['table_key']}: expected {len(expected)} dimensions, "
            f"got {len(actual)}"
        )
    for index, (current, minimum) in enumerate(
        zip(actual, expected),
        start=1,
    ):
        if current < minimum:
            raise RuntimeError(
                f"{table['table_key']}: dimension {index} shrank from "
                f"{minimum} to {current}"
            )


def _value_text_pairs(variable):
    values = list(variable.get("values", []))
    labels = list(variable.get("valueTexts", values))
    if len(values) != len(labels):
        raise RuntimeError(
            f"{variable.get('text', variable.get('code'))}: "
            "value and label counts differ"
        )
    return list(zip(values, labels))


def luzon_region_codes(geo_var, scope, expected_ids=None):
    aliases = alias_map(scope)
    region_to_code = {}
    code_to_region = {}
    label_by_code = {}

    for code, label in _value_text_pairs(geo_var):
        region_id = aliases.get(normalize_geo_label(label))
        if region_id is None:
            continue
        if region_id in region_to_code and region_to_code[region_id] != code:
            raise RuntimeError(
                f"{geo_var.get('text')}: duplicate region row for {region_id}"
            )
        region_to_code[region_id] = code
        code_to_region[code] = region_id
        label_by_code[code] = str(label)

    if not region_to_code:
        raise RuntimeError("no Luzon region rows found")

    expected = set(expected_ids or [])
    missing = expected - set(region_to_code)
    if missing:
        raise RuntimeError(
            f"{geo_var.get('text')}: missing Luzon regions "
            f"{sorted(missing)}; matched {sorted(region_to_code)}"
        )

    return region_to_code, code_to_region, label_by_code


def year_codes(year_var, years):
    wanted = {str(year) for year in years}
    result = {}
    for code, label in _value_text_pairs(year_var):
        label_text = str(label).strip()
        if label_text in wanted:
            if label_text in result:
                raise RuntimeError(f"duplicate year row for {label_text}")
            result[label_text] = code

    missing = wanted - set(result)
    if missing:
        raise RuntimeError(
            f"year selection incomplete; missing {sorted(missing)}"
        )
    return result


def period_codes(period_var):
    wanted = set(PERIOD_ORDER)
    result = {}
    for code, label in _value_text_pairs(period_var):
        normalized = normalize_period_label(label)
        if normalized in wanted:
            if normalized in result:
                raise RuntimeError(f"duplicate period row for {normalized}")
            result[normalized] = code

    if "Annual" not in result:
        raise RuntimeError("Annual period not found")
    return result


def crop_codes(crop_var, wanted_normalized=None):
    result = {}
    for code, label in _value_text_pairs(crop_var):
        normalized = normalize_crop_label(label)
        if wanted_normalized is not None and normalized not in wanted_normalized:
            continue
        if normalized in result and result[normalized][0] != code:
            raise RuntimeError(
                f"duplicate normalized crop label in one source: {label}"
            )
        result[normalized] = (code, str(label))

    if wanted_normalized is not None:
        missing = set(wanted_normalized) - set(result)
        if missing:
            raise RuntimeError(
                f"requested crop labels not found: {sorted(missing)}"
            )
    return result


def query_batches(selected):
    lengths = [len(values) for _, values in selected]
    if not lengths or any(length == 0 for length in lengths):
        raise RuntimeError("OpenSTAT query has an empty selection")

    total = math.prod(lengths)
    if total <= SAFE_MAX_CELLS:
        yield selected
        return

    splittable = [
        index
        for index, length in enumerate(lengths)
        if length > 1
    ]
    if not splittable:
        raise RuntimeError("query cannot be split below the cell limit")

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
            "selection": {
                "filter": "item",
                "values": values,
            },
        })
    return {"query": query, "response": {"format": "csv"}}


def fetch_table_values(
    api_base,
    table,
    scope,
    *,
    wanted_crops=None,
    wanted_regions=None,
    wanted_years=None,
    wanted_periods=None,
):
    url = table_url(api_base, table)
    metadata = http_json(url)
    verify_shape(metadata, table)

    crop_var = crop_variable(metadata, table)
    geo_var = geo_variable(metadata)
    year_var = year_variable(metadata)
    period_var = period_variable(metadata)

    crops = crop_codes(crop_var, wanted_crops)
    region_to_code, _, _ = luzon_region_codes(
        geo_var,
        scope,
        table.get("expected_luzon_regions"),
    )
    years = year_codes(
        year_var,
        wanted_years or REF_YEARS,
    )
    periods = period_codes(period_var)

    if wanted_regions is None:
        selected_region_ids = sorted(region_to_code)
    else:
        selected_region_ids = list(wanted_regions)
        missing = set(selected_region_ids) - set(region_to_code)
        if missing:
            raise RuntimeError(
                f"{table['table_key']}: requested regions missing "
                f"{sorted(missing)}"
            )

    selected_periods = (
        list(wanted_periods)
        if wanted_periods is not None
        else [period for period in PERIOD_ORDER if period in periods]
    )
    missing_periods = set(selected_periods) - set(periods)
    if missing_periods:
        raise RuntimeError(
            f"{table['table_key']}: requested periods missing "
            f"{sorted(missing_periods)}"
        )

    selected = [
        (crop_var, [record[0] for record in crops.values()]),
        (geo_var, [region_to_code[region] for region in selected_region_ids]),
        (
            year_var,
            [years[str(year)] for year in (wanted_years or REF_YEARS)],
        ),
        (period_var, [periods[period] for period in selected_periods]),
    ]

    frames = []
    for batch in query_batches(selected):
        frames.append(post_csv(url, px_body(batch)))
        time.sleep(REQUEST_PAUSE_SECONDS)

    return frames


def _parse_data_column(column):
    tokens = str(column).strip().split()
    if len(tokens) < 2:
        return None
    year_text = tokens[0].strip()
    period_text = normalize_period_label(" ".join(tokens[1:]))
    if year_text not in REF_YEAR_TEXT:
        return None
    if period_text not in PERIOD_ORDER:
        return None
    return (year_text, period_text)


def parse_frames(frames, scope):
    aliases = alias_map(scope)
    result = {}

    for frame_index, text in enumerate(frames, start=1):
        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        if header is None:
            raise RuntimeError(
                f"OpenSTAT frame {frame_index} has no header"
            )
        if len(header) < 3:
            raise RuntimeError(
                f"OpenSTAT frame {frame_index} has too few columns"
            )

        parsed_columns = [
            _parse_data_column(column)
            for column in header[2:]
        ]
        if not any(parsed_columns):
            raise RuntimeError(
                f"OpenSTAT frame {frame_index} has no recognized data columns"
            )

        for row_number, row in enumerate(reader, start=2):
            if len(row) != len(header):
                raise RuntimeError(
                    f"OpenSTAT frame {frame_index} row {row_number} "
                    "does not match its header"
                )

            crop_text = row[0].strip()
            geo_text = row[1].strip()
            crop_key = normalize_crop_label(crop_text)
            region_id = aliases.get(normalize_geo_label(geo_text))
            if not crop_key:
                raise RuntimeError("OpenSTAT returned an empty crop label")
            if region_id is None:
                raise RuntimeError(
                    f"OpenSTAT returned a non-Luzon region row: {geo_text}"
                )

            for parsed, cell in zip(parsed_columns, row[2:]):
                if parsed is None:
                    continue
                year_text, period = parsed
                key = (crop_key, region_id, year_text, period)
                record = {
                    "crop_text": crop_text,
                    "region_label": geo_text.lstrip(". "),
                    "cell": cell.strip(),
                }
                previous = result.get(key)
                if previous is not None and previous != record:
                    raise RuntimeError(
                        "OpenSTAT returned conflicting duplicate cells for "
                        f"{key}"
                    )
                result[key] = record

    return result


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
    if not math.isfinite(value):
        return None
    return value


def valid_crops(registry):
    result = {}
    for crop in registry.get("crops", []):
        if crop.get("planning_supported") is not True:
            continue
        coverage = crop.get("coverage", {})
        if not (
            coverage.get("production")
            and coverage.get("area")
        ):
            continue

        canonical = normalize_crop_label(crop.get("canonical_label", ""))
        if not canonical:
            raise RuntimeError("planning crop has no canonical label")
        if canonical in result:
            raise RuntimeError(
                f"duplicate planning crop label: {canonical}"
            )
        result[canonical] = crop

    if not result:
        raise RuntimeError("no valid crops with production and area")
    return result


def _source_table_list(crop, family):
    tables = crop.get("source_tables", {}).get(family, [])
    if isinstance(tables, str):
        return [tables]
    return list(tables)


def build_yield_tables(manifest, scope, registry):
    crop_index = valid_crops(registry)
    by_key = {
        table["table_key"]: table
        for table in manifest["tables"]
    }
    if len(by_key) != len(manifest["tables"]):
        raise RuntimeError("manifest has duplicate table keys")

    detailed = []
    seen_detail_keys = set()

    for production_key, area_key in TABLE_PAIRS:
        if production_key not in by_key or area_key not in by_key:
            raise RuntimeError(
                f"manifest is missing {production_key} or {area_key}"
            )

        production_table = by_key[production_key]
        area_table = by_key[area_key]

        production_frames = fetch_table_values(
            manifest["api_base"],
            production_table,
            scope,
        )
        area_frames = fetch_table_values(
            manifest["api_base"],
            area_table,
            scope,
        )

        production_values = parse_frames(production_frames, scope)
        area_values = parse_frames(area_frames, scope)

        common_keys = sorted(
            set(production_values) & set(area_values),
            key=lambda key: (
                key[0],
                key[1],
                key[2],
                PERIOD_ORDER.index(key[3]),
            ),
        )

        for key in common_keys:
            crop_norm, region_id, year_text, period = key
            crop = crop_index.get(crop_norm)
            if crop is None:
                continue

            production_tables = _source_table_list(crop, "production")
            area_tables = _source_table_list(crop, "area")
            if production_key not in production_tables:
                continue
            if area_key not in area_tables:
                continue

            production = to_number(production_values[key]["cell"])
            area = to_number(area_values[key]["cell"])
            if production is None or area is None:
                continue
            if production < 0 or area <= 0:
                continue

            yield_value = production / area
            if not math.isfinite(yield_value) or yield_value < 0:
                continue

            detail_key = (
                crop["crop_id"],
                region_id,
                year_text,
                period,
            )
            if detail_key in seen_detail_keys:
                raise RuntimeError(
                    f"duplicate yield row across table pairs: {detail_key}"
                )
            seen_detail_keys.add(detail_key)

            detailed.append({
                "crop_id": crop["crop_id"],
                "display_name": crop["display_name"],
                "region_id": region_id,
                "region_label": production_values[key]["region_label"],
                "year": year_text,
                "period": period,
                "production_mt": production,
                "area_ha": area,
                "yield_mt_per_ha": yield_value,
                "production_table": production_key,
                "area_table": area_key,
                "source_id": SOURCE_ID,
                "data_status": DATA_STATUS,
            })

    detailed.sort(
        key=lambda row: (
            row["crop_id"],
            row["region_id"],
            row["year"],
            PERIOD_ORDER.index(row["period"]),
        )
    )
    return detailed


def summarize_annual(detailed):
    groups = {}
    for row in detailed:
        if row["period"] != "Annual":
            continue
        if str(row["year"]) not in REF_YEAR_TEXT:
            continue

        key = (
            row["crop_id"],
            row["display_name"],
            row["region_id"],
            row["region_label"],
        )
        groups.setdefault(key, {})[str(row["year"])] = row

    summary = []
    for (
        crop_id,
        display_name,
        region_id,
        region_label,
    ), rows_by_year in sorted(groups.items()):
        if len(rows_by_year) < MIN_SUMMARY_YEARS:
            continue

        rows = [
            rows_by_year[year]
            for year in sorted(rows_by_year)
        ]
        yields = [row["yield_mt_per_ha"] for row in rows]
        summary.append({
            "crop_id": crop_id,
            "display_name": display_name,
            "region_id": region_id,
            "region_label": region_label,
            "ref_period": REF_PERIOD_LABEL,
            "n_years": len(rows),
            "avg_yield_mt_per_ha": sum(yields) / len(yields),
            "min_yield_mt_per_ha": min(yields),
            "max_yield_mt_per_ha": max(yields),
            "unit": "mt_per_ha",
            "source_id": SOURCE_ID,
            "data_status": DATA_STATUS,
        })

    summary.sort(
        key=lambda row: (row["crop_id"], row["region_id"])
    )
    return summary


def write_detailed_csv(path, detailed):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=DETAILED_FIELDS,
            lineterminator="\n",
        )
        writer.writeheader()
        for row in detailed:
            output = dict(row)
            output["production_mt"] = f"{row['production_mt']:.2f}"
            output["area_ha"] = f"{row['area_ha']:.2f}"
            output["yield_mt_per_ha"] = f"{row['yield_mt_per_ha']:.4f}"
            writer.writerow(output)


def write_summary_csv(path, summary):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=SUMMARY_FIELDS,
            lineterminator="\n",
        )
        writer.writeheader()
        for row in summary:
            output = dict(row)
            for field in (
                "avg_yield_mt_per_ha",
                "min_yield_mt_per_ha",
                "max_yield_mt_per_ha",
            ):
                output[field] = f"{row[field]:.4f}"
            writer.writerow(output)


def lookup_summary(summary, crop_id, region_id):
    for row in summary:
        if (
            row["crop_id"] == crop_id
            and row["region_id"] == region_id
        ):
            return row
    return None


def render_docs(detailed, summary):
    tomato = lookup_summary(summary, "tomato", "IV-A")
    eggplant = lookup_summary(summary, "eggplant", "IV-A")
    if tomato is None or eggplant is None:
        raise RuntimeError(
            "tomato and eggplant need CALABARZON summary rows"
        )

    tomato_avg = float(tomato["avg_yield_mt_per_ha"])
    eggplant_avg = float(eggplant["avg_yield_mt_per_ha"])
    tomato_example = 2.0 * tomato_avg
    eggplant_example = 1.5 * eggplant_avg

    annual_rows = sum(
        1
        for row in detailed
        if row["period"] == "Annual"
    )
    crop_count = len({row["crop_id"] for row in detailed})
    region_count = len({row["region_id"] for row in detailed})

    lines = [
        "# Yield reference",
        "",
        "This file explains the TANIM historical yield reference.",
        "",
        "## What yield means",
        "",
        "Yield shows how much crop was produced per hectare.",
        "",
        "The unit is metric tons per hectare.",
        "",
        "The formula is:",
        "",
        "Yield = Production in metric tons divided by Harvested area in hectares.",
        "",
        "TANIM uses PSA production volume and harvested area from matching crop records.",
        "",
        "Crop joins use the same exact normalized crop label in the paired production and area tables.",
        "Similar names are not merged by guesswork.",
        "",
        "## Reference window",
        "",
        f"The reference window is {REF_PERIOD_LABEL}.",
        "Year 2026 is still partial, so it is not included.",
        "",
        "A summary row needs all five Annual years inside the window.",
        "The n_years field is 5 for every summary row.",
        "",
        "The summary stores the arithmetic mean, lowest annual yield, and highest annual yield.",
        "The average is the app reference. The lowest and highest values show historical spread.",
        "",
        f"The committed snapshot has {annual_rows} Annual yield rows for {crop_count} crops in {region_count} Luzon regions.",
        "",
        "## Planning bridge",
        "",
        "Start with planned area in hectares.",
        "",
        "Expected production = Planned area in hectares times Average yield.",
        "",
        f"Example: 2 hectares of tomato times {tomato_avg:.2f} is about {tomato_example:.2f} metric tons.",
        f"Example: 1.5 hectares of eggplant times {eggplant_avg:.2f} is about {eggplant_example:.2f} metric tons.",
        "",
        "If farm size is approximate, keep the area margin and show an estimated production range.",
        "",
        "## Period detail",
        "",
        "The detailed file has one row per crop, region, year, and available period.",
        "Period can be Quarter1, Quarter2, Semester1, Quarter3, Quarter4, Semester2, or Annual.",
        "",
        "Quarterly yield exists only when both quarterly production and quarterly harvested area exist.",
        "Missing source values stay missing. TANIM does not fill them with invented values.",
        "",
        "The summary uses Annual rows only.",
        "It is not quarter specific.",
        "",
        "## Geography",
        "",
        "The source scope can include NCR, CAR, Region I, Region II, Region III, Region IV-A, MIMAROPA, and Region V.",
        "",
        "Some source tables do not publish NCR crop rows.",
        "The committed yield snapshot therefore contains only the Luzon regions that have matching production and area rows.",
        "",
        "This version uses region rows only.",
        "",
        "## Files",
        "",
        "Detailed rows are in datasets/generated/yield_reference.csv.",
        "Summary rows are in datasets/generated/yield_summary.csv.",
        "",
        "The detailed file keeps production, area, yield, source table keys, source id, and data status.",
        "The summary keeps the reference window, year count, average yield, minimum yield, maximum yield, unit, source id, and data status.",
        "",
        "## Limits",
        "",
        "Historical yield is a production reference. It is not market demand.",
        "It does not prove that a glut or shortage will happen.",
        "",
        "GRCI still needs a separate, clearly labelled comparison reference.",
        "See docs/GRCI_SPEC.md for the allowed reference types and evidence rules.",
        "",
        "PSA source tables can be revised.",
        "Run the live audit before replacing the committed snapshot.",
        "",
    ]
    return "\n".join(lines)


def write_docs(path, detailed, summary):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_docs(detailed, summary),
        encoding="utf-8",
    )


def _load_csv(path, expected_fields):
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_fields:
            raise RuntimeError(
                f"{path.name} schema changed: {reader.fieldnames}"
            )
        return list(reader)


def _finite_csv_number(row, field, row_label):
    try:
        value = float(row[field])
    except (TypeError, ValueError) as error:
        raise RuntimeError(
            f"{row_label}: {field} is not numeric"
        ) from error
    if not math.isfinite(value):
        raise RuntimeError(
            f"{row_label}: {field} must be finite"
        )
    return value


def validate_committed_rows(detailed, summary):
    if not detailed or not summary:
        raise RuntimeError("yield files are empty")

    detailed_keys = set()
    annual_by_key = {}

    for index, row in enumerate(detailed, start=2):
        label = f"detailed row {index}"
        key = (
            row["crop_id"],
            row["region_id"],
            row["year"],
            row["period"],
        )
        if key in detailed_keys:
            raise RuntimeError(f"duplicate detailed key: {key}")
        detailed_keys.add(key)

        if not row["crop_id"].strip() or not row["display_name"].strip():
            raise RuntimeError(f"{label}: crop fields are missing")
        if row["region_id"] not in LUZON_IDS:
            raise RuntimeError(f"{label}: invalid region id")
        if row["year"] not in REF_YEAR_TEXT:
            raise RuntimeError(f"{label}: year is outside the reference window")
        if row["period"] not in PERIOD_ORDER:
            raise RuntimeError(f"{label}: invalid period")
        if (
            row["production_table"],
            row["area_table"],
        ) not in PAIR_SET:
            raise RuntimeError(f"{label}: invalid source table pair")
        if row["source_id"] != SOURCE_ID:
            raise RuntimeError(f"{label}: wrong source id")
        if row["data_status"] != DATA_STATUS:
            raise RuntimeError(f"{label}: wrong data status")

        region_label = row["region_label"].upper()
        if any(word in region_label for word in BANNED_GEO_WORDS):
            raise RuntimeError(
                f"{label}: non-Luzon geography text found"
            )

        production = _finite_csv_number(row, "production_mt", label)
        area = _finite_csv_number(row, "area_ha", label)
        yield_value = _finite_csv_number(
            row,
            "yield_mt_per_ha",
            label,
        )
        if production < 0 or area <= 0 or yield_value < 0:
            raise RuntimeError(f"{label}: invalid numeric range")
        if abs((production / area) - yield_value) > 0.01:
            raise RuntimeError(f"{label}: yield math failed")

        if row["period"] == "Annual":
            annual_key = (row["crop_id"], row["region_id"])
            year_map = annual_by_key.setdefault(annual_key, {})
            if row["year"] in year_map:
                raise RuntimeError(
                    f"duplicate Annual year for {annual_key}"
                )
            year_map[row["year"]] = yield_value

    summary_keys = set()
    for index, row in enumerate(summary, start=2):
        label = f"summary row {index}"
        key = (row["crop_id"], row["region_id"])
        if key in summary_keys:
            raise RuntimeError(f"duplicate summary key: {key}")
        summary_keys.add(key)

        if row["region_id"] not in LUZON_IDS:
            raise RuntimeError(f"{label}: invalid region id")
        if row["ref_period"] != REF_PERIOD_LABEL:
            raise RuntimeError(f"{label}: wrong reference window")
        if row["unit"] != "mt_per_ha":
            raise RuntimeError(f"{label}: wrong unit")
        if row["source_id"] != SOURCE_ID:
            raise RuntimeError(f"{label}: wrong source id")
        if row["data_status"] != DATA_STATUS:
            raise RuntimeError(f"{label}: wrong data status")

        try:
            n_years = int(row["n_years"])
        except ValueError as error:
            raise RuntimeError(f"{label}: invalid year count") from error
        if n_years != len(REF_YEARS):
            raise RuntimeError(f"{label}: summary needs all five reference years")

        avg = _finite_csv_number(
            row,
            "avg_yield_mt_per_ha",
            label,
        )
        low = _finite_csv_number(
            row,
            "min_yield_mt_per_ha",
            label,
        )
        high = _finite_csv_number(
            row,
            "max_yield_mt_per_ha",
            label,
        )
        if avg <= 0 or low < 0 or high < 0 or not low <= avg <= high:
            raise RuntimeError(f"{label}: invalid summary values")

        values_by_year = annual_by_key.get(key)
        if not values_by_year:
            raise RuntimeError(
                f"{label}: no matching detailed Annual rows"
            )
        values = list(values_by_year.values())
        if len(values) != n_years:
            raise RuntimeError(f"{label}: year count does not match detail")
        if abs(avg - sum(values) / len(values)) > 0.02:
            raise RuntimeError(f"{label}: average does not match detail")
        if abs(low - min(values)) > 0.02:
            raise RuntimeError(f"{label}: minimum does not match detail")
        if abs(high - max(values)) > 0.02:
            raise RuntimeError(f"{label}: maximum does not match detail")

    required = {("tomato", "IV-A"), ("eggplant", "IV-A")}
    if not required <= summary_keys:
        raise RuntimeError(
            "tomato and eggplant CALABARZON summary rows are required"
        )


def _typed_for_docs(detailed, summary):
    typed_detail = []
    for row in detailed:
        typed = dict(row)
        typed["production_mt"] = float(row["production_mt"])
        typed["area_ha"] = float(row["area_ha"])
        typed["yield_mt_per_ha"] = float(row["yield_mt_per_ha"])
        typed_detail.append(typed)

    typed_summary = []
    for row in summary:
        typed = dict(row)
        typed["n_years"] = int(row["n_years"])
        typed["avg_yield_mt_per_ha"] = float(
            row["avg_yield_mt_per_ha"]
        )
        typed["min_yield_mt_per_ha"] = float(
            row["min_yield_mt_per_ha"]
        )
        typed["max_yield_mt_per_ha"] = float(
            row["max_yield_mt_per_ha"]
        )
        typed_summary.append(typed)

    return typed_detail, typed_summary


def check_committed_files(detailed_path, summary_path, docs_path):
    for path in (detailed_path, summary_path, docs_path):
        if not path.exists():
            raise RuntimeError(f"committed file is missing: {path}")

    detailed = _load_csv(detailed_path, DETAILED_FIELDS)
    summary = _load_csv(summary_path, SUMMARY_FIELDS)
    validate_committed_rows(detailed, summary)

    typed_detail, typed_summary = _typed_for_docs(detailed, summary)
    expected_docs = render_docs(typed_detail, typed_summary)
    actual_docs = docs_path.read_text(encoding="utf-8")
    if actual_docs != expected_docs:
        raise RuntimeError(
            "YIELD_REFERENCE.md is stale; rebuild the yield reference"
        )

    print(
        f"OK: {len(detailed)} detailed yields and "
        f"{len(summary)} summary rows passed offline checks"
    )


def check_live_sample():
    manifest = read_json(MANIFEST)
    scope = read_json(SCOPE)
    by_key = {
        table["table_key"]: table
        for table in manifest["tables"]
    }

    production_table = by_key["PSA-PROD-VEG-ROOT"]
    area_table = by_key["PSA-AREA-VEG-ROOT"]
    wanted_crops = {"tomato", "eggplant"}

    production_frames = fetch_table_values(
        manifest["api_base"],
        production_table,
        scope,
        wanted_crops=wanted_crops,
        wanted_regions=["IV-A"],
        wanted_years=REF_YEARS,
        wanted_periods=["Annual"],
    )
    area_frames = fetch_table_values(
        manifest["api_base"],
        area_table,
        scope,
        wanted_crops=wanted_crops,
        wanted_regions=["IV-A"],
        wanted_years=REF_YEARS,
        wanted_periods=["Annual"],
    )

    production = parse_frames(production_frames, scope)
    area = parse_frames(area_frames, scope)

    for crop in sorted(wanted_crops):
        for year in REF_YEAR_TEXT:
            key = (crop, "IV-A", year, "Annual")
            if key not in production or key not in area:
                raise RuntimeError(
                    f"live sample is missing {crop} {year} Annual"
                )
            prod_value = to_number(production[key]["cell"])
            area_value = to_number(area[key]["cell"])
            if (
                prod_value is None
                or area_value is None
                or prod_value < 0
                or area_value <= 0
            ):
                raise RuntimeError(
                    f"live sample has invalid {crop} {year} values"
                )
            yield_value = prod_value / area_value
            if not math.isfinite(yield_value) or yield_value <= 0:
                raise RuntimeError(
                    f"live sample has invalid {crop} {year} yield"
                )

    print(
        "OK: live OpenSTAT sample has tomato and eggplant "
        "CALABARZON Annual values for 2021-2025"
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Build TANIM historical yield reference from PSA "
            "production and harvested area."
        )
    )
    parser.add_argument(
        "--detailed-output",
        type=pathlib.Path,
        default=DEFAULT_DETAILED,
    )
    parser.add_argument(
        "--summary-output",
        type=pathlib.Path,
        default=DEFAULT_SUMMARY,
    )
    parser.add_argument(
        "--docs-output",
        type=pathlib.Path,
        default=DEFAULT_DOCS,
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Audit committed yield files without replacing them.",
    )
    parser.add_argument(
        "--live-sample",
        action="store_true",
        help=(
            "With --check-only, fetch a small OpenSTAT sample "
            "for tomato and eggplant."
        ),
    )
    args = parser.parse_args()

    if args.live_sample and not args.check_only:
        parser.error("--live-sample requires --check-only")

    if args.check_only:
        check_committed_files(
            args.detailed_output,
            args.summary_output,
            args.docs_output,
        )
        if args.live_sample:
            check_live_sample()
        return

    manifest = read_json(MANIFEST)
    scope = read_json(SCOPE)
    registry = read_json(GENERATED_REGISTRY)

    detailed = build_yield_tables(manifest, scope, registry)
    if not detailed:
        raise RuntimeError(
            "no yields could be computed; check production and area joins"
        )

    summary = summarize_annual(detailed)
    if not summary:
        raise RuntimeError(
            "no summary rows; all five Annual years are required"
        )

    write_detailed_csv(args.detailed_output, detailed)
    write_summary_csv(args.summary_output, summary)
    write_docs(args.docs_output, detailed, summary)

    print(
        f"Wrote {len(detailed)} detailed yields to "
        f"{args.detailed_output}"
    )
    print(
        f"Wrote {len(summary)} summary rows to "
        f"{args.summary_output}"
    )
    print(f"Wrote yield docs to {args.docs_output}")


if __name__ == "__main__":
    main()
