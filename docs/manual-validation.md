# Manual release validation

Automated tests cannot prove coding-agent discovery, third-party service availability, or every
operating-system setup path. Complete this checklist before calling a release stable.

## Fresh clone

- Clone into a directory without an existing `.alem/`.
- Run setup from PowerShell on Windows and a POSIX shell on macOS or Linux.
- Confirm every created path is inside the clone.
- Confirm user-level `.codex`, `.claude`, `.agents`, Python, and Node locations are unchanged.
- Run `alem health` and investigate every failure.

## Agent discovery

- Start a new Codex session in the repository and ask it to name the canonical `literature-search`
  skill path after reading project instructions.
- Start a new Claude Code session and perform the same check.
- Ask each agent to explain that adapters are not independent copies.
- Confirm neither agent reports a skill that is absent from `skills/`.

## Plugin lifecycle

- Validate the third-party example plugin.
- Confirm installation without explicit approval fails.
- Install it locally and confirm no global environment changes.
- Confirm invocation before execution approval fails.
- Enable with execution approval, discover its capability, and invoke it.
- Modify an installed plugin file and confirm its digest approval is invalidated.
- Disable it, confirm it is no longer routed, then remove it.
- Install both academic-search providers and verify configured default and fallback behavior using a
  recorded test query. Do not interpret a network outage as a passing test.

## Research integrity

- Create a project and resume each workflow from its on-disk state in a fresh agent session.
- Verify a literature-search run records query, database, date, screening counts, and exclusions.
- Confirm a made-up DOI is rejected or marked unverified rather than entered as evidence.
- Confirm the research question, methodology, analysis, and final-manuscript gates require a human
  decision record.
- Export a project and inspect the archive for secrets, raw data, and private files.
