---
name: citation-verification
description: Verify source identity and whether each citation supports the specific manuscript claim.
---

# Citation verification

## Inputs

Manuscript, bibliography, claim-to-evidence map, accessible source text/metadata, and verification scope.

## Procedure

1. Inventory all citations and uncited factual claims.
2. Use `citation_verify` or authoritative metadata sources to verify identity, authors, title, venue, year, DOI, version, correction/retraction status, and accessibility.
3. Read the relevant source section and judge support as direct, partial, contextual, contradictory, or not verified; record page/section.
4. Check citation placement, quotation accuracy, secondary-citation risks, and reference-list/orphan mismatches.
5. Flag rather than repair uncertain metadata by guesswork. Return unsupported claims to the author.

## Output

`14-citations/citation-ledger.csv`, issue report, verified bibliography, and unresolved action list.

## Quality checks

- Verification covers claim support, not metadata alone.
- Exact quotations match the source/version.
- Retractions and corrections are surfaced.
- “Verified” includes verifier, date, and source.
