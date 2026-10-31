---
name: dataset-discovery
description: Find and assess datasets for relevance, legality, quality, access, privacy, and reproducibility.
---

# Dataset discovery

## Inputs

Research variables, population/context, temporal/geographic coverage, scale, format, legal/ethical constraints, and compute limits.

## Procedure

1. Search repositories and papers through `dataset_search` or `academic_search`; record query, provider, date, and result identifiers.
2. Verify publisher, canonical URL, version, license/terms, access procedure, citation, and maintenance status.
3. Inspect documentation for sampling, schema, labels, missingness, known biases, and preprocessing.
4. Evaluate construct fit, leakage risk, representativeness, privacy/sensitivity, and permitted uses.
5. Compare candidates in a decision matrix; identify data unavailable for inspection.
6. Record checksums and a retrieval recipe when acquisition is approved; do not commit restricted/raw data.

## Output

`07-data/dataset-assessment.md`, candidate inventory, data-use constraints, selected version, and approval block.

## Quality checks

- Dataset existence and license are verified.
- Limitations and population mismatch are explicit.
- Sensitive acquisition awaits approval.
- Version and retrieval are reproducible.
