# Integrations

No integration is mandatory. An unavailable provider must not prevent local project, knowledge,
evidence, or writing workflows from operating.

## See implemented status

Run:

```bash
./alem tools list
./alem tools status [id]
./alem tools doctor [id]
./alem integration list
```

`integrations/registry.toml` is the maintainer-controlled release registry. Schema 3 distinguishes
acceptance, authorship, implementation maturity, and readiness. Validate it against catalogue
sources, versions, hashes, capabilities, and dependencies with:

```bash
./alem integration validate
```

OpenAlex, Semantic Scholar, Orchestra assets, Wenyu's catalog, and the Awesome Research Tools
catalog are currently accepted and provisioned through the common manager. Feynman remains a
candidate because its upstream runtime is not yet reproducibly managed by Alem. Candidate records
and catalog results are visible for discovery but are never automatic install targets.

An accepted row pins its catalogue version and SHA-256 source-tree digest. Legacy schema 1 and 2
rows migrate as candidates. Normal setup and `alem update` reconcile accepted releases only;
`alem update` does not update the Alem core package or repository checkout. Reconciliation stores
author and release provenance in `.alem/state/plugins.json`, retains prior releases for rollback,
and reports failures without erasing working installations. `alem plugin rollback <id>` restores a
retained release and pins it; `alem plugin unpin <id>` lets future reconciliation advance it.

Maturity values are `discovered`, `assessed`, `adapted`, `contract-tested`, `workflow-proven`,
`blocked`, and `deprecated`. Trust is tracked separately as `official`, `verified`, `unverified`,
or `not-executable`. Authorship only identifies who contributed the adapter. Acceptance means a
maintainer reviewed the exact release for distribution; it does not mean the plugin has no
external prerequisites or that its research claims are endorsed.

## Cost and privacy categories

| Category | Meaning |
| --- | --- |
| `free-open-source` | Local software with an open-source license |
| `free-service` | Hosted service with terms and rate limits; availability is not guaranteed |
| `optional API key` | Core operation does not require the credential |
| `paid optional` | Never required for useful base functionality |

Network plugins disclose destination hosts and credentials in their manifests. Search queries sent
to a hosted academic index are not local, even when the service is free. Never send confidential
topics or unpublished data without reviewing the service's terms and privacy policy.

## Failure handling

Readiness states are `ready`, `needs-configuration`, `missing-hardware`, `missing-runtime`,
`service-unavailable`, `unsupported-platform`, and `error`. A blocked accepted tool remains
available in status output. `tools configure` prints variable names and instructions without
reading or storing secrets. Readiness checks use bounded, non-authenticated service checks and do
not invoke plugin code.

The capability router prefers task-compatible ready providers. A provider timeout, invalid
response, missing required credential, or rate-limit response is recorded and permits a configured
contract-compatible fallback. If no provider can run, Alem returns actionable diagnostics instead
of fabricating an empty search result. Inputs and outputs with registered capability contracts are
schema-validated. Workflows must record database, query, retrieval date, and provider metadata.
