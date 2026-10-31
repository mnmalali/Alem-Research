# Plugin security and trust model

Third-party plugins are arbitrary code. Alem 0.2 does **not** claim that a TOML
manifest, Python protocol, subprocess, or permission declaration isolates
that code.

## What Alem enforces

- Installation is rejected until the user gives explicit installation
  approval after inspecting the manifest and dependency plan.
- Execution requires a second explicit approval. Merely installing or enabling
  a plugin is not execution approval.
- The installed tree is hashed. Any file change invalidates the execution
  approval and prevents that provider from running until it is reviewed and
  reinstalled/updated.
- Workspace-local dependency files are separately hashed and their installed
  distributions are locked as `name==version`; execution approval binds both
  trees. Dependency installs accept only exact index pins, binary wheels, and
  no transitive resolution, and are staged before atomic replacement.
- Plugin code is never imported into the Alem process. Each invocation uses a
  fresh `python -I -S` subprocess, trusted-core-first import paths, a minimal
  environment, a JSON request/response protocol, and a timeout.
- Arbitrary parent-process environment variables are not forwarded. Declared
  credentials are supplied for one request and only to that plugin.
- Plugin source, dependencies, state, and data remain below workspace
  `.alem/`. Plugin trees may not contain symbolic links.
- Broken providers do not block a healthy configured fallback.
- Required plugin dependency edges are enforced in reverse: an enabled
  dependent prevents its dependency from being disabled or removed. Optional
  edges do not create that lock.

These controls reduce accidents and create an auditable boundary. They are not
security isolation.

## What Alem 0.2 does not enforce

Once approved, plugin Python code runs with the same operating-system account
as Alem. It can attempt to read or modify files outside the workspace, open
undeclared network connections, spawn processes, inspect the machine, or call
native interfaces. The manifest's `network`, filesystem, `subprocess`, and
`native_code` values are truthful-declaration requirements for review; v1 has
no portable enforcement mechanism. `python -I` isolates Python configuration,
not the operating system.

Do not run an untrusted plugin merely because `alem plugin validate` passes.
Validation proves schema and compatibility, not intent, provenance, or safety.

## Operator checklist

Before approving installation:

1. Confirm the repository, author, version/tag/commit, and license.
2. Read the complete plugin source and its transitive dependency plan.
3. Compare requested permissions and credentials with actual behavior.
4. Treat every dependency wheel, especially native code, as additional code
   requiring review. Exact pins and hashes detect later mutation but do not
   establish that the original package was safe.
5. Prefer a dedicated OS account, VM, or container for plugins that are not
   fully trusted. Disable network and mount only required workspace paths at
   that external boundary.

Before approving execution, inspect the installed files and digest-changing
update. Never provide credentials unrelated to the declared capability.
Disable and remove a plugin when it is no longer needed. `remove` preserves
plugin data by default to prevent accidental loss; request data purge
explicitly after reviewing the path.

## Future isolation adapters

A later API-compatible release may add opt-in platform backends such as a
locked-down container, Linux namespaces/seccomp, macOS sandbox profiles, or a
Windows AppContainer/Job boundary. Such a backend must be tested and described
per platform; Alem will not label a best-effort Python hook as a sandbox. The
manifest is suitable input to a real policy engine but never substitutes for
one.

Security reports should avoid public disclosure until maintainers have
acknowledged receipt. Repository-specific contact details must be added before
public release.
