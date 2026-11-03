"""Resumable workflow state, capability execution, and human approval gates."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from alem.artifacts import register_artifact
from alem.config import load_config
from alem.errors import AlemError
from alem.extensions import PluginManager
from alem.projects import slugify
from alem.workspace import Workspace

WORKFLOW_SCHEMA_VERSION = 1
RUN_SCHEMA_VERSION = 1
RUN_STATES = {
    "pending",
    "running",
    "awaiting_agent",
    "awaiting_approval",
    "complete",
    "failed",
    "blocked",
}


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    id: str
    name: str
    action: str | None
    skill: str | None
    capabilities: tuple[str, ...]
    capability_versions: Mapping[str, str]
    outputs: tuple[str, ...]
    gate: str | None


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    id: str
    name: str
    path: Path
    required_inputs: tuple[str, ...]
    steps: tuple[WorkflowStep, ...]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _workflow_path(workspace: Workspace, workflow_id: str) -> Path:
    if "/" in workflow_id or "\\" in workflow_id or workflow_id.startswith("."):
        raise AlemError("workflow id must be a filename stem")
    for suffix in (".yaml", ".yml"):
        candidate = workspace.path("workflows", workflow_id + suffix)
        if candidate.is_file():
            return candidate
    raise AlemError(f"unknown workflow: {workflow_id}")


def load_workflow(workspace: Workspace, workflow_id: str) -> WorkflowDefinition:
    path = _workflow_path(workspace, workflow_id)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise AlemError(f"cannot read workflow {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != WORKFLOW_SCHEMA_VERSION:
        raise AlemError(f"workflow {workflow_id} must use schema_version: 1")
    declared_id = raw.get("id")
    name = raw.get("name")
    if declared_id != workflow_id or not isinstance(name, str) or not name.strip():
        raise AlemError(f"workflow identity does not match {path.name}")
    inputs = raw.get("inputs", {})
    required_inputs: tuple[str, ...] = ()
    if isinstance(inputs, dict):
        required = inputs.get("required", [])
        if isinstance(required, list) and all(isinstance(item, str) for item in required):
            required_inputs = tuple(required)

    raw_steps = raw.get("steps", raw.get("stages"))
    if not isinstance(raw_steps, list) or not raw_steps:
        raise AlemError(f"workflow {workflow_id} must define non-empty steps or stages")
    gate_after: dict[str, str] = {}
    raw_gates = raw.get("human_gates", [])
    if isinstance(raw_gates, list):
        for value in raw_gates:
            if (
                isinstance(value, dict)
                and isinstance(value.get("after"), str)
                and isinstance(value.get("id"), str)
            ):
                gate_after[value["after"]] = value["id"]

    steps: list[WorkflowStep] = []
    seen: set[str] = set()
    for index, value in enumerate(raw_steps):
        if not isinstance(value, dict):
            raise AlemError(f"workflow step {index} must be an object")
        step_id = str(value.get("id", "")).strip()
        if not step_id or step_id in seen:
            raise AlemError(f"workflow step {index} has a missing or duplicate id")
        seen.add(step_id)
        capability = value.get("capability")
        capabilities_value = value.get("capabilities")
        capabilities: tuple[str, ...]
        if isinstance(capability, str):
            capabilities = (capability,)
        elif isinstance(capabilities_value, list) and all(
            isinstance(item, str) for item in capabilities_value
        ):
            capabilities = tuple(capabilities_value)
        else:
            capabilities = ()
        versions_value = value.get("capability_versions", {})
        versions: dict[str, str] = {}
        if isinstance(versions_value, dict):
            versions.update(
                {
                    str(key): str(version)
                    for key, version in versions_value.items()
                    if isinstance(key, str) and isinstance(version, str)
                }
            )
        if isinstance(value.get("capability_version"), str) and len(capabilities) == 1:
            versions[capabilities[0]] = value["capability_version"]
        for item in capabilities:
            versions.setdefault(item, "1.0")
        raw_outputs = value.get("outputs", value.get("output", []))
        if isinstance(raw_outputs, str):
            outputs = (raw_outputs,)
        elif isinstance(raw_outputs, list) and all(isinstance(item, str) for item in raw_outputs):
            outputs = tuple(raw_outputs)
        else:
            outputs = ()
        action = value.get("action")
        skill = value.get("skill")
        gate = value.get("gate", gate_after.get(step_id))
        steps.append(
            WorkflowStep(
                id=step_id,
                name=str(value.get("name", step_id)),
                action=action if isinstance(action, str) else None,
                skill=skill if isinstance(skill, str) else None,
                capabilities=capabilities,
                capability_versions=versions,
                outputs=outputs,
                gate=gate if isinstance(gate, str) else None,
            )
        )
    return WorkflowDefinition(workflow_id, name.strip(), path, required_inputs, tuple(steps))


def validate_workflow(workspace: Workspace, workflow_id: str) -> dict[str, Any]:
    definition = load_workflow(workspace, workflow_id)
    return {
        "valid": True,
        "id": definition.id,
        "name": definition.name,
        "steps": len(definition.steps),
        "required_inputs": list(definition.required_inputs),
        "capabilities": sorted(
            {capability for step in definition.steps for capability in step.capabilities}
        ),
        "human_gates": [step.gate for step in definition.steps if step.gate],
    }


def _project_root(workspace: Workspace, project: str) -> Path:
    root = workspace.path("projects", slugify(project))
    if not (root / "PROJECT.md").is_file():
        raise AlemError(f"unknown research project: {project}")
    return root


def _runs_root(project_root: Path) -> Path:
    root = project_root / "provenance" / "workflow-runs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _run_path(project_root: Path, run_id: str) -> Path:
    if not run_id.startswith("run-") or any(value in run_id for value in ("/", "\\", "..")):
        raise AlemError(f"invalid workflow run id: {run_id}")
    return _runs_root(project_root) / f"{run_id}.json"


def _save_run(project_root: Path, run: dict[str, Any]) -> None:
    run["updated_at"] = _now()
    path = _run_path(project_root, str(run["id"]))
    path.write_text(
        json.dumps(run, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    events = _runs_root(project_root) / "events.jsonl"
    event = {
        "at": run["updated_at"],
        "run_id": run["id"],
        "workflow": run["workflow"],
        "state": run["state"],
        "current_step": run.get("current_step"),
    }
    with events.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
    _update_status(project_root, run)


def _update_status(project_root: Path, run: Mapping[str, Any]) -> None:
    status = project_root / "STATUS.md"
    if not status.is_file():
        return
    start = "<!-- alem:workflow-state:start -->"
    end = "<!-- alem:workflow-state:end -->"
    block = (
        f"{start}\n"
        f"- Run: `{run['id']}`\n"
        f"- Workflow: `{run['workflow']}`\n"
        f"- State: `{run['state']}`\n"
        f"- Current step: `{run.get('current_step') or 'complete'}`\n"
        f"- Updated: `{run['updated_at']}`\n"
        f"{end}"
    )
    text = status.read_text(encoding="utf-8")
    if start in text and end in text:
        prefix, tail = text.split(start, 1)
        _, suffix = tail.split(end, 1)
        text = prefix.rstrip() + "\n\n" + block + suffix
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    status.write_text(text, encoding="utf-8", newline="\n")


def start_workflow(
    workspace: Workspace,
    workflow_id: str,
    project: str,
    *,
    allow_missing_inputs: bool = False,
) -> dict[str, Any]:
    definition = load_workflow(workspace, workflow_id)
    project_root = _project_root(workspace, project)
    missing = [item for item in definition.required_inputs if not (project_root / item).is_file()]
    if missing and not allow_missing_inputs:
        raise AlemError("workflow inputs are missing: " + ", ".join(missing))
    created = _now()
    identity = hashlib.sha256(
        f"{workflow_id}\0{project_root.name}\0{created}".encode()
    ).hexdigest()[:10]
    run_id = "run-" + created[:19].replace(":", "").replace("-", "") + "-" + identity
    steps = [
        {
            **asdict(step),
            "capability_versions": dict(step.capability_versions),
            "state": "pending",
            "evidence": [],
            "artifacts": [],
            "started_at": None,
            "completed_at": None,
        }
        for step in definition.steps
    ]
    run = {
        "schema_version": RUN_SCHEMA_VERSION,
        "id": run_id,
        "workflow": workflow_id,
        "workflow_path": definition.path.relative_to(workspace.root).as_posix(),
        "project": project_root.name,
        "created_at": created,
        "updated_at": created,
        "state": "pending",
        "current_step": definition.steps[0].id,
        "missing_inputs": missing,
        "steps": steps,
        "approvals": [],
    }
    _save_run(project_root, run)
    return run


def load_run(workspace: Workspace, project: str, run_id: str) -> dict[str, Any]:
    project_root = _project_root(workspace, project)
    path = _run_path(project_root, run_id)
    if not path.is_file():
        raise AlemError(f"unknown workflow run: {run_id}")
    try:
        run = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AlemError(f"cannot read workflow run {run_id}: {exc}") from exc
    if not isinstance(run, dict) or run.get("schema_version") != RUN_SCHEMA_VERSION:
        raise AlemError(f"invalid workflow run: {run_id}")
    if run.get("state") not in RUN_STATES:
        raise AlemError(f"invalid workflow run state: {run.get('state')}")
    return run


def list_runs(workspace: Workspace, project: str) -> list[dict[str, Any]]:
    project_root = _project_root(workspace, project)
    values: list[dict[str, Any]] = []
    for path in sorted(_runs_root(project_root).glob("run-*.json")):
        values.append(load_run(workspace, project, path.stem))
    return values


def _current(run: dict[str, Any]) -> dict[str, Any]:
    current = run.get("current_step")
    for step in run.get("steps", []):
        if isinstance(step, dict) and step.get("id") == current:
            return step
    raise AlemError("workflow has no current step")


def _manager(workspace: Workspace) -> PluginManager:
    config = load_config(workspace)
    catalogues = config.raw.get("plugins", {}).get("catalogues", [])
    catalogue = None
    if isinstance(catalogues, list) and catalogues and isinstance(catalogues[0], str):
        candidate = workspace.path(catalogues[0])
        if candidate.is_file():
            catalogue = candidate
    return PluginManager(workspace.root, catalogue=catalogue)


def _credentials(manager: PluginManager, capability: str, version: str) -> dict[str, str]:
    names: set[str] = set()
    for candidate in manager.registry(enabled_only=True).resolve(
        capability, capability_version=version
    ):
        manifest = manager._installed_manifest(  # noqa: SLF001 - approved metadata only
            candidate.plugin_id,
            manager._load_state()["plugins"][candidate.plugin_id],  # noqa: SLF001
        )
        names.update(manifest.required_credentials)
        names.update(manifest.optional_credentials)
    return {name: os.environ[name] for name in names if os.environ.get(name)}


def advance_workflow(
    workspace: Workspace,
    project: str,
    run_id: str,
    *,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    project_root = _project_root(workspace, project)
    run = load_run(workspace, project, run_id)
    if run["state"] == "complete":
        return run
    if run["state"] == "awaiting_approval":
        raise AlemError("workflow is awaiting a recorded human approval")
    step = _current(run)
    if step["state"] == "pending":
        step["started_at"] = _now()
    capabilities = tuple(step.get("capabilities", ()))
    if capabilities and payload is not None:
        if len(capabilities) != 1:
            raise AlemError(
                "this step declares multiple capabilities; complete them separately "
                "and record evidence"
            )
        capability = capabilities[0]
        version = step.get("capability_versions", {}).get(capability, "1.0")
        manager = _manager(workspace)
        response = manager.invoke(
            capability,
            payload,
            capability_version=version,
            credentials=_credentials(manager, capability, version),
        )
        output_root = _runs_root(project_root) / run_id
        output_root.mkdir(parents=True, exist_ok=True)
        output_path = output_root / f"{step['id']}-{capability}.json"
        output_path.write_text(
            json.dumps(response.to_mapping(), indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        record = register_artifact(
            workspace,
            project,
            output_path,
            artifact_type=f"capability_result.{capability}",
            creator=str(response.metadata.get("provider", "alem-capability-router")),
            source=f"{capability}:{version}",
            evidence_status="unverified",
            metadata={"workflow_run": run_id, "step": step["id"]},
        )
        step["artifacts"].append(record.id)
        step["evidence"].append(output_path.relative_to(project_root).as_posix())
        step["state"] = "complete"
        step["completed_at"] = _now()
        _after_step(run, step)
    else:
        step["state"] = "awaiting_agent"
        run["state"] = "awaiting_agent"
    _save_run(project_root, run)
    return run


def _expected_outputs(project_root: Path, run_id: str, step: Mapping[str, Any]) -> list[Path]:
    return [
        project_root / str(value).replace("{run_id}", run_id)
        for value in step.get("outputs", [])
    ]


def complete_step(
    workspace: Workspace,
    project: str,
    run_id: str,
    step_id: str,
    *,
    evidence: tuple[str, ...] = (),
    allow_missing_outputs: bool = False,
) -> dict[str, Any]:
    project_root = _project_root(workspace, project)
    run = load_run(workspace, project, run_id)
    step = _current(run)
    if step.get("id") != step_id:
        raise AlemError(f"current workflow step is {step.get('id')!r}, not {step_id!r}")
    expected = _expected_outputs(project_root, run_id, step)
    missing = [path.relative_to(project_root).as_posix() for path in expected if not path.exists()]
    if missing and not allow_missing_outputs:
        raise AlemError("expected workflow outputs are missing: " + ", ".join(missing))
    recorded: list[str] = []
    for value in evidence:
        candidate = workspace.assert_local(project_root / value)
        try:
            relative = candidate.relative_to(project_root)
        except ValueError as exc:
            raise AlemError("workflow evidence must be inside the project") from exc
        if not candidate.exists():
            raise AlemError(f"workflow evidence does not exist: {value}")
        recorded.append(relative.as_posix())
    recorded.extend(
        path.relative_to(project_root).as_posix() for path in expected if path.exists()
    )
    step["evidence"] = list(dict.fromkeys([*step.get("evidence", []), *recorded]))
    step["state"] = "complete"
    step["completed_at"] = _now()
    _after_step(run, step)
    _save_run(project_root, run)
    return run


def _after_step(run: dict[str, Any], step: dict[str, Any]) -> None:
    gate = step.get("gate")
    if gate and not any(item.get("gate") == gate for item in run.get("approvals", [])):
        run["state"] = "awaiting_approval"
        run["current_step"] = step["id"]
        return
    steps = run.get("steps", [])
    position = next(index for index, item in enumerate(steps) if item.get("id") == step["id"])
    if position + 1 >= len(steps):
        run["state"] = "complete"
        run["current_step"] = None
    else:
        run["state"] = "running"
        run["current_step"] = steps[position + 1]["id"]


def approve_gate(
    workspace: Workspace,
    project: str,
    run_id: str,
    gate: str,
    *,
    approver: str,
    decision: str,
) -> dict[str, Any]:
    if not approver.strip() or not decision.strip():
        raise AlemError("approval requires an approver and decision record")
    project_root = _project_root(workspace, project)
    run = load_run(workspace, project, run_id)
    if run["state"] != "awaiting_approval":
        raise AlemError("workflow is not awaiting approval")
    step = _current(run)
    if step.get("gate") != gate:
        raise AlemError(f"current gate is {step.get('gate')!r}, not {gate!r}")
    run["approvals"].append(
        {
            "gate": gate,
            "step": step["id"],
            "approver": approver.strip(),
            "decision": decision.strip(),
            "approved_at": _now(),
        }
    )
    _after_step(run, step)
    _save_run(project_root, run)
    return run
