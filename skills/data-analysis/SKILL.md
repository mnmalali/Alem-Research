---
name: data-analysis
description: Execute transparent, reproducible statistical or computational analysis against an approved plan.
---

# Data analysis

## Inputs

Approved analysis plan, immutable/raw-data references, data dictionary, prepared dataset, environment lock, and decision log.

## Procedure

1. Validate schema, units, ranges, missingness, duplicates, and cohort counts before modeling.
2. Separate immutable inputs, deterministic preparation, analysis, and presentation outputs.
3. Follow the predeclared plan; log deviations with timestamp, rationale, and whether outcome knowledge influenced them.
4. Report estimates, uncertainty, diagnostics, assumptions, sample sizes, and sensitivity analyses.
5. Use seeded randomness and record package/runtime versions. Never hand-edit generated values.
6. Apply disclosure/privacy controls before exporting tables or plots.

## Output

Scripts/notebooks, environment lock, validation report, decision log, machine-readable results, figures, and a results README under `10-analysis/`.

## Quality checks

- A clean run can regenerate outputs.
- Counts reconcile through every transformation.
- Statistical assumptions and failed diagnostics are visible.
- Interpretation is kept out of raw result artifacts.
