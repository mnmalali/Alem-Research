# Extension API versioning and deprecation policy

Alem versions three related surfaces independently:

1. Alem releases use semantic versions.
2. The extension API uses `major.minor`; current version is `1.0`.
3. The strict plugin manifest has an integer `schema_version`; current schema
   is `1`.

A plugin declares an API range such as `>=1.0,<2.0`. Installation refuses an
incompatible range. Capability contracts also have versions: a provider of
`academic_search` `1.0` is interchangeable only with consumers written for
that contract.

Execution requests name an exact `capability_version`, defaulting to `1.0` for
the foundation API. Provider discovery and routing filter on that exact value
before applying configured default/fallback IDs. There is no implicit
major-version or minor-version coercion in schema 1.

## Compatibility rules

- Patch and minor Alem releases may add optional request context, response
  metadata, manifest warnings, public helper classes, and new capabilities.
- Within API major 1, existing required request fields, response meanings,
  public protocol method signatures, and manifest fields will not be removed
  or reinterpreted incompatibly.
- New optional manifest keys require a new manifest schema because schema 1
  rejects unknown keys. Alem may read multiple schema versions during a
  migration.
- Removing or renaming a public API symbol, adding a required protocol method,
  or changing JSON semantics requires API major 2.
- Capability breaking changes use a new capability version and may coexist
  with the old one.

## Deprecation

Deprecations are documented in release notes and emitted during validation.
An API 1 feature receives at least one minor-release cycle and 90 days of
notice before removal, whichever is longer. Removal occurs only in the next
major API. Security fixes may disable unsafe behavior sooner; maintainers will
publish the reason and migration path.

Official plugins test the oldest supported API range and the current release.
Community maintainers should use bounded ranges, avoid `>=1.0` without an upper
major bound, and test warnings as part of update preparation.
