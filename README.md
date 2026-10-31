# Alem Research

> **Foundation release:** Alem is usable for local project setup, knowledge management, structured
> research planning, and workspace-local plugins. Third-party plugin processes are **not** an
> operating-system sandbox. Review requested permissions and code before approval.

**Your research. Your knowledge. Your AI research workspace.**

Alem Research is a local-first, open-source workspace that gives Codex and Claude Code shared
research instructions, persistent evidence, specialist roles, reproducible project structure, and
provider-neutral integrations. It is a research environment—not a general chatbot and not a hosted
service.

## Start in three commands

Python 3.11 or newer and Git are the only core prerequisites. No global Alem installation is needed.

```bash
git clone https://github.com/alem-research/alem-research.git
cd alem-research
sh ./alem setup --create-venv
./alem health
./alem project create "My research topic"
```

On Windows PowerShell, replace `./alem` with `.\alem.ps1`.

Setup writes mutable state and optional dependencies only beneath `.alem/` in this checkout. It
generates project-local Codex and Claude Code skill adapters and does not touch `~/.codex`,
`~/.claude`, `~/.agents`, or a global Python/Node environment.

## What works now

| Capability | Foundation status |
| --- | --- |
| Numbered, resumable research project template | Implemented |
| Obsidian-compatible Markdown knowledge and provenance | Implemented |
| 16 lifecycle skills and 8 specialist agent contracts | Implemented |
| Codex/Claude project-local discovery adapters | Implemented; manual client verification required |
| Plugin manifest/API v1, validation, registry, dependencies, approvals | Implemented |
| Install, enable, disable, update, remove, and invoke plugins | Implemented |
| OpenAlex and Semantic Scholar academic search providers | Implemented; live service availability varies |
| Third-party plugin lifecycle demonstration | Implemented and automated |
| Zotero, PDF extraction, Crossref, arXiv, PubMed, Europe PMC | Planned, not represented as complete |

See [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) for evidence and [`TODO.md`](TODO.md)
for release blockers.

## Use provider-neutral research tools

Workflows ask for capabilities such as `academic_search`; they do not import a provider. Inspect the
checked-in catalogue, then use separate installation and execution approvals:

```bash
./alem plugin search academic
./alem plugin validate plugins/official/openalex
./alem plugin install org.alem.openalex --approve
./alem plugin enable org.alem.openalex --approve
./alem capability invoke academic_search --input '{"query":"open science", "limit":3}'
```

Install and enable `org.alem.semantic-scholar` to make the configured fallback available. Search
queries are then sent to the selected external service; they are not private local processing.

To prove the public API works without network access, use the community example:

```bash
./alem plugin install dev.community.static-search --approve
./alem plugin enable dev.community.static-search --approve
./alem capability invoke academic_search --provider dev.community.static-search --input '{"query":"demo"}'
./alem plugin disable dev.community.static-search
./alem plugin remove dev.community.static-search --yes --purge-data
```

## Develop a plugin

Generate a functional, tested starter rather than copying core internals:

```bash
./alem plugin create "My metadata provider" --id community.my-metadata
./alem plugin validate plugins/community/my-metadata-provider
```

The stable public surface, manifest fields, permission model, templates, tests, and contribution
process are in [`docs/plugin-development.md`](docs/plugin-development.md) and
[`CONTRIBUTING-PLUGINS.md`](CONTRIBUTING-PLUGINS.md).

## Preserve evidence, not chat memory

Every lifecycle stage writes structured files that a later agent session can reopen. Source records
separate verified metadata and reported findings from interpretation, hypothesis, and uncertainty.
Important choices require human approval: the final research question, methodology, consequential
data collection, analysis choices, and final manuscript.

Refresh the maintained wiki index only when knowledge has been reviewed:

```bash
./alem knowledge index
```

Do not label a review systematic unless its protocol, databases, queries, dates, screening counts,
criteria, and exclusions support that claim.

## Documentation

- [Getting started](docs/getting-started.md)
- [Architecture](docs/architecture.md)
- [Research lifecycle](docs/research-lifecycle.md)
- [Knowledge system](docs/knowledge-system.md)
- [Plugin development](docs/plugin-development.md)
- [Plugin security limitations](docs/plugin-security.md)
- [Integrations](docs/integrations.md)
- [Upstream source and license audit](docs/upstream-audit.md)
- [Manual release validation](docs/manual-validation.md)
- [Contributing](CONTRIBUTING.md)

## License

Alem Research is released under the [MIT License](LICENSE). Referenced upstream projects retain
their own licenses. No upstream project audited for this release is silently vendored into Alem.
