<p align="center">
  <img src="docs/assets/alem-research-banner.png" alt="Alem Research — Research deeper with AI" width="100%">
</p>

<h1 align="center">Alem Research🦉</h1>

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
  <a href="#whats-new-in-10">What’s new in 1.0</a> ·
  <a href="#why-alem">Why Alem</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#extension-framework">Extensions</a> ·
  <a href="#documentation">Documentation</a> ·
  <a href="#citation">Citation</a>
</p>

> [!IMPORTANT]
> **Stable 1.0 release:** Alem provides task-scoped context routing, resumable research workflows,
> provenance-preserving artifacts, and workspace-local integrations. Third-party processes are not an
> operating-system sandbox. Review their code and requested permissions before approval.

## What’s new in 1.0

Alem 1.0 turns the workspace into a scalable integration platform for AI research tools. GitHub
projects can be adapted behind stable Alem capabilities and used together without placing every
installed tool, skill, or provider into every agent conversation.

| Improvement | What it provides |
| --- | --- |
| Task-scoped context | The `alem-router` selects only the skills and capabilities relevant to the current request. |
| Constant startup footprint | Adding more integrations does not add more startup adapters in the default lazy mode. |
| Composable integrations | Providers exchange contract-validated results and durable artifact references. |
| Resumable research | Workflow runs preserve stage state, evidence, outputs, failures, and human decisions. |
| Transparent trust | Integration maturity, review status, permissions, and execution approval remain separate. |
| Stable contracts | Alem `1.0.0` keeps extension API `1.0`, plugin manifest schema `1`, and workspace schema `1`. |

```text
Research task
     │
     ▼
Alem context router ── selects a small task-specific toolset
     │
     ▼
Capability gateway ── routes to approved default and fallback providers
     │
     ▼
Project artifacts ── preserve evidence, provenance, lineage, and integrity
```

The complete implementation and validation evidence is recorded in
[`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md),
[`CHANGELOG.md`](CHANGELOG.md), and the
[`1.0 validation report`](docs/validation-report.md).

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
| **Human controlled** | Consequential research decisions and external writes retain explicit approval gates; accepted tool releases are maintainer-reviewed and managed automatically. |
| **Reproducible by design** | Numbered lifecycle stages, run records, citation ledgers, and release checklists make work recoverable. |

## What is included

| Area | Stable capability |
| --- | --- |
| Research lifecycle | A resumable 16-stage project structure from ideation through publication |
| Research practice | 16 specialist skills, one lazy context router, and 8 agent contracts |
| Knowledge | An Obsidian-compatible Markdown wiki with provenance-aware templates |
| Context | Task planning loads only the smallest relevant set of installed skills and capabilities |
| Extensions | Versioned APIs and machine-readable capability contracts |
| Workflows | Executable, resumable state with artifact records and human approval gates |
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
.\alem.ps1 context plan "Find papers and verify the citations"
```

### macOS or Linux

```bash
git clone https://github.com/mnmalali/Alem-Research.git alem-research
cd alem-research
./alem setup --create-venv
./alem health --strict
./alem project create "My research topic"
./alem context plan "Find papers and verify the citations"
```

Setup writes mutable state and optional dependencies beneath `.alem/` in the checkout. It does not
modify `~/.codex`, `~/.claude`, `~/.agents`, or a global Python or Node environment.

Lazy context mode is the default. Setup makes the `alem-router` skill discoverable and keeps the
rest of the installed ecosystem in a compact local index. A task plan selects the relevant skill
files and capabilities without placing every integration in the agent's starting context:

```bash
./alem context plan "Extract evidence from these papers and verify the manuscript citations"
./alem context explain <plan-id>
./alem context activate <plan-id>
```

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

Capability requests and responses are validated against contracts under `contracts/capabilities/`.
Large results are written as project artifacts with source, evidence status, lineage, and a digest;
the conversation needs only their compact references. Installed, enabled, execution-approved, and
task-activated are separate states.

Setup provisions every maintainer-accepted release automatically, including both Alem-authored and
community-contributed tools. Inspect acceptance and readiness with:

```bash
./alem tools list
./alem tools status org.alem.openalex
./alem tools doctor
./alem capability invoke academic_search --input '{"query":"open science","limit":3}'
```

`alem update` reconciles accepted integration versions in the release already present locally; it
does not self-update Alem core. A provider that needs credentials, hardware, a runtime, or a live
service remains listed with a readiness status. Queries sent to external providers are network
requests and should not be treated as private local processing.

### Plugin catalogue

The checked-in [plugin catalogue](catalogue/index.toml) lists discoverable sources. The
maintainer-controlled [`integrations/registry.toml`](integrations/registry.toml) determines which
exact releases are accepted and provisioned automatically by `alem setup` and `alem update`.
Catalogue verification, acceptance, authorship, and runtime readiness are separate states. A
community badge is attribution only; accepted Alem-authored and community-contributed tools use
the same managed installation and routing policy. Catalog-only candidates are never provisioned.

#### Official plugins

| Plugin | Capability | Description |
| --- | --- | --- |
| [`org.alem.openalex`](plugins/official/openalex) | `academic_search` | Search scholarly works through OpenAlex. |
| [`org.alem.semantic-scholar`](plugins/official/semantic-scholar) | `academic_search` | Search scholarly works through Semantic Scholar. |

#### Community plugins

| Plugin | Catalogue verification | Acceptance | Capability | Description |
| --- | --- | --- | --- |
| [`community.feynman-bridge`](plugins/community/feynman-bridge) | Verified | Candidate | `research_agent` | Bridge candidate; upstream runtime is not managed by Alem yet. |
| [`community.orchestra-research-skills`](plugins/community/orchestra-research-skills) | Verified | Accepted | skills | Curated, namespaced research skills from Orchestra Research. |
| [`community.wenyu-research-catalog`](plugins/community/wenyu-research-catalog) | Verified | Accepted | `research_skill_catalog` | Offline catalog of research skills and runtime requirements. |
| [`community.awesome-research-tools-catalog`](plugins/community/awesome-research-tools-catalog) | Verified | Accepted | `research_tool_catalog` | Offline discovery catalog of research tools. |
| [`dev.community.static-search`](examples/plugins/community-static-search) | Verified | Candidate | `academic_search` | Deterministic example plugin used for lifecycle tests and learning. |

The list below includes catalog entries whether accepted or candidate. Check `alem tools list` for
the accepted release set and readiness. A catalog discovery result is not an endorsement, accepted
tool, or automatic install target. Readiness does not endorse claims or imply a security sandbox.
The `community.*` plugin namespace is not an authorship badge; this release's accepted catalog
adapters are marked `alem-official` in the release registry, while the automated acceptance fixture
also verifies the same path for a `community-contributor` release.

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

- Locally installed candidate plugins require separate explicit installation and execution approval; accepted releases are reviewed through the maintainer-controlled registry.
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
| [Context routing](docs/context-routing.md) | Lazy task selection, activation, and context budgets |
| [Capability contracts](docs/capability-contracts.md) | Validated provider I/O and artifact provenance |
| [Workflow runtime](docs/workflow-runtime.md) | Resumable runs and human approval gates |
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
  version = {1.0.0},
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
