---
id: alem-research-brain-log
type: activity-log
status: maintained
created: 2026-11-03
updated: 2026-11-13
tags: [log, brain]
---

# Brain log

Append-only record of meaningful brain operations. Each entry records the date, operation,
artifact or pages affected, and provenance or uncertainty when relevant.

## [2026-11-03] setup | Obsidian brain initialized

- Linked `knowledge/` to the canonical repository wiki at `../knowledge/`.
- Added the brain index, operating contract, and maintenance rules.
- No research claims were added or changed.
- Plugin state was inspected but not modified.

## [2026-11-03] maintenance | Alem 1.0 integration and context architecture implemented

- `verified_evidence`: repository code and automated tests now implement lazy task-context routing,
  capability contracts, artifact provenance, resumable workflows, and integration maturity/trust
  validation.
- Product metadata was advanced to `1.0.0`; extension API `1.0`, manifest schema `1`, and workspace
  schema `1` remain the stable compatibility boundaries.
- Validation recorded 50 passing tests, one Windows privilege-dependent skip, strict health with no
  warnings, integration/workflow validation, dependency consistency, and a successful wheel build.
- No academic research claim was promoted into the shared knowledge wiki; the durable technical
  decision and its limitations are maintained in repository architecture and release documents.

## [2026-11-10] maintenance | Three user-selected writing/provenance skills added

- `verified_evidence`: added `humanizer`, `academic-humanizer`, and the primary `remove-ai-marks`
  skill from their pinned GitHub main-branch revisions under the canonical `skills/` tree.
- Recorded upstream repositories, revisions, MIT license links, imported paths, and scope limits in
  `docs/upstream-register.toml`.
- Fixed Alem context metadata parsing for YAML block-scalar skill descriptions and added a regression
  test; context rebuild and targeted searches now expose all three skills by their real descriptions.
- The watermark repository's optional `clean-user-facing-text` companion was not imported; the
  request was kept to three skills. No academic knowledge claim was promoted.

## [2026-11-13] maintenance | Owl CLI and model gateway implementation

- `verified_evidence`: repository code and automated checks added the owl-branded terminal layer,
  workspace-local model configuration/credentials, explicit provider support states, and the
  contract-validated `model_completion` gateway. Evidence: `src/alem/terminal/`, `src/alem/models.py`,
  `contracts/capabilities/model_completion/1.0.json`, and `tests/test_models.py`.
- Technical decision: direct API-key and local OpenAI-compatible/Anthropic protocol paths are
  implemented in the core gateway; subscription OAuth remains explicitly unsupported unless a
  documented official runtime is added. Existing plugin and Feynman governance was preserved.
- No academic research claim was promoted into the shared knowledge wiki. Community plugins were
  not installed or enabled; the change is maintained in project code and model-provider docs.

## [2026-11-13] correction | Persistent terminal interface

- `verified_evidence`: the earlier static dashboard exited immediately and the captured PTY had
  `NO_COLOR=1` and `TERM=dumb`, which explained the monochrome owl. The new Textual app remains
  open, accepts composer input, and renders the owl's five palette colors in a truecolor PTY.
- Added SSE response handling through the existing model capability boundary and mapped `/lit`
  and `/deepresearch` to existing workflow starts. No academic claim was promoted.
- Subsequent maintenance added hidden in-TUI API-key setup, 256-color rendering verification,
  resize coverage, and explicit no-model/provider-error checks. Native Windows Terminal visuals
  and live provider calls were not verified.

## [2026-11-13] correction | Interactive model selection

- `verified_evidence`: Alem now opens a keyboard-driven provider/model picker from `/model` or
  Ctrl+M, persists the chosen reference, offers hidden API-key setup for unconfigured providers,
  and reads installed model IDs from local `/models` endpoints before offering them. Evidence:
  `src/alem/terminal/model_picker.py`, `src/alem/models.py`, and `tests/test_tui.py`.
- Design source retrieved 2026-11-13: archived `opencode-ai/opencode` commit
  `73ee493265acf15fcd8caab2bc8cd3bd375b63cb`,
  `internal/tui/components/dialog/models.go` and `internal/tui/tui.go` (provider navigation,
  selection message, and model update path). Alem uses its own gateway and persisted state.
- Verification: 81 tests passed, one Windows symbolic-link privilege skip; strict health and
  Ruff checks passed. Live provider response and native Windows Terminal visuals remain unverified.
- No academic research claim was promoted into the shared knowledge wiki.
