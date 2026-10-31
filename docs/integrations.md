# Integrations

No integration is mandatory. An unavailable provider must not prevent local project, knowledge,
evidence, or writing workflows from operating.

## See implemented status

Run:

```bash
./alem integration list
```

The command reads `integrations/registry.toml`, which distinguishes bundled plugins from planned
work. `OpenAlex` and `Semantic Scholar` are the only network integrations implemented in the
foundation release. Both expose the abstract `academic_search` capability and can be replaced.

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
response. Workflows must record database, query, retrieval date, and provider metadata.
