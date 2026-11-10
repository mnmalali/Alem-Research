# Plugin development kit

Status: extension API `1.0`, manifest schema `1`, integration registry schema `3`, Alem `1.0.0` stable release.

Alem plugins add providers without changing core code. Workflows request a
capability such as `academic_search`; routing selects an enabled provider at
runtime. A plugin can contain tools, skills, agents, workflows, or a
combination. The checked-in catalogue is a Git repository artifact, not a
marketplace service.

Executable tools, agents, skills, and workflows share the versioned `invoke`
contract and capability router. Declarative skill/agent/workflow paths are
validated under `[assets]` and exposed by
`PluginManager.discover_assets(...)`. In eager compatibility mode, Codex and Claude adapters
consume that same enabled-skill view and generate namespaced, ignored pointer adapters on enable.
Disabling, updating, or removing the plugin removes stale generated adapters. Declarative agent and
workflow assets remain available through
`PluginManager.discover_assets(...)` and `alem plugin assets`; plugins do not
implement or duplicate agent-specific installation systems.

In the default lazy context mode, plugin skills are indexed but do not each receive a host adapter.
The `alem-router` selects a minimal set and reads the canonical asset path. Add a sibling
`routing.toml` to a skill when its description alone cannot discriminate its lifecycle stage,
inputs, outputs, mutation behavior, or activation boundaries. See
[`context-routing.md`](context-routing.md).

## Start a plugin

Run `alem plugin create <name>` to generate a validated starter directly under
`plugins/community/<name>` (override the destination with `--path`). The raw
files in `examples/plugins/_template/tool` are optional reference templates
for maintainers and documentation tooling. The complete third-party example is
`examples/plugins/community-static-search`; it imports only
`alem.extensions.api`.

A plugin directory normally contains:

```text
my-plugin/
├── plugin.toml       # strict, declarative metadata and permissions
├── plugin.py         # optional entry point for executable capabilities
├── README.md         # installation, usage, limits, privacy, evidence notes
└── tests/
```

Validate a local development plugin before submitting it:

```console
alem plugin validate path/to/my-plugin
alem plugin install path/to/my-plugin --approve
alem plugin enable org.example.my-plugin --approve
```

Installation and execution are different trust decisions. Without `--approve`,
the non-interactive install command prints the plan and exits; rerunning it
with `--approve` records installation approval. Enabling executable code
requires its own explicit `--approve` flag and records approval of the current
digest. The CLI never treats validation, installation, or enablement alone as
implicit consent for another step.

This manual path is for local development and candidates. An accepted release is provisioned
automatically during normal setup and update after a maintainer approves its exact version and
digest in `integrations/registry.toml`. Alem-authored and community-contributed releases use the
same policy. The contributor badge is attribution only. Maintainer acceptance authorizes Alem's
managed execution path; it does not create an OS sandbox or certify the truth of research output.

## Contribution to automatic availability

The supported lifecycle is:

1. **Build an adapter.** Start from `alem plugin create`, import only
   `alem.extensions.api`, and implement a versioned capability contract with normalized output
   and provider/source provenance. Bundle code or dependencies only when redistribution rights
   permit it; do not rely on global installers or hidden executables.
2. **Validate locally.** Run `alem plugin validate <path>`, the plugin's tests, the full Alem test
   suite, `alem integration validate`, and a bounded lazy `alem context plan` fixture. Use mocks
   for service failures and keep credentials out of fixtures.
3. **Submit a PR.** Include the plugin, catalogue entry, tests, documentation, source revision,
   license and notice files, and a candidate integration record. Candidate submissions are not
   provisioned or executed just because they appear in the catalogue.
4. **Maintainer review and acceptance.** Review source and license rights, dependency closure,
   network/filesystem/subprocess permissions, credentials, telemetry, supported platforms,
   service costs, supply-chain risk, maintenance contact, compatibility, provenance, and failure
   behavior. The maintainer changes the registry row to `acceptance = "accepted"`, records
   authorship and contributor attribution, and pins the exact release version and source-tree
   SHA-256 digest. A catalogue verification badge cannot perform this promotion.
5. **Release.** The repository PR and release process carries the accepted registry and plugin
   source together. `.github/CODEOWNERS` requests maintainer review; repository settings must
   require code-owner approval for that review to be enforced. Pushing a `vX.Y.Z` tag matching
   `pyproject.toml` runs `.github/workflows/release.yml`, which reruns lint, tests, and registry
   validation before publishing the GitHub source release. The digest makes contents reproducible
   relative to the checked-in registry, but is not a detached cryptographic signature.
6. **Automatic availability.** After the release reaches a user's checkout/package, `alem setup`
   or `alem update` verifies the pinned source and provisions it into `.alem/`, records its
   provenance, and makes it discoverable through the existing capability/context routers. Users
   do not clone, install, or enable accepted tools one by one.
7. **Upgrade or rollback.** A new version and digest require the same compatibility and safety
   review. Alem retains a prior content-addressed release; `alem plugin rollback <id>` restores and
   pins it, and `alem plugin unpin <id>` resumes updates.

`alem update` only reconciles accepted integrations in the release already present in the local
repository/package. Updating Alem core itself is performed by the package manager or Git release
process and is not an in-app self-update.

## Manifest schema 1

Unknown keys are errors. Paths must be relative and remain inside the plugin.
Versions use numeric semantic versions; ranges are comma-separated `>=`, `>`,
`<=`, `<`, or `==` comparisons.

| Section | Required fields | Meaning |
|---|---|---|
| root | `schema_version = 1` | Manifest contract, independent of API version. |
| `[plugin]` | `id`, `name`, `version`, `api`, `description`, `author`, `repository`, `license`, `types`; `entrypoint` for executable capabilities | Namespaced identity and public API compatibility. IDs are lowercase and namespaced. Entry points use `relative.py:attribute`. |
| `[[capabilities]]` | `name`, `version`, `extension_type`, `priority`, `description` | Provider-neutral contract offered to routing. Names are lowercase snake/dotted identifiers. |
| `[compatibility]` | `python`, `operating_systems`, `coding_agents` | Supported runtimes: OS values are `windows`, `linux`, `macos`; agent values are `codex`, `claude-code`, `none`. |
| `[dependencies]` | `plugins`, `python` | Plugin dependency inline tables contain `id`, `version`, optional `optional`. Python requirements are installed only with a separate workspace-local dependency option. |
| `[permissions]` | `network`, `filesystem_read`, `filesystem_write`, `subprocess`, `native_code` | Reviewable requested authority. Hostnames, not URLs, go in `network`. See the security limitation below. |
| `[credentials]` | `required`, `optional` | Uppercase credential names. Values are supplied per invocation and never stored in the manifest. |
| `[documentation]` | `installation`, `usage` | Short actionable instructions; keep the full explanation in README. |
| `[assets]` | `skills`, `agents`, `workflows` | Relative paths for declarative extension assets. Empty arrays are valid. |

Supported extension types are exactly `tool`, `skill`, `agent`, and
`workflow`. An executable capability's `extension_type` must appear in the
plugin's `types`. A data-only skill can use `capabilities = []`, omit the entry
point, and declare `assets.skills`.

## Public Python API

Plugins should import only documented names from `alem.extensions.api` (the
same names are re-exported from `alem.extensions` for generated starters):

- `API_VERSION`
- `ExecutionRequest` and `ExecutionResponse`
- `Extension`, `ToolExtension`, `SkillExtension`, `AgentExtension`, and
  `WorkflowExtension` protocols
- optional convenience class `BaseExtension`

The entry-point attribute is either an instance or a zero-argument class with
`invoke(request)`. Inputs and outputs must be JSON serializable. Plugins run in
a fresh subprocess; do not rely on in-process state, current directories, or
conversation memory. Persistent files belong in
`request.context["plugin_data_dir"]`. Credentials are present only under
`request.context["credentials"]` and only if declared.

`ExecutionRequest.capability_version` is an exact contract version. Routing
never selects a provider that declares a different version. The CLI defaults
to `1.0`; use `--capability-version` when invoking or listing another version.

Every request carries both `capability` and `capability_version` (default
`1.0`). The registry filters providers by an exact capability-contract version
before applying configured defaults and fallbacks. A `2.0` provider is never
silently selected for a `1.0` workflow; consumers opt into the new contract
explicitly.

```python
from alem.extensions.api import BaseExtension, ExecutionRequest, ExecutionResponse

class SearchProvider(BaseExtension):
    extension_type = "tool"

    def invoke(self, request: ExecutionRequest) -> ExecutionResponse:
        query = str(request.input.get("query", "")).strip()
        if not query:
            raise ValueError("query is required")
        return ExecutionResponse({"query": query, "items": []})

plugin = SearchProvider()
```

Do not import `manager`, `registry`, `runner`, or other implementation modules
from plugin code. Core is free to change those within an API series.

## `academic_search` capability 1.0

Input requires `query: string` and may contain `limit: integer`. Output is an
object with `query`, `items`, `total`, `retrieved_at`, and `database`. Each
item uses the normalized fields `title`, `authors`, `year`, `doi`, `url`,
`external_id`, `abstract`, `citation_count`, `source`, and
`verification_status`. Missing metadata uses JSON `null`, never invented
values. Providers must identify the database and retrieval time. Retrieved
metadata is not equivalent to independently verified full text.

`org.alem.openalex` and `org.alem.semantic-scholar` implement this contract.
A user can set one default and the other as fallback without editing a
literature-review workflow.

The machine-readable contract is `contracts/capabilities/academic_search/1.0.json`. A contributed
provider must pass both its own tests and Alem's contract validation. New capability contracts
belong under `contracts/capabilities/<name>/<version>.json`; breaking semantics require a new
capability version rather than reinterpretation of an existing schema.

## Dependencies and installation

The v1 resolver supports a deterministic dependency graph with one selected
version per plugin, comparator ranges, optional plugin dependencies, cycle
detection, and conflict detection. It is intentionally not a SAT solver.
Dependencies are resolved from the same checked-in catalogue and installed
dependency-first.

Required plugin dependencies for local/manual installs must be installed and enabled before a
dependent can be enabled. Accepted dependencies are released together and reconciled dependency
first. Alem refuses to disable
or remove a plugin while an enabled installed plugin requires it and lists the
blocking dependent IDs. Optional dependency edges do not block lifecycle
operations.

Python dependencies are never installed globally. If a reviewed plugin
declares them, Alem requires an explicit dependency-install option and uses
`.alem/plugin-dependencies/<plugin-id>`. Schema 1 accepts only exact index
requirements such as `package==1.2.3` or `package[extra]==1.2.3`; pip options,
URLs, local paths, ranges, and editable sources are rejected. Installation uses
`--isolated --no-cache-dir --no-input --no-deps --only-binary=:all:` with a
workspace-local temporary home/config/cache. Declare the complete pinned wheel
set because transitive resolution is disabled.

A deterministic `name==version` lock and dependency-tree digest are recorded
with plugin state. Execution approval binds both the plugin and dependency
digests, so changing either prevents execution. Updates stage code and
dependencies before replacement; a failed dependency install leaves the
previous approved installation intact. The runner gives trusted Alem API code
precedence over plugin dependencies and uses `-S`, so a dependency cannot
shadow `alem` or inherit globally installed site packages.

All plugin code, state, dependencies, data, and route settings live under the
workspace `.alem/` directory. No global agent or language environment is
modified.

## Test templates and quality gates

The generated starter includes a unit test; the raw template also includes a
test file. `tests/test_extensions.py` is the
integration reference: it validates all catalogue manifests, verifies the
third-party install/discover/enable/invoke/disable/remove lifecycle, detects
post-approval file changes, and tests default-to-fallback routing without live
network calls.

Before submission run:

```console
alem plugin validate path/to/plugin
python -m pytest
```

Tests must mock network failure and rate limiting, verify normalized output,
avoid real credentials, and show that missing optional services fail without
corrupting workspace state.

Accepted-release CI also checks clean launcher bootstrap on Windows, Linux, and macOS before
running `health --strict` and `--help`. The Windows launcher seeds PyYAML and all other declared
core dependencies in the actual `.alem/venv` interpreter before importing the CLI.

## Security limitation

Manifest permissions are declarations for review and future enforcement, not
a sandbox. Python `-I`, a clean environment, a subprocess boundary, digest
checks, and explicit approvals improve containment and auditability but cannot
stop malicious code from using the current user's OS privileges. Read
`docs/plugin-security.md` before approving third-party code.
