---
name: experiment-design
description: Define controlled experiments, computational benchmarks, and run records that resist outcome-driven changes.
---

# Experiment design

## Inputs

Approved hypotheses, experimental units, interventions/conditions, measures, resources, ethics, and analysis plan.

## Procedure

1. Define experimental unit, treatment assignment, controls, randomization, blinding, replication, and contamination risks.
2. Set primary metrics, baselines, minimum meaningful effects, stopping criteria, and failure criteria.
3. Justify sample/run count and factor design; distinguish biological/independent replication from repeated measurement.
4. Freeze configurations, data versions, seeds, code revision, hardware/software environment, and logging schema.
5. Pilot procedures without consuming confirmatory evidence where that distinction matters.
6. Register every run, including failed or excluded runs, and apply only predeclared exclusion rules.

## Output

`09-experiments/experiment-plan.md`, configuration schema, run registry, deviation log, and approval gate.

## Quality checks

- Controls address important alternative explanations.
- Replication unit is correct.
- Outcome-dependent stopping is prevented or disclosed.
- Failed runs remain auditable.
