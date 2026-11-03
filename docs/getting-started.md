# Getting started

> Alem 1.0 is a stable local integration release. Plugin code is not sandboxed by the operating system. Inspect
> a plugin and its requested permissions before approving installation or execution.

## Set up a local workspace

Prerequisites are Git and Python 3.11 or newer. No global package installation is required.

On Windows PowerShell:

```powershell
git clone https://github.com/mnmalali/Alem-Research.git
Set-Location Alem-Research
.\alem.ps1 setup --create-venv
.\alem.ps1 health
```

On macOS or Linux:

```bash
git clone https://github.com/mnmalali/Alem-Research.git
cd Alem-Research
sh ./alem setup --create-venv
./alem health
```

The setup command creates only ignored paths under `.alem/`, plus regenerable skill adapters under
the repository's `.agents/` and `.claude/` directories. It automatically installs and enables
Alem's official plugins. Community plugins are listed and classified during setup but remain
opt-in; the agent should tell you they are available and ask before installing them. Setup does
not edit user-level agent settings.

Setup defaults to lazy context mode. Only the `alem-router` adapter is exposed at startup; all
other installed skills and capabilities remain available through the local context index.

## Create a research project

```bash
./alem project create "Transparent evaluation of retrieval systems"
```

Open the new directory under `projects/`, complete `PROJECT.md`, and use the numbered folders in
order when the decision depends on earlier work. Human approval gates are recorded in project
state; an agent must not silently make consequential research decisions.

Plan and activate only the context needed for the current task:

```bash
./alem context plan "Find recent papers and verify their citations"
./alem context activate <plan-id>
```

Start the durable lifecycle when the project inputs are ready:

```bash
./alem workflow start full-research-lifecycle --project my-research-topic
```

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
