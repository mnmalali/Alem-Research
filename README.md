<p align="center">
  <img src="docs/assets/alem-research-banner.png" alt="Alem Research — Research deeper with AI" width="100%">
</p>

<h1 align="center">Alem Research</h1>

<p align="center">
  <strong>A local-first, extensible AI research workspace for rigorous and reproducible inquiry.</strong>
</p>

<p align="center">
  <a href="https://github.com/mnmalali/Alem-Research/actions/workflows/ci.yml"><img src="https://github.com/mnmalali/Alem-Research/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-cb8a58.svg" alt="MIT License"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11%2B-3776ab.svg" alt="Python 3.11 or newer"></a>
  <a href="CITATION.cff"><img src="https://img.shields.io/badge/cite-CITATION.cff-8c6f56.svg" alt="Cite Alem Research"></a>
</p>

<p align="center">
  <a href="#why-alem">Why Alem</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#extension-framework">Extensions</a> ·
  <a href="#documentation">Documentation</a> ·
  <a href="#citation">Citation</a>
</p>

> [!IMPORTANT]
> **Foundation release:** Alem is ready for local workspace setup, structured research projects,
> knowledge management, and workspace-local plugins. Third-party plugin processes are not an
> operating-system sandbox. Review their code and requested permissions before approval.

## Why Alem

Research with AI should produce more than a transient conversation. Alem turns research activity
into an inspectable workspace of questions, sources, decisions, evidence, analysis, and reusable
knowledge.

It gives Codex and Claude Code the same project-local research instructions while keeping the core
independent of any single coding agent, search provider, model, or external service.

| Principle | What it means in practice |
| --- | --- |
| **Local first** | Projects, knowledge, configuration, plugins, and mutable state remain inside the repository. |
| **Evidence before claims** | Workflows preserve provenance and separate verified facts from interpretation and uncertainty. |
| **Provider neutral** | Workflows request capabilities such as `academic_search`, not hardcoded services. |
| **Human controlled** | Important research decisions and all third-party plugin execution require explicit approval. |
| **Reproducible by design** | Numbered lifecycle stages, run records, citation ledgers, and release checklists make work recoverable. |

## What is included

| Area | Foundation capability |
| --- | --- |
| Research lifecycle | A resumable 16-stage project structure from ideation through publication |
| Research practice | 16 reusable skills and 8 specialist agent contracts |
| Knowledge | An Obsidian-compatible Markdown wiki with provenance-aware templates |
| Extensions | Versioned APIs for tools, skills, agents, and workflows |
| Academic search | Interchangeable OpenAlex and Semantic Scholar providers |
| Upstream integrations | Feynman bridge, curated research skills, and offline tool/skill catalogs |
| Coding agents | Project-local discovery adapters for Codex and Claude Code |
| Governance | Plugin approvals, manifest validation, dependency locking, and documented security limits |
| Community | A repository catalogue, plugin starter kit, examples, tests, and contribution guidance |

The detailed implementation evidence and known limitations are maintained in
[`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) and [`TODO.md`](TODO.md).

## Quick start

### Requirements

- Python 3.11 or newer
- Git
- Codex or Claude Code is optional; the Alem CLI also works independently

No global Alem installation is required.

### Windows PowerShell

```powershell
git clone https://github.com/mnmalali/Alem-Research.git alem-research
cd alem-research
.\alem.ps1 setup --create-venv
.\alem.ps1 health --strict
.\alem.ps1 project create "My research topic"
```

### macOS or Linux

```bash
git clone https://github.com/mnmalali/Alem-Research.git alem-research
cd alem-research
./alem setup --create-venv
./alem health --strict
./alem project create "My research topic"
```

Setup writes mutable state and optional dependencies beneath `.alem/` in the checkout. It does not
modify `~/.codex`, `~/.claude`, `~/.agents`, or a global Python or Node environment.

## Research workspace

Every project begins with a consistent structure that can be resumed by a later person or agent:

```text
projects/<project>/
├── 01-ideation/          Candidate directions
├── 03-literature/        Search protocol and source trail
├── 05-question/          Approved research question
├── 06-methodology/       Reproducible protocol
├── 09-experiments/       Plans and run registry
├── 10-analysis/          Analysis artifacts
├── 13-paper/             Manuscript
├── 14-citations/         Citation ledger
├── 16-publication/       Release and reproducibility checks
└── provenance/           Evidence and decision history
```

The omitted numbers are present in generated projects; the abbreviated tree highlights the major
checkpoints. See the [research lifecycle](docs/research-lifecycle.md) for the complete model.

## Extension framework

Alem workflows depend on abstract, versioned capabilities. Multiple plugins can provide the same
capability, and users can choose a default provider with ordered fallbacks.

```text
Research workflow
      │
      ▼
academic_search capability
      │
      ├── OpenAlex
      ├── Semantic Scholar
      └── Community provider
```

Supplied research tools are integrated through the same workspace-local extension system. The
current upstream integrations and their limits are documented in
[`docs/upstream-integrations.md`](docs/upstream-integrations.md). Catalog plugins discover
candidates; they do not silently install or trust linked projects.

Inspect the catalogue and invoke an academic-search provider:

```bash
./alem plugin search academic
./alem plugin validate plugins/official/openalex
./alem plugin install org.alem.openalex --approve
./alem plugin enable org.alem.openalex --approve
./alem capability invoke academic_search --input '{"query":"open science","limit":3}'
```

Install and enable `org.alem.semantic-scholar` to make the configured fallback available. Queries
sent to external providers are network requests and should not be treated as private local
processing.

### Build a plugin

Create a tested plugin without importing Alem internals:

```bash
./alem plugin create "My metadata provider" --id community.my-metadata
./alem plugin validate plugins/community/my-metadata-provider
```

The stable public API, manifest specification, permission model, templates, automated tests, and
submission process are documented in the [plugin development guide](docs/plugin-development.md)
and [plugin contribution guide](CONTRIBUTING-PLUGINS.md).

## Knowledge that survives the session

Alem's shared knowledge layer stores sourced concepts, datasets, debates, findings, methods,
papers, questions, and researcher records as ordinary Markdown. Promote reviewed information into
the maintained index with:

```bash
./alem knowledge index
```

Do not label a review systematic unless its protocol, databases, exact queries, dates, screening
counts, eligibility criteria, and exclusions support that claim.

## Security and privacy

- Plugin installation and execution require separate, explicit approval.
- Dependencies are pinned, workspace-local, and checked against recorded digests.
- Plugin manifests declare requested network, filesystem, credential, and execution permissions.
- Permission declarations are policy and audit information—not an OS security boundary.
- Privacy-aware exports exclude common secrets, credentials, raw sensitive data, and unsafe links.

Read the [plugin security model](docs/plugin-security.md), [privacy guidance](docs/privacy-and-security.md),
and [security policy](SECURITY.md) before enabling third-party code.

## Documentation

| Guide | Purpose |
| --- | --- |
| [Getting started](docs/getting-started.md) | Setup, health checks, and the first project |
| [Architecture](docs/architecture.md) | Core boundaries, extension contracts, and routing |
| [Research lifecycle](docs/research-lifecycle.md) | The end-to-end research process |
| [Knowledge system](docs/knowledge-system.md) | Wiki structure, provenance, and maintenance |
| [Plugin development](docs/plugin-development.md) | Public API, manifests, templates, and testing |
| [Integrations](docs/integrations.md) | Implemented and planned external services |
| [Validation report](docs/validation-report.md) | Automated and manual verification evidence |
| [Upstream audit](docs/upstream-audit.md) | Source, license, and adoption decisions |

## Development

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest
alem health --strict
```

CI exercises Python 3.11 and 3.13 on Linux, Windows, and macOS. Contributions are welcome; begin
with [`CONTRIBUTING.md`](CONTRIBUTING.md) or [`CONTRIBUTING-PLUGINS.md`](CONTRIBUTING-PLUGINS.md).

## Citation

Alem Research was created and is maintained by
[Mohamad Numan Alali](https://github.com/mnmalali). If you use it in academic or professional work,
please cite the software. GitHub and compatible reference managers can read the full metadata from
[`CITATION.cff`](CITATION.cff).

```bibtex
@software{alem_research_2026,
  author  = {Mohamad Numan Alali},
  title   = {Alem Research: An Open-Source AI Research Workspace},
  year    = {2026},
  version = {0.2.0},
  url     = {https://github.com/mnmalali/Alem-Research},
  license = {MIT}
}
```

## License

Alem Research is released under the [MIT License](LICENSE). Referenced upstream projects retain
their own licenses. No audited upstream project is silently vendored into Alem.

---

<p align="center">
  <strong>Research deeper. Preserve the evidence. Keep control of the process.</strong>
</p>
