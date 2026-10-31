---
name: literature-search
description: Run reproducible, provider-neutral academic searches and preserve complete search provenance.
---

# Literature search

## Inputs

Approved scope, concepts/synonyms, eligibility rules, date/language filters, and target databases.

## Procedure

1. Translate concepts into database-appropriate query blocks; retain the exact query sent to each provider.
2. Request the `academic_search` capability. Record resolved provider, database, timestamps, pagination, filters, and any truncation or failure.
3. Export raw results before normalization. Preserve provider identifiers and response provenance.
4. Normalize title, authors, year, venue, DOI, URL, abstract availability, and retrieval source; never fill missing metadata by guesswork.
5. Deduplicate conservatively using DOI, then stable identifier, then documented title/author rules.
6. Append searches instead of overwriting earlier runs. Record query changes and rationale.

## Output

`03-literature/search-protocol.md`, timestamped raw result files, `records.jsonl`, and `search-log.csv`.

## Quality checks

- Every record is traceable to a query and provider.
- Reported counts reconcile from retrieved to deduplicated records.
- Rate limits, partial pages, and unavailable providers are explicit.
- A second provider can replace the first without changing the workflow.
