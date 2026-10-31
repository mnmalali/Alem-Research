# TODO

## Foundation release blockers

- Run the complete automated suite on Windows, Linux, and macOS.
- Perform real Codex and Claude Code discovery checks from fresh sessions.
- Update/authenticate the local Codex and Claude Code clients before repeating discovery checks.
- Exercise OpenAlex and Semantic Scholar against current terms and rate limits.
- Configure the final public repository URL, security contact, and maintainer identity.
- Ensure the POSIX launcher is committed with Git mode `100755` from a file-mode-aware checkout.
- Review every bundled and optional dependency license before a tagged release.

## Next phases

- Add Crossref, arXiv, PubMed, and Europe PMC as independent provider plugins.
- Add local PDF metadata/extraction only after resolving PyMuPDF licensing and alternatives.
- Add BibTeX/CSL and an optional Zotero adapter.
- Add explicit workflow checkpoint commands and structured handoff validation.
- Add reproducible Jupyter/Quarto environments inside the workspace.
- Evaluate OS-enforced plugin sandbox backends separately for Windows, macOS, and Linux.

Out of scope for v0.1: a hosted marketplace, distributed plugin service, automatic trust scoring,
and a general-purpose SAT dependency solver.
