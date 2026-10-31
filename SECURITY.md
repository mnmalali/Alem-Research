# Security policy

## Supported versions

The project is pre-1.0. Security fixes target the latest tagged minor release and the `main` branch.
Older development snapshots may require upgrading rather than backporting.

## Report privately

Use GitHub's **Report a vulnerability** feature for the repository. If that channel is unavailable,
contact the maintainer through a private address published in the repository profile. Do not open a
public issue before a fix or coordinated disclosure plan exists.

Include the affected version, operating system, minimal reproduction, impact, and whether secrets or
research data may have been exposed. Use synthetic data and revoke any accidentally included token.

## Plugin boundary

Treat third-party plugin code as arbitrary code. Manifests, approval prompts, hashes, and subprocess
execution improve reviewability and integrity; they do not create a security sandbox. Alem 0.2 does
not claim to stop approved malicious code from reading user-accessible files or using the network.
See [`docs/plugin-security.md`](docs/plugin-security.md).
