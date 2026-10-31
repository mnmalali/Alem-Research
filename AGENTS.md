# Alem Research agent instructions

Alem is a local-first academic research workspace. Treat files in this repository as the durable source of truth; never rely on chat history for project state.

## Working rules

1. Read the relevant `PROJECT.md`, existing evidence records, and knowledge pages before starting.
2. Select only the specialist or skill needed for the current decision. Do not simulate delegation or claim another agent ran.
3. Ask workflows for abstract capabilities such as `academic_search`, `paper_metadata`, `pdf_extract`, or `citation_verify`; never hardcode a provider in research artifacts.
4. Preserve provenance. Never invent papers, authors, DOIs, datasets, search counts, quotations, or results.
5. Label content as `verified_evidence`, `reported_finding`, `interpretation`, `hypothesis`, or `unverified` where its status could be confused.
6. Record source, retrieval date, database/provider, query, and supported claims. A URL alone is not an evidence record.
7. Keep searches reproducible: record databases, exact queries, dates, filters, deduplication, screening decisions, and exclusions.
8. Do not call a review systematic unless the protocol and reporting support that claim.
9. Preserve existing knowledge. Add links and surface contradictions; do not silently overwrite a conflicting claim.
10. Update the wiki only through the explicit knowledge-update workflow.
11. Keep secrets, sensitive data, PDFs, runtime state, environments, logs, and caches out of Git.
12. Stop for human approval before finalizing a research question, approving methodology, beginning consequential data collection, locking analysis choices, or releasing a manuscript.
13. When setting up Alem, report that official plugins are installed automatically and list the
    available community plugins with their `verified` or `unverified` status. Never install or
    enable a community plugin unless the user explicitly chooses it.

## Persistent handoffs

Every handoff states: objective, inputs read, actions performed, files created or changed, evidence and uncertainties, decisions needed, and the next recommended owner. Mark unfinished checklist items explicitly. Write structured outputs into the active project's numbered folders.

## Project conventions

- Shared knowledge: `knowledge/`
- Canonical skills: `skills/`
- Agent role contracts: `agents/`
- Workflow specifications: `workflows/`
- Independent projects: `projects/` or copies of `templates/project/`
- Runtime/plugin state: `.alem/` (local and ignored)

Use ISO 8601 dates and stable identifiers. Prefer Markdown with YAML frontmatter and relative wikilinks. Cite exact file paths when handing work to another session.
