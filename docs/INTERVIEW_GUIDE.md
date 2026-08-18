# Interview Guide

## 30-second explanation

> Auto Evidence 360 combines seven real federal vehicle datasets in a local lakehouse pipeline and a Tableau Public workbook. I built a governed pipeline in Python and DuckDB that validates every source, removes sensitive complaint fields, standardizes vehicle identities, and creates a review queue with a plain-language reason. The dashboard helps a used-car team decide what deserves deeper review, but it deliberately does not claim a universal reliability score.

## 90-second explanation

> The business problem is that a vehicle reviewer has to check several disconnected public sources before acquiring or listing a used car. I downloaded more than 1.4 million real records from NHTSA, DOE/EPA, and FHWA and retained URLs, timestamps, schemas, row counts, and checksums.
>
> In the lakehouse, Bronze preserves each approved extract and fails if the manifest does not match. Silver types and deduplicates the records, classifies official text into explainable topics, and creates a normalized make/model/year key. Exact reference matching varies a lot by source, so unmatched names go into an alias review queue rather than being silently joined. Gold publishes a star schema, source-specific facts, an evidence mart, and a transparent review-priority queue, and exports small curated Parquet files to Tableau Public.
>
> Tableau answers why a vehicle needs review and lets the user drill into the source evidence. The key analytical guardrail is that complaint and bulletin counts are signals, not reliability rates, because we do not have a make/model/year exposure denominator.

## The complex-but-simple map

| Technical phrase | Plain-English explanation |
|---|---|
| Medallion architecture | Raw copy, cleaned copy, decision-ready copy |
| Provenance | Proof of where every file came from |
| SHA-256 checksum | A fingerprint showing whether a file changed |
| Entity resolution | Deciding when two sources mean the same vehicle |
| Grain | What one row represents |
| Semantic model | The business rules between tables and metrics |
| Curated export | Small, safe tables published for the dashboard |
| Data-quality gate | A failed check that stops bad data from being published |
| Rule-based topic model | Transparent keyword categories on official text |
| Review priority | A reason to inspect evidence, not a vehicle-quality verdict |

## Explain the hardest part

> Different sources use different names and levels of detail for the same vehicle. I first created a deterministic normalized key across model years 1900 to current plus one. Then I measured exact matches against EPA and NCAP references with two coverage measures: all valid keys and EPA/NCAP-era-eligible keys. I did not automatically accept fuzzy matches because a wrong vehicle join can create a confident but false dashboard. Instead, unresolved identities enter a prioritized work queue (P0, P1, or P2) with the source names and reason. That makes match coverage visible and auditable.

## Explain the best metric lesson

> The raw row count is often the wrong metric. A recall campaign repeats for different models, years, and components, and its potential-unit estimate can repeat too. My pipeline counts distinct campaigns and takes one estimate per campaign before summing. The same discipline applies to complaint reports, service documents, NCAP variants, and EPA configurations.

## Explain why there is no machine-learning score

> I considered a predictive score, but the available public data do not contain a valid labeled outcome or make/model/year exposure denominator. A black-box score would look advanced while weakening the analysis. I used explainable review rules and transparent topic classification instead. Adding ML later would require a clearly defined target, representative training data, evaluation by segment, and human oversight.

## Questions you should expect

### Is a vehicle with more complaints less reliable?

Not necessarily. Complaints are self-reported and reporting opportunity and propensity differ. I call them complaint-report signals and show them with coverage and other source evidence.

### Does a recall row apply to a specific car?

No. The dashboard works at make/model/year evidence level. VIN applicability and remedy status require a separate live VIN-level NHTSA check.

### Why use FHWA registrations?

They add state-level vehicle-population context. They cannot create make/model/year reliability rates because that detail is absent, so I keep them in a separate fact and label the limitation.

### How do you know the pipeline is reproducible?

The source configuration records exact URLs and assumptions; downloads write metadata and hashes; the upload manifest records source and output hashes, schemas, and row counts; the pipeline is a one-command local run; and Bronze/Gold gates plus nightly GitHub Actions stop inconsistent publication.

### What would you add in production?

- Approved alias master data with reviewer history.
- Incremental snapshots and slowly changing source status.
- Live NHTSA VIN lookup in a controlled user workflow.
- Data-owner alerting and service-level objectives.
- Usage telemetry, stakeholder threshold validation, and model endorsement workflow.

## Three sentences not to say

- “This dashboard proves which car is safest.”
- “More bulletins mean the vehicle is worse.”
- “These are failures per vehicle.”

Say instead:

> These real public records create a transparent review priority. The dashboard shows the evidence, coverage, and limitations so a person can make the next decision.
