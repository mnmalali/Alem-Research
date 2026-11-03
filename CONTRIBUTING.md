# Contributing to Alem Research

Thank you for helping build a dependable, community-owned research workspace. Contributions should
make research more reproducible without coupling the core to a provider, coding agent, or hosted
service.

## Prepare a change

1. Open or reference an issue that explains the research need and smallest useful scope.
2. Work in a focused branch and preserve unrelated files.
3. Keep mutable state, private research, downloaded papers, secrets, and datasets out of Git.
4. Add tests that fail without the change and documentation that matches actual behavior.
5. Run the validation commands below before opening a pull request.

```bash
sh ./alem setup --create-venv
.alem/venv/bin/python -m pip install --no-cache-dir -e ".[dev]"
.alem/venv/bin/python -m ruff check .
.alem/venv/bin/python -m pytest
./alem health --strict
```

On Windows PowerShell, keep the same workspace-local boundary:

```powershell
.\alem.ps1 setup --create-venv
.\.alem\venv\Scripts\python.exe -m pip install --no-cache-dir -e ".[dev]"
.\.alem\venv\Scripts\python.exe -m ruff check .
.\.alem\venv\Scripts\python.exe -m pytest
.\alem.ps1 health --strict
```

## Design rules

- Core workflows depend on abstract capabilities, never named providers.
- New integrations are plugins unless they implement essential workspace mechanics.
- Runtime writes and dependencies stay beneath `.alem/`.
- Agent instructions have one canonical source; adapters remain small and regenerable.
- New skills and tools remain lazy-indexable; do not expose an entire upstream library at startup.
- Capability inputs and outputs use versioned contracts and durable results use artifact records.
- Missing optional integrations fail clearly and do not disable unrelated research work.
- Evidence metadata must identify what was verified and what remains interpretation or hypothesis.
- No feature is marked complete only because files or stubs exist.
- Every user-visible tool or integration addition requires a semantic Alem version bump, a
  changelog entry, and synchronized package/citation metadata. Plugin versions remain separate
  from the Alem release version.

Changes to public manifests, protocols, or persisted state require an API-versioning and migration
assessment. See [`docs/plugin-api-versioning.md`](docs/plugin-api-versioning.md).

## Submit code or content

Pull requests should state:

- the user-facing problem and chosen scope;
- architecture and privacy effects;
- evidence that tests passed, including operating systems exercised;
- new dependencies and their licenses;
- documentation and migration changes;
- limitations and manual checks still required.

For catalogue plugins, follow [`CONTRIBUTING-PLUGINS.md`](CONTRIBUTING-PLUGINS.md). A catalogue entry
does not imply a security endorsement.

## Report security issues

Use the private process in [`SECURITY.md`](SECURITY.md). Never include a real credential, private
dataset, unpublished manuscript, or participant information in an issue or test fixture.
