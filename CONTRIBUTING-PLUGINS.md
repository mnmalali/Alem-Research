# Contributing an Alem plugin

Alem's catalogue is maintained through ordinary GitHub pull requests. It is a
reviewed index, not an endorsement or security sandbox.

## Submission contents

A community PR must include:

1. Plugin source in a self-contained directory (or a pinned, immutable source
   mechanism once a later schema supports it).
2. A schema-1 `plugin.toml` declaring unique ID, author, repository, version,
   Alem API range, extension types, capabilities, dependencies, credentials,
   requested network/filesystem/execution permissions, SPDX license,
   supported operating systems, and supported coding agents.
3. README installation and usage instructions, rate limits, privacy/data-flow
   notes, failure behavior, and evidence limitations.
4. A `catalogue/index.toml` entry marked `community`.
5. Unit tests and an integration test using only public
   `alem.extensions.api` contracts. Network tests must use recorded or mocked
   responses and contain no secrets.
6. The plugin's license and all required third-party notices. The submitter is
   responsible for redistribution rights.

Start with `alem plugin create <name>` (generated under
`plugins/community/<name>` unless `--path` is supplied), then run
`alem plugin validate <path>` and the full test suite. The community static-search example demonstrates the
expected layout and lifecycle without pretending its synthetic record is a
real source.

When contributing an external research tool, add an Alem adapter or a reviewed declarative asset
under `plugins/community/`; do not make the upstream repository a hidden runtime dependency.
Record the exact upstream commit, license, copied file paths, local modifications, permissions,
and external setup in the plugin README and `docs/upstream-register.toml`. Prefer a narrow
provider-neutral capability or an offline catalog over arbitrary command passthrough. External
code still requires separate install and execution approval.

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
special reviewer attention and fresh user execution approval after update.
Maintainers may mark or remove entries for malware, abandoned vulnerable
dependencies, license problems, persistent API breakage, or unverifiable
provenance. Existing local installations are not silently deleted.

## Maintainer boundary

Official plugins follow the same manifest, validation, approval, and public
API rules as community plugins. Core workflows depend on capabilities, never
an official plugin ID. A new provider should normally require only a plugin,
catalogue entry, and tests—not a core change.
