# Post-1.0 roadmap

These are additive integrations and hardening opportunities, not blockers to the stable local
contracts in 1.0.

- Add independently audited providers for Crossref, arXiv, PubMed, and Europe PMC.
- Select a license-compatible local PDF extraction implementation and add `pdf_extract` 1.0.
- Add BibTeX/CSL and optional Zotero `reference_management` providers.
- Add reproducible Jupyter/Quarto environment profiles.
- Add optional OS-enforced execution backends for Windows, macOS, and Linux.
- Add detached signature or Sigstore verification for accepted integration releases; schema 3 SHA-256
  digests pin content but do not authenticate who approved the registry.
- Add an optional MCP façade over the stable Alem context and capability gateway.
- Expand routing evaluation fixtures as community integrations are accepted.
- Observe the configured GitHub Actions matrix on the public repository and record run links in
  `docs/validation-report.md` before publishing platform-specific compatibility claims.
