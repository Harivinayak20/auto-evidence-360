# Tableau Public workbook blueprint

Three dashboards, one parameter, two calculated fields, sourced exclusively from the curated exports in `data/tableau_public/`. The same business design is reproduced in `docs/POWER_BI_BLUEPRINT.md` for the Fabric variant.

## Data sources

| Parquet file | Rows | Purpose |
|---|---|---|
| `evidence_summary.parquet` | 82,400 | One row per vehicle key: counts, coverage, review priority, alias priority, reasons |
| `alias_work_queue.parquet` | 36,925 | Actionable unresolved identities (P0/P1), one row per key |
| `data_trust.parquet` | small | Bronze audit and entity-match quality evidence |

Import into Tableau Public Desktop: connect to each Parquet file, join nothing (independent sources), set `vehicle_key` as the hidden key field.

## Dashboard 1 - Review priority (executive)

Purpose: answer "how many vehicles need what kind of review, and why."

- Big number cards: Critical 1,355 / High 2,222 / Review 39,955 / Monitor 38,868.
- Bar chart: review priority vs `review_reason` (dominant reasons: open investigation, do-not-drive, complaint thresholds).
- Scatter: `complaint_reports` (x, log) vs `severe_complaint_share` (y), colored by priority, sized by `recall_campaigns`.
- Top 20 table: `vehicle_label`, counts, priority, reason.
- Parameter `priority filter` (Critical / High / Review) drives all worksheets; filter action on the bar chart filters the table.

## Dashboard 2 - Evidence per vehicle (analyst drill-down)

Purpose: answer "show me everything that put this vehicle in the queue."

- Tooltip/drill: click a vehicle row anywhere -> Dashboard 1 sheet filters to that `vehicle_key`; all cards and the table react.
- Detail table: `vehicle_label`, `evidence_source_count`, complaint/recall/investigation/document counts, `review_reason`, `reference_match_status`.
- Reference-match context: share of queue rows with `reference_match_status = UNRESOLVED` and their `alias_priority` split.

## Dashboard 3 - Alias work queue and data trust

Purpose: show the human-in-the-loop story and prove the numbers are traceable.

- Donut or bar: alias priority P0 1,420 / P1 35,505 (P2 11,476 shown as an aggregate card from `data_trust`).
- Table: P0 rows first (`vehicle_label`, `alias_reason`, counts, `review_status`).
- Text cards from `data_trust`: bronze contracts PASS, match rates per source (complaints 64.86%, recalls 15.47%, investigations 30.91% / 33.55% era-eligible, communications 33.24%, union 16.78% / 17.15% era-eligible), `rule_version = portfolio_v1`, `threshold_validation_status = unvalidated`.

## Calculated fields

```text
review_priority_rank = CASE review_priority
  WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
  WHEN 'REVIEW' THEN 3 ELSE 4 END

alias_priority_rank = CASE alias_priority
  WHEN 'P0' THEN 1 WHEN 'P1' THEN 2 WHEN 'P2' THEN 3 ELSE 4 END
```

Use the ranks for sort order everywhere; keep the labels as the display text.

## Formatting and framing

- Light theme only (consistent with the repo theme file for the Fabric variant).
- Every dashboard carries a footer text box: "Review priority is an operating rule (portfolio_v1, unvalidated), not a safety score."
- Latest-source-date and batch context come from `data_trust`; refresh by re-running `src/local/run_pipeline.py` and re-publishing.
- No invented metrics: complaint volume is never presented as a defect rate.

## Publish

1. Tableau Public Desktop (free, Mac and Windows) -> sign in.
2. File -> New -> connect to the three Parquet files.
3. Build the dashboards, then File -> Save to Tableau Public As.
4. Workbook name: "Auto Evidence 360 - Public Review Priority".
5. Publish with "Show sheets as tabs" enabled.

## QA checklist before publish

- [ ] Priority counts match the committed baseline (1,355 / 2,222 / 39,955 / 38,868).
- [ ] Alias queue shows exactly P0 1,420 + P1 35,505 rows, no P2 rows.
- [ ] Filter and tooltip interactions work on every dashboard.
- [ ] Every dashboard shows the unvalidated-rule footer.
- [ ] No complaint narrative, VIN, city, or contact field appears anywhere.
- [ ] Workbook URL captured for `README.md` and the LinkedIn series.