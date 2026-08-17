# Fabric notebook source

# %% [markdown]
# # 02 - Conform Silver and Resolve Vehicle Identities
# Type and deduplicate the public records, create a deterministic vehicle key,
# classify official text into explainable topics, and expose unresolved identities.
# No fuzzy match is silently accepted.

# %%
from functools import reduce

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql import types as T


def normalized_text(column_name: str):
    value = F.upper(F.trim(F.coalesce(F.col(column_name), F.lit(""))))
    value = F.regexp_replace(value, r"[^A-Z0-9]+", " ")
    return F.trim(F.regexp_replace(value, r"\s+", " "))


def yyyymmdd(column_name: str):
    return F.to_date(F.col(column_name), "yyyyMMdd")


def boolean_flag(column_name: str):
    return F.lower(F.trim(F.coalesce(F.col(column_name), F.lit("")))).isin(
        "y", "yes", "true", "1"
    )


def add_vehicle_identity(
    frame: DataFrame,
    make_column: str,
    model_column: str,
    year_column: str,
) -> DataFrame:
    conformed = (
        frame.withColumn("normalized_make", normalized_text(make_column))
        .withColumn("normalized_model", normalized_text(model_column))
        .withColumn("model_year_int", F.col(year_column).cast("int"))
    )
    valid_identity = (
        (F.length("normalized_make") > 0)
        & (F.length("normalized_model") > 0)
        & F.col("model_year_int").between(1900, 2100)
    )
    return conformed.withColumn(
        "vehicle_key",
        F.when(
            valid_identity,
            F.sha2(
                F.concat_ws(
                    "||", "normalized_make", "normalized_model", F.col("model_year_int").cast("string")
                ),
                256,
            ),
        ),
    )


def evidence_topic(*column_names: str):
    text = F.upper(F.concat_ws(" ", *[F.coalesce(F.col(name), F.lit("")) for name in column_names]))
    return (
        F.when(text.rlike(r"FIRE|FLAME|THERMAL|BURN"), "FIRE_OR_THERMAL")
        .when(text.rlike(r"BRAKE|ABS"), "BRAKES")
        .when(text.rlike(r"AIR.?BAG|AIRBAG|SRS"), "AIR_BAGS")
        .when(text.rlike(r"STEER"), "STEERING")
        .when(text.rlike(r"ENGINE|POWER.?TRAIN|TRANSMISSION|PROPULSION"), "POWERTRAIN")
        .when(text.rlike(r"ELECTRIC|BATTERY|WIRING|SOFTWARE|PROGRAM|CONTROL MODULE"), "ELECTRICAL_OR_SOFTWARE")
        .when(text.rlike(r"TIRE|WHEEL"), "TIRES_OR_WHEELS")
        .when(text.rlike(r"VISIBILITY|WINDSHIELD|WIPER|CAMERA"), "VISIBILITY")
        .when(text.rlike(r"SEAT.?BELT|RESTRAINT"), "OCCUPANT_RESTRAINT")
        .otherwise("OTHER")
    )


def write_silver(frame: DataFrame, table_name: str):
    (
        frame.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(table_name)
    )

# %% [markdown]
# ## Source-specific conformance

# %%
complaints = add_vehicle_identity(
    spark.table("bronze_complaints").filter(F.col("product_type") == "V"),
    "source_make",
    "source_model",
    "model_year",
)
complaints = (
    complaints.withColumn("incident_date_parsed", yyyymmdd("incident_date"))
    .withColumn("received_date", yyyymmdd("complaint_received_date"))
    .withColumn("record_created_date_parsed", yyyymmdd("record_created_date"))
    .withColumn("injury_count_int", F.coalesce(F.col("injury_count").cast("int"), F.lit(0)))
    .withColumn("death_count_int", F.coalesce(F.col("death_count").cast("int"), F.lit(0)))
    .withColumn("mileage_at_failure_int", F.col("mileage_at_failure").cast("long"))
    .withColumn("crash_reported_flag", boolean_flag("crash_flag"))
    .withColumn("fire_reported_flag", boolean_flag("fire_flag"))
    .withColumn("medical_attention_reported_flag", boolean_flag("medical_attention_flag"))
    .withColumn("vehicle_towed_reported_flag", boolean_flag("vehicle_towed_flag"))
    .withColumn(
        "severe_report_flag",
        F.col("crash_reported_flag")
        | F.col("fire_reported_flag")
        | (F.col("injury_count_int") > 0)
        | (F.col("death_count_int") > 0),
    )
    .withColumn("evidence_topic", evidence_topic("component_name"))
    .dropDuplicates(["complaint_record_id"])
)
write_silver(complaints, "silver_complaints")

# %%
recalls = add_vehicle_identity(
    spark.table("bronze_recalls").filter(F.col("product_type") == "V"),
    "source_make",
    "source_model",
    "model_year",
)
recalls = (
    recalls.withColumn("report_received_date_parsed", yyyymmdd("report_received_date"))
    .withColumn("potential_units_affected_int", F.col("potential_units_affected").cast("long"))
    .withColumn("do_not_drive", boolean_flag("do_not_drive_flag"))
    .withColumn("park_outside", boolean_flag("park_outside_flag"))
    .withColumn(
        "evidence_topic",
        evidence_topic("component_name", "defect_summary", "consequence_summary"),
    )
    .dropDuplicates(["recall_record_id"])
)
write_silver(recalls, "silver_recalls")

# %%
investigations = add_vehicle_identity(
    spark.table("bronze_investigations"), "source_make", "source_model", "model_year"
)
investigations = (
    investigations.withColumn("opened_date_parsed", yyyymmdd("opened_date"))
    .withColumn("closed_date_parsed", yyyymmdd("closed_date"))
    .withColumn("open_investigation_flag", F.col("closed_date_parsed").isNull())
    .withColumn("evidence_topic", evidence_topic("component_name", "subject", "summary"))
    .withColumn(
        "investigation_record_key",
        F.sha2(
            F.concat_ws(
                "||",
                F.coalesce(F.col("investigation_number"), F.lit("")),
                F.coalesce(F.col("vehicle_key"), F.lit("")),
                F.coalesce(F.col("component_name"), F.lit("")),
            ),
            256,
        ),
    )
    .dropDuplicates(["investigation_record_key"])
)
write_silver(investigations, "silver_investigations")

# %%
communications = add_vehicle_identity(
    spark.table("bronze_manufacturer_communications"),
    "source_make",
    "source_model",
    "model_year",
)
communications = (
    communications.withColumn("date_added_parsed", yyyymmdd("date_added"))
    .withColumn("communication_date", yyyymmdd("manufacturer_communication_date"))
    .withColumn(
        "evidence_topic",
        evidence_topic("nhtsa_components", "manufacturer_system", "manufacturer_subsystem", "summary"),
    )
    .withColumn(
        "communication_record_key",
        F.sha2(
            F.concat_ws(
                "||",
                F.coalesce(F.col("nhtsa_communication_id"), F.lit("")),
                F.coalesce(F.col("document_id"), F.lit("")),
                F.coalesce(F.col("vehicle_key"), F.lit("")),
                F.coalesce(F.col("nhtsa_components"), F.lit("")),
            ),
            256,
        ),
    )
    .dropDuplicates()
    .dropDuplicates(["communication_record_key"])
)
write_silver(communications, "silver_manufacturer_communications")

# %%
ncap = add_vehicle_identity(spark.table("bronze_ncap_ratings"), "make", "model", "model_yr")
for column_name in [
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
]:
    ncap = ncap.withColumn(f"{column_name}_int", F.col(column_name).cast("int"))

ncap = (
    ncap.withColumn("rollover_possibility_decimal", F.col("rollover_possibility").cast("double"))
    .withColumn("static_stability_factor_decimal", F.col("static_stabi_factor").cast("double"))
    .withColumn(
        "ncap_variant_key",
        F.sha2(
            F.concat_ws(
                "||", "vehicle_key", "body_style", "vehicle_type", "drive_train", "num_of_seating"
            ),
            256,
        ),
    )
    .dropDuplicates()
)
write_silver(ncap, "silver_ncap_ratings")

# %%
fuel_economy = add_vehicle_identity(spark.table("bronze_fuel_economy"), "make", "model", "year")
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
for column_name in integer_columns:
    fuel_economy = fuel_economy.withColumn(f"{column_name}_int", F.col(column_name).cast("int"))
for column_name in decimal_columns:
    fuel_economy = fuel_economy.withColumn(f"{column_name}_decimal", F.col(column_name).cast("double"))
fuel_economy = fuel_economy.dropDuplicates(["id"])
write_silver(fuel_economy, "silver_fuel_economy")

# %%
state_registrations = (
    spark.table("bronze_state_registrations")
    .withColumn("year_int", F.col("year").cast("int"))
    .withColumn("state_name", F.initcap(F.trim("state")))
    .withColumn("category_normalized", F.upper(F.trim("category")))
    .withColumn("registration_type_normalized", F.upper(F.trim("registration_type")))
    .withColumn("registered_vehicles", F.col("vehicles").cast("long"))
    .dropDuplicates(["year", "state", "category", "registration_type"])
)
write_silver(state_registrations, "silver_state_registrations")

# %% [markdown]
# ## Deterministic entity bridge
# EPA and NCAP are reference sources. Exact normalized make/model/year matches are
# marked high confidence. Everything else remains usable at its source identity but
# is explicitly queued for alias review rather than silently fuzzy-matched.

# %%
identity_inputs = [
    (complaints, "NHTSA_COMPLAINT"),
    (recalls, "NHTSA_RECALL"),
    (investigations, "NHTSA_INVESTIGATION"),
    (communications, "NHTSA_MANUFACTURER_COMMUNICATION"),
    (ncap, "NHTSA_NCAP"),
    (fuel_economy, "EPA_FUEL_ECONOMY"),
]

identity_frames = []
for frame, source_system in identity_inputs:
    identity_frames.append(
        frame.select(
            F.lit(source_system).alias("source_system"),
            "normalized_make",
            "normalized_model",
            "model_year_int",
            "vehicle_key",
        ).filter(F.col("vehicle_key").isNotNull())
    )

vehicle_identities = reduce(DataFrame.unionByName, identity_frames).dropDuplicates()
reference_keys = (
    vehicle_identities.filter(F.col("source_system").isin("NHTSA_NCAP", "EPA_FUEL_ECONOMY"))
    .select("vehicle_key")
    .distinct()
    .withColumn("reference_exact_match_flag", F.lit(True))
)

vehicle_bridge = (
    vehicle_identities.join(reference_keys, "vehicle_key", "left")
    .fillna({"reference_exact_match_flag": False})
    .withColumn("canonical_vehicle_key", F.col("vehicle_key"))
    .withColumn(
        "match_method",
        F.when(F.col("reference_exact_match_flag"), "EXACT_NORMALIZED_MAKE_MODEL_YEAR").otherwise(
            "SOURCE_IDENTITY_UNRESOLVED_TO_REFERENCE"
        ),
    )
    .withColumn(
        "match_confidence",
        F.when(F.col("reference_exact_match_flag"), "HIGH").otherwise("UNRESOLVED"),
    )
)
write_silver(vehicle_bridge, "silver_vehicle_identity_bridge")

alias_review_queue = (
    vehicle_bridge.filter(~F.col("reference_exact_match_flag"))
    .groupBy("vehicle_key", "normalized_make", "normalized_model", "model_year_int")
    .agg(
        F.countDistinct("source_system").alias("source_system_count"),
        F.sort_array(F.collect_set("source_system")).alias("source_systems"),
    )
    .withColumn("review_status", F.lit("UNREVIEWED"))
    .withColumn("review_reason", F.lit("No exact EPA or NCAP make/model/year reference match"))
)
write_silver(alias_review_queue, "silver_vehicle_alias_review_queue")

match_quality = (
    vehicle_bridge.groupBy("source_system")
    .agg(
        F.countDistinct("vehicle_key").alias("distinct_vehicle_keys"),
        F.countDistinct(F.when(F.col("reference_exact_match_flag"), F.col("vehicle_key"))).alias(
            "reference_exact_match_keys"
        ),
    )
    .withColumn(
        "reference_exact_match_rate",
        F.col("reference_exact_match_keys") / F.col("distinct_vehicle_keys"),
    )
)
write_silver(match_quality, "audit_silver_entity_match_quality")

display(match_quality.orderBy("source_system"))
