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
| Coverage | Reference Exact-Match Rate | Vehicle keys exactly matching EPA/NCAP reference divided by vehicle keys | Distinct vehicle key | Prioritize alias review |
| Coverage | Average Evidence Sources per Vehicle | Average count of source families present per vehicle | Vehicle key | Interpret sparse evidence cautiously |
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
- Denominator: distinct source vehicle keys in scope.
- Exclusion: blank or invalid source identity.
- Caveat: this measures data integration coverage, not vehicle quality.

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

These rules are transparent operating thresholds for the portfolio scenario. They require stakeholder validation before production use.

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
