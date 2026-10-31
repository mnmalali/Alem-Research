# Plugin development kit

Status: extension API `1.0`, manifest schema `1`, Alem `0.1` foundation.

Alem plugins add providers without changing core code. Workflows request a
capability such as `academic_search`; routing selects an enabled provider at
runtime. A plugin can contain tools, skills, agents, workflows, or a
combination. The checked-in catalogue is a Git repository artifact, not a
marketplace service.

Executable tools, agents, skills, and workflows share the versioned `invoke`
contract and capability router. Declarative skill/agent/workflow paths are
validated under `[assets]` and exposed by
`PluginManager.discover_assets(...)`. Codex and Claude adapters consume that
same enabled-skill view and generate namespaced, ignored pointer adapters on
enable. Disabling, updating, or removing the plugin removes stale generated
adapters. Declarative agent and workflow assets remain available through
`PluginManager.discover_assets(...)` and `alem plugin assets`; plugins do not
implement or duplicate agent-specific installation systems.

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

Validate before installation:

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

## Dependencies and installation

The v1 resolver supports a deterministic dependency graph with one selected
version per plugin, comparator ranges, optional plugin dependencies, cycle
detection, and conflict detection. It is intentionally not a SAT solver.
Dependencies are resolved from the same checked-in catalogue and installed
dependency-first.

Required plugin dependencies must be installed and enabled (with their own
execution approval) before a dependent can be enabled. Alem refuses to disable
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

## Security limitation

Manifest permissions are declarations for review and future enforcement, not
a sandbox. Python `-I`, a clean environment, a subprocess boundary, digest
checks, and explicit approvals improve containment and auditability but cannot
stop malicious code from using the current user's OS privileges. Read
`docs/plugin-security.md` before approving third-party code.
