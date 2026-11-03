# Routing decisions

An Alem context plan is a bounded recommendation, not evidence that every selected integration is
safe, healthy, or appropriate. Prefer the smallest set that can produce the requested artifact.

## Selection order

1. Match the requested outcome and current lifecycle stage.
2. Match available input and required output artifact types.
3. Exclude incompatible platforms, unavailable runtimes, and unapproved providers.
4. Prefer read-only and local providers when they satisfy the task.
5. Use the configured capability default and fallbacks instead of choosing a provider by brand.
6. Load a domain-specific skill only when the task actually enters that domain.

Use `alem context explain [plan-id]` when the selection is surprising. The plan's inactive
suggestions are discovery leads; they are not installed or approved tools.

When the user explicitly names a compatible installed integration, add it with `--include`. When
they exclude one, respect `--exclude` even if it otherwise ranks highly.
