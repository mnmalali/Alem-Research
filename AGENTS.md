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

## Persistent Obsidian brain

The Obsidian vault is `alem research brain/`. It is the project-facing view of the shared
knowledge wiki; `alem research brain/knowledge/` is a directory junction to the canonical
repository folder `knowledge/`. Treat the repository files as the durable source of truth.

Before answering a research or project question:

1. Read `alem research brain/index.md` and `alem research brain/log.md`.
2. Search `alem research brain/knowledge/` and read the relevant linked pages.
3. Read the active project's `PROJECT.md`, evidence records, and status files when the question
   concerns a specific project.
4. Distinguish recalled brain content from newly verified evidence; do not present an old or
   unverified note as current fact without checking it.

At the end of a conversation, perform a brain-maintenance check. Update the brain only when the
conversation produced reusable, supported knowledge, a durable project decision, a new source,
or a meaningful contradiction or correction. Use `workflows/knowledge-update.yaml` for shared
knowledge promotion; do not promote casual chat, unsupported speculation, secrets, PDFs, or
project-sensitive material. Append a concise entry to `alem research brain/log.md` for an
ingest, query that produced a filed artifact, correction, or maintenance pass. If no durable
change is warranted, do not create noise; record the decision only in the handoff when useful.

Every brain update must preserve provenance, use the evidence-status labels, update backlinks and
the index when pages change, and review the diff before reporting completion. Human approval gates
in rule 12 still apply.

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
