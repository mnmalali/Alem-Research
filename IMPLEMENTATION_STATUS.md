# Implementation status

Release target: `1.0.0`

Status is evidence-based: `implemented` means code or content exists; `verified` means a recorded
automated or manual check passed. External services and coding-agent clients remain independently
versioned systems.

| Area | Status | Evidence |
| --- | --- | --- |
| Local workspace and CLI | Implemented; locally verified on Windows | `src/alem/`, CLI and containment tests |
| Lazy context routing | Implemented; automated tests passed | `src/alem/context.py`, `skills/alem-router/`, context tests |
| Capability contracts | Implemented; automated validation passed | `contracts/capabilities/`, contract tests |
| Typed artifact provenance | Implemented; tamper test passed | `src/alem/artifacts.py`, artifact tests |
| Resumable workflow engine | Implemented; gate/resume tests passed | `src/alem/workflows.py`, all bundled workflows validate |
| Knowledge wiki | Implemented; automated verification passed | `knowledge/`, controlled index tests |
| Extension API and registry | Implemented; automated lifecycle tests passed | API 1.0, manifest 1, routing/fallback tests |
| Accepted release registry | Implemented; schema 3 validates source versions, hashes, capabilities, and dependency closure | `integrations/registry.toml`, `alem integration validate` |
| Accepted integration setup/update | Implemented; official and community-authorship fixtures provision, update idempotently, roll back, and pin | `src/alem/reconciliation.py`, accepted integration tests |
| Readiness and task routing | Implemented; availability remains visible through missing config/hardware/runtime and offline-service states | `src/alem/tool_status.py`, `tools` CLI, routing tests |
| Academic-search providers | Implemented; offline tests passed; external services currently unreachable on this host | OpenAlex and Semantic Scholar plugins |
| Community integrations | Accepted assets/catalog adapters provision automatically; Feynman and example static search remain candidates | Release registry and candidate classification tests |
| Runtime bootstrap | Implemented; launcher installs declared core dependencies into `.alem/venv` before CLI import | `scripts/bootstrap_runtime.py`, Windows smoke commands |
| Interactive owl TUI and model gateway | Implemented; Textual app stays open with composer, real SSE response updates, cancellation request, guided hidden API-key setup, provider/model commands, and selected workflow dispatch. Automated tests cover terminal fallback, 256-color conversion, resizing, protocol parsing, and keyboard input; Windows PTY truecolor output was inspected. Native Windows Terminal screenshot verification and live provider responses remain unverified. | `src/alem/terminal/`, `src/alem/models.py`, `contracts/capabilities/model_completion/1.0.json`, `tests/test_models.py`, `tests/test_tui.py` |
| Cross-platform automation | Clean launcher smoke and test matrix configured for Windows, Linux, and macOS; hosted jobs not yet observed | `.github/workflows/ci.yml` |
| Source release workflow | Implemented; matching version tags rerun validation and publish the complete repository source archive | `.github/workflows/release.yml` |
| Detached release signature verification | Not implemented; registry SHA-256 pins content but does not authenticate a signer | Tracked as follow-up in `TODO.md` |
| OS-enforced plugin sandbox | Not claimed | Approval, hashing, subprocess isolation, documented limits |

## Release interpretation

Version 1.0 means the public extension API, workspace schema, task-context model, capability
contracts, artifact envelope, and migration policy are stable enough for durable research
workspaces. Accepted releases are provisioned through the same version-pinned path regardless of
authorship. The current release registry's accepted entries are Alem-authored; automated fixtures
prove that `community-contributor` releases take that same path. This does not mean every cataloged
research repository is integrated or that accepted third-party code is safe. Catalog-only entries
remain candidates until independently audited, adapted, contract-tested, and explicitly promoted in
the integration registry.
