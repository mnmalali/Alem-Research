# Upstream source audit

Status: foundation audit
Evidence captured: 2026-10-31 (Asia/Dubai)
Method: live GitHub repository/gist metadata, default-branch trees, README and installation documentation, dependency manifests, contribution guidance, and the complete license file were inspected. Repository state is pinned below; dates describe the upstream state observed during this audit, not a promise about future availability.

This audit is an architecture input and integration record, not permission to vendor upstream
work blindly. Alem has **no required runtime dependency on any source in this document**; optional
workspace-local adapters and curated assets are recorded in
[`upstream-integrations.md`](upstream-integrations.md).

## Decision summary

| Source | Observed revision | License | Alem decision |
| --- | --- | --- | --- |
| Karpathy, `llm-wiki` gist | `ac46de1ad27f92b28ac95459c782c07f6b8c964a` | No license stated | **Adapt the pattern independently.** Do not copy or redistribute the text. |
| Companion, Feynman | `89b0242919faf89b38dcb6ae8be92f6dbcd77203` (`v0.5.61`) | MIT | **Optional integration/wrapper only.** Do not make Feynman an Alem runtime dependency. |
| Orchestra Research, AI Research Skills | `773a52944ba4747a18bd4ae9ade53fff041adcbc` (`v1.7.2`) | MIT repository license | **Reference and selectively adapt after per-skill review.** Do not run its user-global installer from Alem. |
| Wenyu Chiou, AI Research Skills | `8547d889612ca624d523f39d20d35a97dbd87802` (catalog metadata `1.7.21`) | MIT | **Adapt contract and evidence-gate ideas.** Treat its external plugin repositories as separate upstreams. |
| Awesome AI Research Tools | `1369c3c55e17f37a9abbe7f4ddc5ba2b0636a7f1` | CC0-1.0 | **Reference as a discovery lead.** Independently verify every listed tool, license, price, privacy policy, and API before integration. |

The machine-readable companion is [`upstream-register.toml`](upstream-register.toml).

## 1. Karpathy's LLM Wiki concept

Primary source: [gist and revision](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f/ac46de1ad27f92b28ac95459c782c07f6b8c964a), created 2026-04-04.

### What it is

This is an implementation-neutral idea document, not a software package. It proposes three layers:

1. immutable raw sources as the source of truth;
2. an incrementally maintained, interlinked Markdown wiki; and
3. an agent instruction/schema document such as `AGENTS.md` or `CLAUDE.md`.

Its operating loop is `ingest -> query -> lint`. An index provides content navigation, while an append-only log records chronological maintenance. Obsidian is suggested as a viewer and Git as history; local search is optional once the corpus outgrows a hand-maintained index.

### Installation, configuration, and agent support

There is no installer, executable, dependency manifest, or fixed directory schema. The text explicitly presents the approach as modular and mentions Codex, Claude Code, OpenCode/Pi, and similar agents as possible maintainers. The chosen agent instruction file is the configuration surface.

### Maintenance and limitations

The inspected gist has one published revision. It is deliberately abstract: it supplies neither deterministic provenance checks nor conflict resolution, scale guarantees, access control, tests, or transactional writes. Markdown and links help humans inspect state but do not prove that a claim is correct or that a cited source was read.

### License decision

No license is stated on the gist. Public visibility is not a redistribution license. Alem therefore adopts only the uncopyrightable architectural ideas in an independently written implementation and cites the source; it must not copy the gist text, examples, or phrasing into distributed files without separate permission.

### Alem use

Adopt independently:

- immutable source records separated from derived knowledge;
- explicit knowledge-update rather than automatic rewriting after every chat;
- read-existing-content-first behavior;
- index, backlinks, contradictions, and an append-only maintenance log;
- `ingest`, `query`, and `lint` as distinct workflows.

Add what the idea document leaves open: YAML provenance fields, evidence status, approval gates, structured project state, validation, and Git-visible changes.

## 2. Feynman

Primary sources: [repository at audited revision](https://github.com/Companion-Inc/feynman/tree/89b0242919faf89b38dcb6ae8be92f6dbcd77203), [README](https://github.com/Companion-Inc/feynman/blob/89b0242919faf89b38dcb6ae8be92f6dbcd77203/README.md), [package manifest](https://github.com/Companion-Inc/feynman/blob/89b0242919faf89b38dcb6ae8be92f6dbcd77203/package.json), [license](https://github.com/Companion-Inc/feynman/blob/89b0242919faf89b38dcb6ae8be92f6dbcd77203/LICENSE), and [agent contract](https://github.com/Companion-Inc/feynman/blob/89b0242919faf89b38dcb6ae8be92f6dbcd77203/AGENTS.md).

### Architecture and capabilities

Feynman is a Node.js/TypeScript research-agent CLI built on the Pi coding-agent runtime. The audited package reports version `0.5.61` and requires Node `>=22.22.0`. It combines:

- a CLI/bootstrap/setup layer under `src/`;
- Pi extensions and research-database adapters under `extensions/`;
- Markdown workflow prompts and skills;
- four Pi subagents (`researcher`, `verifier`, `reviewer`, `writer`);
- persistent output, paper, experiment, note, and provenance artifacts; and
- a substantial Node test suite and release/provenance automation.

Its README lists alphaXiv, Semantic Scholar, OpenAlex, arXiv, PubMed, Europe PMC, bioRxiv, medRxiv, Crossref, web, Hugging Face, and local-document search. MCP is its extension route for tools such as Zotero.

### Installation, configuration, and dependencies

The documented primary installs are a remote shell/PowerShell installer or global npm package, followed by `feynman setup`. A skills-only bundle is documented for Codex and OpenCode. The runtime is Pi-first; the presence of repository `AGENTS.md` and `CLAUDE.md` is a contributor instruction surface, not evidence that the Feynman runtime itself is a native Codex/Claude plugin.

Direct runtime dependencies include Pi agent/MCP/web/document/subagent packages, `fast-xml-parser`, `undici`, `@clack/prompts`, `posthog-node`, and Companion's alpha hub. Model-provider access is configured separately. OpenAlex and Semantic Scholar keys are optional but avoid shared rate limits.

Anonymous PostHog telemetry is enabled by default and can be disabled with `FEYNMAN_TELEMETRY=off`; that privacy difference must be explicit in any Alem wrapper.

### Maintenance and limitations

The default branch was updated on 2026-10-30 and release `v0.5.61` was published that day, so it was actively maintained at audit time. Important boundaries for Alem are:

- upstream's default global installation is incompatible with Alem's workspace-only rule;
- a Node runtime and model provider remain required for the full CLI;
- upstream configuration, telemetry, outputs, and security boundaries are not Alem's contracts;
- its internal extension API is not Alem's stable plugin API; and
- an unavailable Feynman installation must never disable Alem's core workflows.

### License and Alem use

The full MIT license grants reuse subject to retaining its copyright and permission notice in copies or substantial portions. The foundation does not copy Feynman code, so no vendored notice is currently required. Alem may later provide an **optional, capability-adapted subprocess integration** after the user explicitly installs and approves a pinned Feynman version inside the workspace. Useful patterns to learn from are evidence sidecars, verifier separation, narrow research roles, failure-aware API adapters, and workflow-specific outputs.

## 3. Orchestra Research AI Research Skills

Primary sources: [repository at audited revision](https://github.com/Orchestra-Research/AI-Research-SKILLs/tree/773a52944ba4747a18bd4ae9ade53fff041adcbc), [README](https://github.com/Orchestra-Research/AI-Research-SKILLs/blob/773a52944ba4747a18bd4ae9ade53fff041adcbc/README.md), [installer package](https://github.com/Orchestra-Research/AI-Research-SKILLs/blob/773a52944ba4747a18bd4ae9ade53fff041adcbc/packages/ai-research-skills/package.json), [contribution guide](https://github.com/Orchestra-Research/AI-Research-SKILLs/blob/773a52944ba4747a18bd4ae9ade53fff041adcbc/CONTRIBUTING.md), and [license](https://github.com/Orchestra-Research/AI-Research-SKILLs/blob/773a52944ba4747a18bd4ae9ade53fff041adcbc/LICENSE).

### Architecture and capabilities

The repository is a large library of 98 `SKILL.md` packages organized into 23 numbered AI-research-engineering categories. A central autoresearch skill routes work through domain skills. Skill folders may include one-level `references/`, templates, scripts, and examples. A Claude marketplace manifest groups skills into installable categories, while an npm installer detects multiple agent hosts.

The collection is strongest in ML engineering: model architecture, training, post-training, evaluation, inference, RAG, MLOps, interpretability, and paper-writing support. Its contribution contract defines frontmatter, progressive disclosure, workflow checklists, examples, and validation expectations.

### Installation, configuration, and dependencies

The recommended `npx @orchestra-research/ai-research-skills` installer detects agents and writes a shared `~/.orchestra/skills/` tree with symlinks (copy fallback on Windows). It also offers a Claude Code marketplace. The installer package requires Node `>=18` and depends on `chalk`, `inquirer`, and `ora`. The README claims support for Claude Code, Codex, Gemini, Cursor, OpenCode, Hermes, Qoder, and others, but each host still requires its own discovery verification.

That user-global installer behavior is intentionally **not used by Alem**. A future import tool would copy a specifically approved, pinned skill into the Alem workspace and retain attribution.

### Maintenance and limitations

The latest audited release is `v1.7.2` (2026-06-16); repository activity continued on other refs through 2026-10-11. The library is broad and useful for discovery, but breadth creates risks:

- many skills describe optional frameworks, cloud services, or large compute stacks that most Alem users do not need;
- declared skill dependencies are guidance and are not an isolation boundary;
- upstream content and examples can age independently of the described tools;
- installing all skills increases routing ambiguity and prompt load; and
- claims about host support require real host testing.

The root `package.json` says `ISC`, while the repository license and shipped installer package say `MIT`. This appears to be legacy manifest drift, but it must be resolved with upstream before redistributing npm-root package material. Alem relies on the explicit repository `LICENSE` only for reviewed source files and records each imported file's provenance.

### License and Alem use

The repository's full MIT license was inspected. Any copied or adapted substantial content must retain the upstream copyright and permission notice and be recorded in Alem's attribution register. The foundation copies none of it. Alem may selectively adapt structural practices—concise frontmatter, progressive disclosure, testable checklists, and per-skill quality gates—after checking each candidate skill for relevance, accuracy, dependencies, license, and duplication.

## 4. WenyuChiou/ai-research-skills

Primary sources: [repository at audited revision](https://github.com/WenyuChiou/ai-research-skills/tree/8547d889612ca624d523f39d20d35a97dbd87802), [README](https://github.com/WenyuChiou/ai-research-skills/blob/8547d889612ca624d523f39d20d35a97dbd87802/README.md), [design contract](https://github.com/WenyuChiou/ai-research-skills/blob/8547d889612ca624d523f39d20d35a97dbd87802/docs/design-philosophy.md), [runtime contract](https://github.com/WenyuChiou/ai-research-skills/blob/8547d889612ca624d523f39d20d35a97dbd87802/docs/runtime-contract.md), [install guide](https://github.com/WenyuChiou/ai-research-skills/blob/8547d889612ca624d523f39d20d35a97dbd87802/docs/install.md), and [license](https://github.com/WenyuChiou/ai-research-skills/blob/8547d889612ca624d523f39d20d35a97dbd87802/LICENSE).

### Architecture and capabilities

This repository describes itself as a catalog/registry rather than a monorepo. Its marketplace points to five separately maintained plugin repositories that expose 17 portable skills. The catalog documents an eight-stage lifecycle, durable `.research/` and `.paper/` artifacts, schema-checked handoffs, evidence-gap states, human approval gates, and optional delegation adapters.

The executable literature runtime is a separate `research-hub-pipeline` Python distribution. Zotero, Obsidian, and NotebookLM are optional integrations rather than prerequisites for prompt-only guidance. Catalog-side JSON Schema, Python validators, test corpora, and CI test catalog consistency; they do not prove the behavior of every external plugin.

### Installation, configuration, and agent support

Claude Code marketplace installation is the primary and best-verified route. Codex, Cursor, Gemini, Hermes, OpenClaw, and generic clients use portable `SKILL.md` loading or separate host adapters, with varying verification levels. The documentation is unusually explicit that marketplace installation does not prove another host loaded a skill.

Several documented routes write user-level Claude directories or use global Python installation. Those routes violate Alem's workspace-only rule and are not reused. External plugin versions and Git refs in the marketplace are separate supply-chain inputs; a catalog version alone does not pin all transitive code.

### Maintenance and limitations

The audited default branch was updated on 2026-10-30. Catalog metadata reports `1.7.21`, while the latest GitHub release observed was `v1.7.18` (2026-10-29); consumers should pin a commit, not infer content identity from either label alone.

The upstream docs acknowledge important boundaries: the catalog validates registry shape rather than external runtime behavior, semantic correctness requires live testing, plugins live in other repositories, and some host compatibility is manual. Additional limitations for Alem are optional browser automation, external model/data destinations, Zotero credentials, and delegate CLIs.

### License and Alem use

The catalog is MIT licensed. Each referenced plugin repository and any bundled third-party asset still needs its own audit before copying. Alem does not vendor the catalog. It independently adopts strong ideas: durable typed handoffs, a hard distinction between installed instructions and executable capability, evidence-gap states, explicit human gates, honest compatibility claims, and small host adapters around one canonical system.

## 5. Awesome AI Research Tools

Primary sources: [repository at audited revision](https://github.com/0x11c11e/awesome-ai-research-tools/tree/1369c3c55e17f37a9abbe7f4ddc5ba2b0636a7f1), [README](https://github.com/0x11c11e/awesome-ai-research-tools/blob/1369c3c55e17f37a9abbe7f4ddc5ba2b0636a7f1/README.md), [contribution rules](https://github.com/0x11c11e/awesome-ai-research-tools/blob/1369c3c55e17f37a9abbe7f4ddc5ba2b0636a7f1/contributing.md), and [license](https://github.com/0x11c11e/awesome-ai-research-tools/blob/1369c3c55e17f37a9abbe7f4ddc5ba2b0636a7f1/LICENSE).

### Architecture, installation, and maintenance

This is a curated Markdown list, not executable software. The audited README contains 76 tools across discovery, agents, paper Q&A, references, citation graphs, writing, analysis, transcription, scholarly APIs, knowledge management, and trackers. A GitHub Action checks links. There is no runtime dependency or agent configuration.

The default branch was updated on 2026-10-08. The list says links were manually refreshed in August 2026, but a resolving link is not proof of maintenance quality, free access, security, privacy, reproducibility, or suitability.

### License and Alem use

The list is dedicated under CC0-1.0; its complete waiver/fallback license was inspected. CC0 applies to the list author's contribution, not the trademarks, code, documentation, datasets, or terms of each linked service. Alem uses it only to discover candidates, then audits a candidate's primary documentation and license. It is never a dependency or trust root.

## Licensing and dependency assessment

### Foundation dependency policy

| Class | Foundation decision |
| --- | --- |
| Required dependencies from these upstreams | None. |
| Vendored source or skill text | None in the foundation. |
| Optional executable integration | Feynman may be wrapped later through Alem's capability API, pinned and installed in the workspace only. |
| Optional skill import | One skill at a time, after relevance, security, license, dependency, and duplication review. |
| External catalog data | Reference-only; never treated as an executable trust signal. |

For future adoption, Alem must record the exact upstream URL, commit/tag, file paths, license, local modifications, dependency lock, and retained notices. A mutable branch name or `curl | shell` command is not a reproducible pin.

### Free-first classification

- Karpathy's concept, the inspected repositories, Feynman source, and the skill catalogs are publicly accessible; that does not make the model providers, APIs, compute, or third-party services they mention free.
- Feynman's Node runtime and many academic APIs can be used without a paid SaaS subscription, but model access and service rate limits remain external.
- Orchestra skills cover both open-source and commercial/cloud tools. A skill's MIT license says nothing about the described product's cost.
- Wenyu's core skill text can be read without every integration, but live model execution, NotebookLM, Zotero Web API, or browser automation have separate credentials, privacy, and availability constraints.
- The awesome list intentionally mixes open-source, freemium, and paid services; Alem must classify each integration independently.

## Architecture consequences for Alem

The audit supports six foundation choices:

1. **Alem owns a small, versioned extension API.** Upstream internal APIs are provider details behind adapters.
2. **Workflows request capabilities.** For example, literature review requests `academic_search`; it does not import Feynman, OpenAlex, Semantic Scholar, or a catalog directly.
3. **Host compatibility is an adapter concern.** Canonical agents, skills, workflows, and plugin state stay in Alem; Codex and Claude adapters expose the same source rather than fork it.
4. **Install state is workspace-local.** No upstream user-global installer is called by default.
5. **Evidence state is durable and typed.** Search results, claims, gaps, approvals, and handoffs survive agent sessions and distinguish verified evidence from interpretation.
6. **Manifests are not sandboxes.** Approval, digest pinning, subprocess boundaries, permission declarations, and documented OS-sandbox limitations are separate controls.

## Risks and unresolved decisions

- **Agent discovery:** Codex and Claude project-local discovery must be smoke-tested with real supported versions. A correctly placed file is not sufficient proof.
- **Upstream drift:** pins age. Updates need a diff, license recheck, test run, and renewed execution approval when code changes.
- **Transitive licensing:** a repository-level license may not cover copied third-party templates, documentation snapshots, data, or logos.
- **API terms and privacy:** academic providers differ in rate limits, attribution requirements, accepted identifiers, and data retention. Provider adapters must expose those differences without leaking them into workflows.
- **Skill conflicts:** importing large overlapping libraries would make routing ambiguous. Alem should curate a small default set and keep domain skills optional.
- **External runtimes:** wrapping Feynman or research-hub introduces their telemetry, credentials, models, and state conventions. An adapter must disclose and constrain those boundaries.
- **Windows links:** shared Codex/Claude skill discovery cannot assume symlink privileges; an adapter-generated pointer/copy strategy needs drift checks.
- **Security:** neither Markdown instructions nor plugin manifests isolate code. Real isolation depends on platform sandboxing; without it, execution remains explicitly trusted code with documented limits.

## Update procedure

Re-run this audit before vendoring or enabling an upstream integration:

1. fetch default-branch metadata and the intended tag/commit;
2. inspect the complete license and changed dependency manifests;
3. diff the old and new pinned revisions, including installer behavior and telemetry;
4. check security advisories and release notes;
5. update `upstream-register.toml` and attribution notices;
6. run Alem validation and integration tests inside a disposable workspace; and
7. request explicit user approval before installing or executing changed third-party code.
