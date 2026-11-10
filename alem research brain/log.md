---
id: alem-research-brain-log
type: activity-log
status: maintained
created: 2026-11-03
updated: 2026-11-03
tags: [log, brain]
---

# Brain log

Append-only record of meaningful brain operations. Each entry records the date, operation,
artifact or pages affected, and provenance or uncertainty when relevant.

## [2026-11-03] setup | Obsidian brain initialized

- Linked `knowledge/` to the canonical repository wiki at `../knowledge/`.
- Added the brain index, operating contract, and maintenance rules.
- No research claims were added or changed.
- Plugin state was inspected but not modified.

## [2026-11-03] maintenance | Alem 1.0 integration and context architecture implemented

- `verified_evidence`: repository code and automated tests now implement lazy task-context routing,
  capability contracts, artifact provenance, resumable workflows, and integration maturity/trust
  validation.
- Product metadata was advanced to `1.0.0`; extension API `1.0`, manifest schema `1`, and workspace
  schema `1` remain the stable compatibility boundaries.
- Validation recorded 50 passing tests, one Windows privilege-dependent skip, strict health with no
  warnings, integration/workflow validation, dependency consistency, and a successful wheel build.
- No academic research claim was promoted into the shared knowledge wiki; the durable technical
  decision and its limitations are maintained in repository architecture and release documents.

## [2026-11-10] maintenance | Three user-selected writing/provenance skills added

- `verified_evidence`: added `humanizer`, `academic-humanizer`, and the primary `remove-ai-marks`
  skill from their pinned GitHub main-branch revisions under the canonical `skills/` tree.
- Recorded upstream repositories, revisions, MIT license links, imported paths, and scope limits in
  `docs/upstream-register.toml`.
- Fixed Alem context metadata parsing for YAML block-scalar skill descriptions and added a regression
  test; context rebuild and targeted searches now expose all three skills by their real descriptions.
- The watermark repository's optional `clean-user-facing-text` companion was not imported; the
  request was kept to three skills. No academic knowledge claim was promoted.
