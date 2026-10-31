# Workflows

Workflow specifications are resumable contracts. They name capabilities, inputs, outputs, validation, and human gates; the plugin registry chooses a provider at runtime. Provider names belong only in execution provenance.

State values are `pending`, `running`, `awaiting_approval`, `complete`, `failed`, or `blocked`. A runner writes stage state to the active project's `STATUS.md` and keeps immutable run evidence under the stage folder.

- `full-research-lifecycle.yaml` maps the complete lifecycle.
- `literature-review.yaml` is an executable literature workflow skeleton.
- `research-design.yaml` covers the question-to-protocol gate.
- `knowledge-update.yaml` is the only standard path for promoting project findings into shared knowledge.
