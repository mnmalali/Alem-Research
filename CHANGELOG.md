# Changelog

All notable changes are recorded here. Alem uses semantic versioning for releases and separately
versions its extension API and persisted schemas.

## 0.1.0 — unreleased foundation

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
