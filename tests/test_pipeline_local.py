#!/usr/bin/env python3
"""End-to-end pipeline contract tests. Skipped when the approved extracts are
absent. Reuses an existing lakehouse via AUTO_EVIDENCE_DB to avoid rerunning
the full pipeline twice (CI runs the pipeline before tests)."""

from __future__ import annotations

import os
import pathlib
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src" / "local"))

try:
    import duckdb

    import run_pipeline

    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "fabric_upload"

EXPECTED_VEHICLE_KEYS = 82400
EXPECTED_PRIORITY_COUNTS = {"CRITICAL": 1355, "HIGH": 2222, "REVIEW": 39955, "MONITOR": 38868}
EXPECTED_ALIAS_COUNTS = {"NONE": 33999, "P0": 1420, "P1": 35505, "P2": 11476}
EXPECTED_EXACT_MATCH_RATE = 0.4126092233009709
EXPECTED_ERA_MATCH_RATE = 0.419047501663914

REUSE_DB = os.environ.get("AUTO_EVIDENCE_DB")
REUSE_EXPORT = os.environ.get("AUTO_EVIDENCE_EXPORT")


@unittest.skipUnless(
    HAS_DUCKDB and (DATA_DIR / "manifest.json").exists(),
    "duckdb and the approved extracts are required",
)
class TestPipelineLocal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if REUSE_DB:
            cls.db_path = pathlib.Path(REUSE_DB)
            cls.export_dir = pathlib.Path(REUSE_EXPORT) if REUSE_EXPORT else cls.db_path.parent / "curated"
        else:
            cls.tmp = tempfile.mkdtemp(prefix="auto_evidence_test_")
            cls.db_path = pathlib.Path(cls.tmp) / "lakehouse.duckdb"
            cls.export_dir = pathlib.Path(cls.tmp) / "curated"
            try:
                run_pipeline.main(
                    [
                        "--db", str(cls.db_path),
                        "--data", str(DATA_DIR),
                        "--export", str(cls.export_dir),
                    ]
                )
            except SystemExit as exc:
                raise AssertionError(f"pipeline exited {exc.code}") from exc
        cls.con = duckdb.connect(str(cls.db_path))

    @classmethod
    def tearDownClass(cls):
        cls.con.close()
        tmp = getattr(cls, "tmp", None)
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_bronze_contracts_all_pass(self):
        failed = self.con.execute(
            "SELECT count(*) FROM audit_bronze_ingestion WHERE status = 'FAIL'"
        ).fetchone()[0]
        self.assertEqual(failed, 0)
        audited = self.con.execute(
            "SELECT count(DISTINCT table_name) FROM audit_bronze_ingestion"
        ).fetchone()[0]
        self.assertEqual(audited, 7)

    def test_vehicle_key_count(self):
        count = self.con.execute("SELECT count(*) FROM gold_dim_vehicle").fetchone()[0]
        self.assertEqual(count, EXPECTED_VEHICLE_KEYS)

    def test_review_priority_counts(self):
        counts = dict(
            self.con.execute(
                "SELECT review_priority, count(*) FROM gold_agg_vehicle_evidence GROUP BY review_priority"
            ).fetchall()
        )
        self.assertEqual(counts, EXPECTED_PRIORITY_COUNTS)

    def test_alias_priority_counts(self):
        counts = dict(
            self.con.execute(
                "SELECT alias_priority, count(*) FROM gold_agg_vehicle_evidence GROUP BY alias_priority"
            ).fetchall()
        )
        self.assertEqual(counts, EXPECTED_ALIAS_COUNTS)

    def test_reference_match_rates(self):
        rate = self.con.execute(
            "SELECT CAST(count(DISTINCT CASE WHEN reference_exact_match_flag THEN vehicle_key END) "
            "AS DOUBLE) / count(DISTINCT vehicle_key) FROM silver_vehicle_identity_bridge"
        ).fetchone()[0]
        era_rate = self.con.execute(
            "SELECT CAST(count(DISTINCT CASE WHEN reference_year_eligible AND reference_exact_match_flag "
            "THEN vehicle_key END) AS DOUBLE) / NULLIF(count(DISTINCT CASE WHEN reference_year_eligible "
            "THEN vehicle_key END), 0) FROM silver_vehicle_identity_bridge"
        ).fetchone()[0]
        self.assertAlmostEqual(rate, EXPECTED_EXACT_MATCH_RATE, places=6)
        self.assertAlmostEqual(era_rate, EXPECTED_ERA_MATCH_RATE, places=6)

    def test_data_quality_checks_all_pass(self):
        failed = self.con.execute(
            "SELECT count(*) FROM gold_data_quality_checks WHERE NOT passed"
        ).fetchone()[0]
        self.assertEqual(failed, 0)

    def test_alias_work_queue_contains_only_p0_p1(self):
        p2 = self.con.execute(
            "SELECT count(*) FROM gold_alias_work_queue WHERE alias_priority = 'P2'"
        ).fetchone()[0]
        self.assertEqual(p2, 0)
        rows = self.con.execute(
            "SELECT count(*) FROM gold_alias_work_queue"
        ).fetchone()[0]
        self.assertEqual(rows, EXPECTED_ALIAS_COUNTS["P0"] + EXPECTED_ALIAS_COUNTS["P1"])

    def test_curated_exports_written(self):
        expected = {"evidence_summary.parquet", "alias_work_queue.parquet", "data_trust.parquet"}
        found = {path.name for path in self.export_dir.glob("*.parquet")}
        self.assertEqual(found, expected)
        rows = duckdb.connect().execute(
            f"SELECT count(*) FROM read_parquet('{self.export_dir / 'evidence_summary.parquet'}')"
        ).fetchone()[0]
        self.assertEqual(rows, EXPECTED_VEHICLE_KEYS)


if __name__ == "__main__":
    unittest.main()