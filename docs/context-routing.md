# Task-scoped context routing

Alem installs and indexes integrations independently from what an agent sees in one task. The
default `lazy` mode exposes one small `alem-router` adapter. Canonical skills, enabled plugin
assets, capability providers, and catalog-only candidates remain discoverable in a workspace-local
index under `.alem/cache/`.

## States

| State | Meaning |
| --- | --- |
| Available | Listed in the checked-in catalogue; not installed or trusted for execution. |
| Installed | Code or assets are workspace-local; not necessarily enabled. |
| Enabled | Eligible for discovery and routing after execution approval. |
| Activated | Selected by a context plan for the current task. |
| Invoked | Actually executed through a capability request. |

Activation does not grant installation, execution, network, credential, or external-write
permission.

## Commands

```bash
alem context build
alem context search "citation verification" --all
alem context plan "Verify whether these sources support the manuscript claims"
alem context explain <plan-id>
alem context activate <plan-id>
alem context status
alem context deactivate
```

Plans record detected lifecycle stages, selected skill paths, capabilities and providers, inactive
suggestions, exclusions, estimated context tokens, and the index digest. They are stored beneath
`.alem/state/context/` and are intentionally excluded from Git.

The index fingerprints configuration, skill metadata, catalogue state, and installed plugin
metadata. Planning rebuilds it automatically when those sources change.

## Routing metadata

Every skill has a concise `name` and discriminating `description`. A skill may add a sibling
`routing.toml` when its task boundaries need more structure:

```toml
schema_version = 1

[routing]
workflow_stages = ["literature-search"]
use_when = ["find scholarly papers"]
avoid_when = ["format an existing bibliography"]
inputs = ["research_question"]
outputs = ["search_run"]
domains = ["general"]
mutation = "local-reversible"
network = true
estimated_tokens = 1200
```

Capability entries are derived from installed plugin manifests and configured provider routes.
Catalog entries can appear as inactive suggestions but are never treated as executable.

## Compatibility

`[context] mode = "eager"` regenerates all traditional Codex and Claude Code adapters. Workspaces
without a context table retain eager behavior. New Alem 1.0 workspaces use lazy mode.
