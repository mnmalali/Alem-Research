# Upstream integration map

This document records how supplied research repositories become usable Alem extensions. A URL
in the upstream register is not treated as an installed tool: each integration has a local
manifest, a pinned source revision, a license/attribution record, tests, and explicit install
and execution approval.

| Upstream | Alem integration | Current status | Boundary |
| --- | --- | --- | --- |
| Companion Feynman `89b0242` | `community.feynman-bridge` | Implemented and enabled in this workspace | Installed as ignored workspace runtime `0.5.61`; telemetry defaults off; subprocess is approved separately |
| Orchestra AI Research Skills `773a529` | `community.orchestra-research-skills` | Six curated skill assets imported | Optional, namespaced instructions; no global installer; full library is not silently bulk-installed |
| Wenyu AI Research Skills `8547d88` | `community.wenyu-research-catalog` | Implemented offline catalog tool | Catalog metadata only; linked repositories and `research-hub-pipeline` remain separate integrations |
| Awesome AI Research Tools `1369c3c` | `community.awesome-research-tools-catalog` | Implemented offline discovery tool | Results are leads, not endorsements or auto-install targets |
| Karpathy LLM Wiki gist `ac46de1` | Alem knowledge architecture | Independently implemented | Not executable; no license was stated, so gist text is not redistributed |

## Install the integrations

Official plugins are installed and enabled automatically by `alem setup`. Community plugins are
reported during setup but remain opt-in:

```powershell
.\alem.ps1 setup --create-venv
.\alem.ps1 plugin search
```

Review the plugin source first, then use the normal two-step Alem approval flow:

```powershell
.\alem.ps1 plugin validate plugins/community/orchestra-research-skills
.\alem.ps1 plugin install community.orchestra-research-skills --approve
.\alem.ps1 plugin enable community.orchestra-research-skills --approve

.\alem.ps1 plugin install community.wenyu-research-catalog --approve
.\alem.ps1 plugin enable community.wenyu-research-catalog --approve

.\alem.ps1 plugin install community.awesome-research-tools-catalog --approve
.\alem.ps1 plugin enable community.awesome-research-tools-catalog --approve
```

The Feynman adapter uses a deliberately workspace-local CLI install. Alem does not run Feynman's
global npm installer:

```powershell
npm install --prefix .alem/tools/feynman @companion-ai/feynman@0.5.61 --no-audit --no-fund
.\alem.ps1 plugin install community.feynman-bridge --approve
.\alem.ps1 plugin enable community.feynman-bridge --approve
```

## Query the catalogs

```powershell
.\alem.ps1 capability invoke research_skill_catalog --input '{"query":"design","limit":10}'
.\alem.ps1 capability invoke research_tool_catalog --input '{"query":"citation","limit":10}'
```

Catalog results preserve their upstream revision in response metadata. They are discovery
evidence only; a contributor must audit the candidate's source, license, dependencies, privacy,
security, and runtime contract before adding a new executable plugin.
