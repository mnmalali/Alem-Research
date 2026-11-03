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
| Integration maturity registry | Implemented; consistency validation passed | `integrations/registry.toml`, `alem integration validate` |
| Academic-search providers | Implemented; offline tests passed | OpenAlex and Semantic Scholar plugins |
| Community integrations | Implemented as opt-in adapters/assets/catalogs | Feynman, Orchestra, Wenyu, Awesome catalog |
| Cross-platform automation | Configured for Windows, Linux, and macOS | `.github/workflows/ci.yml` |
| OS-enforced plugin sandbox | Not claimed | Approval, hashing, subprocess isolation, documented limits |

## Release interpretation

Version 1.0 means the public extension API, workspace schema, task-context model, capability
contracts, artifact envelope, and migration policy are stable enough for durable research
workspaces. It does not mean every cataloged research repository is integrated or that approved
third-party code is safe. Catalog-only entries remain discovery leads until independently audited,
adapted, tested, and promoted in the integration registry.
