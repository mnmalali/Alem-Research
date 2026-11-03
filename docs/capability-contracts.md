# Capability contracts and artifacts

Provider-neutral capability contracts live under `contracts/capabilities/<name>/<version>.json`.
Each contract identifies the capability and exact version and contains JSON Schemas for input and
output. Alem validates input before provider selection and validates each provider response before
accepting it. An invalid provider result is recorded as a provider failure and an approved fallback
may be attempted.

Inspect a contract with:

```bash
alem capability describe academic_search
```

Adding a provider for an existing capability does not change a workflow. A breaking semantic
change requires a new capability version that can coexist with the previous version.

## Artifact envelope

Large or durable results belong in project files, not conversation context. Register one with:

```bash
alem artifact register my-project 03-literature/records.jsonl \
  --type search.records \
  --creator org.alem.openalex \
  --source academic_search:1.0 \
  --evidence-status unverified
```

An artifact record preserves:

- stable identifier and type;
- creator and source;
- evidence-status label;
- project-relative path and SHA-256 digest;
- creation time;
- input artifact lineage; and
- structured metadata.

Use `alem artifact verify`, `list`, and `show` to inspect the durable record. Retrieved metadata is
normally `unverified` until the relevant source and claim have been checked.
