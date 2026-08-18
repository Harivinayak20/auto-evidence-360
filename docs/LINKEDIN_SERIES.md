# Five-Post LinkedIn Series

Each post proves a different employable skill. Publish only after its artifact is complete, and keep the native post copy separate from any on-screen video script.

## Post 1: I replaced portfolio fiction with traceable public data

**Hook:** My data project started with a source register, not a dashboard theme.

Story:

- Introduce the used-car review decision in one sentence.
- Show the seven official datasets and 1,411,783 verified rows.
- Explain URL, retrieval timestamp, checksum, schema, row count, grain, and limitation.
- Mention that complaint narratives and quasi-identifying fields are removed before anything is published.

Proof artifact: source register plus manifest/checksum screenshot.

Hiring signal: requirements analysis, data governance, privacy judgment, and reproducibility.

Closing question: What provenance evidence do you expect before trusting a public-data dashboard?

## Post 2: 1.4 million rows were easier than one trustworthy join

**Hook:** The hardest part of combining government vehicle data was not scale. It was identity.

Story:

- Show the Bronze-Silver-Gold lakehouse pipeline (Python, DuckDB, Parquet; Fabric-ready PySpark variants included).
- Explain normalized make/model/year in plain language.
- Share verified exact-reference coverage with both published measures: 64.86% complaints, 15.47% recalls, 33.24% manufacturer communications, and 30.91% investigations across all valid keys (33.55% among EPA/NCAP-era-eligible keys, model year 1984 or later).
- Explain why unresolved names enter a prioritized alias work queue (P0/P1/P2) instead of a hidden fuzzy match.

Proof artifact: pipeline diagram plus entity-match quality table.

Hiring signal: data engineering, data quality, entity resolution, and risk control.

Closing question: When would you accept a fuzzy match automatically, and when would you require review?

## Post 3: A correct row count can still create a wrong KPI

**Hook:** One recall campaign can appear on many rows. Summing those rows can manufacture millions of affected vehicles.

Story:

- Show the star schema and explicit fact grains.
- Contrast raw recall rows with distinct campaigns.
- Explain why complaints count distinct reports and service communications count distinct documents.
- Drop one verifiable finding: 122,313 vehicle complaint reports in the snapshot, of which 11,104 (about 9%) carry a crash, fire, injury, or death indicator.

Proof artifact: gold table list, metric catalog, and reconciliation output.

Hiring signal: dimensional modeling, metric governance, and analytical skepticism.

Closing question: Which business metric in your reporting is most vulnerable to double-counting?

## Post 4: I built a decision queue, not a mysterious safety score

**Hook:** Complex analytics should make the decision easier to explain, not harder to defend.

Story:

- Walk through Critical, High, Review, and Monitor rules.
- Show the plain-language reason attached to every queued vehicle.
- Demonstrate drill-through from priority to campaign, investigation, complaint, and document evidence in the Tableau workbook.
- Drop one verifiable finding: 201 distinct do-not-drive campaigns across vehicle recalls, with Ford, Mazda, and BMW leading, and a park-outside cluster led by Hyundai (19) and Kia (14).
- State that thresholds are review rules (`rule_version = portfolio_v1`, `threshold_validation_status = unvalidated`), not federal standards or automated rejection decisions.

Proof artifact: Tableau dashboard screenshots (Review Priority and Evidence per Vehicle).

Hiring signal: business analysis, operational analytics, explainability, and responsible BI.

Closing question: Would your stakeholders rather receive a score or a reason they can verify?

## Post 5: The dashboard page that decides whether to trust the dashboard

**Hook:** My final dashboard can stop the rest of the workbook from being used.

Story:

- Show manifest expected-versus-actual counts, schema status, checksums, alias coverage, and orphan-key tests.
- Demonstrate a controlled failure and the `STOP AND INVESTIGATE` state.
- Present three validated findings only after reconciliation (201 do-not-drive campaigns; the Hyundai/Kia park-outside cluster; 223 open investigations, including 107 records with a blank make that the pipeline surfaces rather than hides).
- End with what the sources cannot prove: no universal reliability rate, VIN remedy status, or causal claim.

Proof artifact: Data Trust dashboard plus a 60-90 second demo.

Hiring signal: end-to-end ownership, stakeholder communication, QA, and honest limitation handling.

Closing question: What condition should automatically block a refresh in your organization?

## Publishing sequence

- Post 1: data provenance and privacy.
- Post 2: pipeline architecture and entity resolution.
- Post 3: semantic model and metric correctness.
- Post 4: decision design and explainability.
- Post 5: trust, findings, and end-to-end demo.

Space posts four to seven days apart. Reuse the project identity but use a different evidence image for each post. Do not publish findings until they reconcile to the final pipeline build and the live Tableau workbook.

## Verification checklist before posting

- [ ] `python src/local/run_pipeline.py` ends with "reconciliation against local baseline: ALL PASS".
- [ ] `python -m unittest discover -s tests -v` is green.
- [ ] GitHub Actions shows a green nightly run for the current extracts.
- [ ] Tableau workbook counts match 1,355 / 2,222 / 39,955 / 38,868 and P0 1,420 + P1 35,505.
- [ ] The live workbook URL is pasted into the relevant post.