# Fabric notebook source
# Attach this notebook to a Lakehouse, then upload data/fabric_upload/* to:
# Files/landing/auto_evidence_360/

# %% [markdown]
# # 01 - Ingest Bronze
# Preserve the approved source extracts, attach provenance, and stop the run when
# a file is missing, its schema changes, or its row count differs from manifest.

# %%
from datetime import datetime, timezone

from pyspark.sql import functions as F


LANDING_ROOT = "Files/landing/auto_evidence_360"
MANIFEST_PATH = f"{LANDING_ROOT}/manifest.json"
BRONZE_PREFIX = "bronze_"

SOURCE_FILES = {
    "complaints": "complaints.csv.gz",
    "recalls": "recalls.csv.gz",
    "investigations": "investigations.csv.gz",
    "manufacturer_communications": "manufacturer_communications.csv.gz",
    "ncap_ratings": "ncap_ratings.csv.gz",
    "fuel_economy": "fuel_economy.csv.gz",
    "state_registrations": "state_registrations.csv.gz",
}

batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
ingested_at = datetime.now(timezone.utc)

# %%
manifest = spark.read.option("multiLine", "true").json(MANIFEST_PATH)
manifest_extracts = (
    manifest.select(F.explode("extracts").alias("extract"))
    .select("extract.*")
)
manifest_rows = {row["table_name"]: row.asDict(recursive=True) for row in manifest_extracts.collect()}

missing_manifest_entries = sorted(set(SOURCE_FILES) - set(manifest_rows))
if missing_manifest_entries:
    raise ValueError(f"Manifest is missing entries: {missing_manifest_entries}")

# %%
audit_rows = []
loaded_tables = {}

for table_name, file_name in SOURCE_FILES.items():
    contract = manifest_rows[table_name]
    source_path = f"{LANDING_ROOT}/{file_name}"

    raw = (
        spark.read.option("header", "true")
        .option("encoding", "UTF-8")
        .option("quote", '"')
        .option("escape", '"')
        .option("multiLine", "true")
        .option("mode", "FAILFAST")
        .csv(source_path)
    )

    expected_columns = contract["columns"]
    schema_matches = raw.columns == expected_columns
    actual_rows = raw.count()
    expected_rows = int(contract["rows"])
    row_count_matches = actual_rows == expected_rows
    status = "PASS" if schema_matches and row_count_matches else "FAIL"

    audit_rows.append(
        (
            batch_id,
            table_name,
            contract["source_id"],
            file_name,
            contract["source_sha256"],
            contract["output_sha256"],
            expected_rows,
            actual_rows,
            schema_matches,
            row_count_matches,
            status,
            ingested_at,
        )
    )

    loaded_tables[table_name] = (
        raw.withColumn("_source_id", F.lit(contract["source_id"]))
        .withColumn("_source_file", F.lit(file_name))
        .withColumn("_source_sha256", F.lit(contract["source_sha256"]))
        .withColumn("_extract_sha256", F.lit(contract["output_sha256"]))
        .withColumn("_batch_id", F.lit(batch_id))
        .withColumn("_ingested_at", F.lit(ingested_at).cast("timestamp"))
    )

# %%
audit_columns = [
    "batch_id",
    "table_name",
    "source_id",
    "source_file",
    "source_sha256",
    "extract_sha256",
    "expected_rows",
    "actual_rows",
    "schema_matches",
    "row_count_matches",
    "status",
    "ingested_at",
]
audit = spark.createDataFrame(audit_rows, audit_columns)
audit.write.format("delta").mode("append").saveAsTable("audit_bronze_ingestion")

failed_contracts = [row for row in audit_rows if row[10] == "FAIL"]
if failed_contracts:
    failed_names = [row[1] for row in failed_contracts]
    raise ValueError(f"Bronze contract failed for: {failed_names}. Inspect audit_bronze_ingestion.")

# %%
for table_name, frame in loaded_tables.items():
    (
        frame.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(f"{BRONZE_PREFIX}{table_name}")
    )

manifest.withColumn("_batch_id", F.lit(batch_id)).write.format("delta").mode("overwrite").saveAsTable(
    "bronze_source_manifest"
)

display(audit.orderBy("table_name"))
