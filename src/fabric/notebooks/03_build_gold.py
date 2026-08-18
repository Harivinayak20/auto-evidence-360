# Fabric notebook source

# %% [markdown]
# # 03 - Build Gold Decision Model
# Publish a star schema, an aggregate evidence mart, a transparent review queue,
# and reconciliation checks. Review priority is a rule, not a safety score.

# %%
from functools import reduce

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql import types as T


def write_gold(frame: DataFrame, table_name: str):
    (
        frame.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(table_name)
    )


complaints = spark.table("silver_complaints")
recalls = spark.table("silver_recalls")
investigations = spark.table("silver_investigations")
communications = spark.table("silver_manufacturer_communications")
ncap = spark.table("silver_ncap_ratings")
fuel = spark.table("silver_fuel_economy")
registrations = spark.table("silver_state_registrations")
bridge = spark.table("silver_vehicle_identity_bridge")

# %% [markdown]
# ## Conformed dimensions

# %%
dim_vehicle = (
    bridge.groupBy("canonical_vehicle_key")
    .agg(
        F.first("normalized_make", ignorenulls=True).alias("make"),
        F.first("normalized_model", ignorenulls=True).alias("model"),
        F.first("model_year_int", ignorenulls=True).alias("model_year"),
        F.countDistinct("source_system").alias("source_system_count"),
        F.max(F.col("reference_exact_match_flag").cast("int")).cast("boolean").alias(
            "reference_exact_match_flag"
        ),
        F.max(F.col("reference_year_eligible").cast("int")).cast("boolean").alias(
            "reference_year_eligible"
        ),
        F.first("reference_match_status", ignorenulls=True).alias("reference_match_status"),
        F.first("rule_version", ignorenulls=True).alias("rule_version"),
        F.first("threshold_validation_status", ignorenulls=True).alias(
            "threshold_validation_status"
        ),
    )
    .withColumnRenamed("canonical_vehicle_key", "vehicle_key")
    .withColumn("vehicle_label", F.concat_ws(" ", "model_year", "make", "model"))
)
write_gold(dim_vehicle, "gold_dim_vehicle")

date_values = [
    complaints.select(F.col("incident_date_parsed").alias("date_value")),
    complaints.select(F.col("received_date").alias("date_value")),
    recalls.select(F.col("report_received_date_parsed").alias("date_value")),
    investigations.select(F.col("opened_date_parsed").alias("date_value")),
    communications.select(F.col("communication_date").alias("date_value")),
]
date_bounds = reduce(DataFrame.unionByName, date_values).filter("date_value is not null").agg(
    F.min("date_value").alias("min_date"), F.max("date_value").alias("max_date")
).first()
dim_date = (
    spark.range(1)
    .select(
        F.explode(F.sequence(F.lit(date_bounds["min_date"]), F.lit(date_bounds["max_date"]))).alias(
            "date"
        )
    )
    .withColumn("date_key", F.date_format("date", "yyyyMMdd").cast("int"))
    .withColumn("year", F.year("date"))
    .withColumn("quarter", F.quarter("date"))
    .withColumn("month_number", F.month("date"))
    .withColumn("month_name", F.date_format("date", "MMMM"))
    .withColumn("year_month", F.date_format("date", "yyyy-MM"))
    .withColumn("week_of_year", F.weekofyear("date"))
)
write_gold(dim_date, "gold_dim_date")

topic_names = [
    "FIRE_OR_THERMAL",
    "BRAKES",
    "AIR_BAGS",
    "STEERING",
    "POWERTRAIN",
    "ELECTRICAL_OR_SOFTWARE",
    "TIRES_OR_WHEELS",
    "VISIBILITY",
    "OCCUPANT_RESTRAINT",
    "OTHER",
]
dim_topic = spark.createDataFrame([(name, name.replace("_", " ").title()) for name in topic_names], [
    "topic_key",
    "topic_label",
])
write_gold(dim_topic, "gold_dim_evidence_topic")

# %% [markdown]
# ## Facts at explicit grains

# %%
fact_complaint = complaints.select(
    "complaint_record_id",
    "complaint_id",
    "vehicle_key",
    F.date_format("incident_date_parsed", "yyyyMMdd").cast("int").alias("incident_date_key"),
    F.date_format("received_date", "yyyyMMdd").cast("int").alias("received_date_key"),
    "component_name",
    "evidence_topic",
    "crash_reported_flag",
    "fire_reported_flag",
    "severe_report_flag",
    "injury_count_int",
    "death_count_int",
    "mileage_at_failure_int",
    "incident_state",
    "_source_id",
    "_batch_id",
)
write_gold(fact_complaint, "gold_fact_complaint")

fact_recall = recalls.select(
    "recall_record_id",
    "campaign_number",
    "vehicle_key",
    F.date_format("report_received_date_parsed", "yyyyMMdd").cast("int").alias(
        "report_received_date_key"
    ),
    "component_name",
    "evidence_topic",
    "potential_units_affected_int",
    "do_not_drive",
    "park_outside",
    "filing_manufacturer",
    "defect_summary",
    "consequence_summary",
    "corrective_action",
    "_source_id",
    "_batch_id",
)
write_gold(fact_recall, "gold_fact_recall")

fact_investigation = investigations.select(
    "investigation_record_key",
    "investigation_number",
    "vehicle_key",
    F.date_format("opened_date_parsed", "yyyyMMdd").cast("int").alias("opened_date_key"),
    F.date_format("closed_date_parsed", "yyyyMMdd").cast("int").alias("closed_date_key"),
    "open_investigation_flag",
    "component_name",
    "evidence_topic",
    "subject",
    "summary",
    "campaign_number",
    "_source_id",
    "_batch_id",
)
write_gold(fact_investigation, "gold_fact_investigation")

fact_communication = communications.select(
    "communication_record_key",
    "nhtsa_communication_id",
    "document_id",
    "vehicle_key",
    F.date_format("communication_date", "yyyyMMdd").cast("int").alias("communication_date_key"),
    "communication_type",
    "nhtsa_components",
    "evidence_topic",
    "summary",
    "_source_id",
    "_batch_id",
)
write_gold(fact_communication, "gold_fact_manufacturer_communication")

fact_ncap = ncap.select(
    "ncap_variant_key",
    "vehicle_key",
    "body_style",
    "vehicle_type",
    "drive_train",
    "num_of_seating",
    F.col("overall_stars_int").alias("overall_stars"),
    F.col("overall_frnt_stars_int").alias("overall_front_stars"),
    F.col("overall_side_stars_int").alias("overall_side_stars"),
    F.col("rollover_stars_int").alias("rollover_stars"),
    "rollover_possibility_decimal",
    "static_stability_factor_decimal",
    "blind_spot_detection",
    "adaptive_cruise_control",
    "frnt_collision_warning",
    "lane_departure_warning",
    "_source_id",
    "_batch_id",
)
write_gold(fact_ncap, "gold_fact_ncap_variant")

fact_fuel = fuel.select(
    F.col("id_int").alias("epa_vehicle_id"),
    "vehicle_key",
    F.col("VClass").alias("vehicle_class"),
    F.col("fuelType").alias("fuel_type"),
    "drive",
    "trany",
    F.col("cylinders_int").alias("cylinders"),
    F.col("displ_decimal").alias("engine_displacement_liters"),
    F.col("city08_int").alias("city_mpg"),
    F.col("highway08_int").alias("highway_mpg"),
    F.col("comb08_int").alias("combined_mpg"),
    F.col("fuelCost08_int").alias("annual_fuel_cost"),
    F.col("ghgScore_int").alias("ghg_score"),
    F.col("co2TailpipeGpm_decimal").alias("tailpipe_co2_grams_per_mile"),
    F.col("range_int").alias("range_miles"),
    "_source_id",
    "_batch_id",
)
write_gold(fact_fuel, "gold_fact_fuel_economy_variant")

fact_registration = registrations.select(
    F.col("year_int").alias("year"),
    "state_name",
    "category_normalized",
    "registration_type_normalized",
    "registered_vehicles",
    "_source_id",
    "_batch_id",
)
write_gold(fact_registration, "gold_fact_state_registration")

# %% [markdown]
# ## Vehicle evidence mart and transparent review queue

# %%
complaint_event = complaints.groupBy("vehicle_key", "complaint_id").agg(
    F.max(F.col("severe_report_flag").cast("int")).alias("severe_report_int"),
    F.max(F.col("crash_reported_flag").cast("int")).alias("crash_report_int"),
    F.max(F.col("fire_reported_flag").cast("int")).alias("fire_report_int"),
    F.max("injury_count_int").alias("injury_count"),
    F.max("death_count_int").alias("death_count"),
)
complaint_agg = complaint_event.groupBy("vehicle_key").agg(
    F.count("complaint_id").alias("complaint_reports"),
    F.sum("severe_report_int").alias("severe_complaint_reports"),
    F.sum("crash_report_int").alias("crash_reported_complaints"),
    F.sum("fire_report_int").alias("fire_reported_complaints"),
    F.sum("injury_count").alias("reported_injuries"),
    F.sum("death_count").alias("reported_deaths"),
)

recall_agg = recalls.groupBy("vehicle_key").agg(
    F.countDistinct("campaign_number").alias("recall_campaigns"),
    F.countDistinct(F.when(F.col("do_not_drive"), F.col("campaign_number"))).alias(
        "do_not_drive_campaigns"
    ),
    F.countDistinct(F.when(F.col("park_outside"), F.col("campaign_number"))).alias(
        "park_outside_campaigns"
    ),
)

investigation_agg = investigations.groupBy("vehicle_key").agg(
    F.countDistinct("investigation_number").alias("investigations"),
    F.countDistinct(F.when(F.col("open_investigation_flag"), F.col("investigation_number"))).alias(
        "open_investigations"
    ),
)

communication_agg = communications.groupBy("vehicle_key").agg(
    F.countDistinct("document_id").alias("manufacturer_documents")
)

ncap_agg = ncap.groupBy("vehicle_key").agg(
    F.countDistinct("ncap_variant_key").alias("ncap_tested_variants"),
    F.expr("percentile_approx(overall_stars_int, 0.5)").alias("median_overall_stars"),
)

fuel_agg = fuel.groupBy("vehicle_key").agg(
    F.countDistinct("id").alias("epa_variants"),
    F.expr("percentile_approx(comb08_int, 0.5)").alias("median_combined_mpg"),
    F.expr("percentile_approx(fuelCost08_int, 0.5)").alias("median_annual_fuel_cost"),
)

evidence_mart = dim_vehicle
for aggregate in [complaint_agg, recall_agg, investigation_agg, communication_agg, ncap_agg, fuel_agg]:
    evidence_mart = evidence_mart.join(aggregate, "vehicle_key", "left")

count_columns = [
    "complaint_reports",
    "severe_complaint_reports",
    "crash_reported_complaints",
    "fire_reported_complaints",
    "reported_injuries",
    "reported_deaths",
    "recall_campaigns",
    "do_not_drive_campaigns",
    "park_outside_campaigns",
    "investigations",
    "open_investigations",
    "manufacturer_documents",
    "ncap_tested_variants",
    "epa_variants",
]
evidence_mart = evidence_mart.fillna(0, subset=count_columns)
evidence_mart = (
    evidence_mart.withColumn(
        "severe_complaint_share",
        F.when(
            F.col("complaint_reports") > 0,
            F.col("severe_complaint_reports") / F.col("complaint_reports"),
        ),
    )
    .withColumn(
        "evidence_source_count",
        (F.col("complaint_reports") > 0).cast("int")
        + (F.col("recall_campaigns") > 0).cast("int")
        + (F.col("investigations") > 0).cast("int")
        + (F.col("manufacturer_documents") > 0).cast("int")
        + (F.col("ncap_tested_variants") > 0).cast("int")
        + (F.col("epa_variants") > 0).cast("int"),
    )
    .withColumn(
        "review_priority",
        F.when(
            (F.col("do_not_drive_campaigns") > 0) | (F.col("park_outside_campaigns") > 0),
            "CRITICAL",
        )
        .when(F.col("open_investigations") > 0, "HIGH")
        .when(
            (F.col("complaint_reports") >= 10) & (F.col("severe_complaint_reports") >= 3),
            "HIGH",
        )
        .when(
            (F.col("recall_campaigns") > 0)
            | (F.col("complaint_reports") >= 5)
            | (F.col("manufacturer_documents") >= 10),
            "REVIEW",
        )
        .otherwise("MONITOR"),
    )
    .withColumn(
        "review_reason",
        F.when(
            F.col("do_not_drive_campaigns") > 0,
            F.lit("At least one do-not-drive recall campaign"),
        )
        .when(
            F.col("park_outside_campaigns") > 0,
            F.lit("At least one park-outside recall campaign"),
        )
        .when(F.col("open_investigations") > 0, F.lit("At least one open NHTSA investigation"))
        .when(
            (F.col("complaint_reports") >= 10) & (F.col("severe_complaint_reports") >= 3),
            F.lit("Minimum-volume complaint signal with multiple severe reports"),
        )
        .when(F.col("recall_campaigns") > 0, F.lit("Recall campaign evidence exists"))
        .when(F.col("complaint_reports") >= 5, F.lit("Complaint reports meet review threshold"))
        .when(
            F.col("manufacturer_documents") >= 10,
            F.lit("Manufacturer communication volume meets review threshold"),
        )
        .otherwise(F.lit("No current rule crossed")),
    )
    .withColumn(
        "alias_priority",
        F.when(
            F.col("reference_exact_match_flag"),
            F.lit("NONE"),
        )
        .when(
            (F.col("do_not_drive_campaigns") > 0)
            | (F.col("park_outside_campaigns") > 0)
            | (F.col("open_investigations") > 0),
            F.lit("P0"),
        )
        .when(
            (F.col("source_system_count") >= 2)
            | (F.col("complaint_reports") >= 10)
            | (F.col("severe_complaint_reports") >= 3)
            | (F.col("recall_campaigns") > 0)
            | (F.col("manufacturer_documents") >= 10),
            F.lit("P1"),
        )
        .otherwise(F.lit("P2")),
    )
    .withColumn(
        "alias_reason",
        F.when(
            F.col("reference_exact_match_flag"),
            F.lit("Exact EPA or NCAP reference match; no alias review required"),
        )
        .when(
            (F.col("do_not_drive_campaigns") > 0)
            | (F.col("park_outside_campaigns") > 0)
            | (F.col("open_investigations") > 0),
            F.lit("Unresolved identity with do-not-drive, park-outside, or open-investigation evidence"),
        )
        .when(
            (F.col("source_system_count") >= 2)
            | (F.col("complaint_reports") >= 10)
            | (F.col("severe_complaint_reports") >= 3)
            | (F.col("recall_campaigns") > 0)
            | (F.col("manufacturer_documents") >= 10),
            F.lit("Unresolved identity with multi-source or high-signal evidence"),
        )
        .otherwise(F.lit("Unresolved low-signal identity; aggregate backlog only")),
    )
)
write_gold(evidence_mart, "gold_agg_vehicle_evidence")

review_queue = evidence_mart.filter(F.col("review_priority") != "MONITOR").select(
    "vehicle_key",
    "vehicle_label",
    "review_priority",
    "review_reason",
    "complaint_reports",
    "severe_complaint_reports",
    "recall_campaigns",
    "do_not_drive_campaigns",
    "park_outside_campaigns",
    "open_investigations",
    "manufacturer_documents",
    "ncap_tested_variants",
    "epa_variants",
    "reference_exact_match_flag",
    "reference_year_eligible",
    "reference_match_status",
    "rule_version",
    "threshold_validation_status",
)
write_gold(review_queue, "gold_vehicle_review_queue")

# %% [markdown]
# ## Alias work queue
# The complete unresolved backlog stays in Silver. Gold publishes only actionable
# P0 and P1 identities; P2 low-signal backlog appears as an aggregate count in the
# evidence mart, never as individual queue entries.

# %%
alias_work_queue = (
    evidence_mart.filter(
        (F.col("reference_match_status") == "UNRESOLVED")
        & F.col("alias_priority").isin("P0", "P1")
    )
    .select(
        "vehicle_key",
        "vehicle_label",
        "alias_priority",
        "alias_reason",
        "source_system_count",
        "complaint_reports",
        "severe_complaint_reports",
        "recall_campaigns",
        "do_not_drive_campaigns",
        "park_outside_campaigns",
        "open_investigations",
        "manufacturer_documents",
        "rule_version",
        "threshold_validation_status",
    )
    .withColumn("review_status", F.lit("UNREVIEWED"))
)
write_gold(alias_work_queue, "gold_alias_work_queue")

# %% [markdown]
# ## Reconciliation and referential-integrity checks

# %%
dimension_keys = dim_vehicle.select("vehicle_key").distinct()
fact_checks = [
    ("gold_fact_complaint", fact_complaint),
    ("gold_fact_recall", fact_recall),
    ("gold_fact_investigation", fact_investigation),
    ("gold_fact_manufacturer_communication", fact_communication),
    ("gold_fact_ncap_variant", fact_ncap),
    ("gold_fact_fuel_economy_variant", fact_fuel),
]

quality_rows = []
duplicate_vehicle_keys = dim_vehicle.groupBy("vehicle_key").count().filter("count > 1").count()
quality_rows.append(("DIM_VEHICLE_UNIQUENESS", duplicate_vehicle_keys, 0, duplicate_vehicle_keys == 0))

for table_name, frame in fact_checks:
    orphan_count = (
        frame.filter(F.col("vehicle_key").isNotNull())
        .select("vehicle_key")
        .distinct()
        .join(dimension_keys, "vehicle_key", "left_anti")
        .count()
    )
    quality_rows.append((f"{table_name.upper()}_ORPHAN_KEYS", orphan_count, 0, orphan_count == 0))

alias_queue_p2_count = alias_work_queue.filter(F.col("alias_priority") == "P2").count()
quality_rows.append(("ALIAS_QUEUE_CONTAINS_ONLY_P0_P1", alias_queue_p2_count, 0, alias_queue_p2_count == 0))

quality = spark.createDataFrame(
    quality_rows, ["check_name", "actual_value", "expected_value", "passed"]
).withColumn("checked_at", F.current_timestamp())
write_gold(quality, "gold_data_quality_checks")

if quality.filter(~F.col("passed")).count() > 0:
    raise ValueError("Gold reconciliation failed. Inspect gold_data_quality_checks.")

display(review_queue.groupBy("review_priority").count().orderBy("review_priority"))
