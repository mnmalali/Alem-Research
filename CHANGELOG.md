# Changelog

All notable changes are recorded here. Alem uses semantic versioning for releases and separately
versions its extension API and persisted schemas.

## Unreleased

### Added

- Keyboard-driven model picker with provider navigation, guided API-key setup,
  live local model discovery, and persisted selection in the research TUI.

- Persistent Textual research interface with composer, activity stream, model
  selection, provider status, cancellation, and workflow command dispatch.

- Purple/amber owl terminal dashboard with safe TTY, `NO_COLOR`, `TERM=dumb`,
  Windows, narrow-column, and legacy-encoding fallbacks.
- Workspace-local `model_completion` capability contract and provider-neutral
  gateway for tested OpenAI-compatible and Anthropic API-key/local protocols.
- `alem model` commands for provider/model catalog inspection, secure API-key
  setup, selection, status, diagnostics, endpoint configuration, and fallbacks.
- Explicit catalogued/unsupported provider states so ChatGPT/Claude subscription
  OAuth is not confused with API access or emulated through private flows.

### Documentation

- Added CLI dashboard, provider setup, support matrix, local endpoint, and model
  security guides.

## 1.0.0 — 2026-11-03

### Added

- Lazy, task-scoped context routing with compact indexes, explainable plans, activation records,
  budgets, explicit includes/excludes, and eager-mode compatibility.
- The always-discoverable `alem-router` skill with progressive context disclosure.
- Machine-readable JSON capability contracts with provider input/output validation.
- Typed project artifact records with evidence status, lineage, source, and digest verification.
- Resumable workflow runs, capability steps, durable state, expected-output checks, and recorded
  human approval gates.
- Canonical integration maturity/trust registry with catalogue and plugin consistency validation.
- Runtime dependencies on PyYAML and jsonschema for workflow and contract validation.

### Changed

- New workspaces use lazy context mode: only the router is exposed to coding agents at startup.
- Enabled integrations remain available through the capability gateway without placing their
  implementation or every skill description in the initial model context.
- Feynman's canonical integration status now matches its implemented community bridge.
- Product and citation metadata are `1.0.0`; extension API remains compatible at `1.0` and plugin
  manifest schema remains `1`.

### Compatibility

- Workspaces without a `[context]` table retain eager adapter behavior.
- Integration registry schema 1 remains readable; the canonical registry now uses schema 2.

## 0.2.0 — 2026-10-31

### Added

- Workspace-local Feynman `research_agent` bridge using the pinned `0.5.61` CLI runtime.
- Curated Orchestra Research skill assets with namespaced Codex and Claude adapters.
- Offline Wenyu research-skill and Awesome AI Research Tools discovery capabilities.
- Upstream integration records, attribution notices, and contributor guidance for adding tools.
- Automatic installation and enablement of official plugins during `alem setup`.
- Explicit `verified`/`unverified` trust classification for opt-in community plugins.

### Changed

- The Alem package and citation metadata are now version `0.2.0`.

## 0.1.0 — 2026-10-30

### Added

- Local-only workspace bootstrap, diagnostics, project creation/export, and knowledge indexing.
- Shared Codex/Claude instructions, 16 canonical research skills, 8 agent contracts, and resumable
  lifecycle workflows.
- Extension API/manifest v1 with catalogue discovery, dependency planning, two approval gates,
  digest validation, capability routing, and subprocess execution.
- Interchangeable OpenAlex and Semantic Scholar providers plus a third-party static example.
- Upstream source/license audit, public contribution guidance, CI, tests, and manual checks.

### Security note

- Plugin subprocesses are not operating-system sandboxes. The limitation is intentional and
  documented rather than represented as isolation.
