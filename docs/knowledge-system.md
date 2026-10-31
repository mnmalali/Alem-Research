# Knowledge system

`knowledge/` is an Obsidian-compatible Markdown wiki for durable, shared knowledge. Individual projects keep their own evidence and only promote broadly reusable findings through `workflows/knowledge-update.yaml`.

## Page contract

Every page has YAML frontmatter with a stable `id`, `type`, lifecycle `status`, creation/update dates, and tags. Factual claims include a nearby source reference or a link to an evidence record. Wikilinks connect concepts, people, methods, papers, datasets, questions, findings, and debates.

Use these evidence labels in prose or structured records:

- `verified_evidence`: checked against the cited source.
- `reported_finding`: accurately attributed to a source but not independently reproduced.
- `interpretation`: analyst synthesis derived from identified evidence.
- `hypothesis`: testable proposition, not a finding.
- `unverified`: lead requiring verification.

## Controlled updates

1. Read the index and related pages.
2. Prepare a change proposal with sources, affected pages, new links, and contradictions.
3. Validate frontmatter, identifiers, and backlinks.
4. Apply additive edits; retain conflicting claims with explicit attribution.
5. Update `knowledge/index.md` and append `knowledge/CHANGELOG.md`.
6. Review the Git diff before committing.

Do not rewrite the wiki after every interaction. Promote only reusable, supported knowledge.
