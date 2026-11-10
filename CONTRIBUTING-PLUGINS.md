# Contributing an Alem plugin

Alem's catalogue is maintained through ordinary GitHub pull requests. It is a
reviewed index, not an endorsement or security sandbox.

## Submission contents

A community PR must include:

1. Plugin source in a self-contained, redistributable directory with a pinned
   release version and reproducible source-tree digest.
2. A schema-1 `plugin.toml` declaring unique ID, author, repository, version,
   Alem API range, extension types, capabilities, dependencies, credentials,
   requested network/filesystem/execution permissions, SPDX license,
   supported operating systems, and supported coding agents.
3. README installation and usage instructions, rate limits, privacy/data-flow
   notes, failure behavior, and evidence limitations.
4. A `catalogue/index.toml` entry marked `community`. Catalogue verification
   (`verified` or `unverified`) is separate from acceptance and never triggers
   provisioning.
5. Unit tests and an integration test using only public
   `alem.extensions.api` contracts. Network tests must use recorded or mocked
   responses and contain no secrets.
6. The plugin's license and all required third-party notices. The submitter is
   responsible for redistribution rights.
7. For every contributed skill whose activation boundaries are not completely captured by its
   concise frontmatter description, a schema-1 `routing.toml` declaring `use_when`, `avoid_when`,
   lifecycle stages, inputs, outputs, mutation class, network use, and estimated context size.
8. A schema-3 candidate record in `integrations/registry.toml` that separates
   acceptance, authorship, maturity, and readiness. Contributors submit it as
   `acceptance = "candidate"`; only a maintainer may promote it to accepted.

Start with `alem plugin create <name>` (generated under
`plugins/community/<name>` unless `--path` is supplied), then run
`alem plugin validate <path>` and the full test suite. The community static-search example demonstrates the
expected layout and lifecycle without pretending its synthetic record is a
real source.

Run `alem integration validate` and at least one realistic `alem context plan` fixture before
submission. A new integration must not cause initial agent context to grow in lazy mode.

When contributing an external research tool, add an Alem adapter or a reviewed declarative asset
under `plugins/community/`; do not make the upstream repository a hidden runtime dependency.
Record the exact upstream commit, license, copied file paths, local modifications, permissions,
and external setup in the plugin README and `docs/upstream-register.toml`. Prefer a narrow
provider-neutral capability or an offline catalog over arbitrary command passthrough. Submission
does not grant acceptance or execution.

## Build, validate, submit, and release

The supported lifecycle is `build adapter -> validate -> submit PR -> maintainer acceptance ->
release -> automatic user availability`:

1. Use `alem plugin create <name>` and only the versioned `alem.extensions.api` surface. Add
   normalized capability output and source/provider provenance. Do not copy code unless the
   license permits redistribution; do not invoke global installers or silently download model
   weights.
2. Run `alem plugin validate <path>`, focused tests, `python -m pytest`,
   `alem integration validate`, and a lazy context-plan fixture. CI should cover clean launcher
   bootstrap, supported OS/Python versions, mocked network errors, and prerequisite diagnostics.
3. Submit source, tests, docs, catalogue entry, and candidate registry record. The review packet
   must identify license/attribution, pinned source revision, complete dependencies, requested
   permissions and credentials, telemetry/data flow, OS/architecture support, costs, supply-chain
   concerns, and maintenance contact.
4. Maintainers review the packet and exact code. They accept only by changing the release-registry
   row to `accepted` with `authorship`, contributor attribution when applicable, exact semantic
   version, and SHA-256 tree digest. A catalogue badge cannot do this.
5. The accepted source and registry entry ship together in an Alem release. `.github/CODEOWNERS`
   requests maintainer review; repository settings must require code-owner approval for that review
   to be enforced. Pushing a `vX.Y.Z` tag matching `pyproject.toml` runs `.github/workflows/release.yml`,
   which reruns lint, tests, and integration validation before publishing the GitHub source release.
   Normal `alem setup` and `alem update` then provision accepted official and community releases
   through one managed path; users need no tool-by-tool clone, install, or enable step.
6. A version upgrade repeats review and validation. Prior content-addressed releases can be
   restored and pinned with `alem plugin rollback <id>`; `alem plugin unpin <id>` resumes updates.

The current digest is a reproducible integrity pin, not a detached cryptographic signature. Review
enforcement depends on the repository's branch-protection settings. Alem core updates arrive via
the package manager or GitHub source release; `alem update` reconciles integrations in the release
already installed.

## Review criteria

Reviewers check identifier ownership, useful non-duplicative capability,
public-API-only imports, manifest/source agreement, least-privilege requests,
dependency pinning, credential handling, normalized evidence/provenance,
failure isolation, tests, documentation, maintenance plan, and license
compatibility. Automated validation is necessary but not sufficient.

Python dependencies must be exact index pins (`name==version`, optional
extras), have binary wheels for supported platforms, and list their complete
closure because Alem installs with `--no-deps`. Options, URLs, local paths,
editable installs, and version ranges are rejected by manifest schema 1.

Plugins must not fabricate papers, identifiers, authors, datasets, search
outcomes, or results. Synthetic fixtures must be unmistakably labeled and
must not flow into research evidence as verified records.

## Updating and removal

Updates use a new semantic version and explain user-visible, permission,
dependency, and capability-contract changes. Permission expansion requires
special reviewer attention and revalidation before maintainer acceptance of the new release.
Maintainers may mark or remove entries for malware, abandoned vulnerable
dependencies, license problems, persistent API breakage, or unverifiable
provenance. Existing local installations are not silently deleted.

## Maintainer boundary

Official and community-authored accepted plugins follow the same manifest,
validation, and public API rules. Authorship is attribution, not a different
installation tier. Core workflows depend on capabilities, never a plugin ID.
A new provider should normally require only a plugin, catalogue entry,
registry record, and tests—not a core change.
