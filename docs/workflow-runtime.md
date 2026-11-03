# Workflow runtime

Workflow YAML is executable state rather than a prompt-only checklist. Alem validates bundled
definitions, starts project-local run records, resumes the current step, invokes single-capability
steps, checks expected outputs, registers capability results as artifacts, and blocks at human
approval gates.

```bash
alem workflow validate full-research-lifecycle
alem workflow start full-research-lifecycle --project my-project
alem workflow next <run-id> --project my-project
alem workflow complete <run-id> 01 --project my-project \
  --evidence 01-ideation/candidate-topics.md
alem workflow approve <run-id> choose_direction --project my-project \
  --approver "Researcher name" --decision "Selected direction A for the recorded reasons."
alem workflow status <run-id> --project my-project
```

Agent or human-authored steps move to `awaiting_agent` until their expected files exist and the
step is explicitly completed. A capability step can be executed with `workflow next --input` when
it declares exactly one capability. Multiple-capability steps remain explicit so that evidence
from each operation can be reviewed before completion.

Run records and an append-only event log live under
`projects/<project>/provenance/workflow-runs/`. A managed block in `STATUS.md` identifies the
current run and step. Alem never interprets creating a file as approval of a research question,
methodology, consequential collection, analysis choice, or release.
