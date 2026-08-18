#!/usr/bin/env python3
"""Run the full local lakehouse pipeline end to end and reconcile Gold outputs
against the independent local baseline."""

from __future__ import annotations

import argparse
import importlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import duckdb

bronze = importlib.import_module("01_ingest_bronze")
silver = importlib.import_module("02_conform_silver")
gold = importlib.import_module("03_build_gold")
curated = importlib.import_module("04_export_curated")

EXPECTED_PRIORITY_COUNTS = {"CRITICAL": 1355, "HIGH": 2222, "REVIEW": 39955, "MONITOR": 38868}
EXPECTED_ALIAS_COUNTS = {"NONE": 33999, "P0": 1420, "P1": 35505, "P2": 11476}
EXPECTED_VEHICLE_KEYS = 82400


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/lakehouse/auto_evidence_360.duckdb")
    parser.add_argument("--data", default="data/fabric_upload")
    parser.add_argument("--export", default="data/tableau_public")
    return parser.parse_args(argv)


def reconcile(con: duckdb.DuckDBPyConnection, baseline_path: pathlib.Path) -> list[str]:
    failures = []

    vehicle_keys = int(
        con.execute("SELECT count(*) FROM gold_agg_vehicle_evidence").fetchone()[0]
    )
    if vehicle_keys != EXPECTED_VEHICLE_KEYS:
        failures.append(f"vehicle_keys={vehicle_keys} expected {EXPECTED_VEHICLE_KEYS}")

    priority_counts = dict(
        con.execute(
            "SELECT review_priority, count(*) FROM gold_agg_vehicle_evidence "
            "GROUP BY review_priority"
        ).fetchall()
    )
    for level, expected in EXPECTED_PRIORITY_COUNTS.items():
        if priority_counts.get(level) != expected:
            failures.append(f"priority[{level}]={priority_counts.get(level)} expected {expected}")

    alias_counts = dict(
        con.execute(
            "SELECT alias_priority, count(*) FROM gold_agg_vehicle_evidence "
            "GROUP BY alias_priority"
        ).fetchall()
    )
    for level, expected in EXPECTED_ALIAS_COUNTS.items():
        if alias_counts.get(level) != expected:
            failures.append(f"alias[{level}]={alias_counts.get(level)} expected {expected}")

    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline_priorities = baseline["priority_counts"]
        baseline_alias = baseline["alias_work_queue_counts"]
        baseline_exact_rate = baseline["reference_exact_match_rate"]
        baseline_era_rate = baseline["era_eligible_reference_exact_match_rate"]
        if baseline_priorities != priority_counts:
            failures.append(f"priority_counts differ from baseline: {priority_counts}")
        if baseline_alias != alias_counts:
            failures.append(f"alias_work_queue_counts differ from baseline: {alias_counts}")
        actual_exact_rate = float(
            con.execute(
                "SELECT CAST(count(DISTINCT CASE WHEN reference_exact_match_flag THEN vehicle_key END) "
                "AS DOUBLE) / count(DISTINCT vehicle_key) FROM silver_vehicle_identity_bridge"
            ).fetchone()[0]
        )
        actual_era_rate = float(
            con.execute(
                "SELECT CAST(count(DISTINCT CASE WHEN reference_year_eligible AND reference_exact_match_flag "
                "THEN vehicle_key END) AS DOUBLE) / NULLIF(count(DISTINCT CASE WHEN reference_year_eligible "
                "THEN vehicle_key END), 0) FROM silver_vehicle_identity_bridge"
            ).fetchone()[0]
        )
        for label, actual, expected in [
            ("reference_exact_match_rate", actual_exact_rate, baseline_exact_rate),
            ("era_eligible_reference_exact_match_rate", actual_era_rate, baseline_era_rate),
        ]:
            if abs(actual - expected) > 1e-9:
                failures.append(f"{label}={actual:.6f} expected {expected:.6f}")

    return failures


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = pathlib.Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    bronze.main(["--db", str(db_path), "--data", args.data])
    silver.main(["--db", str(db_path)])
    gold.main(["--db", str(db_path)])
    curated.main(["--db", str(db_path), "--export", args.export])

    con = duckdb.connect(str(db_path))
    failures = reconcile(con, pathlib.Path("analysis/output/decision_baseline.json"))
    con.close()

    if failures:
        for failure in failures:
            print(f"RECONCILE FAIL: {failure}")
        raise SystemExit(1)
    print("reconciliation against local baseline: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())