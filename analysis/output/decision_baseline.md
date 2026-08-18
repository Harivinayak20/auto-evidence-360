# Decision Baseline

## TL;DR

- 82,400 normalized make/model/year keys are represented across the approved sources.
- 1,355 keys meet a Critical review rule and 2,222 meet a High rule.
- 41.26% of unioned keys exactly match the EPA or NCAP reference; 41.90% of EPA/NCAP-era-eligible keys (model year 1984 or later) match.
- The operational evidence queue is independent of EPA/NCAP enrichment status.
- These are public-record evidence signals and operating rules, not reliability rates.

## Metadata

- Rule version: `portfolio_v1`
- Threshold validation status: `unvalidated` (pending stakeholder validation)
- Model-year window: 1900 through 2027

## Review priority

| Priority | Vehicle keys |
|---|---:|
| Critical | 1,355 |
| High | 2,222 |
| Review | 39,955 |
| Monitor | 38,868 |

## Alias work queue (unresolved identities only)

The complete unresolved backlog stays in Silver. Gold publishes an actionable work queue:

| Alias priority | Vehicle keys |
|---|---:|
| P0: unresolved with do-not-drive, park-outside, or open-investigation evidence | 1,420 |
| P1: unresolved with multi-source or high-signal evidence | 35,505 |
| P2: unresolved low-signal backlog (aggregate only) | 11,476 |

## Distinct business entities after grain correction

| Entity | Count |
|---|---:|
| Complaint reports | 122,140 |
| Severe-indicator complaint reports | 6,966 |
| Vehicle-campaign pairs | 92,783 |
| Vehicle-investigation pairs | 28,537 |
| Vehicle-document pairs | 554,854 |
| NCAP tested variants | 17,156 |
| EPA configurations | 50,242 |

The vehicle-pair counts above intentionally differ from global distinct campaign, investigation, or document counts. The Power BI measures apply the correct context-specific grain.
