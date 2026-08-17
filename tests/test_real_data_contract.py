import csv
import gzip
import hashlib
import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPLOAD_ROOT = PROJECT_ROOT / "data" / "fabric_upload"
MANIFEST_PATH = UPLOAD_ROOT / "manifest.json"
PROFILE_PATH = PROJECT_ROOT / "analysis" / "output" / "source_profile.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RealDataContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.extracts = {item["table_name"]: item for item in cls.manifest["extracts"]}

    def test_seven_real_extracts_total_1411783_rows(self):
        self.assertEqual(7, len(self.extracts))
        self.assertEqual(1_411_783, sum(item["rows"] for item in self.extracts.values()))

    def test_extract_headers_and_sha256_match_manifest(self):
        for extract in self.extracts.values():
            path = UPLOAD_ROOT / extract["output_file"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(extract["output_sha256"], sha256_file(path), path.name)
            with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
                header = next(csv.reader(handle))
            self.assertEqual(extract["columns"], header, path.name)

    def test_complaint_cloud_extract_excludes_sensitive_fields(self):
        complaint_columns = {column.lower() for column in self.extracts["complaints"]["columns"]}
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
        profiled_rows = sum(item["rows"] for item in profile["datasets"])
        manifest_rows = sum(item["rows"] for item in self.extracts.values())
        self.assertEqual(manifest_rows, profiled_rows)
        self.assertEqual(0, sum(item["malformed_rows"] for item in profile["datasets"]))


if __name__ == "__main__":
    unittest.main()
