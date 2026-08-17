# Real-Source Data Profile

Generated: 2026-08-17T19:51:01.874852+00:00

No raw narratives, VIN fragments, contact fields, or row-level records are emitted in this profile.

## Dataset profile

| Source | Rows | Columns | Malformed | Exact duplicates | Distinct vehicle keys | Year coverage | Date range |
|---|---:|---:|---:|---:|---:|---|---|
| nhtsa_complaints | 182,995 | 51 | 0 (0.00%) | 0 | 6,923 | 1986 to 2027 | 20250101 to 20260813 |
| nhtsa_recalls | 244,398 | 29 | 0 (0.00%) | 0 | 39,956 | 1965 to 2027 | 20100101 to 20260810 |
| nhtsa_investigations | 154,249 | 11 | 0 (0.00%) | 0 | 14,844 | 1965 to 2026 | 19720310 to 20260731 |
| nhtsa_manufacturer_communications | 731,898 | 14 | 0 (0.00%) | 1,527 | 19,472 | 2000 to 2027 | 20241204 to 20260815 |
| nhtsa_ncap | 17,313 | 128 | 0 (0.00%) | 1 | 12,282 | 1990 to 2026 | n/a to n/a |
| epa_fuel_economy | 50,242 | 84 | 0 (0.00%) | 0 | 26,359 | 1984 to 2027 | n/a to n/a |
| fhwa_state_registrations | 30,688 | 5 | 0 (0.00%) | 0 | 0 | 1900 to 2024 | n/a to n/a |

## Exact cross-source vehicle-key coverage

Reference is the union of normalized EPA and NCAP make/model/year keys. This is the baseline before alias or token matching.

| Source | Distinct keys | Exact matches | Exact match rate |
|---|---:|---:|---:|
| nhtsa_complaints | 6,923 | 4,490 | 64.86% |
| nhtsa_recalls | 39,956 | 6,182 | 15.47% |
| nhtsa_investigations | 14,844 | 4,980 | 33.55% |
| nhtsa_manufacturer_communications | 19,472 | 6,473 | 33.24% |

## Interpretation

- Repeated NHTSA business IDs can be legitimate because one complaint, campaign, investigation, or bulletin may cover multiple components or vehicles.
- Low exact match coverage is an entity-resolution requirement, not permission to use fuzzy matches silently.
- Complaint counts are self-reported public-record volume. They are not failure rates without make/model/year exposure data.
- Sensitive complaint fields are excluded before the conformed layer.
