"""Full local data-contract tests.

These tests require the ignored bulk data package (data/raw plus the
data/fabric_upload extracts). They are skipped automatically on a clean
clone; see test_repo_contract.py for the always-on repository contract.
"""

import csv
import gzip
import hashlib
import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPLOAD_ROOT = PROJECT_ROOT / "data" / "fabric_upload"
MANIFEST_PATH = UPLOAD_ROOT / "manifest.json"

DATA_PACKAGE_PRESENT = (UPLOAD_ROOT / "complaints.csv.gz").is_file()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@unittest.skipUnless(DATA_PACKAGE_PRESENT, "extract package not present; run download and prepare locally")
class RealDataContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.extracts = {item["table_name"]: item for item in cls.manifest["extracts"]}

    def test_extract_headers_and_sha256_match_manifest(self):
        for extract in self.extracts.values():
            path = UPLOAD_ROOT / extract["output_file"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(extract["output_sha256"], sha256_file(path), path.name)
            with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
                header = next(csv.reader(handle))
            self.assertEqual(extract["columns"], header, path.name)

    def test_vehicle_only_complaint_rows_reconcile_to_silver_target(self):
        vehicle_complaint_rows = 0
        with gzip.open(UPLOAD_ROOT / "complaints.csv.gz", "rt", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["product_type"] == "V":
                    vehicle_complaint_rows += 1
        self.assertEqual(180_526, vehicle_complaint_rows)

    def test_vehicle_only_recall_rows_reconcile_to_silver_target(self):
        vehicle_recall_rows = 0
        with gzip.open(UPLOAD_ROOT / "recalls.csv.gz", "rt", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["product_type"] == "V":
                    vehicle_recall_rows += 1
        self.assertEqual(217_702, vehicle_recall_rows)


if __name__ == "__main__":
    unittest.main()