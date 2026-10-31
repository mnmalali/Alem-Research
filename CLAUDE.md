# Claude Code entry point

Read and follow [`AGENTS.md`](AGENTS.md); it is the shared source of truth for all coding agents in Alem Research.

Claude-specific notes:

- Discover project-local skills through `.claude/skills/`; those entries point to the canonical definitions in `skills/`.
- Keep plans and generated state inside this workspace.
- Do not create or edit user-level `~/.claude` configuration.
- Use the same evidence, approval, handoff, and capability-routing rules as every other agent.
