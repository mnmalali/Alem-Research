from __future__ import annotations

import json
from pathlib import Path

import pytest

from alem.artifacts import register_artifact, verify_artifact
from alem.context import activate_plan, build_context_index, load_context_index, plan_context
from alem.contracts import ContractRegistry
from alem.errors import AlemError
from alem.extensions.errors import PluginExecutionError
from alem.integrations import load_integrations, validate_integrations
from alem.setup_workspace import sync_all_skill_adapters
from alem.workflows import advance_workflow, approve_gate, complete_step, start_workflow
from alem.workspace import Workspace


def workspace(tmp_path: Path) -> Workspace:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "alem.toml").write_text(
        """[alem]
workspace_version = 1
name = "Context test"

[plugins]
api_version = "1.0"
catalogues = []
require_install_approval = true
require_execution_approval = true

[context]
mode = "lazy"
max_skills = 3
max_capabilities = 3
max_context_tokens = 4000
allow_expansion = true
""",
        encoding="utf-8",
    )
    for name, description in (
        ("alem-router", "Select minimal research context."),
        ("literature-search", "Find scholarly papers reproducibly."),
        ("citation-verification", "Verify that citations support manuscript claims."),
        ("data-analysis", "Analyze approved datasets reproducibly."),
    ):
        skill = root / "skills" / name / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n# {name}\n",
            encoding="utf-8",
        )
    project = root / "projects" / "study"
    (project / "provenance").mkdir(parents=True)
    (project / "PROJECT.md").write_text("# Study\n", encoding="utf-8")
    (project / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    workflows = root / "workflows"
    workflows.mkdir()
    (workflows / "test-flow.yaml").write_text(
        """schema_version: 1
id: test-flow
name: Test flow
steps:
  - id: scope
    action: Write the scope
    output: 01-scope.md
    gate: approve_scope
  - id: report
    action: Write the report
    output: 02-report.md
""",
        encoding="utf-8",
    )
    return Workspace(root.resolve())


def test_lazy_context_selects_only_relevant_skills(tmp_path: Path) -> None:
    ws = workspace(tmp_path)
    ws.ensure_runtime()
    index = build_context_index(ws)
    adapters = sync_all_skill_adapters(ws, mode="lazy")
    plan = plan_context(ws, "Find papers and verify the citations")
    active = activate_plan(ws, plan.id)

    assert len(index["entries"]) == 3
    assert adapters["skills"] == 1
    assert (ws.root / ".agents/skills/alem-router/SKILL.md").is_file()
    assert not (ws.root / ".agents/skills/data-analysis/SKILL.md").exists()
    assert "literature-search" in {item.id for item in plan.skills}
    assert "citation-verification" in {item.id for item in plan.skills}
    assert "data-analysis" not in {item.id for item in plan.skills}
    assert active["plan_id"] == plan.id


def test_lazy_startup_adapter_count_does_not_grow_with_catalog(tmp_path: Path) -> None:
    ws = workspace(tmp_path)
    for index in range(120):
        skill = ws.root / "skills" / f"specialized-{index}" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            "---\n"
            f"name: specialized-{index}\n"
            f"description: Handle specialized domain task {index}.\n"
            "---\n"
            "# Specialized\n",
            encoding="utf-8",
        )

    result = sync_all_skill_adapters(ws, mode="lazy")

    assert result["skills"] == 1
    assert len(list((ws.root / ".agents/skills").glob("*/SKILL.md"))) == 1
    assert len(list((ws.root / ".claude/skills").glob("*/SKILL.md"))) == 1


def test_context_index_rebuilds_when_skill_metadata_changes(tmp_path: Path) -> None:
    ws = workspace(tmp_path)
    ws.ensure_runtime()
    first = build_context_index(ws)
    skill = ws.root / "skills/literature-search/SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8").replace("Find scholarly", "Discover academic"),
        encoding="utf-8",
    )

    second = load_context_index(ws)

    assert second["source_digest"] != first["source_digest"]
    entry = next(item for item in second["entries"] if item["id"] == "literature-search")
    assert "Discover academic" in entry["description"]


def test_artifact_registration_detects_tampering(tmp_path: Path) -> None:
    ws = workspace(tmp_path)
    artifact = ws.root / "projects/study/evidence.json"
    artifact.write_text('{"claim":"reported"}\n', encoding="utf-8")
    record = register_artifact(
        ws,
        "study",
        "evidence.json",
        artifact_type="evidence.record",
        creator="test-provider",
        source="fixture",
        evidence_status="reported_finding",
    )

    assert verify_artifact(ws, "study", record.id)["valid"] is True
    artifact.write_text('{"claim":"changed"}\n', encoding="utf-8")
    assert verify_artifact(ws, "study", record.id)["valid"] is False


def test_contract_registry_validates_inputs(tmp_path: Path) -> None:
    ws = workspace(tmp_path)
    contract = ws.root / "contracts/capabilities/example/1.0.json"
    contract.parent.mkdir(parents=True)
    contract.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "capability": "example",
                "version": "1.0",
                "input": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {"query": {"type": "string", "minLength": 1}},
                },
                "output": {"type": "object"},
            }
        ),
        encoding="utf-8",
    )
    loaded = ContractRegistry(ws).get("example")
    assert loaded is not None
    loaded.validate_input({"query": "valid"})
    with pytest.raises(PluginExecutionError, match="violates its contract"):
        loaded.validate_input({})


def test_integration_registry_separates_maturity_and_trust(tmp_path: Path) -> None:
    ws = workspace(tmp_path)
    registry = ws.root / "integrations/registry.toml"
    registry.parent.mkdir()
    registry.write_text(
        """schema_version = 2

[[integrations]]
id = "candidate-tool"
name = "Candidate tool"
kind = "provider"
status = "discovered"
trust = "unverified"
capabilities = ["paper_metadata"]
cost = "unknown"
authentication = "unknown"
privacy = "Not yet assessed."
notes = "Discovery record only."
""",
        encoding="utf-8",
    )

    records = load_integrations(ws)
    validation = validate_integrations(ws)

    assert records[0].status == "discovered"
    assert records[0].trust == "unverified"
    assert validation == {
        "valid": True,
        "schema_version": 2,
        "integrations": 1,
        "errors": [],
    }


def test_workflow_runs_resume_and_require_human_gate(tmp_path: Path) -> None:
    ws = workspace(tmp_path)
    project = ws.root / "projects/study"
    run = start_workflow(ws, "test-flow", "study")
    run = advance_workflow(ws, "study", run["id"])
    assert run["state"] == "awaiting_agent"

    (project / "01-scope.md").write_text("# Scope\n", encoding="utf-8")
    run = complete_step(ws, "study", run["id"], "scope")
    assert run["state"] == "awaiting_approval"
    with pytest.raises(AlemError, match="awaiting a recorded human approval"):
        advance_workflow(ws, "study", run["id"])

    run = approve_gate(
        ws,
        "study",
        run["id"],
        "approve_scope",
        approver="Researcher",
        decision="Scope accepted for the fixture.",
    )
    assert run["current_step"] == "report"
    (project / "02-report.md").write_text("# Report\n", encoding="utf-8")
    run = complete_step(ws, "study", run["id"], "report")
    assert run["state"] == "complete"
    assert "State: `complete`" in (project / "STATUS.md").read_text(encoding="utf-8")
