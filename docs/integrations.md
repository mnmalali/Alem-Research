# Integrations

No integration is mandatory. An unavailable provider must not prevent local project, knowledge,
evidence, or writing workflows from operating.

## See implemented status

Run:

```bash
./alem integration list
```

The command reads `integrations/registry.toml`, which distinguishes bundled plugins from planned
work and separates integration maturity from trust. Validate consistency with:

```bash
./alem integration validate
```

OpenAlex and Semantic Scholar provide interchangeable network search. Feynman is an opt-in external
research-agent bridge. Orchestra contributes lazy-indexed skill assets, while the Wenyu and Awesome
catalogs provide offline discovery only. A catalog result is not an installed integration.

Maturity values are `discovered`, `assessed`, `adapted`, `contract-tested`, `workflow-proven`,
`blocked`, and `deprecated`. Trust is tracked separately as `official`, `verified`, `unverified`,
or `not-executable`.

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

The capability router tries only installed, enabled, execution-approved, compatible providers. A
provider timeout, invalid response, missing optional credential, or rate-limit response is recorded
and permits a configured fallback. It never fabricates an empty search result as a successful
response. Inputs and outputs with registered capability contracts are schema-validated. Workflows
must record database, query, retrieval date, and provider metadata.
