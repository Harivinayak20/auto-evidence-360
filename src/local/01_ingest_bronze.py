#!/usr/bin/env python3
"""Bronze: validate the approved extracts against the manifest, stamp provenance,
and load into the local lakehouse. Any missing file, schema drift, or row-count
mismatch stops the pipeline."""

from __future__ import annotations

import argparse
import pathlib
import sys

import duckdb

EXPECTED_TABLES = [
    "complaints",
    "recalls",
    "investigations",
    "manufacturer_communications",
    "ncap_ratings",
    "fuel_economy",
    "state_registrations",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to the DuckDB lakehouse file")
    parser.add_argument("--data", required=True, help="Directory holding manifest.json and the csv.gz extracts")
    return parser.parse_args(argv)


def load_manifest(con: duckdb.DuckDBPyConnection, manifest_path: str) -> list[dict]:
    con.execute(
        f"CREATE TEMP TABLE _manifest_extracts AS "
        f"SELECT unnest(extracts) AS extract FROM read_json('{manifest_path}', format='auto')"
    )
    rows = con.execute(
        "SELECT extract.table_name, extract.source_id, extract.rows, extract.columns, "
        "extract.source_sha256, extract.output_sha256 "
        "FROM _manifest_extracts ORDER BY extract.table_name"
    ).fetchall()
    manifests = []
    for table_name, source_id, rows, columns, source_sha256, output_sha256 in rows:
        manifests.append(
            {
                "table_name": table_name,
                "source_id": source_id,
                "rows": int(rows),
                "columns": list(columns),
                "source_sha256": source_sha256,
                "output_sha256": output_sha256,
            }
        )
    return manifests


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_dir = pathlib.Path(args.data)
    con = duckdb.connect(args.db)

    batch_id = con.execute(
        "SELECT strftime(now() AT TIME ZONE 'UTC', '%Y%m%dT%H%M%SZ')"
    ).fetchone()[0]
    ingested_at = con.execute("SELECT now() AT TIME ZONE 'UTC'").fetchone()[0]

    manifests = load_manifest(con, str(data_dir / "manifest.json"))
    by_name = {m["table_name"]: m for m in manifests}
    missing = sorted(set(EXPECTED_TABLES) - set(by_name))
    if missing:
        con.close()
        raise ValueError(f"Manifest is missing entries: {missing}")

    audit_rows = []
    for table_name in EXPECTED_TABLES:
        contract = by_name[table_name]
        source_path = data_dir / f"{table_name}.csv.gz"

        columns = con.execute(
            f"SELECT * FROM read_csv('{source_path}', header=true, quote='\"', "
            f"escape='\"', all_varchar=true) LIMIT 1"
        ).description
        actual_columns = [column[0] for column in columns]
        schema_matches = actual_columns == contract["columns"]
        actual_rows = int(
            con.execute(
                f"SELECT count(*) FROM read_csv('{source_path}', header=true, quote='\"', "
                f"escape='\"', all_varchar=true)"
            ).fetchone()[0]
        )
        row_count_matches = actual_rows == contract["rows"]
        status = "PASS" if schema_matches and row_count_matches else "FAIL"

        audit_rows.append(
            {
                "batch_id": batch_id,
                "table_name": table_name,
                "source_id": contract["source_id"],
                "source_file": f"{table_name}.csv.gz",
                "source_sha256": contract["source_sha256"],
                "extract_sha256": contract["output_sha256"],
                "expected_rows": contract["rows"],
                "actual_rows": actual_rows,
                "schema_matches": schema_matches,
                "row_count_matches": row_count_matches,
                "status": status,
            }
        )

        if status == "PASS":
            con.execute(
                f"CREATE OR REPLACE TABLE bronze_{table_name} AS "
                f"SELECT *, "
                f"'{contract['source_id']}' AS _source_id, "
                f"'{table_name}.csv.gz' AS _source_file, "
                f"'{contract['source_sha256']}' AS _source_sha256, "
                f"'{contract['output_sha256']}' AS _extract_sha256, "
                f"'{batch_id}' AS _batch_id, "
                f"TIMESTAMP '{ingested_at}' AS _ingested_at "
                f"FROM read_csv('{source_path}', header=true, quote='\"', "
                f"escape='\"', all_varchar=true)"
            )

    con.execute(
        "CREATE TABLE IF NOT EXISTS audit_bronze_ingestion ("
        "batch_id VARCHAR, table_name VARCHAR, source_id VARCHAR, source_file VARCHAR, "
        "source_sha256 VARCHAR, extract_sha256 VARCHAR, expected_rows BIGINT, actual_rows BIGINT, "
        "schema_matches BOOLEAN, row_count_matches BOOLEAN, status VARCHAR, ingested_at TIMESTAMP)"
    )
    values_sql = ",".join(
        f"('{r['batch_id']}', '{r['table_name']}', '{r['source_id']}', '{r['source_file']}', "
        f"'{r['source_sha256']}', '{r['extract_sha256']}', {r['expected_rows']}, {r['actual_rows']}, "
        f"{r['schema_matches']}, {r['row_count_matches']}, '{r['status']}')"
        for r in audit_rows
    )
    con.execute(
        f"INSERT INTO audit_bronze_ingestion SELECT *, TIMESTAMP '{ingested_at}' FROM (VALUES {values_sql}) "
        "AS t(batch_id, table_name, source_id, source_file, source_sha256, extract_sha256, "
        "expected_rows, actual_rows, schema_matches, row_count_matches, status)"
    )

    failed = [r["table_name"] for r in audit_rows if r["status"] == "FAIL"]
    con.close()
    if failed:
        raise ValueError(f"Bronze contract failed for: {failed}. Inspect audit_bronze_ingestion.")

    for row in audit_rows:
        print(
            f"bronze {row['table_name']:<28} rows={row['actual_rows']:>7} "
            f"schema={row['schema_matches']} counts={row['row_count_matches']}"
        )
    print(f"batch {batch_id}: all bronze contracts PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())