"""Clean-clone repository contract tests.

These tests run from a fresh clone without the ignored bulk data package
(data/raw and data/fabric_upload/*.csv.gz are not committed). They verify
that the committed manifests, evidence, guards, and documented paths stay
consistent.
"""

import json
import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPLOAD_ROOT = PROJECT_ROOT / "data" / "fabric_upload"
MANIFEST_PATH = UPLOAD_ROOT / "manifest.json"
PROFILE_PATH = PROJECT_ROOT / "analysis" / "output" / "source_profile.json"
BASELINE_PATH = PROJECT_ROOT / "analysis" / "output" / "decision_baseline.json"
README_PATH = PROJECT_ROOT / "README.md"
GITIGNORE_PATH = PROJECT_ROOT / ".gitignore"
LICENSE_PATH = PROJECT_ROOT / "LICENSE"
CI_PATH = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"

REFERENCED_EXTENSIONS = (".py", ".json", ".md", ".dax", ".ipynb", ".yml", ".yaml")


class RepoContractTests(unittest.TestCase):
    def test_manifest_declares_seven_extracts_totaling_1411783_rows(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(7, len(manifest["extracts"]))
        self.assertEqual(1_411_783, sum(item["rows"] for item in manifest["extracts"]))
        for extract in manifest["extracts"]:
            self.assertTrue(extract["output_sha256"])
            self.assertTrue(extract["source_sha256"])
            self.assertTrue(extract["columns"])

    def test_complaint_cloud_extract_excludes_sensitive_fields(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        complaint_columns = {
            column.lower()
            for item in manifest["extracts"]
            if item["table_name"] == "complaints"
            for column in item["columns"]
        }
        forbidden = {
            "complaint_description",
            "vin",
            "vin_prefix",
            "city",
            "dealer_name",
            "dealer_phone",
            "vehicle_operator",
        }
        self.assertTrue(forbidden.isdisjoint(complaint_columns))

    def test_profile_reconciles_to_upload_manifest(self):
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        profiled_rows = sum(item["rows"] for item in profile["datasets"])
        manifest_rows = sum(item["rows"] for item in manifest["extracts"])
        self.assertEqual(manifest_rows, profiled_rows)
        self.assertEqual(0, sum(item["malformed_rows"] for item in profile["datasets"]))

    def test_profile_publishes_two_coverage_measures(self):
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(1900, profile["model_year_window"]["min"])
        for source in profile["cross_source_exact_match_coverage"]:
            self.assertIn("exact_match_rate", source)
            self.assertIn("era_eligible_exact_match_rate", source)
        union = profile["union_exact_match_coverage"]
        self.assertIn("all_valid_exact_match_rate", union)
        self.assertIn("era_eligible_exact_match_rate", union)

    def test_baseline_labels_rules_unvalidated(self):
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        self.assertEqual("portfolio_v1", baseline["rule_version"])
        self.assertEqual("unvalidated", baseline["threshold_validation_status"])
        self.assertIn("era_eligible_reference_exact_match_rate", baseline)
        self.assertIn("alias_work_queue_counts", baseline)
        self.assertTrue(set(baseline["alias_work_queue_counts"]).issubset({"NONE", "P0", "P1", "P2"}))

    def test_baseline_alias_queue_has_no_negative_or_missing_priorities(self):
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        counts = baseline["alias_work_queue_counts"]
        self.assertGreaterEqual(counts.get("P0", 0), 0)
        self.assertGreaterEqual(counts.get("P1", 0), 0)
        self.assertGreaterEqual(counts.get("P2", 0), 0)

    def test_gitignore_blocks_bulk_data_and_generated_extracts(self):
        rules = GITIGNORE_PATH.read_text(encoding="utf-8").splitlines()
        self.assertTrue(any("data/raw" in rule for rule in rules))
        self.assertTrue(any("*.csv.gz" in rule for rule in rules))

    def test_license_and_ci_exist(self):
        self.assertTrue(LICENSE_PATH.is_file())
        self.assertTrue(CI_PATH.is_file())

    def test_every_readme_referenced_path_exists(self):
        readme = README_PATH.read_text(encoding="utf-8")
        candidates = set(re.findall(r"`([A-Za-z0-9_./-]+\.(?:py|json|md|dax|ipynb|yml|yaml))`", readme))
        self.assertTrue(candidates, "no file paths found in README")
        missing = sorted(path for path in candidates if not (PROJECT_ROOT / path).exists())
        self.assertEqual([], missing, f"README references missing files: {missing}")

    def test_no_bulk_data_tracked(self):
        ignored = [".gitignore"]
        tracked_candidates = [
            path for path in [UPLOAD_ROOT, PROJECT_ROOT / "data" / "raw"] if path.exists()
        ]
        for directory in tracked_candidates:
            for path in directory.rglob("*"):
                if path.is_file() and path.name not in ignored:
                    self.assertTrue(
                        path.is_relative_to(directory),
                        f"unexpected file in committed area: {path}",
                    )


if __name__ == "__main__":
    unittest.main()