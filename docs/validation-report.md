# Alem 1.0 validation report

Validation date: 2026-11-03 (Asia/Dubai)
Host exercised: Windows 11, Python 3.14.0
Scope: local 1.0 core, context, workflow, artifact, integration, and plugin acceptance checks

## Automated checks

| Check | Result | Evidence |
| --- | --- | --- |
| Python compilation | Passed | `python -m compileall -q src` |
| Test suite | Passed, 50; skipped, 1 | `.alem/venv/Scripts/python -m pytest -q` |
| Core and CLI tests | Passed | Containment, setup/adapters, project/export privacy, knowledge, CLI/starter |
| Extension tests | Passed, 21 | Manifests, providers, approvals, lifecycle, dependencies, assets, routing, rollback |
| Context scaling | Passed | Adding 120 skills still generated one startup adapter in lazy mode |
| Contract and artifact tests | Passed | JSON contract rejection and artifact tamper detection |
| Workflow state and gates | Passed | Resume, expected outputs, approval blocking, completion |
| Integration consistency | Passed, 12 records | Schema-2 fixture and `alem integration validate` |
| Bundled workflow validation | Passed | Full lifecycle, literature review, and research design |
| Ruff | Passed | Workspace-local Ruff 0.17.3: `python -m ruff check .` |
| Repository whitespace | Passed | `git diff --check` |
| Health check | Passed, no warnings | `.\alem.ps1 health --strict` |
| Package dependency check | Passed | `python -m pip check` |
| Wheel build | Passed | `alem_research-1.0.0-py3-none-any.whl` |

The skipped test attempts to create a symbolic link and verify export rejection. Windows denied link
creation to the current non-elevated account (`WinError 1314`); the same production path also rejects
Windows junctions/reparse points, and the test will execute on symlink-capable CI hosts. The suite
run from `.alem/venv` had no unrelated global pytest-plugin warnings.

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
and 3.13 on Windows, Linux, and macOS after upload.
