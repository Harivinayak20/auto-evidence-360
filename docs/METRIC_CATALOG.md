# Metric Catalog

## Metric system

The report separates evidence volume, urgent source flags, context coverage, and data trust. No count is labeled a reliability or failure rate.

| Layer | Metric | Definition | Grain rule | Action |
|---|---|---|---|---|
| Outcome | Review Queue Vehicles | Distinct vehicle keys with Critical, High, or Review priority | Vehicle key | Assign human review |
| Outcome | Critical Review Vehicles | Distinct vehicle keys with a do-not-drive or park-outside campaign | Vehicle key | Review immediately |
| Signal | Complaint Reports | Distinct NHTSA complaint IDs | Complaint report, not component row | Inspect components and dates |
| Signal | Severe Complaint Reports | Distinct complaint IDs with crash, fire, injury, or death source indicators | Complaint report | Escalate evidence review |
| Signal | Recall Campaigns | Distinct NHTSA campaign numbers | Campaign, not product row | Review consequence and remedy |
| Signal | Open Investigations | Distinct investigation numbers without a closed date | Investigation | Track agency status |
| Signal | Manufacturer Documents | Distinct document IDs | Document, not vehicle/component row | Inspect recurring service topics |
| Context | Median Overall NCAP Stars | Median across tested variants in context | Tested variant | Show rating with coverage |
| Context | Median Combined MPG | Median across EPA configurations in context | EPA configuration | Explain operating-cost context |
| Context | Median Annual Fuel Cost | Median EPA annual fuel cost across configurations | EPA configuration | Compare ownership context |
| Coverage | Reference Exact-Match Rate (All Valid Keys) | Vehicle keys exactly matching EPA/NCAP reference divided by all valid vehicle keys (model years 1900 through current year plus one) | Distinct vehicle key | Prioritize alias review |
| Coverage | Reference Exact-Match Rate (Era-Eligible Keys) | Same numerator divided by EPA/NCAP-era-eligible keys (model year 1984 or later, when the reference sources begin) | Distinct vehicle key | Remove pre-reference-era keys from the denominator |
| Coverage | Alias Work Queue P0 | Unresolved identities with do-not-drive, park-outside, or open-investigation evidence | Distinct vehicle key | Review immediately |
| Coverage | Alias Work Queue P1 | Unresolved identities with multi-source or high-signal evidence | Distinct vehicle key | Review next |
| Coverage | Alias Work Queue P2 | Unresolved low-signal backlog; shown only in aggregate | Aggregate count | Monitor aggregate only |
| Coverage | Average Evidence Sources per Vehicle | Average count of source families present per vehicle | Vehicle key | Interpret sparse evidence cautiously |
| Trust | Rule Version | `portfolio_v1` | Constant | Identify rule lineage |
| Trust | Threshold Validation Status | `unvalidated` until stakeholder validation | Constant | Do not treat as production policy |
| Trust | Failed Data Quality Checks | Count of failed Gold uniqueness/orphan checks | Check execution | Stop and investigate |

## Core contracts

### Complaint Reports

- Numerator: distinct `complaint_id`.
- Detail grain: a complaint can repeat across component rows.
- Severe flag: maximum of crash, fire, injury, or death indicators across the complaint's component rows.
- Caveat: complaints are self-reported and do not have a make/model/year exposure denominator.

### Recall Campaigns

- Numerator: distinct `campaign_number`.
- Detail grain: a campaign repeats across models, years, products, and components.
- Potential units affected: take the maximum campaign estimate once per campaign in the current filter context, then sum across distinct campaigns.
- Caveat: the campaign estimate is not a count of unrepaired vehicles and is not additive across raw rows.

### Open Investigations

- Numerator: distinct `investigation_number` where parsed closed date is blank.
- Caveat: an investigation is an agency process, not proof that every scoped vehicle is defective.

### Manufacturer Communication Documents

- Numerator: distinct `document_id`.
- Caveat: more documents can reflect service-documentation practice or coverage breadth, not worse reliability.

### NCAP and EPA context

- Unit: tested variant/configuration, never assumed to represent every trim.
- Default aggregation: median, accompanied by distinct variant count.
- NCAP caveat: ratings and methods can vary by model year, and the downloadable file is not quality-certified by NHTSA.

### Reference Exact-Match Rate

- Numerator: distinct normalized make/model/year keys found in EPA or NCAP reference keys.
- Denominator: all valid source vehicle keys for the all-valid measure; EPA/NCAP-era-eligible keys (model year 1984 or later) for the era-eligible measure.
- Exclusion: blank or invalid source identity.
- Caveat: this measures data integration coverage, not vehicle quality.

### Alias work queue

- The complete unresolved backlog stays in Silver; Gold publishes only P0 and P1 identities as queue entries.
- P0: unresolved identity with do-not-drive, park-outside, or open-investigation evidence.
- P1: unresolved identity with multi-source or high-signal evidence (2+ source systems, 10+ complaints, 3+ severe reports, any recall, or 10+ documents).
- P2: unresolved low-signal identities appear only as an aggregate count.
- The operational review queue never depends on EPA/NCAP enrichment status.

## Review-priority rules

| Rule, evaluated top to bottom | Priority | Owner action |
|---|---|---|
| Do-not-drive recall campaign exists | Critical | Verify campaign applicability in VIN-level workflow before acquisition/listing |
| Park-outside recall campaign exists | Critical | Review fire-risk instructions and remedy workflow |
| Open NHTSA investigation exists | High | Review scope, status, and related evidence |
| At least 10 complaint reports and at least 3 severe-indicator reports | High | Examine time, component, and coverage pattern |
| Recall campaign exists | Review | Read consequence and corrective action |
| At least 5 complaint reports | Review | Inspect component and severe-indicator mix |
| At least 10 manufacturer documents | Review | Inspect document types and topics |
| No rule crossed | Monitor | Retain in evidence view; do not label safe |

These rules are transparent operating thresholds for the portfolio scenario. They require stakeholder validation before production use. Every rule row carries `rule_version = portfolio_v1` and `threshold_validation_status = unvalidated`.

## Required breakdowns

- Vehicle: make, model, model year, reference-match status.
- Evidence: source family, topic, component, priority, reason.
- Time: incident, received, opened, communication, or campaign-received date as appropriate.
- Geography: complaint incident state and aggregate state registrations, kept separate unless a documented mapping and denominator are used.
- Context: tested NCAP variant and EPA configuration.
- Trust: source snapshot, batch, checksum, match coverage, and quality status.

## Reconciliation rules

- Distinct complaints must reconcile between the aggregate mart and complaint fact after collapsing component rows.
- Recall campaigns must reconcile on distinct campaign number, not row count.
- Potential units affected cannot be summed directly from the fact table.
- Each Gold vehicle fact's non-null `vehicle_key` must resolve to one `gold_dim_vehicle` row.
- `gold_dim_vehicle[vehicle_key]` must be unique.
- Critical review vehicles must have at least one qualifying urgency flag.
- A failed quality check changes the report status to `STOP AND INVESTIGATE`.
