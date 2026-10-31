# Implementation status

Status is evidence-based: `implemented` means code or content exists; `verified` additionally means
the recorded automated or manual check passed.

| Area | Status | Evidence |
| --- | --- | --- |
| Local workspace and CLI bootstrap | Implemented; verified on Windows | `alem`, `alem.ps1`, `src/alem/`, automated CLI tests |
| Workspace-local setup and health | Implemented; verified on Windows | `alem setup`, `alem health --strict`, path-containment tests |
| Knowledge wiki and controlled index | Implemented; automated verification passed | `knowledge/`, `alem knowledge index`, preservation tests |
| Project template and lifecycle | Implemented; automated verification passed | `templates/project/`, `workflows/`, create/export tests |
| Core skills and agents | Implemented; manual agent verification pending | 16 `skills/`, 8 `agents/`, contract checks |
| Extension API and registry | Implemented; 21 extension tests passed | `src/alem/extensions/`, `docs/validation-report.md` |
| Two academic-search providers | Implemented; OpenAlex live smoke passed, Semantic Scholar returned HTTP 429 | `plugins/official/`, mocked normalization/fallback tests |
| Third-party plugin lifecycle proof | Implemented; automated and CLI lifecycle verification passed | `examples/plugins/`, `docs/validation-report.md` |
| Codex and Claude Code loading | Files implemented; live loading blocked by local client/auth errors | `AGENTS.md`, `CLAUDE.md`, adapters, `docs/validation-report.md` |
| Additional research integrations | Planned | `integrations/registry.toml` |
| Cross-platform release tests | Not yet run | `docs/manual-validation.md` |
