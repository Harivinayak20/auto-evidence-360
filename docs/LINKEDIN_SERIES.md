# Five-Post LinkedIn Series

Each post proves a different employable skill. Publish only after its artifact is complete, and keep the native post copy separate from any on-screen video script.

## Post 1: I replaced portfolio fiction with traceable public data

**Hook:** My Power BI project started with a source register, not a dashboard theme.

Story:

- Introduce the used-car review decision in one sentence.
- Show the seven official datasets and 1,411,783 verified rows.
- Explain URL, retrieval timestamp, checksum, schema, row count, grain, and limitation.
- Mention that complaint narratives and quasi-identifying fields are removed before Fabric upload.

Proof artifact: source register plus manifest/checksum screenshot.

Hiring signal: requirements analysis, data governance, privacy judgment, and reproducibility.

Closing question: What provenance evidence do you expect before trusting a public-data dashboard?

## Post 2: 1.4 million rows were easier than one trustworthy join

**Hook:** The hardest part of combining government vehicle data was not scale. It was identity.

Story:

- Show the Fabric Bronze-Silver-Gold architecture.
- Explain normalized make/model/year in plain language.
- Share verified exact-reference coverage: 64.86% complaints, 15.47% recalls, 33.55% investigations, and 33.24% manufacturer communications.
- Explain why unresolved names enter an alias review queue instead of a hidden fuzzy match.

Proof artifact: executed quality notebook plus entity-resolution workbench.

Hiring signal: data engineering, data quality, entity resolution, and risk control.

Closing question: When would you accept a fuzzy match automatically, and when would you require review?

## Post 3: A correct row count can still create a wrong KPI

**Hook:** One recall campaign can appear on many rows. Summing those rows can manufacture millions of affected vehicles.

Story:

- Show the star schema and explicit fact grains.
- Contrast raw recall rows with distinct campaigns.
- Show the DAX measure that takes one campaign estimate before summing.
- Explain why complaints count distinct reports and service communications count distinct documents.

Proof artifact: semantic model diagram, metric catalog, and reconciliation visual.

Hiring signal: dimensional modeling, DAX, metric governance, and analytical skepticism.

Closing question: Which business metric in your reporting is most vulnerable to double-counting?

## Post 4: I built a decision queue, not a mysterious safety score

**Hook:** Complex analytics should make the decision easier to explain, not harder to defend.

Story:

- Walk through Critical, High, Review, and Monitor rules.
- Show the plain-language reason attached to every queued vehicle.
- Demonstrate drill-through from priority to campaign, investigation, complaint, and document evidence.
- State that thresholds are review rules, not federal standards or automated rejection decisions.

Proof artifact: Executive Evidence Command Center and Vehicle Evidence 360 drill-through.

Hiring signal: business analysis, operational analytics, explainability, and responsible BI.

Closing question: Would your stakeholders rather receive a score or a reason they can verify?

## Post 5: The dashboard page that decides whether to trust the dashboard

**Hook:** My final Power BI page can stop the rest of the report from being used.

Story:

- Show manifest expected-versus-actual counts, schema status, checksums, alias coverage, and orphan-key tests.
- Demonstrate a controlled failure and the `STOP AND INVESTIGATE` report state.
- Present three validated findings only after reconciliation.
- End with what the sources cannot prove: no universal reliability rate, VIN remedy status, or causal claim.

Proof artifact: Data Trust and Provenance page plus a 60-90 second demo.

Hiring signal: end-to-end ownership, stakeholder communication, QA, and honest limitation handling.

Closing question: What condition should automatically block a BI refresh in your organization?

## Publishing sequence

- Post 1: data provenance and privacy.
- Post 2: Fabric architecture and entity resolution.
- Post 3: semantic model and DAX correctness.
- Post 4: decision design and explainability.
- Post 5: trust, findings, and end-to-end demo.

Space posts four to seven days apart. Reuse the project identity but use a different evidence image for each post. Do not publish findings until they reconcile to the final Fabric and Power BI build.
