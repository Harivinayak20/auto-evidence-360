#!/usr/bin/env python3
"""Stream and profile Auto Evidence 360 raw sources without exposing row content."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = PROJECT_ROOT / "data" / "raw"
OUTPUT_ROOT = PROJECT_ROOT / "analysis" / "output"
MAX_MODEL_YEAR = datetime.now().year + 1


@dataclass(frozen=True)
class DatasetSpec:
    source_id: str
    path: Path
    delimiter: str
    header: bool
    expected_fields: int | None
    id_field: int | str
    make_field: int | str | None = None
    model_field: int | str | None = None
    year_field: int | str | None = None
    date_field: int | str | None = None
    product_field: int | str | None = None
    product_value: str | None = None


SPECS = [
    DatasetSpec(
        "nhtsa_complaints",
        RAW_ROOT / "nhtsa_complaints_2025_2026" / "extracted" / "COMPLAINTS_RECEIVED_2025-2026.txt",
        "\t", False, 51, 0, 3, 4, 5, 16, 45, "V",
    ),
    DatasetSpec(
        "nhtsa_recalls",
        RAW_ROOT / "nhtsa_recalls_post_2010" / "extracted" / "FLAT_RCL_POST_2010.txt",
        "\t", False, 29, 0, 2, 3, 4, 15, 10, "V",
    ),
    DatasetSpec(
        "nhtsa_investigations",
        RAW_ROOT / "nhtsa_investigations_all" / "extracted" / "FLAT_INV.txt",
        "\t", False, 11, 0, 1, 2, 3, 6,
    ),
    DatasetSpec(
        "nhtsa_manufacturer_communications",
        RAW_ROOT / "nhtsa_tsbs_2025_2026" / "extracted" / "TSBS_RECEIVED_2025-2026.txt",
        "\t", False, 14, 0, 7, 8, 9, 2,
    ),
    DatasetSpec(
        "nhtsa_ncap",
        RAW_ROOT / "nhtsa_ncap_ratings" / "Safercar_data.csv",
        ",", True, None, "FRNT_TEST_NO", "MAKE", "MODEL", "MODEL_YR", None,
    ),
    DatasetSpec(
        "epa_fuel_economy",
        RAW_ROOT / "epa_fuel_economy_vehicles" / "extracted" / "vehicles.csv",
        ",", True, None, "id", "make", "model", "year", None,
    ),
    DatasetSpec(
        "fhwa_state_registrations",
        RAW_ROOT / "fhwa_state_registrations" / "rows.csv",
        ",", True, 5, "State", None, None, "Year", None,
    ),
]


@lru_cache(maxsize=100_000)
def normalize_text(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.findall(r"[A-Z0-9]+", ascii_value.upper()))


def get_value(row: list[str], field: int | str | None, header_map: dict[str, int]) -> str:
    if field is None:
        return ""
    index = field if isinstance(field, int) else header_map[field]
    return row[index].strip() if index < len(row) else ""


MIN_MODEL_YEAR = 1900
REFERENCE_ERA_START_YEAR = 1984


def valid_model_year(value: str) -> bool:
    return value.isdigit() and MIN_MODEL_YEAR <= int(value) <= MAX_MODEL_YEAR


def reference_year_eligible(year_value: str) -> bool:
    return year_value.isdigit() and int(year_value) >= REFERENCE_ERA_START_YEAR


def date_bounds_update(value: str, current_min: str | None, current_max: str | None) -> tuple[str | None, str | None]:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 8:
        return current_min, current_max
    candidate = digits[:8]
    if not (19000101 <= int(candidate) <= 21001231):
        return current_min, current_max
    return min(filter(None, [current_min, candidate])), max(filter(None, [current_max, candidate]))


def profile_dataset(spec: DatasetSpec) -> tuple[dict, set[str]]:
    if not spec.path.exists():
        return {"source_id": spec.source_id, "status": "not_downloaded", "path": str(spec.path.relative_to(PROJECT_ROOT))}, set()

    rows = 0
    malformed_rows = 0
    exact_duplicate_rows = 0
    missing_make = 0
    missing_model = 0
    missing_year = 0
    min_year = None
    max_year = None
    vehicle_rows = 0
    valid_vehicle_rows = 0
    min_date = None
    max_date = None
    business_ids: set[str] = set()
    row_hashes: set[int] = set()
    vehicle_keys: set[str] = set()

    with spec.path.open("r", encoding="latin-1", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter=spec.delimiter, quoting=csv.QUOTE_MINIMAL if spec.header else csv.QUOTE_NONE)
        header_map: dict[str, int] = {}
        expected_fields = spec.expected_fields
        if spec.header:
            header = next(reader)
            header_map = {name: index for index, name in enumerate(header)}
            expected_fields = len(header)

        for row in reader:
            rows += 1
            if expected_fields is not None and len(row) != expected_fields:
                malformed_rows += 1
                continue

            digest = hash(tuple(row))
            if digest in row_hashes:
                exact_duplicate_rows += 1
            else:
                row_hashes.add(digest)

            business_id = get_value(row, spec.id_field, header_map)
            if business_id:
                business_ids.add(business_id)

            date_value = get_value(row, spec.date_field, header_map)
            if date_value:
                min_date, max_date = date_bounds_update(date_value, min_date, max_date)

            year_value = get_value(row, spec.year_field, header_map)
            if year_value.isdigit() and 1900 <= int(year_value) <= MAX_MODEL_YEAR:
                numeric_year = int(year_value)
                min_year = numeric_year if min_year is None else min(min_year, numeric_year)
                max_year = numeric_year if max_year is None else max(max_year, numeric_year)

            if spec.make_field is None:
                continue
            if spec.product_field is not None:
                if get_value(row, spec.product_field, header_map).upper() != spec.product_value:
                    continue
            vehicle_rows += 1
            make = get_value(row, spec.make_field, header_map)
            model = get_value(row, spec.model_field, header_map)
            year = year_value
            missing_make += not bool(make)
            missing_model += not bool(model)
            missing_year += not valid_model_year(year)
            if make and model and valid_model_year(year):
                valid_vehicle_rows += 1
                vehicle_keys.add(f"{normalize_text(make)}|{normalize_text(model)}|{year}")

    result = {
        "source_id": spec.source_id,
        "status": "profiled",
        "path": str(spec.path.relative_to(PROJECT_ROOT)),
        "rows": rows,
        "columns": expected_fields,
        "malformed_rows": malformed_rows,
        "malformed_rate": malformed_rows / rows if rows else None,
        "exact_duplicate_rows": exact_duplicate_rows,
        "distinct_business_ids": len(business_ids),
        "rows_per_business_id": rows / len(business_ids) if business_ids else None,
        "vehicle_rows": vehicle_rows,
        "valid_vehicle_rows": valid_vehicle_rows,
        "missing_make_rate": missing_make / vehicle_rows if vehicle_rows else None,
        "missing_model_rate": missing_model / vehicle_rows if vehicle_rows else None,
        "invalid_or_missing_year_rate": missing_year / vehicle_rows if vehicle_rows else None,
        "distinct_normalized_vehicle_keys": len(vehicle_keys),
        "min_year": min_year,
        "max_year": max_year,
        "min_source_date": min_date,
        "max_source_date": max_date,
    }
    return result, vehicle_keys


def format_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def main() -> None:
    profiles = []
    keys_by_source: dict[str, set[str]] = {}
    for spec in SPECS:
        print(f"Profiling {spec.source_id}...", flush=True)
        profile, keys = profile_dataset(spec)
        profiles.append(profile)
        keys_by_source[spec.source_id] = keys

    reference_keys = keys_by_source.get("nhtsa_ncap", set()) | keys_by_source.get("epa_fuel_economy", set())
    match_coverage = []
    for source_id in [
        "nhtsa_complaints", "nhtsa_recalls", "nhtsa_investigations", "nhtsa_manufacturer_communications"
    ]:
        source_keys = keys_by_source.get(source_id, set())
        era_eligible_keys = {key for key in source_keys if reference_year_eligible(key.rsplit("|", 1)[-1])}
        matched = source_keys & reference_keys
        era_matched = era_eligible_keys & reference_keys
        match_coverage.append({
            "source_id": source_id,
            "distinct_vehicle_keys": len(source_keys),
            "exact_reference_matches": len(matched),
            "exact_match_rate": len(matched) / len(source_keys) if source_keys else None,
            "era_eligible_vehicle_keys": len(era_eligible_keys),
            "era_eligible_exact_reference_matches": len(era_matched),
            "era_eligible_exact_match_rate": len(era_matched) / len(era_eligible_keys) if era_eligible_keys else None,
        })

    all_operational_keys = set()
    all_era_eligible_keys = set()
    for source_id in ["nhtsa_complaints", "nhtsa_recalls", "nhtsa_investigations", "nhtsa_manufacturer_communications"]:
        source_keys = keys_by_source.get(source_id, set())
        all_operational_keys |= source_keys
        all_era_eligible_keys |= {key for key in source_keys if reference_year_eligible(key.rsplit("|", 1)[-1])}

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile_scope": "downloaded public source files; no row content emitted",
        "model_year_window": {"min": MIN_MODEL_YEAR, "max": MAX_MODEL_YEAR},
        "reference_era_start_year": REFERENCE_ERA_START_YEAR,
        "datasets": profiles,
        "cross_source_exact_match_coverage": match_coverage,
        "union_exact_match_coverage": {
            "all_valid_vehicle_keys": len(all_operational_keys),
            "all_valid_exact_reference_matches": len(all_operational_keys & reference_keys),
            "all_valid_exact_match_rate": (len(all_operational_keys & reference_keys) / len(all_operational_keys)) if all_operational_keys else None,
            "era_eligible_vehicle_keys": len(all_era_eligible_keys),
            "era_eligible_exact_reference_matches": len(all_era_eligible_keys & reference_keys),
            "era_eligible_exact_match_rate": (len(all_era_eligible_keys & reference_keys) / len(all_era_eligible_keys)) if all_era_eligible_keys else None,
        },
        "privacy_exclusions": {
            "nhtsa_complaints": [
                "CITY", "VIN", "CDESCR", "DEALER_NAME", "DEALER_TEL", "DEALER_CITY",
                "DEALER_STATE", "DEALER_ZIP", "VEHICLE_OPERATOR"
            ],
            "policy": "Excluded fields never enter silver/gold tables or Power BI. Complaint narratives are not used for NLP."
        },
        "interpretation_guardrail": "Counts are public-record signals, not make/model reliability or causal estimates.",
    }

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "source_profile.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    markdown = [
        "# Real-Source Data Profile",
        "",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "No raw narratives, VIN fragments, contact fields, or row-level records are emitted in this profile.",
        "",
        "## Dataset profile",
        "",
        "| Source | Rows | Columns | Malformed | Exact duplicates | Distinct vehicle keys | Year coverage | Date range |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for profile in profiles:
        if profile["status"] != "profiled":
            markdown.append(f"| {profile['source_id']} | not downloaded | | | | | | |")
            continue
        markdown.append(
            f"| {profile['source_id']} | {profile['rows']:,} | {profile['columns']} | "
            f"{profile['malformed_rows']:,} ({format_pct(profile['malformed_rate'])}) | "
            f"{profile['exact_duplicate_rows']:,} | {profile['distinct_normalized_vehicle_keys']:,} | "
            f"{profile['min_year'] or 'n/a'} to {profile['max_year'] or 'n/a'} | "
            f"{profile['min_source_date'] or 'n/a'} to {profile['max_source_date'] or 'n/a'} |"
        )

    markdown += [
        "",
        "## Exact cross-source vehicle-key coverage",
        "",
        "Valid model years span 1900 through the current year plus one. The reference set is the union of normalized EPA and NCAP make/model/year keys. This is the baseline before alias or token matching.",
        "",
        "Two coverage measures are published: all valid operational keys, and EPA/NCAP-era-eligible keys (model year 1984 or later, when the reference sources begin).",
        "",
        "| Source | Distinct keys | Exact matches | Exact match rate | Era-eligible keys | Era-eligible matches | Era-eligible match rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for match in match_coverage:
        markdown.append(
            f"| {match['source_id']} | {match['distinct_vehicle_keys']:,} | "
            f"{match['exact_reference_matches']:,} | {format_pct(match['exact_match_rate'])} | "
            f"{match['era_eligible_vehicle_keys']:,} | "
            f"{match['era_eligible_exact_reference_matches']:,} | "
            f"{format_pct(match['era_eligible_exact_match_rate'])} |"
        )

    markdown += [
        "",
        "## Interpretation",
        "",
        "- Repeated NHTSA business IDs can be legitimate because one complaint, campaign, investigation, or bulletin may cover multiple components or vehicles.",
        "- Low exact match coverage is an entity-resolution requirement, not permission to use fuzzy matches silently.",
        "- The era-eligible measure removes pre-1984 keys that no EPA or NCAP reference could ever match.",
        "- Complaint counts are self-reported public-record volume. They are not failure rates without make/model/year exposure data.",
        "- Sensitive complaint fields are excluded before the conformed layer.",
    ]
    (OUTPUT_ROOT / "source_profile.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(json.dumps({"json": str(OUTPUT_ROOT / "source_profile.json"), "markdown": str(OUTPUT_ROOT / "source_profile.md")}, indent=2))


if __name__ == "__main__":
    main()
