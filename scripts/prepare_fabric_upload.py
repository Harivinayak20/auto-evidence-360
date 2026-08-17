#!/usr/bin/env python3
"""Create privacy-minimized, source-traceable extracts for Fabric upload."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = PROJECT_ROOT / "data" / "raw"
OUTPUT_ROOT = PROJECT_ROOT / "data" / "fabric_upload"


@dataclass(frozen=True)
class ExtractSpec:
    table_name: str
    source_id: str
    source_path: Path
    delimiter: str
    source_has_header: bool
    columns: tuple[tuple[str, int | str], ...]
    expected_fields: int | None = None


COMPLAINT_COLUMNS = (
    ("complaint_record_id", 0), ("complaint_id", 1), ("manufacturer_name", 2),
    ("source_make", 3), ("source_model", 4), ("model_year", 5), ("crash_flag", 6),
    ("incident_date", 7), ("fire_flag", 8), ("injury_count", 9), ("death_count", 10),
    ("component_name", 11), ("record_created_date", 15), ("complaint_received_date", 16),
    ("mileage_at_failure", 17), ("occurrence_count", 18), ("complaint_type", 20),
    ("police_report_flag", 21), ("product_type", 45), ("medical_attention_flag", 47),
    ("vehicle_towed_flag", 48), ("incident_state", 49),
)

RECALL_COLUMNS = (
    ("recall_record_id", 0), ("campaign_number", 1), ("source_make", 2), ("source_model", 3),
    ("model_year", 4), ("manufacturer_campaign_number", 5), ("component_name", 6),
    ("filing_manufacturer", 7), ("product_type", 10), ("potential_units_affected", 11),
    ("recall_initiator", 13), ("report_received_date", 15), ("defect_summary", 19),
    ("consequence_summary", 20), ("corrective_action", 21), ("recalled_component_id", 23),
    ("do_not_drive_flag", 27), ("park_outside_flag", 28),
)

INVESTIGATION_COLUMNS = (
    ("investigation_number", 0), ("source_make", 1), ("source_model", 2), ("model_year", 3),
    ("component_name", 4), ("manufacturer_name", 5), ("opened_date", 6), ("closed_date", 7),
    ("campaign_number", 8), ("subject", 9), ("summary", 10),
)

TSB_COLUMNS = (
    ("nhtsa_communication_id", 0), ("replacement_document_id", 1), ("date_added", 2),
    ("document_id", 3), ("manufacturer_communication_date", 4), ("internal_campaign_or_version", 5),
    ("communication_type", 6), ("source_make", 7), ("source_model", 8), ("model_year", 9),
    ("nhtsa_components", 10), ("manufacturer_system", 11), ("manufacturer_subsystem", 12),
    ("summary", 13),
)

NCAP_FIELDS = (
    "MAKE", "MODEL", "MODEL_YR", "BODY_STYLE", "VEHICLE_TYPE", "DRIVE_TRAIN", "VEHICLE_CLASS",
    "BODY_FRAME", "NUM_OF_SEATING", "BLIND_SPOT_DETECTION", "ADAPTIVE_CRUISE_CONTROL", "ABS",
    "AUTO_CRASH_NOTIFICATION", "FRNT_COLLISION_WARNING", "NHTSA_FCW_EVALUATION",
    "LANE_DEPARTURE_WARNING", "NHTSA_LDW_EVALUATION", "CRASH_IMMINENT_BRAKE", "NHTSA_CIB_EVALUATION",
    "DYNAMIC_BRAKE_SUPPORT", "NHTSA_DBS_EVALUATION", "NHTSA_ESC", "OVERALL_STARS",
    "FRNT_DRIV_STARS", "FRNT_PASS_STARS", "OVERALL_FRNT_STARS", "SIDE_DRIV_STARS",
    "SIDE_PASS_STARS", "SIDE_BARRIER_STAR", "SIDE_POLE_STARS", "OVERALL_SIDE_STARS",
    "ROLLOVER_POSSIBILITY", "STATIC_STABI_FACTOR", "TIP", "ROLLOVER_STARS",
    "NHTSA_BACKUP_CAMERA", "BACKUP_CAMERA",
)

EPA_FIELDS = (
    "id", "make", "model", "year", "VClass", "fuelType", "fuelType1", "fuelType2", "drive", "trany",
    "cylinders", "displ", "atvType", "city08", "highway08", "comb08", "cityE", "highwayE", "combE",
    "co2TailpipeGpm", "fuelCost08", "ghgScore", "range", "charge240", "youSaveSpend", "createdOn", "modifiedOn",
)


SPECS = (
    ExtractSpec(
        "complaints", "nhtsa_complaints_2025_2026",
        RAW_ROOT / "nhtsa_complaints_2025_2026" / "extracted" / "COMPLAINTS_RECEIVED_2025-2026.txt",
        "\t", False, COMPLAINT_COLUMNS, 51,
    ),
    ExtractSpec(
        "recalls", "nhtsa_recalls_post_2010",
        RAW_ROOT / "nhtsa_recalls_post_2010" / "extracted" / "FLAT_RCL_POST_2010.txt",
        "\t", False, RECALL_COLUMNS, 29,
    ),
    ExtractSpec(
        "investigations", "nhtsa_investigations_all",
        RAW_ROOT / "nhtsa_investigations_all" / "extracted" / "FLAT_INV.txt",
        "\t", False, INVESTIGATION_COLUMNS, 11,
    ),
    ExtractSpec(
        "manufacturer_communications", "nhtsa_tsbs_2025_2026",
        RAW_ROOT / "nhtsa_tsbs_2025_2026" / "extracted" / "TSBS_RECEIVED_2025-2026.txt",
        "\t", False, TSB_COLUMNS, 14,
    ),
    ExtractSpec(
        "ncap_ratings", "nhtsa_ncap_ratings",
        RAW_ROOT / "nhtsa_ncap_ratings" / "Safercar_data.csv",
        ",", True, tuple((field.lower(), field) for field in NCAP_FIELDS),
    ),
    ExtractSpec(
        "fuel_economy", "epa_fuel_economy_vehicles",
        RAW_ROOT / "epa_fuel_economy_vehicles" / "extracted" / "vehicles.csv",
        ",", True, tuple((field, field) for field in EPA_FIELDS),
    ),
    ExtractSpec(
        "state_registrations", "fhwa_state_registrations",
        RAW_ROOT / "fhwa_state_registrations" / "rows.csv",
        ",", True, (("year", "Year"), ("state", "State"), ("category", "Category"), ("registration_type", "Type"), ("vehicles", "Vehicles")),
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_sha(source_id: str) -> str:
    metadata_path = RAW_ROOT / source_id / "source_metadata.json"
    return json.loads(metadata_path.read_text(encoding="utf-8"))["sha256"]


def create_extract(spec: ExtractSpec) -> dict:
    if not spec.source_path.exists():
        raise FileNotFoundError(spec.source_path)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_ROOT / f"{spec.table_name}.csv.gz"
    malformed_rows = 0
    row_count = 0

    with spec.source_path.open("r", encoding="latin-1", errors="replace", newline="") as source_handle:
        reader = csv.reader(
            source_handle,
            delimiter=spec.delimiter,
            quoting=csv.QUOTE_MINIMAL if spec.source_has_header else csv.QUOTE_NONE,
        )
        header_map = {}
        if spec.source_has_header:
            source_header = next(reader)
            header_map = {name: index for index, name in enumerate(source_header)}
            missing = [source_field for _, source_field in spec.columns if source_field not in header_map]
            if missing:
                raise ValueError(f"{spec.source_id} is missing expected fields: {missing}")

        with gzip.open(output_path, "wt", encoding="utf-8", newline="") as output_handle:
            writer = csv.writer(output_handle)
            writer.writerow([output_name for output_name, _ in spec.columns])
            for row in reader:
                if spec.expected_fields is not None and len(row) != spec.expected_fields:
                    malformed_rows += 1
                    continue
                output_row = []
                for _, source_field in spec.columns:
                    index = source_field if isinstance(source_field, int) else header_map[source_field]
                    output_row.append(row[index].strip() if index < len(row) else "")
                writer.writerow(output_row)
                row_count += 1

    if malformed_rows:
        raise ValueError(f"{spec.source_id} had {malformed_rows} malformed rows; extract not approved")
    return {
        "table_name": spec.table_name,
        "source_id": spec.source_id,
        "source_path": str(spec.source_path.relative_to(PROJECT_ROOT)),
        "source_sha256": source_sha(spec.source_id),
        "output_file": output_path.name,
        "output_sha256": sha256_file(output_path),
        "rows": row_count,
        "columns": [output_name for output_name, _ in spec.columns],
        "malformed_rows": malformed_rows,
    }


def main() -> None:
    extracts = []
    for spec in SPECS:
        print(f"Preparing {spec.table_name}...", flush=True)
        extracts.append(create_extract(spec))
    manifest = {
        "project": "Auto Evidence 360",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "privacy-minimized extracts approved for Microsoft Fabric upload",
        "privacy_policy": "Consumer narratives, VIN fragments, cities, dealer contact fields, and vehicle-operator fields are excluded.",
        "extracts": extracts,
    }
    (OUTPUT_ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({item["table_name"]: item["rows"] for item in extracts}, indent=2))


if __name__ == "__main__":
    main()
