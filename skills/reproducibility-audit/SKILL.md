---
name: reproducibility-audit
description: Audit whether an independent researcher can recover inputs, environment, procedures, and reported outputs.
---

# Reproducibility audit

## Inputs

Repository revision, protocol, data inventory, environment locks, scripts/notebooks, run registry, outputs, manuscript, and access constraints.

## Procedure

1. Build a dependency graph from source data and code revision to every reported table/figure/result.
2. Verify acquisition recipes, versions/checksums, licenses, secrets handling, and documented substitutions for restricted data.
3. Recreate the environment from project-local instructions on a clean path where practical.
4. Run validation and deterministic/seeded pipelines; compare produced artifacts and tolerances.
5. Check for hidden manual steps, absolute paths, untracked files, stale outputs, and notebook execution-order dependence.
6. Grade each item as reproduced, reproducible-not-run, blocked-by-access, divergent, or undocumented.

## Output

`16-publication/reproducibility-report.md`, machine-readable audit results, divergence evidence, and prioritized remediation list.

## Quality checks

- “Reproduced” is reserved for an executed comparison.
- Restricted inputs are not exposed.
- Failures include commands, environment, and observed output.
- Release blockers are explicit.
