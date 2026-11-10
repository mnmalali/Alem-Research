# Alem 1.0 validation report

Validation date: 2026-11-10 (Asia/Dubai)
Host exercised: Windows 11, Python 3.14.0
Scope: accepted-tool bootstrap, schema-3 release reconciliation, readiness, routing, and the
existing core, context, workflow, artifact, integration, and plugin checks

## Current unified-tool acceptance checks

| Check | Result | Evidence |
| --- | --- | --- |
| Full test suite | Passed, 59; skipped, 1 | `.alem/venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` |
| Ruff | Passed | `.alem/venv/Scripts/python.exe -m ruff check .` |
| Clean bootstrap dependency regression | Passed | Bootstrap test verifies `PyYAML` and `jsonschema` are installed through `.alem/venv/Scripts/python.exe` before Alem imports `workflows.py` |
| Setup | Passed, exit 0 | `.\alem.ps1 setup --create-venv`; five accepted releases already-current/provisioned; two catalog community candidates remained unprovisioned |
| Strict health | Passed, exit 0 | `.\alem.ps1 health --strict` |
| CLI help | Passed, exit 0 | `.\alem.ps1 --help` |
| Registry validation | Passed, 12 records | `.\alem.ps1 integration validate --json`; schema 3, `valid: true`, no errors |
| Update reconciliation | Passed, idempotent | `.\alem.ps1 update --json`; 5 accepted, 5 already current, 7 candidates untouched, 0 failed |
| Tool readiness | Passed, truthful status | `.\alem.ps1 tools list`; all five accepted tools remained available; three local assets/catalogs were ready; two hosted API checks were `service-unavailable` because this host could not reach them |
| Windows/Linux/macOS clean launcher smoke | Configured; hosted workflow not yet run | `.github/workflows/ci.yml` tests setup, strict health, and help before developer dependency installation |
| Tagged source release | Configured; no release tag was published during this task | `.github/workflows/release.yml` checks the tag/version and reruns lint, tests, and registry validation |

The skipped test attempts to create a symbolic link and verify export rejection. Windows denied link
creation to the current non-elevated account (`WinError 1314`). The full suite required normal
Windows temporary-directory access because this host's sandbox ACL blocks pytest fixtures. The
launcher setup succeeded and installed/verified dependencies in `.alem/venv`; pip printed
non-blocking warnings that it could not remove several temporary directories under the host's
`AppData/Local/Temp` ACL.

The setup command was exercised in the existing checkout rather than a freshly cloned directory.
The unit test simulates creation of a new Windows venv, and CI now performs the launcher sequence on
clean runners. Run that hosted matrix before making cross-platform compatibility claims.

## Reproducible Windows PowerShell first run

```powershell
git clone https://github.com/mnmalali/Alem-Research.git
Set-Location Alem-Research
.\alem.ps1 setup --create-venv
.\alem.ps1 health --strict
.\alem.ps1 --help
.\alem.ps1 tools list
.\alem.ps1 update
```

`setup --create-venv` seeds the exact interpreter selected by the launcher. `tools list` reports
hosted-service failures without removing the accepted tools. `update` reconciles accepted versions
in the checkout already present; it does not self-update Alem core.

## Historical validation details (2026-11-03)

## Plugin acceptance demonstration

`dev.community.static-search` was exercised through the actual CLI:

1. installation without `--approve` failed with exit code 2 and displayed the plan;
2. approved installation copied it beneath `.alem/plugins/` in disabled state;
3. enabling with execution approval made `academic_search` discoverable;
4. subprocess invocation returned the explicitly synthetic, non-citable fixture;
5. disabling removed it from routing; and
6. removal with data purge deleted its local code, dependencies, and data.

No core code or global agent configuration changed during that lifecycle. Automated tests repeat the
same lifecycle in an isolated temporary workspace and prove that modifying installed code invalidates
the approved digest.

## Academic-search providers

Both official plugins strictly validated and were installed/enabled through the same public manager
and CLI as the community example. An offline runtime double verified that an OpenAlex failure routes
to Semantic Scholar in configured order without workflow changes.

A bounded live query (`open science reproducibility`, limit 1) produced:

- OpenAlex: successful normalized metadata response with provider and retrieval provenance;
- Semantic Scholar: HTTP 429 from the public endpoint without an API key.

The Semantic Scholar result is recorded as a service/rate-limit failure, not a passing live test.
Both provider implementations also passed offline response-mapping tests, including DOI/identifier
normalization, missing fields, optional OpenAlex `mailto`, and the optional Semantic Scholar API-key
header. Service availability remains an operational property rather than a guarantee of the Alem
core release.

## Context, contracts, artifacts, and workflows

Lazy setup exposed one `alem-router` adapter for each supported host while indexing 27 locally
available entries in the exercised workspace. A realistic literature-and-citation task selected
the relevant literature/citation skills and `academic_search` without exposing unrelated analysis
or external-agent tooling. The automated scaling fixture added 120 skills without increasing the
startup adapter count, and a source-fingerprint fixture proved stale indexes rebuild after skill
metadata changes.

Registered capability schemas were checked with JSON Schema Draft 2020-12. Artifact tests proved
that content changes invalidate recorded SHA-256 digests. Workflow tests exercised an agent step,
an expected output, an approval block, a recorded approver/decision, resume, and final completion.

## Not yet verified

- macOS and Linux setup (CI is configured but has not run in this local repository);
- actual skill discovery by fresh Codex and Claude Code sessions. Read-only, non-persistent smoke
  attempts were made: Codex CLI 0.130.0 could not use the account's current models because its model
  metadata parser/client support is stale, and Claude Code 2.1.143 returned an invalid OAuth-token
  error. These are external client/auth blockers, not passing discovery checks;
- a clean-host Python 3.11 and 3.13 matrix outside GitHub Actions;
- catalog entries with `discovered` or `assessed` maturity, which are explicitly not executable
  integrations; and
- OS-enforced sandbox execution, which is intentionally not claimed by 1.0.

Follow [`manual-validation.md`](manual-validation.md) before making platform- or client-specific
claims beyond the recorded Windows checks. The configured GitHub Actions matrix runs Python 3.11
and 3.13 on Windows, Linux, and macOS when a pull request is opened or a change is pushed to `main`.
