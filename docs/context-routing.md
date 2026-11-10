# Task-scoped context routing

Alem installs and indexes integrations independently from what an agent sees in one task. The
default `lazy` mode exposes one small `alem-router` adapter. Canonical skills, enabled plugin
assets, capability providers, and catalog-only candidates remain discoverable in a workspace-local
index under `.alem/cache/`.

## States

| State | Meaning |
| --- | --- |
| Candidate | Discovered or submitted, but not maintainer-accepted; never automatically provisioned or executed. |
| Accepted | Exact release is maintainer-approved in `integrations/registry.toml`; authorship is separate metadata. |
| Available | Accepted code is provisioned, registered, enabled, and integrity-approved. Readiness may still block invocation. |
| Readiness | One of `ready`, `needs-configuration`, `missing-hardware`, `missing-runtime`, `service-unavailable`, `unsupported-platform`, or `error`. |
| Activated | Selected by a context plan for the current task. |
| Invoked | Actually executed through a capability request. |

Candidate, accepted, available, ready, and activated are distinct states. A community authorship
badge only identifies the contributor; accepted official and community releases use the same
provisioning and routing policy. Activation does not grant network, credential, or external-write
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

Capability entries are derived from registered plugins and configured provider routes. Accepted
providers with missing prerequisites remain visible with readiness diagnostics. Catalog entries
can appear as inactive suggestions but are never treated as executable.

## Compatibility

`[context] mode = "eager"` regenerates all traditional Codex and Claude Code adapters. Workspaces
without a context table retain eager behavior. New Alem 1.0 workspaces use lazy mode.
