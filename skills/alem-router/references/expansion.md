# Context expansion and recovery

Expand context only after identifying a concrete missing input, output, or capability.

1. Search with `alem context search "<specific need>" --all`.
2. Distinguish enabled entries from installed-but-disabled and catalog-only candidates.
3. For an enabled entry, create a revised plan with `alem context plan` and an explicit
   `--include` value.
4. For an installed but disabled community integration, stop for execution approval before
   enabling it.
5. For a catalog-only candidate, report that integration work is required; never treat discovery
   metadata as an executable tool.
6. If a provider fails, let the capability router try approved fallbacks. Do not load every
   alternative provider's documentation into context.

Record the revised plan ID in the project handoff when expansion changes the method or evidence
path.
