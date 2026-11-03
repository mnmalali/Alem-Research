---
id: alem-research-brain
type: system-guide
status: maintained
created: 2026-11-03
updated: 2026-11-03
tags: [alem, brain, obsidian]
---

# Alem Research Brain

This Obsidian vault is the project-facing interface for Alem's persistent research memory.

Start with [[index]] and [[log]]. The `knowledge/` folder is linked to the repository's canonical
`knowledge/` directory, so edits made here are durable repository edits rather than a copied cache.

## Operating contract

- Read the index, log, and relevant knowledge pages before answering research questions.
- Preserve provenance and label claims as `verified_evidence`, `reported_finding`, `interpretation`,
  `hypothesis`, or `unverified`.
- Add or revise pages only when the conversation creates reusable, supported knowledge.
- Use the repository's `workflows/knowledge-update.yaml` for shared-knowledge promotion.
- Keep raw sources immutable and do not store secrets, PDFs, runtime state, or caches here.
- Append meaningful maintenance events to [[log]]; do not log every trivial exchange.

## Canonical locations

- Shared wiki: [[knowledge/index|knowledge index]]
- Change history: [[knowledge/CHANGELOG|knowledge changelog]]
- Update workflow: `../workflows/knowledge-update.yaml`
- Agent contract: `../AGENTS.md`
