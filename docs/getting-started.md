# Getting started

> Alem 0.2 is an integration release. Plugin code is not sandboxed by the operating system. Inspect
> a plugin and its requested permissions before approving installation or execution.

## Set up a local workspace

Prerequisites are Git and Python 3.11 or newer. No global package installation is required.

On Windows PowerShell:

```powershell
git clone https://github.com/alem-research/alem-research.git
Set-Location alem-research
.\alem.ps1 setup --create-venv
.\alem.ps1 health
```

On macOS or Linux:

```bash
git clone https://github.com/alem-research/alem-research.git
cd alem-research
sh ./alem setup --create-venv
./alem health
```

The setup command creates only ignored paths under `.alem/`, plus regenerable skill adapters under
the repository's `.agents/` and `.claude/` directories. It automatically installs and enables
Alem's official plugins. Community plugins are listed and classified during setup but remain
opt-in; the agent should tell you they are available and ask before installing them. Setup does
not edit user-level agent settings.

## Create a research project

```bash
./alem project create "Transparent evaluation of retrieval systems"
```

Open the new directory under `projects/`, complete `PROJECT.md`, and use the numbered folders in
order when the decision depends on earlier work. Human approval gates are recorded in project
state; an agent must not silently make consequential research decisions.

## Add academic-search providers

Official academic-search providers are installed during setup. To inspect them manually:

```bash
./alem plugin search academic
./alem plugin validate plugins/official/openalex
```

Community plugins are not installed automatically. Review their verification status with
`./alem plugin search`, then install only the ones you choose. The configured official route
uses OpenAlex as default and Semantic Scholar as fallback.
The exact plugin commands and failure behavior are documented in
[`plugin-development.md`](plugin-development.md).

## Keep research evidence

Use project evidence records for every consequential claim and keep verified source metadata
separate from interpretation. Update the shared wiki only through the explicit knowledge workflow,
then rebuild links:

```bash
./alem knowledge index
```

See [`research-lifecycle.md`](research-lifecycle.md) for stage outputs and
[`knowledge-system.md`](knowledge-system.md) for frontmatter and provenance rules.
