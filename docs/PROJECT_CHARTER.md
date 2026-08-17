# Project Charter

## Initiative

Auto Evidence 360: Used-Car Review Intelligence

## Decision statement

Which make/model/year combinations deserve deeper review before a used vehicle is acquired, listed, or recommended, and what public evidence explains that priority?

## Primary users

| User | Decision | Output needed |
|---|---|---|
| Inventory acquisition lead | Where should a manual risk review happen before purchase? | Prioritized vehicle queue with reasons |
| Vehicle quality analyst | Which recall, investigation, complaint, or service topics require investigation? | Evidence drill-through and source links |
| Merchandising manager | What safety-rating and operating-cost context can be disclosed? | NCAP and EPA variant context with coverage caveats |
| Analytics leader | Can the data and dashboard be trusted? | Provenance, match coverage, data-quality, and reconciliation evidence |

## Business outcome

Increase the share of inventory decisions supported by traceable public evidence while reducing two errors:

1. missing a vehicle that crosses a defined review rule;
2. overstating a public-record count as proof of universal vehicle reliability.

## Analytical questions

1. Which vehicles have do-not-drive or park-outside recall campaigns?
2. Which vehicles are connected to open NHTSA investigations?
3. Where do complaint reports include crash, fire, injury, or death indicators?
4. Which components and official-document topics recur across source types?
5. Which vehicle identities match EPA or NCAP references exactly, and which require alias review?
6. Where are NCAP and EPA context available, unavailable, or represented by multiple tested configurations?
7. Did each published metric preserve the correct business grain and source limitation?

## Working hypotheses

- A small portion of vehicle identities will account for a large share of high-priority review rules.
- Exact string normalization will leave material make/model naming gaps across agencies.
- Service-document volume will be much larger than recall or investigation volume and must be counted by distinct document.
- Some apparent vehicle comparisons will change once evidence coverage is shown beside raw counts.

These are testable hypotheses, not conclusions.

## Scope

Included:

- Downloaded public records listed in the source register.
- Batch ingestion, medallion transformations, provenance, privacy minimization, and quality gates.
- Deterministic make/model/year identity keys and an unresolved alias review queue.
- Transparent rule-based text topics on manufacturer and agency descriptions.
- Direct Lake semantic model, Power BI diagnostics, drill-through, and review queue.

Excluded from the first release:

- VIN-level recall applicability or remedy completion.
- Customer, dealer, transaction, price, or sales data.
- Automated acquisition rejection or consumer safety recommendations.
- A universal make/model reliability rate.
- Causal claims or a black-box safety score.

## Decision rules

The first release prioritizes review when a vehicle identity has:

| Priority | Rule | Why it is explainable |
|---|---|---|
| Critical | At least one do-not-drive or park-outside recall campaign | Directly uses NHTSA urgency flags |
| High | At least one open investigation | Directly uses investigation status |
| High | At least 10 complaint reports and at least 3 severe-indicator reports | Uses a minimum-volume guardrail and explicit threshold |
| Review | A recall, at least 5 complaints, or at least 10 manufacturer documents | Routes evidence to a person without declaring a defect |
| Monitor | No current rule crossed | Keeps the vehicle visible without implying safe |

Thresholds are portfolio operating rules to validate with stakeholders. They are not federal standards.

## Acceptance criteria

- A reviewer can explain the decision in 30 seconds without saying “AI safety score.”
- Every uploaded row traces to a source ID and SHA-256 checksum.
- No complaint narrative, VIN fragment, contact field, city, or vehicle-operator field enters Fabric.
- Bronze fails on missing files, schema drift, or manifest row-count mismatch.
- Silver reports exact-reference match coverage and exposes unresolved aliases.
- Gold dimensions are unique and every non-null fact vehicle key resolves.
- DAX counts distinct business entities instead of raw duplicated rows.
- Power BI shows source coverage and caveats beside review signals.
- A recruiter can inspect the source register, executed quality notebook, model, DAX, and five distinct project stories.

## Delivery sequence

1. Source governance and reproducible snapshot.
2. Fabric Bronze, Silver, identity bridge, and Gold decision mart.
3. Power BI semantic model and seven-page report.
4. Finding validation, screenshots, and narrated demo.
5. Five-post LinkedIn case-study release.
