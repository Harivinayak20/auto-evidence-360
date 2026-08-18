#!/usr/bin/env python3
"""Gold: publish a star schema, an aggregate evidence mart, a transparent review
queue, and reconciliation checks. Review priority is a rule, not a safety score."""

from __future__ import annotations

import argparse
import pathlib
import sys

import duckdb


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to the DuckDB lakehouse file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    con = duckdb.connect(args.db)

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_dim_vehicle AS
        SELECT vehicle_key AS vehicle_key,
            min(normalized_make) AS make,
            min(normalized_model) AS model,
            min(model_year_int) AS model_year,
            count(DISTINCT source_system) AS source_system_count,
            bool_or(reference_exact_match_flag) AS reference_exact_match_flag,
            bool_or(reference_year_eligible) AS reference_year_eligible,
            min(reference_match_status) AS reference_match_status,
            min(rule_version) AS rule_version,
            min(threshold_validation_status) AS threshold_validation_status,
            concat_ws(' ', CAST(min(model_year_int) AS VARCHAR), min(normalized_make),
                min(normalized_model)) AS vehicle_label
        FROM silver_vehicle_identity_bridge
        GROUP BY vehicle_key
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_dim_date AS
        WITH date_bounds AS (
            SELECT min(date_value) AS min_date, max(date_value) AS max_date
            FROM (
                SELECT incident_date_parsed AS date_value FROM silver_complaints
                UNION ALL SELECT received_date FROM silver_complaints
                UNION ALL SELECT report_received_date_parsed FROM silver_recalls
                UNION ALL SELECT opened_date_parsed FROM silver_investigations
                UNION ALL SELECT communication_date FROM silver_manufacturer_communications
            )
            WHERE date_value IS NOT NULL
        )
        SELECT CAST(strftime(generate_series, '%Y%m%d') AS INT) AS date_key,
            generate_series AS date,
            year(generate_series) AS year,
            quarter(generate_series) AS quarter,
            month(generate_series) AS month_number,
            strftime(generate_series, '%B') AS month_name,
            strftime(generate_series, '%Y-%m') AS year_month,
            week(generate_series) AS week_of_year
        FROM date_bounds, generate_series(date_bounds.min_date::DATE,
            date_bounds.max_date::DATE, INTERVAL '1 day')
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_dim_evidence_topic AS
        SELECT * FROM (VALUES
            ('FIRE_OR_THERMAL', 'Fire Or Thermal'),
            ('BRAKES', 'Brakes'),
            ('AIR_BAGS', 'Air Bags'),
            ('STEERING', 'Steering'),
            ('POWERTRAIN', 'Powertrain'),
            ('ELECTRICAL_OR_SOFTWARE', 'Electrical Or Software'),
            ('TIRES_OR_WHEELS', 'Tires Or Wheels'),
            ('VISIBILITY', 'Visibility'),
            ('OCCUPANT_RESTRAINT', 'Occupant Restraint'),
            ('OTHER', 'Other')
        ) AS t(topic_key, topic_label)
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_fact_complaint AS
        SELECT complaint_record_id, complaint_id, vehicle_key,
            CAST(strftime(incident_date_parsed, '%Y%m%d') AS INT) AS incident_date_key,
            CAST(strftime(received_date, '%Y%m%d') AS INT) AS received_date_key,
            component_name, evidence_topic,
            crash_reported_flag, fire_reported_flag, severe_report_flag,
            injury_count_int, death_count_int, mileage_at_failure_int,
            incident_state, _source_id, _batch_id
        FROM silver_complaints
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_fact_recall AS
        SELECT recall_record_id, campaign_number, vehicle_key,
            CAST(strftime(report_received_date_parsed, '%Y%m%d') AS INT) AS report_received_date_key,
            component_name, evidence_topic, potential_units_affected_int,
            do_not_drive, park_outside, filing_manufacturer,
            defect_summary, consequence_summary, corrective_action,
            _source_id, _batch_id
        FROM silver_recalls
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_fact_investigation AS
        SELECT investigation_record_key, investigation_number, vehicle_key,
            CAST(strftime(opened_date_parsed, '%Y%m%d') AS INT) AS opened_date_key,
            CAST(strftime(closed_date_parsed, '%Y%m%d') AS INT) AS closed_date_key,
            open_investigation_flag, component_name, evidence_topic,
            subject, summary, campaign_number, _source_id, _batch_id
        FROM silver_investigations
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_fact_manufacturer_communication AS
        SELECT communication_record_key, nhtsa_communication_id, document_id, vehicle_key,
            CAST(strftime(communication_date, '%Y%m%d') AS INT) AS communication_date_key,
            communication_type, nhtsa_components, evidence_topic, summary,
            _source_id, _batch_id
        FROM silver_manufacturer_communications
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_fact_ncap_variant AS
        SELECT ncap_variant_key, vehicle_key, body_style, vehicle_type, drive_train,
            num_of_seating, overall_stars_int AS overall_stars,
            overall_frnt_stars_int AS overall_front_stars,
            overall_side_stars_int AS overall_side_stars,
            rollover_stars_int AS rollover_stars,
            rollover_possibility_decimal, static_stability_factor_decimal,
            blind_spot_detection, adaptive_cruise_control,
            frnt_collision_warning, lane_departure_warning,
            _source_id, _batch_id
        FROM silver_ncap_ratings
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_fact_fuel_economy_variant AS
        SELECT id_int AS epa_vehicle_id, vehicle_key, VClass AS vehicle_class,
            fuelType AS fuel_type, drive, trany,
            cylinders_int AS cylinders, displ_decimal AS engine_displacement_liters,
            city08_int AS city_mpg, highway08_int AS highway_mpg,
            comb08_int AS combined_mpg, fuelCost08_int AS annual_fuel_cost,
            ghgScore_int AS ghg_score, co2TailpipeGpm_decimal AS tailpipe_co2_grams_per_mile,
            range_int AS range_miles, _source_id, _batch_id
        FROM silver_fuel_economy
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_fact_state_registration AS
        SELECT year_int AS year, state_name, category_normalized,
            registration_type_normalized, registered_vehicles, _source_id, _batch_id
        FROM silver_state_registrations
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_agg_vehicle_evidence AS
        WITH complaint_event AS (
            SELECT vehicle_key, complaint_id,
                max(CASE WHEN severe_report_flag THEN 1 ELSE 0 END) AS severe_report_int,
                max(CASE WHEN crash_reported_flag THEN 1 ELSE 0 END) AS crash_report_int,
                max(CASE WHEN fire_reported_flag THEN 1 ELSE 0 END) AS fire_report_int,
                max(injury_count_int) AS injury_count,
                max(death_count_int) AS death_count
            FROM silver_complaints
            GROUP BY vehicle_key, complaint_id
        ),
        complaint_agg AS (
            SELECT vehicle_key,
                count(complaint_id) AS complaint_reports,
                sum(severe_report_int) AS severe_complaint_reports,
                sum(crash_report_int) AS crash_reported_complaints,
                sum(fire_report_int) AS fire_reported_complaints,
                sum(injury_count) AS reported_injuries,
                sum(death_count) AS reported_deaths
            FROM complaint_event
            GROUP BY vehicle_key
        ),
        recall_agg AS (
            SELECT vehicle_key,
                count(DISTINCT campaign_number) AS recall_campaigns,
                count(DISTINCT CASE WHEN do_not_drive THEN campaign_number END) AS do_not_drive_campaigns,
                count(DISTINCT CASE WHEN park_outside THEN campaign_number END) AS park_outside_campaigns
            FROM silver_recalls
            GROUP BY vehicle_key
        ),
        investigation_agg AS (
            SELECT vehicle_key,
                count(DISTINCT investigation_number) AS investigations,
                count(DISTINCT CASE WHEN open_investigation_flag THEN investigation_number END)
                    AS open_investigations
            FROM silver_investigations
            GROUP BY vehicle_key
        ),
        communication_agg AS (
            SELECT vehicle_key, count(DISTINCT document_id) AS manufacturer_documents
            FROM silver_manufacturer_communications
            GROUP BY vehicle_key
        ),
        ncap_agg AS (
            SELECT vehicle_key,
                count(DISTINCT ncap_variant_key) AS ncap_tested_variants,
                median(overall_stars_int) AS median_overall_stars
            FROM silver_ncap_ratings
            GROUP BY vehicle_key
        ),
        fuel_agg AS (
            SELECT vehicle_key,
                count(DISTINCT id) AS epa_variants,
                median(comb08_int) AS median_combined_mpg,
                median(fuelCost08_int) AS median_annual_fuel_cost
            FROM silver_fuel_economy
            GROUP BY vehicle_key
        ),
        mart AS (
            SELECT d.*, c.complaint_reports, c.severe_complaint_reports,
                c.crash_reported_complaints, c.fire_reported_complaints,
                c.reported_injuries, c.reported_deaths,
                r.recall_campaigns, r.do_not_drive_campaigns, r.park_outside_campaigns,
                i.investigations, i.open_investigations,
                m.manufacturer_documents, n.ncap_tested_variants, n.median_overall_stars,
                f.epa_variants, f.median_combined_mpg, f.median_annual_fuel_cost
            FROM gold_dim_vehicle d
            LEFT JOIN complaint_agg c USING (vehicle_key)
            LEFT JOIN recall_agg r USING (vehicle_key)
            LEFT JOIN investigation_agg i USING (vehicle_key)
            LEFT JOIN communication_agg m USING (vehicle_key)
            LEFT JOIN ncap_agg n USING (vehicle_key)
            LEFT JOIN fuel_agg f USING (vehicle_key)
        )
        SELECT *,
            CASE WHEN complaint_reports > 0
                 THEN CAST(severe_complaint_reports AS DOUBLE) / complaint_reports END
                AS severe_complaint_share,
            CAST(complaint_reports > 0 AS INT) + CAST(recall_campaigns > 0 AS INT)
                + CAST(investigations > 0 AS INT) + CAST(manufacturer_documents > 0 AS INT)
                + CAST(ncap_tested_variants > 0 AS INT) + CAST(epa_variants > 0 AS INT)
                AS evidence_source_count,
            CASE
                WHEN do_not_drive_campaigns > 0 OR park_outside_campaigns > 0 THEN 'CRITICAL'
                WHEN open_investigations > 0 THEN 'HIGH'
                WHEN complaint_reports >= 10 AND severe_complaint_reports >= 3 THEN 'HIGH'
                WHEN recall_campaigns > 0 OR complaint_reports >= 5 OR manufacturer_documents >= 10
                    THEN 'REVIEW'
                ELSE 'MONITOR'
            END AS review_priority,
            CASE
                WHEN do_not_drive_campaigns > 0 THEN 'At least one do-not-drive recall campaign'
                WHEN park_outside_campaigns > 0 THEN 'At least one park-outside recall campaign'
                WHEN open_investigations > 0 THEN 'At least one open NHTSA investigation'
                WHEN complaint_reports >= 10 AND severe_complaint_reports >= 3
                    THEN 'Minimum-volume complaint signal with multiple severe reports'
                WHEN recall_campaigns > 0 THEN 'Recall campaign evidence exists'
                WHEN complaint_reports >= 5 THEN 'Complaint reports meet review threshold'
                WHEN manufacturer_documents >= 10
                    THEN 'Manufacturer communication volume meets review threshold'
                ELSE 'No current rule crossed'
            END AS review_reason,
            CASE
                WHEN reference_exact_match_flag THEN 'NONE'
                WHEN do_not_drive_campaigns > 0 OR park_outside_campaigns > 0
                    OR open_investigations > 0 THEN 'P0'
                WHEN source_system_count >= 2 OR complaint_reports >= 10
                    OR severe_complaint_reports >= 3 OR recall_campaigns > 0
                    OR manufacturer_documents >= 10 THEN 'P1'
                ELSE 'P2'
            END AS alias_priority,
            CASE
                WHEN reference_exact_match_flag
                    THEN 'Exact EPA or NCAP reference match; no alias review required'
                WHEN do_not_drive_campaigns > 0 OR park_outside_campaigns > 0
                    OR open_investigations > 0
                    THEN 'Unresolved identity with do-not-drive, park-outside, or open-investigation evidence'
                WHEN source_system_count >= 2 OR complaint_reports >= 10
                    OR severe_complaint_reports >= 3 OR recall_campaigns > 0
                    OR manufacturer_documents >= 10
                    THEN 'Unresolved identity with multi-source or high-signal evidence'
                ELSE 'Unresolved low-signal identity; aggregate backlog only'
            END AS alias_reason
        FROM mart
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_vehicle_review_queue AS
        SELECT vehicle_key, vehicle_label, review_priority, review_reason,
            complaint_reports, severe_complaint_reports, recall_campaigns,
            do_not_drive_campaigns, park_outside_campaigns, open_investigations,
            manufacturer_documents, ncap_tested_variants, epa_variants,
            reference_exact_match_flag, reference_year_eligible, reference_match_status,
            rule_version, threshold_validation_status
        FROM gold_agg_vehicle_evidence
        WHERE review_priority != 'MONITOR'
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_alias_work_queue AS
        SELECT vehicle_key, vehicle_label, alias_priority, alias_reason,
            source_system_count, complaint_reports, severe_complaint_reports,
            recall_campaigns, do_not_drive_campaigns, park_outside_campaigns,
            open_investigations, manufacturer_documents,
            rule_version, threshold_validation_status,
            'UNREVIEWED' AS review_status
        FROM gold_agg_vehicle_evidence
        WHERE reference_match_status = 'UNRESOLVED' AND alias_priority IN ('P0', 'P1')
        """
    )

    duplicate_vehicle_keys = int(
        con.execute(
            "SELECT count(*) FROM (SELECT vehicle_key, count(*) AS n FROM gold_dim_vehicle "
            "GROUP BY vehicle_key HAVING n > 1)"
        ).fetchone()[0]
    )
    quality_rows = [
        ("DIM_VEHICLE_UNIQUENESS", duplicate_vehicle_keys, 0, duplicate_vehicle_keys == 0),
    ]

    fact_checks = [
        "gold_fact_complaint",
        "gold_fact_recall",
        "gold_fact_investigation",
        "gold_fact_manufacturer_communication",
        "gold_fact_ncap_variant",
        "gold_fact_fuel_economy_variant",
    ]
    for table_name in fact_checks:
        orphan_count = int(
            con.execute(
                f"SELECT count(*) FROM (SELECT DISTINCT vehicle_key FROM {table_name} "
                f"WHERE vehicle_key IS NOT NULL) k "
                f"ANTI JOIN gold_dim_vehicle d USING (vehicle_key)"
            ).fetchone()[0]
        )
        quality_rows.append((f"{table_name.upper()}_ORPHAN_KEYS", orphan_count, 0, orphan_count == 0))

    alias_queue_p2_count = int(
        con.execute(
            "SELECT count(*) FROM gold_alias_work_queue WHERE alias_priority = 'P2'"
        ).fetchone()[0]
    )
    quality_rows.append(
        ("ALIAS_QUEUE_CONTAINS_ONLY_P0_P1", alias_queue_p2_count, 0, alias_queue_p2_count == 0)
    )

    con.execute(
        "CREATE OR REPLACE TABLE gold_data_quality_checks AS "
        "SELECT * FROM (VALUES "
        + ",".join(
            f"('{name}', {actual}, {expected}, {passed})"
            for name, actual, expected, passed in quality_rows
        )
        + ") AS t(check_name, actual_value, expected_value, passed)"
    )
    con.execute(
        "ALTER TABLE gold_data_quality_checks ADD COLUMN IF NOT EXISTS checked_at TIMESTAMP DEFAULT now()"
    )

    failed_checks = [name for name, _, _, passed in quality_rows if not passed]
    priority_counts = dict(
        con.execute(
            "SELECT review_priority, count(*) FROM gold_agg_vehicle_evidence "
            "GROUP BY review_priority ORDER BY review_priority"
        ).fetchall()
    )
    con.close()

    print(f"gold_dim_vehicle keys: {sum(priority_counts.values())}")
    print(f"review priority: {priority_counts}")
    if failed_checks:
        raise ValueError(f"Gold reconciliation failed: {failed_checks}. Inspect gold_data_quality_checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())