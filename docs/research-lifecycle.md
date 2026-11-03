# Research lifecycle

Alem represents research as persistent stages, not a single conversation. A stage consumes checked-in project artifacts and produces the next set of reviewable artifacts. `workflows/full-research-lifecycle.yaml` is the machine-readable map and `alem workflow` maintains resumable run state.

| Stage | Main artifact | Human gate |
|---|---|---|
| 01 Ideation | candidate topic matrix | choose direction |
| 02 Gap assessment | novelty and gap memo | approve final question |
| 03 Search | search protocol and raw records | confirm scope |
| 04 Evidence synthesis | evidence table and review | resolve exclusions |
| 05 Questions/hypotheses | question and hypothesis register | approve question |
| 06 Methodology | protocol and analysis plan | approve methodology |
| 07 Dataset discovery | dataset assessment | approve acquisition |
| 08 Preparation | data dictionary and preparation log | approve consequential collection |
| 09 Experiments | experiment registry and run records | approve deviations |
| 10 Analysis | scripts, outputs, statistical decision log | approve analysis choices |
| 11 Interpretation | results and limitations memo | approve claims |
| 12 Knowledge | proposed wiki update and change log | approve merge when material |
| 13 Writing | manuscript draft | approve authorship and content |
| 14 Citation verification | citation ledger | resolve unsupported claims |
| 15 Review | reviewer findings and response matrix | approve revisions |
| 16 Publication | reproducibility bundle and release checklist | approve release |

## Resume protocol

On entry, read `PROJECT.md`, `STATUS.md`, the current stage README, and all referenced evidence records. Confirm that required upstream gates are recorded. On exit, write artifacts atomically, update `STATUS.md`, and leave a handoff containing unresolved decisions and the exact next command or workflow.

Workflow commands never substitute for scientific judgment. Agent-authored steps require explicit
completion, expected artifacts are checked, and declared human gates block downstream progress
until an approver and decision are recorded.

## Capability routing

Workflow files request capabilities such as `academic_search`, `citation_metadata`, `pdf_extract`, `data_analysis`, and `bibliography_export`. The plugin registry resolves providers from workspace configuration. Artifacts record the provider actually used, but never make that provider a prerequisite for resuming the workflow.
