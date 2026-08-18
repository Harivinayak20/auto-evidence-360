#!/usr/bin/env python3
"""Curated exports: publish only the small, gold-level tables a Tableau Public
workbook needs. No raw records, no P2 backlog rows, no internal audit fields."""

from __future__ import annotations

import argparse
import pathlib
import sys

import duckdb


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to the DuckDB lakehouse file")
    parser.add_argument("--export", required=True, help="Directory for curated parquet files")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    con = duckdb.connect(args.db)
    export_dir = pathlib.Path(args.export)
    export_dir.mkdir(parents=True, exist_ok=True)

    con.execute(
        f"COPY (SELECT vehicle_key, vehicle_label, make, model, model_year, "
        f"review_priority, review_reason, alias_priority, complaint_reports, "
        f"severe_complaint_reports, crash_reported_complaints, fire_reported_complaints, "
        f"recall_campaigns, do_not_drive_campaigns, park_outside_campaigns, investigations, "
        f"open_investigations, manufacturer_documents, ncap_tested_variants, epa_variants, "
        f"severe_complaint_share, evidence_source_count, source_system_count, "
        f"reference_match_status, reference_year_eligible, rule_version, "
        f"threshold_validation_status FROM gold_agg_vehicle_evidence) "
        f"TO '{export_dir / 'evidence_summary.parquet'}' (FORMAT PARQUET)"
    )

    con.execute(
        f"COPY (SELECT vehicle_key, vehicle_label, alias_priority, alias_reason, "
        f"source_system_count, complaint_reports, severe_complaint_reports, recall_campaigns, "
        f"do_not_drive_campaigns, park_outside_campaigns, open_investigations, "
        f"manufacturer_documents, review_status FROM gold_alias_work_queue) "
        f"TO '{export_dir / 'alias_work_queue.parquet'}' (FORMAT PARQUET)"
    )

    con.execute(
        f"COPY (SELECT 'bronze_ingestion_audit' AS section, batch_id, table_name, source_id, "
        f"expected_rows, actual_rows, schema_matches, row_count_matches, status "
        f"FROM audit_bronze_ingestion UNION ALL "
        f"SELECT 'entity_match_quality', source_system, '', "
        f"distinct_vehicle_keys, reference_exact_match_keys, "
        f"era_eligible_vehicle_keys, era_eligible_reference_exact_match_keys, '', '' "
        f"FROM audit_silver_entity_match_quality) "
        f"TO '{export_dir / 'data_trust.parquet'}' (FORMAT PARQUET)"
    )

    con.close()
    for path in sorted(export_dir.glob("*.parquet")):
        print(f"exported {path.name} ({path.stat().st_size / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())