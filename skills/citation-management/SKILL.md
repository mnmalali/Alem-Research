---
name: citation-management
description: Maintain deduplicated, stable bibliographic records and reproducible exports without fabricating metadata.
---

# Citation management

## Inputs

Source identifiers, provider metadata, local bibliography, citation style/CSL, and target document format.

## Procedure

1. Resolve metadata through `citation_metadata` using DOI or canonical identifier when available.
2. Preserve original provider response and record retrieval date; never infer missing authors, pages, DOI, or venue.
3. Normalize names and fields without changing meaning. Deduplicate by DOI/identifier, then documented manual review.
4. Assign stable citation keys and maintain aliases when keys change.
5. Export using `bibliography_export`; record tool/version and validation warnings.
6. Track retractions, corrections, preprint/published relationships, and version used.

## Output

Canonical `references.bib` or CSL JSON, metadata ledger, duplicate-resolution log, and export report.

## Quality checks

- Each record maps to a verifiable source.
- No placeholder metadata appears as fact.
- Keys used by the manuscript resolve uniquely.
- Export parses cleanly in the target toolchain.
