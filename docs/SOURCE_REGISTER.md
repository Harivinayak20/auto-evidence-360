# Source Register

Every analytical table must trace back to one of these sources. Download metadata records the exact URL, retrieval timestamp, byte size, HTTP metadata, and SHA-256 checksum.

| Source | What it establishes | Planned use | Important limitation |
|---|---|---|---|
| NHTSA consumer complaints, active snapshot 2025-2026 | Reports submitted to NHTSA about alleged vehicle problems, including component, crash, fire, and injury indicators. | Report trends, severe-outcome signals, and component patterns. Narratives are excluded before Fabric upload. | Self-reported complaints are not verified failures and are not a reliability rate. Reporting propensity varies. |
| NHTSA recalls, post-2010 | Safety recall campaigns, affected products, components, consequence, remedy, and potentially affected units. | Recall burden, affected components, remedy language, campaign timeline. | One campaign may repeat across multiple vehicle/product rows. Count distinct campaigns separately from rows. A campaign record does not show whether a specific VIN was repaired. |
| NHTSA investigations | Formal defect-investigation records and status. | Escalation signal and investigation lifecycle. | Investigation scope does not mean every covered vehicle has a defect. |
| NHTSA manufacturer communications/TSBs, active snapshot 2025-2026 | Communications from manufacturers concerning defects, failures, malfunctions, and service information. | Emerging service themes, transparent text topics, and documentation volume. | More bulletins can reflect documentation practices, not worse quality. |
| NHTSA NCAP ratings | Government crashworthiness, rollover, and crash-avoidance test results for tested variants. | Tested safety-rating context and feature coverage. | Not every trim is tested. Rating methodology and comparability vary across model years. NHTSA marks this dataset as not quality-certified. |
| DOE/EPA FuelEconomy.gov vehicle data | Tested vehicle configurations, MPG/MPGe, annual fuel cost, emissions, powertrain, and class. | Ownership-cost and efficiency context. | Multiple trims/configurations exist for one make/model/year. Aggregation must retain min/median/max and record count. |
| FHWA motor-vehicle registrations | Annual state-reported registration totals. | State-level exposure context for overall complaint-reporting intensity. | No make/model/year denominator. It cannot support model reliability rates. |
| BLS used-car CPI via FRED, configured but deferred | Monthly used-car and truck price index. | Optional market context for reporting and recall timelines. It is not part of the current 1,411,783-row snapshot. | Macro correlation is not causal evidence about a particular vehicle. |

Historical 2020-2024 complaint and manufacturer-communication files are configured for a later snapshot extension. They are not counted or claimed in the active Fabric package.

## Joining contract

The conformed vehicle key is `normalized_make + normalized_model + model_year`.

Every release-1 cross-source identity receives:

- `match_method`: exact normalized reference match or unresolved to reference.
- `match_confidence`: high or unresolved.
- `source_make` and `source_model`: preserved for audit.
- `normalized_make` and `normalized_model`: standardized values.
- `review_reason`: populated for identities awaiting alias review.

Unresolved records remain visible in the quality dashboard and are excluded from reference-comparison KPIs by default. Alias or token matching can be added only through a reviewed mapping table with rationale and history.

## Claims we will not make

- “This is the safest/most reliable vehicle.”
- “This model has X failures per 100,000 vehicles” without a matching exposure denominator.
- “A recall applies to this VIN” without a VIN-level NHTSA lookup.
- “A bulletin proves a defect.”
- “The macro market caused a complaint or recall trend.”

The report will instead say: “These public records create a higher or lower review priority, with the evidence and coverage shown.”
