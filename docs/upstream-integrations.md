# Upstream integration map

An upstream repository or catalog entry is a candidate, not an accepted Alem tool. Acceptance is
recorded explicitly in `integrations/registry.toml` with a pinned release version and source-tree
digest. Only accepted rows are provisioned automatically by normal setup and update. Catalogues
remain discovery metadata; they do not trigger remote cloning, installation, or code execution.

| Upstream or contribution | Alem integration | Acceptance | Current behavior |
| --- | --- | --- | --- |
| OpenAlex | `org.alem.openalex` | Accepted, Alem-authored | Managed academic-search provider; network service readiness is reported. |
| Semantic Scholar | `org.alem.semantic-scholar` | Accepted, Alem-authored | Managed academic-search fallback; an API key is optional. |
| Orchestra AI Research Skills | `community.orchestra-research-skills` | Accepted, Alem-authored adapter with upstream attribution | Reviewed skills ship in the same managed release and are indexed lazily. |
| Wenyu AI Research Skills | `community.wenyu-research-catalog` | Accepted, Alem-authored adapter with upstream attribution | Offline discovery metadata; linked tools remain candidates. |
| Awesome AI Research Tools | `community.awesome-research-tools-catalog` | Accepted, Alem-authored adapter with upstream attribution | Offline discovery leads; listed tools are not endorsed or installed. |
| Companion Feynman | `community.feynman-bridge` | Candidate | The separate upstream runtime is not yet reproducibly provisioned by Alem, so the bridge remains unavailable for automatic setup. |
| Crossref, arXiv, PubMed, Europe PMC, Zotero, local PDF extraction | None yet | Candidate | No accepted adapter is included. Each requires a separate implementation and review. |
| Karpathy LLM Wiki gist | Alem knowledge architecture | Not executable | Independently implemented; source text is not redistributed because no license was stated. |

The names `community.*` in this table identify integration IDs, not proof that the adapter was
written by the upstream project. The registry's `authorship` and `contributor` fields record who
authored the Alem adapter and preserve upstream credit separately.

## User commands

```powershell
.\alem.ps1 setup --create-venv
.\alem.ps1 tools list
.\alem.ps1 tools status
.\alem.ps1 tools doctor
.\alem.ps1 update
```

Setup and update automatically reconcile accepted releases. They do not separately install an
upstream command-line client, modify user-level agent settings, or install model weights. A tool
with an API, account, GPU, runtime, or external service prerequisite remains listed and reports
what is missing. Alem never prints secret values.

## Query the catalogs

```powershell
.\alem.ps1 capability invoke research_skill_catalog --input '{"query":"design","limit":10}'
.\alem.ps1 capability invoke research_tool_catalog --input '{"query":"citation","limit":10}'
```

Catalog results preserve source and revision metadata. They are discovery evidence only. A
contributor must audit source, license, dependencies, privacy, security, and runtime behavior before
submitting an adapter. See [`plugin-development.md`](plugin-development.md) for the build, validate,
PR, maintainer acceptance, release, and automatic availability path.
