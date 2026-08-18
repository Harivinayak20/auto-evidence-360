#!/usr/bin/env python3
"""Build a compact, source-backed baseline for validating Fabric Gold outputs."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import sqlite3
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPLOAD_ROOT = PROJECT_ROOT / "data" / "fabric_upload"
OUTPUT_ROOT = PROJECT_ROOT / "analysis" / "output"
MANIFEST_PATH = UPLOAD_ROOT / "manifest.json"
OUTPUT_CSV = OUTPUT_ROOT / "vehicle_evidence_baseline.csv.gz"
OUTPUT_JSON = OUTPUT_ROOT / "decision_baseline.json"
OUTPUT_MD = OUTPUT_ROOT / "decision_baseline.md"
NON_ALPHANUMERIC = re.compile(r"[^A-Z0-9]+")
MIN_MODEL_YEAR = 1900
MAX_MODEL_YEAR = datetime.now().year + 1
REFERENCE_ERA_START_YEAR = 1984
RULE_VERSION = "portfolio_v1"
THRESHOLD_VALIDATION_STATUS = "unvalidated"


def normalized_text(value: str | None) -> str:
    normalized = NON_ALPHANUMERIC.sub(" ", (value or "").strip().upper())
    return " ".join(normalized.split())


def vehicle_identity(make: str | None, model: str | None, year: str | None):
    normalized_make = normalized_text(make)
    normalized_model = normalized_text(model)
    try:
        model_year = int((year or "").strip())
    except ValueError:
        return None
    if not normalized_make or not normalized_model or not MIN_MODEL_YEAR <= model_year <= MAX_MODEL_YEAR:
        return None
    label = f"{model_year} {normalized_make} {normalized_model}"
    raw_key = f"{normalized_make}||{normalized_model}||{model_year}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest(), normalized_make, normalized_model, model_year, label


def true_flag(value: str | None) -> int:
    return int((value or "").strip().lower() in {"y", "yes", "true", "1"})


def integer(value: str | None, default: int = 0) -> int:
    try:
        return int(float((value or "").strip()))
    except ValueError:
        return default


def rows_from(name: str):
    with gzip.open(UPLOAD_ROOT / f"{name}.csv.gz", "rt", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode = OFF;
        PRAGMA synchronous = OFF;
        PRAGMA temp_store = MEMORY;

        CREATE TABLE vehicle_source (
            vehicle_key TEXT NOT NULL,
            make TEXT NOT NULL,
            model TEXT NOT NULL,
            model_year INTEGER NOT NULL,
            vehicle_label TEXT NOT NULL,
            source_system TEXT NOT NULL,
            PRIMARY KEY (vehicle_key, source_system)
        ) WITHOUT ROWID;

        CREATE TABLE complaint_event (
            vehicle_key TEXT NOT NULL,
            complaint_id TEXT NOT NULL,
            severe INTEGER NOT NULL,
            crash INTEGER NOT NULL,
            fire INTEGER NOT NULL,
            injuries INTEGER NOT NULL,
            deaths INTEGER NOT NULL,
            PRIMARY KEY (vehicle_key, complaint_id)
        ) WITHOUT ROWID;

        CREATE TABLE recall_event (
            vehicle_key TEXT NOT NULL,
            campaign_number TEXT NOT NULL,
            do_not_drive INTEGER NOT NULL,
            park_outside INTEGER NOT NULL,
            PRIMARY KEY (vehicle_key, campaign_number)
        ) WITHOUT ROWID;

        CREATE TABLE investigation_event (
            vehicle_key TEXT NOT NULL,
            investigation_number TEXT NOT NULL,
            open_flag INTEGER NOT NULL,
            PRIMARY KEY (vehicle_key, investigation_number)
        ) WITHOUT ROWID;

        CREATE TABLE communication_event (
            vehicle_key TEXT NOT NULL,
            document_id TEXT NOT NULL,
            PRIMARY KEY (vehicle_key, document_id)
        ) WITHOUT ROWID;

        CREATE TABLE ncap_variant (
            vehicle_key TEXT NOT NULL,
            variant_id TEXT NOT NULL,
            overall_stars INTEGER,
            PRIMARY KEY (vehicle_key, variant_id)
        ) WITHOUT ROWID;

        CREATE TABLE epa_variant (
            vehicle_key TEXT NOT NULL,
            epa_vehicle_id TEXT NOT NULL,
            combined_mpg INTEGER,
            annual_fuel_cost INTEGER,
            PRIMARY KEY (vehicle_key, epa_vehicle_id)
        ) WITHOUT ROWID;
        """
    )


def record_source(connection: sqlite3.Connection, identity, source_system: str) -> None:
    if identity is None:
        return
    connection.execute(
        "INSERT OR IGNORE INTO vehicle_source VALUES (?, ?, ?, ?, ?, ?)",
        (*identity, source_system),
    )


def ingest_complaints(connection: sqlite3.Connection) -> None:
    for row in rows_from("complaints"):
        if row["product_type"] != "V":
            continue
        identity = vehicle_identity(row["source_make"], row["source_model"], row["model_year"])
        if identity is None or not row["complaint_id"]:
            continue
        record_source(connection, identity, "NHTSA_COMPLAINT")
        crash = true_flag(row["crash_flag"])
        fire = true_flag(row["fire_flag"])
        injuries = integer(row["injury_count"])
        deaths = integer(row["death_count"])
        severe = int(bool(crash or fire or injuries > 0 or deaths > 0))
        connection.execute(
            """
            INSERT INTO complaint_event VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(vehicle_key, complaint_id) DO UPDATE SET
                severe = MAX(severe, excluded.severe),
                crash = MAX(crash, excluded.crash),
                fire = MAX(fire, excluded.fire),
                injuries = MAX(injuries, excluded.injuries),
                deaths = MAX(deaths, excluded.deaths)
            """,
            (identity[0], row["complaint_id"], severe, crash, fire, injuries, deaths),
        )
    connection.commit()


def ingest_recalls(connection: sqlite3.Connection) -> None:
    for row in rows_from("recalls"):
        identity = vehicle_identity(row["source_make"], row["source_model"], row["model_year"])
        campaign = row["campaign_number"].strip()
        if identity is None or not campaign or row["product_type"] != "V":
            continue
        record_source(connection, identity, "NHTSA_RECALL")
        connection.execute(
            """
            INSERT INTO recall_event VALUES (?, ?, ?, ?)
            ON CONFLICT(vehicle_key, campaign_number) DO UPDATE SET
                do_not_drive = MAX(do_not_drive, excluded.do_not_drive),
                park_outside = MAX(park_outside, excluded.park_outside)
            """,
            (
                identity[0],
                campaign,
                true_flag(row["do_not_drive_flag"]),
                true_flag(row["park_outside_flag"]),
            ),
        )
    connection.commit()


def ingest_investigations(connection: sqlite3.Connection) -> None:
    for row in rows_from("investigations"):
        identity = vehicle_identity(row["source_make"], row["source_model"], row["model_year"])
        investigation = row["investigation_number"].strip()
        if identity is None or not investigation:
            continue
        record_source(connection, identity, "NHTSA_INVESTIGATION")
        connection.execute(
            """
            INSERT INTO investigation_event VALUES (?, ?, ?)
            ON CONFLICT(vehicle_key, investigation_number) DO UPDATE SET
                open_flag = MAX(open_flag, excluded.open_flag)
            """,
            (identity[0], investigation, int(not row["closed_date"].strip())),
        )
    connection.commit()


def ingest_communications(connection: sqlite3.Connection) -> None:
    for row in rows_from("manufacturer_communications"):
        identity = vehicle_identity(row["source_make"], row["source_model"], row["model_year"])
        document_id = row["document_id"].strip()
        if identity is None or not document_id:
            continue
        record_source(connection, identity, "NHTSA_MANUFACTURER_COMMUNICATION")
        connection.execute(
            "INSERT OR IGNORE INTO communication_event VALUES (?, ?)",
            (identity[0], document_id),
        )
    connection.commit()


def ingest_ncap(connection: sqlite3.Connection) -> None:
    for row in rows_from("ncap_ratings"):
        identity = vehicle_identity(row["make"], row["model"], row["model_yr"])
        if identity is None:
            continue
        record_source(connection, identity, "NHTSA_NCAP")
        variant_text = "||".join(
            [identity[0], row["body_style"], row["vehicle_type"], row["drive_train"], row["num_of_seating"]]
        )
        variant_id = hashlib.sha256(variant_text.encode("utf-8")).hexdigest()
        connection.execute(
            "INSERT OR IGNORE INTO ncap_variant VALUES (?, ?, ?)",
            (identity[0], variant_id, integer(row["overall_stars"], default=-1)),
        )
    connection.commit()


def ingest_epa(connection: sqlite3.Connection) -> None:
    for row in rows_from("fuel_economy"):
        identity = vehicle_identity(row["make"], row["model"], row["year"])
        epa_vehicle_id = row["id"].strip()
        if identity is None or not epa_vehicle_id:
            continue
        record_source(connection, identity, "EPA_FUEL_ECONOMY")
        connection.execute(
            "INSERT OR IGNORE INTO epa_variant VALUES (?, ?, ?, ?)",
            (identity[0], epa_vehicle_id, integer(row["comb08"], -1), integer(row["fuelCost08"], -1)),
        )
    connection.commit()


BASELINE_QUERY = """
WITH vehicles AS (
    SELECT
        vehicle_key,
        MIN(make) AS make,
        MIN(model) AS model,
        MIN(model_year) AS model_year,
        MIN(vehicle_label) AS vehicle_label,
        COUNT(DISTINCT source_system) AS source_system_count,
        MAX(CASE WHEN source_system IN ('NHTSA_NCAP', 'EPA_FUEL_ECONOMY') THEN 1 ELSE 0 END) AS reference_exact_match,
        MAX(CASE WHEN model_year >= {REFERENCE_ERA_START_YEAR} THEN 1 ELSE 0 END) AS reference_year_eligible
    FROM vehicle_source
    GROUP BY vehicle_key
),
complaints AS (
    SELECT vehicle_key, COUNT(*) AS complaint_reports, SUM(severe) AS severe_complaint_reports,
           SUM(crash) AS crash_reported_complaints, SUM(fire) AS fire_reported_complaints,
           SUM(injuries) AS reported_injuries, SUM(deaths) AS reported_deaths
    FROM complaint_event GROUP BY vehicle_key
),
recalls AS (
    SELECT vehicle_key, COUNT(*) AS recall_campaigns, SUM(do_not_drive) AS do_not_drive_campaigns,
           SUM(park_outside) AS park_outside_campaigns
    FROM recall_event GROUP BY vehicle_key
),
investigations AS (
    SELECT vehicle_key, COUNT(*) AS investigations, SUM(open_flag) AS open_investigations
    FROM investigation_event GROUP BY vehicle_key
),
communications AS (
    SELECT vehicle_key, COUNT(*) AS manufacturer_documents
    FROM communication_event GROUP BY vehicle_key
),
ncap AS (
    SELECT vehicle_key, COUNT(*) AS ncap_tested_variants
    FROM ncap_variant GROUP BY vehicle_key
),
epa AS (
    SELECT vehicle_key, COUNT(*) AS epa_variants
    FROM epa_variant GROUP BY vehicle_key
)
SELECT
    v.*,
    '{RULE_VERSION}' AS rule_version,
    '{THRESHOLD_VALIDATION_STATUS}' AS threshold_validation_status,
    COALESCE(c.complaint_reports, 0) AS complaint_reports,
    COALESCE(c.severe_complaint_reports, 0) AS severe_complaint_reports,
    COALESCE(c.crash_reported_complaints, 0) AS crash_reported_complaints,
    COALESCE(c.fire_reported_complaints, 0) AS fire_reported_complaints,
    COALESCE(c.reported_injuries, 0) AS reported_injuries,
    COALESCE(c.reported_deaths, 0) AS reported_deaths,
    COALESCE(r.recall_campaigns, 0) AS recall_campaigns,
    COALESCE(r.do_not_drive_campaigns, 0) AS do_not_drive_campaigns,
    COALESCE(r.park_outside_campaigns, 0) AS park_outside_campaigns,
    COALESCE(i.investigations, 0) AS investigations,
    COALESCE(i.open_investigations, 0) AS open_investigations,
    COALESCE(m.manufacturer_documents, 0) AS manufacturer_documents,
    COALESCE(n.ncap_tested_variants, 0) AS ncap_tested_variants,
    COALESCE(e.epa_variants, 0) AS epa_variants
FROM vehicles v
LEFT JOIN complaints c USING (vehicle_key)
LEFT JOIN recalls r USING (vehicle_key)
LEFT JOIN investigations i USING (vehicle_key)
LEFT JOIN communications m USING (vehicle_key)
LEFT JOIN ncap n USING (vehicle_key)
LEFT JOIN epa e USING (vehicle_key)
ORDER BY v.make, v.model, v.model_year
""".format(
    REFERENCE_ERA_START_YEAR=REFERENCE_ERA_START_YEAR,
    RULE_VERSION=RULE_VERSION,
    THRESHOLD_VALIDATION_STATUS=THRESHOLD_VALIDATION_STATUS,
)


def priority_and_reason(row: dict[str, int | str]):
    if row["do_not_drive_campaigns"] > 0:
        return "CRITICAL", "At least one do-not-drive recall campaign"
    if row["park_outside_campaigns"] > 0:
        return "CRITICAL", "At least one park-outside recall campaign"
    if row["open_investigations"] > 0:
        return "HIGH", "At least one open NHTSA investigation"
    if row["complaint_reports"] >= 10 and row["severe_complaint_reports"] >= 3:
        return "HIGH", "Minimum-volume complaint signal with multiple severe reports"
    if row["recall_campaigns"] > 0:
        return "REVIEW", "Recall campaign evidence exists"
    if row["complaint_reports"] >= 5:
        return "REVIEW", "Complaint reports meet review threshold"
    if row["manufacturer_documents"] >= 10:
        return "REVIEW", "Manufacturer communication volume meets review threshold"
    return "MONITOR", "No current rule crossed"


def alias_priority_and_reason(row: dict[str, int | str]):
    if row["reference_exact_match"]:
        return "NONE", "Exact EPA or NCAP reference match; no alias review required"
    if row["do_not_drive_campaigns"] > 0 or row["park_outside_campaigns"] > 0 or row["open_investigations"] > 0:
        return "P0", "Unresolved identity with do-not-drive, park-outside, or open-investigation evidence"
    if (
        row["source_system_count"] >= 2
        or row["complaint_reports"] >= 10
        or row["severe_complaint_reports"] >= 3
        or row["recall_campaigns"] > 0
        or row["manufacturer_documents"] >= 10
    ):
        return "P1", "Unresolved identity with multi-source or high-signal evidence"
    return "P2", "Unresolved low-signal identity; aggregate backlog only"


def build_outputs(connection: sqlite3.Connection, manifest: dict) -> dict:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    cursor = connection.execute(BASELINE_QUERY)
    source_columns = [description[0] for description in cursor.description]
    output_columns = source_columns + [
        "evidence_source_count",
        "reference_match_status",
        "alias_priority",
        "alias_reason",
        "review_priority",
        "review_reason",
    ]
    priority_counts = Counter()
    reason_counts = Counter()
    alias_priority_counts = Counter()
    totals = Counter()
    vehicle_count = 0
    reference_matches = 0
    era_eligible_count = 0
    era_eligible_matches = 0

    with gzip.open(OUTPUT_CSV, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_columns)
        writer.writeheader()
        for values in cursor:
            row = dict(zip(source_columns, values))
            evidence_source_count = sum(
                int(row[column] > 0)
                for column in [
                    "complaint_reports",
                    "recall_campaigns",
                    "investigations",
                    "manufacturer_documents",
                    "ncap_tested_variants",
                    "epa_variants",
                ]
            )
            priority, reason = priority_and_reason(row)
            alias_priority, alias_reason = alias_priority_and_reason(row)
            row.update(
                evidence_source_count=evidence_source_count,
                reference_match_status="MATCHED" if row["reference_exact_match"] else "UNRESOLVED",
                alias_priority=alias_priority,
                alias_reason=alias_reason,
                review_priority=priority,
                review_reason=reason,
            )
            writer.writerow(row)
            vehicle_count += 1
            reference_matches += int(row["reference_exact_match"])
            if row["reference_year_eligible"]:
                era_eligible_count += 1
                era_eligible_matches += int(row["reference_exact_match"])
            priority_counts[priority] += 1
            reason_counts[reason] += 1
            alias_priority_counts[alias_priority] += 1
            for metric in [
                "complaint_reports",
                "severe_complaint_reports",
                "recall_campaigns",
                "do_not_drive_campaigns",
                "park_outside_campaigns",
                "investigations",
                "open_investigations",
                "manufacturer_documents",
                "ncap_tested_variants",
                "epa_variants",
            ]:
                totals[metric] += int(row[metric])

    summary = {
        "project": "Auto Evidence 360",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_manifest_created_at_utc": manifest["created_at_utc"],
        "purpose": "Independent local baseline for Fabric Gold and Power BI reconciliation",
        "model_year_window": {"min": MIN_MODEL_YEAR, "max": MAX_MODEL_YEAR},
        "rule_version": RULE_VERSION,
        "threshold_validation_status": THRESHOLD_VALIDATION_STATUS,
        "vehicle_keys": vehicle_count,
        "reference_exact_match_vehicle_keys": reference_matches,
        "reference_exact_match_rate": reference_matches / vehicle_count if vehicle_count else None,
        "era_eligible_vehicle_keys": era_eligible_count,
        "era_eligible_reference_exact_match_vehicle_keys": era_eligible_matches,
        "era_eligible_reference_exact_match_rate": era_eligible_matches / era_eligible_count if era_eligible_count else None,
        "priority_counts": dict(sorted(priority_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "alias_work_queue_counts": dict(sorted(alias_priority_counts.items())),
        "business_entity_counts": dict(sorted(totals.items())),
        "output_file": str(OUTPUT_CSV.relative_to(PROJECT_ROOT)),
        "output_sha256": hashlib.sha256(OUTPUT_CSV.read_bytes()).hexdigest(),
        "interpretation": "Counts are public-record evidence signals and review rules, not make/model reliability rates.",
    }
    OUTPUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def write_markdown(summary: dict) -> None:
    priorities = summary["priority_counts"]
    aliases = summary["alias_work_queue_counts"]
    entities = summary["business_entity_counts"]
    lines = [
        "# Decision Baseline",
        "",
        "## TL;DR",
        "",
        f"- {summary['vehicle_keys']:,} normalized make/model/year keys are represented across the approved sources.",
        f"- {priorities.get('CRITICAL', 0):,} keys meet a Critical review rule and {priorities.get('HIGH', 0):,} meet a High rule.",
        f"- {summary['reference_exact_match_rate']:.2%} of unioned keys exactly match the EPA or NCAP reference; {summary['era_eligible_reference_exact_match_rate']:.2%} of EPA/NCAP-era-eligible keys (model year {REFERENCE_ERA_START_YEAR} or later) match.",
        "- The operational evidence queue is independent of EPA/NCAP enrichment status.",
        "- These are public-record evidence signals and operating rules, not reliability rates.",
        "",
        "## Metadata",
        "",
        f"- Rule version: `{RULE_VERSION}`",
        f"- Threshold validation status: `{THRESHOLD_VALIDATION_STATUS}` (pending stakeholder validation)",
        f"- Model-year window: {MIN_MODEL_YEAR} through {MAX_MODEL_YEAR}",
        "",
        "## Review priority",
        "",
        "| Priority | Vehicle keys |",
        "|---|---:|",
    ]
    for priority in ["CRITICAL", "HIGH", "REVIEW", "MONITOR"]:
        lines.append(f"| {priority.title()} | {priorities.get(priority, 0):,} |")
    lines.extend(
        [
            "",
            "## Alias work queue (unresolved identities only)",
            "",
            "The complete unresolved backlog stays in Silver. Gold publishes an actionable work queue:",
            "",
            "| Alias priority | Vehicle keys |",
            "|---|---:|",
            f"| P0: unresolved with do-not-drive, park-outside, or open-investigation evidence | {aliases.get('P0', 0):,} |",
            f"| P1: unresolved with multi-source or high-signal evidence | {aliases.get('P1', 0):,} |",
            f"| P2: unresolved low-signal backlog (aggregate only) | {aliases.get('P2', 0):,} |",
            "",
            "## Distinct business entities after grain correction",
            "",
            "| Entity | Count |",
            "|---|---:|",
            f"| Complaint reports | {entities.get('complaint_reports', 0):,} |",
            f"| Severe-indicator complaint reports | {entities.get('severe_complaint_reports', 0):,} |",
            f"| Vehicle-campaign pairs | {entities.get('recall_campaigns', 0):,} |",
            f"| Vehicle-investigation pairs | {entities.get('investigations', 0):,} |",
            f"| Vehicle-document pairs | {entities.get('manufacturer_documents', 0):,} |",
            f"| NCAP tested variants | {entities.get('ncap_tested_variants', 0):,} |",
            f"| EPA configurations | {entities.get('epa_variants', 0):,} |",
            "",
            "The vehicle-pair counts above intentionally differ from global distinct campaign, investigation, or document counts. The Power BI measures apply the correct context-specific grain.",
        ]
    )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    with tempfile.NamedTemporaryFile(prefix="auto_evidence_", suffix=".sqlite") as database_file:
        connection = sqlite3.connect(database_file.name)
        initialize_database(connection)
        ingest_complaints(connection)
        ingest_recalls(connection)
        ingest_investigations(connection)
        ingest_communications(connection)
        ingest_ncap(connection)
        ingest_epa(connection)
        summary = build_outputs(connection, manifest)
        write_markdown(summary)
        connection.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
