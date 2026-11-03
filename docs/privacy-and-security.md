# Privacy and security

Alem is local-first, not offline-only. Files and runtime state stay in the workspace, while an
enabled network integration can send explicit requests to its declared hosts.

## Data locations

| Data | Default location | Committed |
| --- | --- | --- |
| Framework and templates | repository | yes |
| Mutable runtime and plugins | `.alem/` | no |
| Research projects | `projects/` | no |
| Exports | `exports/` | no |
| Shared knowledge | `knowledge/` | yes; review before publishing |
| Secrets | `.env` or process environment | no |

Setup and plugin management reject paths outside the resolved workspace. Alem does not edit global
Codex, Claude Code, Python, or Node configuration.

## Threat model

Manifests support review and policy decisions; they do not constrain malicious code. The current
release provides digest-bound approvals and a subprocess boundary, but not a hardened sandbox. A
malicious approved plugin may access anything available to the user's process. Use an OS sandbox,
container, disposable VM, or similarly enforced boundary for untrusted code. More detail is in
[`plugin-security.md`](plugin-security.md).

## Reporting a vulnerability

Do not open a public issue for an unpatched vulnerability or leaked credential. Use the repository's
private security-advisory channel. Include affected versions, reproduction steps, impact, and a
minimal proof. Maintainers should acknowledge a report within seven days and publish remediation
status without exposing reporters or research participants.
