#!/usr/bin/env python3
"""Silver: conform and deduplicate the public records, build deterministic vehicle
keys, classify official text into explainable topics, and resolve identities against
the EPA and NCAP reference sources. No fuzzy match is silently accepted."""

from __future__ import annotations

import argparse
import pathlib
import sys

import duckdb

MIN_MODEL_YEAR = 1900
MAX_MODEL_YEAR = 2027
REFERENCE_ERA_START_YEAR = 1984
RULE_VERSION = "portfolio_v1"
THRESHOLD_VALIDATION_STATUS = "unvalidated"

NORMALIZED = (
    "trim(regexp_replace(regexp_replace(upper(trim(coalesce({col}, ''))), "
    "'[^A-Z0-9]+', ' ', 'g'), '\\s+', ' ', 'g'))"
)
VEHICLE_KEY = (
    "CASE WHEN length({make}) > 0 AND length({model}) > 0 "
    "AND {year} BETWEEN {min_year} AND {max_year} "
    "THEN sha256(concat_ws('||', {make}, {model}, CAST({year} AS VARCHAR))) END"
)
EVENT_DATE = "strptime({col}, '%Y%m%d')"
BOOLEAN_FLAG = "lower(trim(coalesce({col}, ''))) IN ('y', 'yes', 'true', '1')"

TOPIC_CASE = (
    "CASE "
    "WHEN regexp_matches({text}, 'FIRE|FLAME|THERMAL|BURN') THEN 'FIRE_OR_THERMAL' "
    "WHEN regexp_matches({text}, 'BRAKE|ABS') THEN 'BRAKES' "
    "WHEN regexp_matches({text}, 'AIR.?BAG|AIRBAG|SRS') THEN 'AIR_BAGS' "
    "WHEN regexp_matches({text}, 'STEER') THEN 'STEERING' "
    "WHEN regexp_matches({text}, 'ENGINE|POWER.?TRAIN|TRANSMISSION|PROPULSION') THEN 'POWERTRAIN' "
    "WHEN regexp_matches({text}, 'ELECTRIC|BATTERY|WIRING|SOFTWARE|PROGRAM|CONTROL MODULE') THEN 'ELECTRICAL_OR_SOFTWARE' "
    "WHEN regexp_matches({text}, 'TIRE|WHEEL') THEN 'TIRES_OR_WHEELS' "
    "WHEN regexp_matches({text}, 'VISIBILITY|WINDSHIELD|WIPER|CAMERA') THEN 'VISIBILITY' "
    "WHEN regexp_matches({text}, 'SEAT.?BELT|RESTRAINT') THEN 'OCCUPANT_RESTRAINT' "
    "ELSE 'OTHER' END"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to the DuckDB lakehouse file")
    return parser.parse_args(argv)


def identity_columns(make_col: str, model_col: str, year_col: str) -> str:
    make = NORMALIZED.format(col=make_col)
    model = NORMALIZED.format(col=model_col)
    return (
        f"{make} AS normalized_make, {model} AS normalized_model, "
        f"try_cast({year_col} AS INT) AS model_year_int, "
        + VEHICLE_KEY.format(
            make="normalized_make",
            model="normalized_model",
            year="model_year_int",
            min_year=MIN_MODEL_YEAR,
            max_year=MAX_MODEL_YEAR,
        )
        + " AS vehicle_key"
    )


def topic_expression(*columns: str) -> str:
    text = "upper(concat_ws(' ', " + ", ".join(f"coalesce({col}, '')" for col in columns) + "))"
    return TOPIC_CASE.format(text=text)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    con = duckdb.connect(args.db)

    con.execute(
        f"""
        CREATE OR REPLACE TABLE silver_complaints AS
        SELECT *, {identity_columns('source_make', 'source_model', 'model_year')},
            {EVENT_DATE.format(col='incident_date')} AS incident_date_parsed,
            {EVENT_DATE.format(col='complaint_received_date')} AS received_date,
            {EVENT_DATE.format(col='record_created_date')} AS record_created_date_parsed,
            coalesce(try_cast(injury_count AS INT), 0) AS injury_count_int,
            coalesce(try_cast(death_count AS INT), 0) AS death_count_int,
            try_cast(mileage_at_failure AS BIGINT) AS mileage_at_failure_int,
            {BOOLEAN_FLAG.format(col='crash_flag')} AS crash_reported_flag,
            {BOOLEAN_FLAG.format(col='fire_flag')} AS fire_reported_flag,
            {BOOLEAN_FLAG.format(col='medical_attention_flag')} AS medical_attention_reported_flag,
            {BOOLEAN_FLAG.format(col='vehicle_towed_flag')} AS vehicle_towed_reported_flag,
            (crash_reported_flag OR fire_reported_flag OR injury_count_int > 0 OR death_count_int > 0)
                AS severe_report_flag,
            {topic_expression('component_name')} AS evidence_topic
        FROM bronze_complaints
        WHERE product_type = 'V'
        QUALIFY row_number() OVER (PARTITION BY complaint_record_id) = 1
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE TABLE silver_recalls AS
        SELECT *, {identity_columns('source_make', 'source_model', 'model_year')},
            {EVENT_DATE.format(col='report_received_date')} AS report_received_date_parsed,
            try_cast(potential_units_affected AS BIGINT) AS potential_units_affected_int,
            {BOOLEAN_FLAG.format(col='do_not_drive_flag')} AS do_not_drive,
            {BOOLEAN_FLAG.format(col='park_outside_flag')} AS park_outside,
            {topic_expression('component_name', 'defect_summary', 'consequence_summary')} AS evidence_topic
        FROM bronze_recalls
        WHERE product_type = 'V'
        QUALIFY row_number() OVER (PARTITION BY recall_record_id) = 1
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE TABLE silver_investigations AS
        SELECT *, {identity_columns('source_make', 'source_model', 'model_year')},
            {EVENT_DATE.format(col='opened_date')} AS opened_date_parsed,
            {EVENT_DATE.format(col='closed_date')} AS closed_date_parsed,
            closed_date_parsed IS NULL AS open_investigation_flag,
            {topic_expression('component_name', 'subject', 'summary')} AS evidence_topic,
            sha256(concat_ws('||', coalesce(investigation_number, ''), coalesce(vehicle_key, ''),
                coalesce(component_name, ''))) AS investigation_record_key
        FROM bronze_investigations
        QUALIFY row_number() OVER (PARTITION BY investigation_record_key) = 1
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE TABLE silver_manufacturer_communications AS
        SELECT * FROM (
            SELECT DISTINCT *, {identity_columns('source_make', 'source_model', 'model_year')},
                {EVENT_DATE.format(col='date_added')} AS date_added_parsed,
                {EVENT_DATE.format(col='manufacturer_communication_date')} AS communication_date,
                {topic_expression('nhtsa_components', 'manufacturer_system', 'manufacturer_subsystem', 'summary')}
                    AS evidence_topic,
                sha256(concat_ws('||', coalesce(nhtsa_communication_id, ''), coalesce(document_id, ''),
                    coalesce(vehicle_key, ''), coalesce(nhtsa_components, ''))) AS communication_record_key
            FROM bronze_manufacturer_communications
        )
        QUALIFY row_number() OVER (PARTITION BY communication_record_key) = 1
        """
    )

    star_columns = [
        "overall_stars",
        "frnt_driv_stars",
        "frnt_pass_stars",
        "overall_frnt_stars",
        "side_driv_stars",
        "side_pass_stars",
        "side_barrier_star",
        "side_pole_stars",
        "overall_side_stars",
        "rollover_stars",
    ]
    star_casts = ", ".join(
        f"try_cast({col} AS INT) AS {col}_int" for col in star_columns
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE silver_ncap_ratings AS
        SELECT DISTINCT *, {identity_columns('make', 'model', 'model_yr')},
            {star_casts},
            try_cast(rollover_possibility AS DOUBLE) AS rollover_possibility_decimal,
            try_cast(static_stabi_factor AS DOUBLE) AS static_stability_factor_decimal,
            sha256(concat_ws('||', vehicle_key, body_style, vehicle_type, drive_train,
                num_of_seating)) AS ncap_variant_key
        FROM bronze_ncap_ratings
        """
    )

    integer_columns = [
        "id",
        "cylinders",
        "city08",
        "highway08",
        "comb08",
        "fuelCost08",
        "ghgScore",
        "range",
        "youSaveSpend",
    ]
    decimal_columns = ["displ", "cityE", "highwayE", "combE", "co2TailpipeGpm", "charge240"]
    integer_casts = ", ".join(f"try_cast({col} AS INT) AS {col}_int" for col in integer_columns)
    decimal_casts = ", ".join(f"try_cast({col} AS DOUBLE) AS {col}_decimal" for col in decimal_columns)
    con.execute(
        f"""
        CREATE OR REPLACE TABLE silver_fuel_economy AS
        SELECT *, {identity_columns('make', 'model', 'year')},
            {integer_casts}, {decimal_casts}
        FROM bronze_fuel_economy
        QUALIFY row_number() OVER (PARTITION BY id) = 1
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE silver_state_registrations AS
        SELECT *, try_cast(year AS INT) AS year_int,
            trim(state) AS state_name,
            upper(trim(category)) AS category_normalized,
            upper(trim(registration_type)) AS registration_type_normalized,
            try_cast(vehicles AS BIGINT) AS registered_vehicles
        FROM bronze_state_registrations
        QUALIFY row_number() OVER (PARTITION BY year, state, category, registration_type) = 1
        """
    )

    identity_sources = [
        ("silver_complaints", "NHTSA_COMPLAINT"),
        ("silver_recalls", "NHTSA_RECALL"),
        ("silver_investigations", "NHTSA_INVESTIGATION"),
        ("silver_manufacturer_communications", "NHTSA_MANUFACTURER_COMMUNICATION"),
        ("silver_ncap_ratings", "NHTSA_NCAP"),
        ("silver_fuel_economy", "EPA_FUEL_ECONOMY"),
    ]
    identity_union = "\nUNION\n".join(
        f"SELECT '{source}' AS source_system, normalized_make, normalized_model, "
        f"model_year_int, vehicle_key FROM {table} WHERE vehicle_key IS NOT NULL"
        for table, source in identity_sources
    )

    con.execute(
        f"""
        CREATE OR REPLACE TABLE silver_vehicle_identity_bridge AS
        WITH identities AS (
            SELECT DISTINCT source_system, normalized_make, normalized_model, model_year_int, vehicle_key
            FROM ({identity_union})
        ),
        reference_keys AS (
            SELECT DISTINCT vehicle_key FROM identities
            WHERE source_system IN ('NHTSA_NCAP', 'EPA_FUEL_ECONOMY')
        )
        SELECT identities.*,
            reference_keys.vehicle_key IS NOT NULL AS reference_exact_match_flag,
            vehicle_key AS canonical_vehicle_key,
            model_year_int >= {REFERENCE_ERA_START_YEAR} AS reference_year_eligible,
            CASE WHEN reference_keys.vehicle_key IS NOT NULL THEN 'MATCHED' ELSE 'UNRESOLVED' END
                AS reference_match_status,
            CASE WHEN reference_keys.vehicle_key IS NOT NULL THEN 'EXACT_NORMALIZED_MAKE_MODEL_YEAR'
                 ELSE 'SOURCE_IDENTITY_UNRESOLVED_TO_REFERENCE' END AS match_method,
            CASE WHEN reference_keys.vehicle_key IS NOT NULL THEN 'HIGH' ELSE 'UNRESOLVED' END
                AS match_confidence,
            '{RULE_VERSION}' AS rule_version,
            '{THRESHOLD_VALIDATION_STATUS}' AS threshold_validation_status
        FROM identities
        LEFT JOIN reference_keys USING (vehicle_key)
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE TABLE silver_vehicle_alias_review_queue AS
        SELECT vehicle_key, normalized_make, normalized_model, model_year_int,
            count(DISTINCT source_system) AS source_system_count,
            list_sort(list(DISTINCT source_system)) AS source_systems,
            bool_or(reference_year_eligible) AS reference_year_eligible,
            'UNREVIEWED' AS review_status,
            'No exact EPA or NCAP make/model/year reference match' AS review_reason
        FROM silver_vehicle_identity_bridge
        WHERE NOT reference_exact_match_flag
        GROUP BY vehicle_key, normalized_make, normalized_model, model_year_int
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE TABLE audit_silver_entity_match_quality AS
        SELECT source_system,
            count(DISTINCT vehicle_key) AS distinct_vehicle_keys,
            count(DISTINCT CASE WHEN reference_exact_match_flag THEN vehicle_key END)
                AS reference_exact_match_keys,
            count(DISTINCT CASE WHEN reference_year_eligible THEN vehicle_key END)
                AS era_eligible_vehicle_keys,
            count(DISTINCT CASE WHEN reference_year_eligible AND reference_exact_match_flag THEN vehicle_key END)
                AS era_eligible_reference_exact_match_keys,
            CAST(count(DISTINCT CASE WHEN reference_exact_match_flag THEN vehicle_key END) AS DOUBLE)
                / count(DISTINCT vehicle_key) AS reference_exact_match_rate,
            CAST(count(DISTINCT CASE WHEN reference_year_eligible AND reference_exact_match_flag THEN vehicle_key END) AS DOUBLE)
                / NULLIF(count(DISTINCT CASE WHEN reference_year_eligible THEN vehicle_key END), 0)
                AS era_eligible_reference_exact_match_rate
        FROM silver_vehicle_identity_bridge
        GROUP BY source_system
        ORDER BY source_system
        """
    )

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())