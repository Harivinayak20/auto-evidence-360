# Power BI Blueprint

## Semantic model

Use a Direct Lake star schema with single-direction, one-to-many relationships. Hide raw identifiers and numeric columns when an explicit measure exists.

Core relationships:

| From | To | Cardinality | Active date role |
|---|---|---|---|
| `gold_dim_vehicle[vehicle_key]` | each vehicle-level fact `[vehicle_key]` | 1:* | n/a |
| `gold_dim_vehicle[vehicle_key]` | `gold_agg_vehicle_evidence[vehicle_key]` | 1:1 | n/a |
| `gold_dim_vehicle[vehicle_key]` | `gold_vehicle_review_queue[vehicle_key]` | 1:1 optional | n/a |
| `gold_dim_evidence_topic[topic_key]` | complaint/recall/investigation/communication `[evidence_topic]` | 1:* | n/a |
| `gold_dim_date[date_key]` | complaint `[received_date_key]` | 1:* | active |
| `gold_dim_date[date_key]` | recall `[report_received_date_key]` | 1:* | active |
| `gold_dim_date[date_key]` | investigation `[opened_date_key]` | 1:* | active |
| `gold_dim_date[date_key]` | communication `[communication_date_key]` | 1:* | active |

Complaint incident date can be an inactive relationship activated by a dedicated measure. Do not connect state registrations to vehicle facts because the registration source lacks make/model/year detail.

Create a `_Measures` table with display folders:

- Executive Review
- Complaints
- Recalls and Investigations
- Manufacturer Communications
- NCAP and EPA Context
- Entity Resolution
- Data Trust

## Page 1: Executive Evidence Command Center

Decision: what needs review and why?

- Hero cards: Critical Review Vehicles, High Review Vehicles, Review Queue Vehicles, Data Quality Status.
- Priority distribution by reason.
- Vehicle matrix: make/model/year, complaint reports, recall campaigns, open investigations, service documents, NCAP/EPA coverage.
- Trend by source date with a source-family field parameter.
- “How to read this page” callout: evidence priority is not a reliability score.
- Drill-through button to Vehicle Evidence 360.

## Page 2: Recall and Investigation Radar

Decision: which formal safety records require immediate reading?

- Cards: Recall Campaigns, Do-Not-Drive Campaigns, Park-Outside Campaigns, Open Investigations.
- Timeline: campaigns and investigation openings.
- Matrix: evidence topic by make/model with distinct campaign and investigation counts.
- Campaign table: number, filing manufacturer, consequence, corrective action, urgency flags.
- Tooltip: potential affected units uses one maximum estimate per distinct campaign.

## Page 3: Complaint Signal Explorer

Decision: where do self-reported signals deserve examination?

- Cards: Complaint Reports, Severe Complaint Reports, Severe Complaint Share.
- Trend by complaint received date; optional switch to incident date.
- Topic/component Pareto.
- Make/model matrix with minimum-report filter and coverage tooltip.
- State map is optional and must say “report location,” not vehicle failure rate.
- No consumer narrative appears in the model or report.

## Page 4: Manufacturer Communication Topics

Decision: what service-document themes are recurring?

- Cards: distinct communication documents and represented vehicles.
- Topic trend by communication date.
- Decomposition: topic to component/system to make/model.
- Document type distribution.
- Detail table: document ID, date, official summary, source vehicle, and topic.
- Caveat: document volume can reflect documentation practices.

## Page 5: Vehicle Context

Decision: what tested safety and operating-cost context is available?

- Cards: Tested NCAP Variants, Median Overall NCAP Stars, EPA Vehicle Variants, Median Combined MPG, Median Annual Fuel Cost.
- NCAP rating distribution by model year.
- MPG versus annual fuel-cost scatter, colored by fuel type.
- Variant table retaining drivetrain, transmission, class, and coverage count.
- Empty-state text when a vehicle has no tested reference variant.

## Page 6: Entity Resolution Workbench

Decision: can the joined view be trusted, and where should aliases be reviewed?

- Exact-reference match rate by source system.
- Matched versus unresolved vehicle keys.
- Queue: source make/model/year, participating source systems, review status, reason.
- Before/after alias mapping section for manually approved mappings.
- Coverage impact simulation: how many records and vehicle keys would an approved alias connect?

## Page 7: Data Trust and Provenance

Decision: should this refresh be used?

- Data Quality Status and failed-check count.
- Manifest expected versus actual rows by source.
- Latest batch ID and ingestion timestamp.
- Source/extract checksum table.
- Gold uniqueness and orphan results.
- Privacy fields excluded checklist.
- Source limitations and link-outs.

## Drill-through: Vehicle Evidence 360

- Vehicle identity and exact-reference-match status.
- Review priority and plain-language reason.
- Complaint, recall, investigation, and communication timelines.
- Component/topic distribution.
- Recall consequence/remedy and investigation/communication summaries.
- NCAP and EPA variant context.
- Coverage and interpretation caveats.

## Interaction design

- Global slicers: model year, make, model, evidence topic, reference-match status.
- Page-specific dates only. Different source dates must not be mixed under one unexplained date label.
- Field parameter switches signal counts but retains the metric definition in a dynamic subtitle.
- Report-page tooltips show grain, numerator, denominator, latest source date, and caveat.
- Drill-through retains vehicle context and offers a clear back action.
- Priority colors: dark red Critical, amber High, blue Review, gray Monitor, always paired with text/icon.

## Visual standards

- Use totals with coverage, never totals alone when missing reference data can change interpretation.
- Avoid gauges, 3D visuals, decorative maps, and unexplained composite scores.
- Wrap official summaries and provide a source-record identifier.
- Keep the executive page useful without interaction.
- Use accessible contrast and do not encode urgency by color alone.
- Put the decision or caveat in the subtitle, not only in documentation.

## QA checklist

- Every card reconciles to a filtered detail table.
- Complaints count distinct complaint ID; communications count distinct document ID.
- Campaign potential-units measure de-duplicates campaign rows.
- Date slicers affect only facts with the intended date role.
- One vehicle selection filters all vehicle-level facts but not aggregate state registrations.
- Critical priority always traces to a qualifying source flag.
- Unresolved reference matches are visibly labeled and excluded from reference-comparison visuals by default.
- Empty NCAP/EPA context displays “not available in this source,” not zero.
- Failed data-quality status is visible on every page through a header indicator.
- Performance Analyzer, tab order, alt text, mobile layout, and export behavior are checked before publishing.
