---
name: alem-router
description: Select and load the smallest approved set of Alem research skills and capabilities needed for the current task.
---

# Alem context router

Use Alem's local context index instead of scanning or loading the complete installed ecosystem.

1. Read the active project's `PROJECT.md` and `STATUS.md` when a project is in scope.
2. Run `alem context plan "<the user's task>" --json` from the workspace root.
3. Inspect the selected skills, capabilities, inactive suggestions, and estimated context size.
4. Activate the plan with `alem context activate <plan-id>`.
5. Read the complete `SKILL.md` only for each selected skill path. Read its supporting references only when its instructions route to them.
6. Invoke executable integrations through `alem capability invoke`; do not load provider source code merely to use a capability.
7. Keep installation, execution approval, and task activation separate. Activation never authorizes a community plugin or an external write.
8. If the plan lacks a necessary capability, use `alem context search "<need>" --all` and read [references/expansion.md](references/expansion.md). Do not load the whole catalog.

Before an external write, consequential data collection, methodology decision, analysis lock, or manuscript release, retain the workspace's human approval gates.

For interpreting plans or resolving ambiguous routing, read [references/routing.md](references/routing.md).
