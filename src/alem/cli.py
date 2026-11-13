"""Command-line interface for the workspace-local Alem foundation."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import textwrap
import tomllib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from alem import __version__
from alem.artifacts import list_artifacts, load_artifact, register_artifact, verify_artifact
from alem.config import load_config
from alem.context import (
    activate_plan,
    build_context_index,
    deactivate_context,
    load_plan,
    plan_context,
    search_context,
)
from alem.errors import AlemError
from alem.extensions import ExtensionError
from alem.health import run_health_checks
from alem.integrations import find_integration, load_integrations, validate_integrations
from alem.knowledge import update_index
from alem.models import (
    ModelConfigStore,
    ModelError,
    configure_provider,
    get_provider,
    list_models,
    model_doctor,
    model_status,
    remove_local_credential,
    save_api_key,
    set_default_model,
    set_model_fallbacks,
    validate_login_method,
)
from alem.projects import create_project, export_project
from alem.setup_workspace import initialize_workspace, sync_all_skill_adapters
from alem.workflows import (
    advance_workflow,
    approve_gate,
    complete_step,
    list_runs,
    load_run,
    start_workflow,
    validate_workflow,
)
from alem.workspace import Workspace

Command = Callable[[argparse.Namespace, Workspace], int]


def _workspace(arguments: argparse.Namespace) -> Workspace:
    return Workspace.discover(arguments.workspace)


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def _cmd_setup(arguments: argparse.Namespace, workspace: Workspace) -> int:
    result = initialize_workspace(workspace, create_venv=arguments.create_venv)
    if arguments.json:
        _print_json(result)
    else:
        print(f"Initialized Alem workspace: {workspace.root}")
        print(f"Runtime: {workspace.runtime.relative_to(workspace.root)}")
        print(
            "Skill adapters: "
            f"{result['skill_adapters']['written']} written, "
            f"{result['skill_adapters']['preserved']} custom adapters preserved"
        )
        if arguments.create_venv:
            status = "created" if result["local_venv_created"] else "already present"
            print(f"Local Python environment: {status}")
        official = result["plugins"]["official"]
        official_values = [
            *official["installed"],
            *official["updated"],
            *official["already_current"],
        ]
        print(
            "Accepted Alem-authored integrations: "
            + (", ".join(official_values) if official_values else "none configured")
            + " (provisioned and enabled automatically)"
        )
        community_accepted = result["plugins"]["community_accepted"]
        accepted_values = [
            *community_accepted["installed"],
            *community_accepted["updated"],
            *community_accepted["already_current"],
        ]
        print(
            "Accepted community-contributor integrations: "
            + (", ".join(accepted_values) if accepted_values else "none in this release")
            + " (same automatic policy)"
        )
        community = result["plugins"]["community_available"]
        verified = ", ".join(community["verified"]) or "none"
        unverified = ", ".join(community["unverified"]) or "none"
        print("Catalog-only community candidates (not provisioned):")
        print(f"  Verified: {verified}")
        print(f"  Unverified: {unverified}")
        reconciliation = result["plugins"]["reconciliation"]
        for item in reconciliation["unsupported"]:
            print(f"  BLOCKED {item['plugin_id']}: {item['reason']}")
        for item in reconciliation["failed"]:
            print(f"  FAILED {item['id']}: {item['reason']}")
        if arguments.create_venv:
            print(
                "Core dependencies were checked in .alem/venv, the launcher's runtime interpreter."
            )
    return 1 if result["plugins"]["reconciliation"]["failed"] else 0


def _cmd_update(arguments: argparse.Namespace, workspace: Workspace) -> int:
    from alem.reconciliation import reconcile_accepted_integrations

    result = reconcile_accepted_integrations(workspace)
    if arguments.json:
        _print_json(result)
    else:
        print(
            "Accepted integrations reconciled: "
            f"{len(result['installed'])} installed, {len(result['updated'])} updated, "
            f"{len(result['already_current'])} already current, {len(result['pinned'])} pinned"
        )
        for item in result["unsupported"]:
            print(f"BLOCKED {item['plugin_id']}: {item['reason']}")
        for item in result["failed"]:
            print(f"FAILED {item['id']}: {item['reason']}")
        print("Alem core updates come from the installed package or repository update process.")
    return 1 if result["failed"] else 0


def _cmd_health(arguments: argparse.Namespace, workspace: Workspace) -> int:
    report = run_health_checks(workspace)
    if arguments.json:
        print(report.as_json())
    else:
        symbols = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "info": "INFO"}
        for check in report.checks:
            print(f"[{symbols[check.status]}] {check.name}: {check.message}")
        print("Health check passed" if report.ok else "Health check failed")
    if not report.ok:
        return 1
    if arguments.strict and any(check.status == "warn" for check in report.checks):
        return 1
    return 0


def _cmd_dashboard(arguments: argparse.Namespace, workspace: Workspace) -> int:
    from alem.terminal.dashboard import render_dashboard

    render_dashboard(workspace, no_color=arguments.no_color)
    return 0


def _cmd_model_list(arguments: argparse.Namespace, workspace: Workspace) -> int:
    values = list_models(workspace, arguments.provider)
    if arguments.available:
        values = [item for item in values if item["readiness"] in {"configured", "local"}]
    if arguments.json:
        _print_json({"models": values})
        return 0
    if not values:
        print("No configured models are available; use `alem model providers` for setup guidance.")
        return 0
    print("MODEL  READINESS  SOURCE")
    for item in values:
        print(f"{item['provider']}/{item['id']}  {item['readiness']}  {item['source']}")
    return 0


def _cmd_model_providers(arguments: argparse.Namespace, workspace: Workspace) -> int:
    status = model_status(workspace)
    if arguments.json:
        _print_json({"providers": status["providers"]})
        return 0
    print("PROVIDER  SUPPORT  AUTH  READINESS")
    for item in status["providers"]:
        print(
            f"{item['id']}  {item['support_state']}  {','.join(item['auth_methods'])}  "
            f"{item['readiness']}"
        )
        if item["notes"]:
            print(f"  {item['notes']}")
    return 0


def _api_key_from_stdin_or_prompt(arguments: argparse.Namespace, provider: str) -> str:
    if arguments.api_key_stdin:
        value = sys.stdin.read().strip()
    elif getattr(sys.stdin, "isatty", lambda: False)():
        value = getpass.getpass(f"API key for {provider} (input hidden): ").strip()
    else:
        raise ModelError(
            "non-interactive login requires --api-key-stdin; secrets are never CLI arguments"
        )
    if not value:
        raise ModelError("API key input was empty")
    return value


def _cmd_model_login(arguments: argparse.Namespace, workspace: Workspace) -> int:
    if not arguments.provider:
        return _cmd_model_providers(arguments, workspace)
    spec = validate_login_method(arguments.provider, arguments.method)
    if arguments.method == "api-key":
        save_api_key(workspace, spec.id, _api_key_from_stdin_or_prompt(arguments, spec.id))
    result = {"provider": spec.id, "method": arguments.method, "status": "configured"}
    if arguments.json:
        _print_json(result)
    else:
        print(f"Configured {spec.name} with {arguments.method}; secret value was not displayed.")
    return 0


def _cmd_model_logout(arguments: argparse.Namespace, workspace: Workspace) -> int:
    get_provider(arguments.provider)
    removed = remove_local_credential(workspace, arguments.provider)
    result = {"provider": arguments.provider, "removed_local_credential": removed}
    if arguments.json:
        _print_json(result)
    else:
        message = (
            "Removed the workspace-local credential."
            if removed
            else "No workspace-local credential was stored."
        )
        print(f"{arguments.provider}: {message}")
        spec = get_provider(arguments.provider)
        if any(os.environ.get(name) for name in spec.env_vars):
            print("An environment credential is still active and was not changed.")
    return 0


def _cmd_model_set(arguments: argparse.Namespace, workspace: Workspace) -> int:
    set_default_model(workspace, arguments.model_ref)
    result = {"current": arguments.model_ref}
    _print_json(result) if arguments.json else print(f"Default model set to {arguments.model_ref}")
    return 0


def _cmd_model_current(arguments: argparse.Namespace, workspace: Workspace) -> int:
    current = model_status(workspace)["current"]
    result = {"current": current}
    if arguments.json:
        _print_json(result)
    else:
        print(current or "No default model selected. Run `alem model set PROVIDER/MODEL`.")
    return 0


def _cmd_model_test(arguments: argparse.Namespace, workspace: Workspace) -> int:
    from alem.models import ModelGateway

    result = ModelGateway(workspace).test_connection(arguments.model_ref)
    _print_json(result) if arguments.json else print(
        f"{result['provider']} reachable at {result['base_url']}"
    )
    return 0


def _cmd_model_status(arguments: argparse.Namespace, workspace: Workspace) -> int:
    result = model_status(workspace)
    if arguments.json:
        _print_json(result)
        return 0
    current = result["current"] or "not selected"
    print(f"Current model: {current}")
    for item in result["providers"]:
        print(f"{item['id']}: {item['readiness']} ({item['credential_source']})")
    return 0


def _cmd_model_doctor(arguments: argparse.Namespace, workspace: Workspace) -> int:
    result = model_doctor(workspace)
    if arguments.json:
        _print_json(result)
        return 0
    for check in result["checks"]:
        print(f"[{check['status'].upper()}] {check['provider']}: {check['message']}")
    return 0


def _cmd_model_configure(arguments: argparse.Namespace, workspace: Workspace) -> int:
    if not arguments.provider:
        raise ModelError(
            "model configure requires a provider; use `alem model providers` to inspect options"
        )
    configure_provider(
        workspace,
        arguments.provider,
        base_url=arguments.base_url,
        model=arguments.model,
    )
    if arguments.api_key_stdin:
        save_api_key(workspace, arguments.provider, sys.stdin.read().strip())
    result = model_status(workspace)
    selected = next(item for item in result["providers"] if item["id"] == arguments.provider)
    if arguments.json:
        _print_json(selected)
    else:
        print(f"Configured {arguments.provider}: {selected['readiness']}")
        if selected["base_url"]:
            print(f"Base URL: {selected['base_url']}")
    return 0


def _cmd_model_defaults(arguments: argparse.Namespace, workspace: Workspace) -> int:
    value = ModelConfigStore(workspace).read()
    result = {"current": value.get("current"), "defaults": value.get("defaults", {})}
    _print_json(result) if arguments.json else print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _cmd_model_fallbacks(arguments: argparse.Namespace, workspace: Workspace) -> int:
    store = ModelConfigStore(workspace)
    value = store.read()
    if arguments.set_models:
        set_model_fallbacks(workspace, arguments.capability, arguments.set_models)
        store = ModelConfigStore(workspace)
        value = store.read()
    result = {
        "capability": arguments.capability,
        "fallbacks": value.get("fallbacks", {}).get(arguments.capability, []),
    }
    if arguments.json:
        _print_json(result)
    else:
        print(", ".join(result["fallbacks"]) or "No model fallbacks configured")
    return 0


def _cmd_config_validate(arguments: argparse.Namespace, workspace: Workspace) -> int:
    config = load_config(workspace)
    result = {
        "valid": True,
        "workspace_version": config.workspace_version,
        "plugin_api_version": config.plugin_api_version,
        "capabilities": {
            name: {"default": route.default, "fallbacks": list(route.fallbacks)}
            for name, route in config.capability_routes.items()
        },
    }
    _print_json(result) if arguments.json else print(
        f"Valid Alem workspace schema {config.workspace_version}; "
        f"extension API {config.plugin_api_version}"
    )
    return 0


def _cmd_project_create(arguments: argparse.Namespace, workspace: Workspace) -> int:
    destination = create_project(workspace, arguments.name, arguments.slug)
    print(f"Created research project: {destination.relative_to(workspace.root)}")
    print(f"Next: complete {destination.relative_to(workspace.root) / 'PROJECT.md'}")
    return 0


def _cmd_project_list(arguments: argparse.Namespace, workspace: Workspace) -> int:
    projects_root = workspace.path("projects")
    projects = (
        sorted(
            path.name
            for path in projects_root.iterdir()
            if path.is_dir() and (path / "PROJECT.md").is_file()
        )
        if projects_root.exists()
        else []
    )
    if arguments.json:
        _print_json({"projects": projects})
    elif projects:
        print("\n".join(projects))
    else:
        print("No research projects found")
    return 0


def _cmd_project_export(arguments: argparse.Namespace, workspace: Workspace) -> int:
    destination = export_project(
        workspace,
        arguments.project,
        arguments.output,
        include_sensitive=arguments.include_sensitive,
    )
    print(f"Exported: {destination.relative_to(workspace.root)}")
    if arguments.include_sensitive:
        print(
            "WARNING: sensitive-file exclusions were disabled; inspect the archive before sharing"
        )
    return 0


def _cmd_knowledge_index(arguments: argparse.Namespace, workspace: Workspace) -> int:
    index, count = update_index(workspace)
    print(f"Indexed {count} knowledge pages in {index.relative_to(workspace.root)}")
    return 0


def _cmd_skill_sync(arguments: argparse.Namespace, workspace: Workspace) -> int:
    counts = sync_all_skill_adapters(workspace, mode=arguments.mode)
    if arguments.json:
        _print_json(counts)
    else:
        print(
            f"Synchronized {counts['skills']} canonical skills; "
            f"wrote {counts['written']} adapters; preserved {counts['preserved']} custom adapters"
        )
    return 0


def _cmd_skill_list(arguments: argparse.Namespace, workspace: Workspace) -> int:
    skills = sorted(path.parent.name for path in workspace.path("skills").glob("*/SKILL.md"))
    if arguments.json:
        _print_json({"skills": skills})
    else:
        print("\n".join(skills) if skills else "No canonical skills found")
    return 0


def _cmd_integration_list(arguments: argparse.Namespace, workspace: Workspace) -> int:
    integrations = [item.to_mapping() for item in load_integrations(workspace)]
    if arguments.status:
        aliases = {"planned": "discovered", "planned-optional": "discovered"}
        status = aliases.get(arguments.status, arguments.status)
        integrations = [item for item in integrations if item.get("status") == status]
    if arguments.json:
        _print_json({"integrations": integrations})
        return 0
    if not integrations:
        print("No integrations matched")
        return 0
    widths = {
        "id": max(2, *(len(str(item.get("id", ""))) for item in integrations)),
        "status": max(6, *(len(str(item.get("status", ""))) for item in integrations)),
    }
    print(
        f"{'ID':<{widths['id']}}  {'STATUS':<{widths['status']}}  "
        "ACCEPTANCE  AUTHORSHIP  CAPABILITIES"
    )
    for item in integrations:
        print(
            f"{item.get('id', ''):<{widths['id']}}  "
            f"{item.get('status', ''):<{widths['status']}}  "
            f"{item.get('acceptance', '')}  {item.get('authorship', '')}  "
            f"{', '.join(item.get('capabilities', []))}"
        )
    return 0


def _cmd_integration_show(arguments: argparse.Namespace, workspace: Workspace) -> int:
    value = find_integration(workspace, arguments.integration).to_mapping()
    _print_json(value) if arguments.json else print(
        f"{value['id']}  {value['status']}  {value['acceptance']}  "
        f"{value['authorship']}\n"
        f"  {value['name']}\n  Capabilities: {', '.join(value['capabilities']) or '-'}\n"
        f"  {value['notes']}"
    )
    return 0


def _cmd_integration_validate(arguments: argparse.Namespace, workspace: Workspace) -> int:
    result = validate_integrations(workspace)
    message = (
        f"Valid integration registry: {result['integrations']} entries"
        if result["valid"]
        else "Invalid integration registry:\n- " + "\n- ".join(result["errors"])
    )
    _print_json(result) if arguments.json else print(message)
    return 0 if result["valid"] else 1


def _cmd_workflow_list(arguments: argparse.Namespace, workspace: Workspace) -> int:
    root = workspace.path("workflows")
    workflows = sorted(
        path.stem
        for pattern in ("*.yaml", "*.yml", "*.md")
        for path in root.glob(pattern)
        if path.name.lower() != "readme.md"
    )
    if arguments.json:
        _print_json({"workflows": workflows})
    else:
        print("\n".join(workflows) if workflows else "No workflows found")
    return 0


def _cmd_workflow_validate(arguments: argparse.Namespace, workspace: Workspace) -> int:
    result = validate_workflow(workspace, arguments.workflow)
    _print_json(result) if arguments.json else print(
        f"Valid workflow {result['id']}: {result['steps']} steps, "
        f"{len(result['human_gates'])} human gates"
    )
    return 0


def _cmd_workflow_start(arguments: argparse.Namespace, workspace: Workspace) -> int:
    run = start_workflow(
        workspace,
        arguments.workflow,
        arguments.project,
        allow_missing_inputs=arguments.allow_missing_inputs,
    )
    _print_json(run) if arguments.json else print(
        f"Started {run['id']} at step {run['current_step']}"
    )
    return 0


def _cmd_workflow_runs(arguments: argparse.Namespace, workspace: Workspace) -> int:
    values = list_runs(workspace, arguments.project)
    if arguments.json:
        _print_json({"runs": values})
    elif not values:
        print("No workflow runs")
    else:
        for run in values:
            print(
                f"{run['id']}  {run['workflow']}  {run['state']}  {run.get('current_step') or '-'}"
            )
    return 0


def _cmd_workflow_status(arguments: argparse.Namespace, workspace: Workspace) -> int:
    run = load_run(workspace, arguments.project, arguments.run)
    if arguments.json:
        _print_json(run)
    else:
        print(f"Run: {run['id']}\nWorkflow: {run['workflow']}\nState: {run['state']}")
        print(f"Current step: {run.get('current_step') or 'complete'}")
    return 0


def _cmd_workflow_next(arguments: argparse.Namespace, workspace: Workspace) -> int:
    payload = None
    if arguments.input:
        payload = json.loads(arguments.input)
        if not isinstance(payload, dict):
            raise AlemError("workflow capability input must be a JSON object")
    run = advance_workflow(
        workspace,
        arguments.project,
        arguments.run,
        payload=payload,
    )
    _print_json(run) if arguments.json else print(
        f"Run {run['id']}: {run['state']} at {run.get('current_step') or 'complete'}"
    )
    return 0


def _cmd_workflow_complete(arguments: argparse.Namespace, workspace: Workspace) -> int:
    run = complete_step(
        workspace,
        arguments.project,
        arguments.run,
        arguments.step,
        evidence=tuple(arguments.evidence),
        allow_missing_outputs=arguments.allow_missing_outputs,
    )
    _print_json(run) if arguments.json else print(
        f"Completed {arguments.step}; run state is {run['state']}"
    )
    return 0


def _cmd_workflow_approve(arguments: argparse.Namespace, workspace: Workspace) -> int:
    run = approve_gate(
        workspace,
        arguments.project,
        arguments.run,
        arguments.gate,
        approver=arguments.approver,
        decision=arguments.decision,
    )
    _print_json(run) if arguments.json else print(
        f"Approved {arguments.gate}; run state is {run['state']}"
    )
    return 0


def _cmd_context_build(arguments: argparse.Namespace, workspace: Workspace) -> int:
    index = build_context_index(workspace)
    result = {
        "schema_version": index["schema_version"],
        "entries": len(index["entries"]),
        "digest": index["digest"],
    }
    _print_json(result) if arguments.json else print(
        f"Indexed {result['entries']} context entries ({result['digest'][:12]})"
    )
    return 0


def _cmd_context_search(arguments: argparse.Namespace, workspace: Workspace) -> int:
    values = search_context(workspace, arguments.query, all_states=arguments.all)
    if arguments.json:
        _print_json({"entries": values})
    elif not values:
        print("No context entries matched")
    else:
        for item in values:
            print(f"{item['kind']}  {item['id']}  {item['state']}\n  {item['description']}")
    return 0


def _cmd_context_plan(arguments: argparse.Namespace, workspace: Workspace) -> int:
    plan = plan_context(
        workspace,
        arguments.task,
        include=tuple(arguments.include),
        exclude=tuple(arguments.exclude),
        rebuild_index=arguments.rebuild,
    )
    if arguments.json:
        _print_json(plan.to_mapping())
    else:
        print(f"Context plan {plan.id}")
        print(f"Stages: {', '.join(plan.stages) or 'general'}")
        print("Skills: " + (", ".join(item.id for item in plan.skills) or "none"))
        print(
            "Capabilities: "
            + (", ".join(item.capability or item.id for item in plan.capabilities) or "none")
        )
        if plan.suggestions:
            print("Available but inactive: " + ", ".join(item.id for item in plan.suggestions))
        print(f"Estimated context: {plan.estimated_context_tokens} tokens")
        print(f"Activate with `alem context activate {plan.id}`")
    return 0


def _cmd_context_activate(arguments: argparse.Namespace, workspace: Workspace) -> int:
    active = activate_plan(workspace, arguments.plan)
    _print_json(active) if arguments.json else print(
        f"Activated context plan {active['plan_id']} for this workspace task"
    )
    return 0


def _cmd_context_status(arguments: argparse.Namespace, workspace: Workspace) -> int:
    try:
        plan = load_plan(workspace, arguments.plan)
    except AlemError:
        if arguments.plan:
            raise
        plan = None
    if arguments.json:
        _print_json({"active": plan})
    elif plan is None:
        print("No active context plan")
    else:
        print(f"Active context: {plan['id']}\nTask: {plan['task']}")
        print("Skills: " + ", ".join(item["id"] for item in plan.get("skills", [])))
        print(
            "Capabilities: "
            + ", ".join(item.get("capability", item["id"]) for item in plan.get("capabilities", []))
        )
    return 0


def _cmd_context_explain(arguments: argparse.Namespace, workspace: Workspace) -> int:
    plan = load_plan(workspace, arguments.plan)
    if arguments.json:
        _print_json({"plan_id": plan["id"], "rationale": plan.get("rationale", [])})
    else:
        print(f"Context plan {plan['id']}")
        for reason in plan.get("rationale", []):
            print(f"- {reason}")
    return 0


def _cmd_context_deactivate(arguments: argparse.Namespace, workspace: Workspace) -> int:
    changed = deactivate_context(workspace)
    if arguments.json:
        _print_json({"deactivated": changed})
    else:
        print("Context deactivated" if changed else "No active context plan")
    return 0


def _cmd_artifact_register(arguments: argparse.Namespace, workspace: Workspace) -> int:
    metadata: dict[str, Any] = {}
    if arguments.metadata:
        parsed = json.loads(arguments.metadata)
        if not isinstance(parsed, dict):
            raise AlemError("artifact metadata must be a JSON object")
        metadata = parsed
    record = register_artifact(
        workspace,
        arguments.project,
        arguments.path,
        artifact_type=arguments.type,
        creator=arguments.creator,
        source=arguments.source,
        evidence_status=arguments.evidence_status,
        inputs=tuple(arguments.input),
        metadata=metadata,
    )
    _print_json(record.to_mapping()) if arguments.json else print(
        f"Registered {record.id}: {record.artifact_type} -> {record.path}"
    )
    return 0


def _cmd_artifact_list(arguments: argparse.Namespace, workspace: Workspace) -> int:
    records = list_artifacts(workspace, arguments.project)
    if arguments.json:
        _print_json({"artifacts": [record.to_mapping() for record in records]})
    elif not records:
        print("No artifacts registered")
    else:
        for record in records:
            print(f"{record.id}  {record.artifact_type}  {record.evidence_status}  {record.path}")
    return 0


def _cmd_artifact_show(arguments: argparse.Namespace, workspace: Workspace) -> int:
    _print_json(load_artifact(workspace, arguments.project, arguments.artifact).to_mapping())
    return 0


def _cmd_artifact_verify(arguments: argparse.Namespace, workspace: Workspace) -> int:
    result = verify_artifact(workspace, arguments.project, arguments.artifact)
    _print_json(result) if arguments.json else print(
        f"{result['id']}: {'valid' if result['valid'] else 'INVALID'}"
    )
    return 0 if result["valid"] else 1


def _add_common_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")


HELP_DASHBOARD = textwrap.dedent(
    """

    Research Workflows (displayed shortcuts; inspect `alem workflow list` for local specs)
      /deepresearch  planned, source-heavy investigation with citation checks
      /lit           literature review and consensus/disagreement mapping
      /review        critique a paper or draft and provide a revision plan
      /audit         compare paper claims with public code
      /replicate     plan reproducibility; run only after environment approval
      /recipe        ranked, evidence-backed ML training recipes
      /compare       compare sources, models, or methods with an evidence matrix
      /draft         turn verified research into a structured draft
      /autoresearch  bounded experiment loop with explicit benchmark constraints
      /summarize     summarize a source, repository, or PDF with provenance

    Models & Providers
      model list, model providers, model login, model set, model current
      model status, model doctor, model configure, model defaults, model fallbacks

    Workspace & Tools
      setup, health, project, workflow, context, artifact, integration, plugin

    Secrets stay local by default. ChatGPT/Claude subscriptions are not API keys;
    unsupported subscription OAuth is reported explicitly rather than emulated.
    """
).strip("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alem",
        description="Your research. Your knowledge. Your AI research workspace.",
        epilog=HELP_DASHBOARD,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"alem {__version__}")
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable ANSI colour and use plain terminal output",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        help="workspace root or a path inside it (default: current directory)",
    )
    commands = parser.add_subparsers(dest="command")

    setup = commands.add_parser(
        "setup",
        help="initialize runtime and reconcile all accepted integration releases",
    )
    setup.add_argument("--create-venv", action="store_true", help="create .alem/venv")
    _add_common_json(setup)
    setup.set_defaults(handler=_cmd_setup)

    update = commands.add_parser(
        "update", help="reconcile accepted integrations from the current Alem release"
    )
    _add_common_json(update)
    update.set_defaults(handler=_cmd_update)

    health = commands.add_parser("health", aliases=["doctor"], help="run diagnostics")
    health.add_argument("--strict", action="store_true", help="treat warnings as failures")
    _add_common_json(health)
    health.set_defaults(handler=_cmd_health)

    model = commands.add_parser(
        "model",
        help="inspect providers, credentials, model selection, and gateway readiness",
        description=(
            "Manage provider-neutral model configuration. "
            "API keys and subscription OAuth are separate."
        ),
    )
    model_commands = model.add_subparsers(dest="model_command", required=True)
    model_list = model_commands.add_parser("list", help="list catalogued model IDs")
    model_list.add_argument("--provider")
    model_list.add_argument(
        "--available", action="store_true", help="show configured/local models only"
    )
    _add_common_json(model_list)
    model_list.set_defaults(handler=_cmd_model_list)
    model_providers = model_commands.add_parser(
        "providers", help="list provider support and auth states"
    )
    _add_common_json(model_providers)
    model_providers.set_defaults(handler=_cmd_model_providers)
    model_login = model_commands.add_parser("login", help="configure a documented provider login")
    model_login.add_argument("provider", nargs="?")
    model_login.add_argument("--method", choices=["oauth", "api-key"], default="api-key")
    model_login.add_argument(
        "--api-key-stdin",
        action="store_true",
        help="read the API key from stdin without echoing it or storing it in shell history",
    )
    _add_common_json(model_login)
    model_login.set_defaults(handler=_cmd_model_login)
    model_logout = model_commands.add_parser(
        "logout", help="remove a workspace-local provider credential"
    )
    model_logout.add_argument("provider")
    _add_common_json(model_logout)
    model_logout.set_defaults(handler=_cmd_model_logout)
    model_set = model_commands.add_parser(
        "set", help="select PROVIDER/MODEL as the workspace default"
    )
    model_set.add_argument("model_ref")
    _add_common_json(model_set)
    model_set.set_defaults(handler=_cmd_model_set)
    model_current = model_commands.add_parser("current", help="show the selected model")
    _add_common_json(model_current)
    model_current.set_defaults(handler=_cmd_model_current)
    model_test = model_commands.add_parser("test", help="test the selected provider endpoint")
    model_test.add_argument("model_ref", nargs="?")
    _add_common_json(model_test)
    model_test.set_defaults(handler=_cmd_model_test)
    model_status_parser = model_commands.add_parser("status", help="show offline model readiness")
    _add_common_json(model_status_parser)
    model_status_parser.set_defaults(handler=_cmd_model_status)
    model_doctor_parser = model_commands.add_parser(
        "doctor", help="diagnose model configuration without sending prompts"
    )
    _add_common_json(model_doctor_parser)
    model_doctor_parser.set_defaults(handler=_cmd_model_doctor)
    model_configure = model_commands.add_parser(
        "configure", help="set an endpoint or workspace model alias"
    )
    model_configure.add_argument("provider", nargs="?")
    model_configure.add_argument("--base-url", help="HTTPS endpoint or HTTP loopback URL")
    model_configure.add_argument("--model", help="add an explicit model ID to the local catalog")
    model_configure.add_argument(
        "--api-key-stdin", action="store_true", help="read an API key from stdin"
    )
    _add_common_json(model_configure)
    model_configure.set_defaults(handler=_cmd_model_configure)
    model_defaults = model_commands.add_parser(
        "defaults", help="show role defaults and the selected model"
    )
    model_defaults.add_argument("--show", action="store_true", help="show configured defaults")
    _add_common_json(model_defaults)
    model_defaults.set_defaults(handler=_cmd_model_defaults)
    model_fallbacks = model_commands.add_parser(
        "fallbacks", help="show or set capability model fallbacks"
    )
    model_fallbacks.add_argument("capability", nargs="?", default="model_completion")
    model_fallbacks.add_argument(
        "--set", dest="set_models", action="append", metavar="PROVIDER/MODEL"
    )
    _add_common_json(model_fallbacks)
    model_fallbacks.set_defaults(handler=_cmd_model_fallbacks)

    config = commands.add_parser("config", help="validate workspace configuration")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    validate = config_commands.add_parser("validate", help="validate alem.toml")
    _add_common_json(validate)
    validate.set_defaults(handler=_cmd_config_validate)

    project = commands.add_parser("project", help="manage research projects")
    project_commands = project.add_subparsers(dest="project_command", required=True)
    project_create = project_commands.add_parser("create", help="create from the project template")
    project_create.add_argument("name")
    project_create.add_argument("--slug")
    project_create.set_defaults(handler=_cmd_project_create)
    project_list = project_commands.add_parser("list", help="list local research projects")
    _add_common_json(project_list)
    project_list.set_defaults(handler=_cmd_project_list)
    project_export = project_commands.add_parser("export", help="create a reviewable ZIP export")
    project_export.add_argument("project")
    project_export.add_argument("--output", type=Path)
    project_export.add_argument(
        "--include-sensitive",
        action="store_true",
        help="include files normally excluded for privacy",
    )
    project_export.set_defaults(handler=_cmd_project_export)

    knowledge = commands.add_parser("knowledge", help="maintain shared Markdown knowledge")
    knowledge_commands = knowledge.add_subparsers(dest="knowledge_command", required=True)
    knowledge_index = knowledge_commands.add_parser(
        "index", help="refresh the controlled wiki index"
    )
    knowledge_index.set_defaults(handler=_cmd_knowledge_index)

    skill = commands.add_parser("skill", aliases=["skills"], help="manage canonical skill adapters")
    skill_commands = skill.add_subparsers(dest="skill_command", required=True)
    skill_list = skill_commands.add_parser("list", help="list canonical skills")
    _add_common_json(skill_list)
    skill_list.set_defaults(handler=_cmd_skill_list)
    skill_sync = skill_commands.add_parser(
        "sync", aliases=["update"], help="regenerate Codex and Claude adapters"
    )
    skill_sync.add_argument("--mode", choices=["lazy", "eager"])
    _add_common_json(skill_sync)
    skill_sync.set_defaults(handler=_cmd_skill_sync)

    integration = commands.add_parser(
        "integration", aliases=["integrations"], help="inspect integrations"
    )
    integration_commands = integration.add_subparsers(dest="integration_command", required=True)
    integration_list = integration_commands.add_parser(
        "list", help="list actual implementation status"
    )
    integration_list.add_argument("--status")
    _add_common_json(integration_list)
    integration_list.set_defaults(handler=_cmd_integration_list)
    integration_show = integration_commands.add_parser(
        "show", help="inspect one canonical integration record"
    )
    integration_show.add_argument("integration")
    _add_common_json(integration_show)
    integration_show.set_defaults(handler=_cmd_integration_show)
    integration_validate = integration_commands.add_parser(
        "validate", help="validate registry, catalogue, and plugin consistency"
    )
    _add_common_json(integration_validate)
    integration_validate.set_defaults(handler=_cmd_integration_validate)

    workflow = commands.add_parser("workflow", aliases=["workflows"], help="inspect workflows")
    workflow_commands = workflow.add_subparsers(dest="workflow_command", required=True)
    workflow_list = workflow_commands.add_parser("list", help="list workflow specifications")
    _add_common_json(workflow_list)
    workflow_list.set_defaults(handler=_cmd_workflow_list)
    workflow_validate = workflow_commands.add_parser(
        "validate", help="validate a workflow specification"
    )
    workflow_validate.add_argument("workflow")
    _add_common_json(workflow_validate)
    workflow_validate.set_defaults(handler=_cmd_workflow_validate)
    workflow_start = workflow_commands.add_parser(
        "start", help="start a durable project workflow run"
    )
    workflow_start.add_argument("workflow")
    workflow_start.add_argument("--project", required=True)
    workflow_start.add_argument("--allow-missing-inputs", action="store_true")
    _add_common_json(workflow_start)
    workflow_start.set_defaults(handler=_cmd_workflow_start)
    workflow_runs = workflow_commands.add_parser("runs", help="list project workflow runs")
    workflow_runs.add_argument("--project", required=True)
    _add_common_json(workflow_runs)
    workflow_runs.set_defaults(handler=_cmd_workflow_runs)
    workflow_status = workflow_commands.add_parser("status", help="show a workflow run")
    workflow_status.add_argument("run")
    workflow_status.add_argument("--project", required=True)
    _add_common_json(workflow_status)
    workflow_status.set_defaults(handler=_cmd_workflow_status)
    workflow_next = workflow_commands.add_parser(
        "next", aliases=["resume"], help="advance or resume the current workflow step"
    )
    workflow_next.add_argument("run")
    workflow_next.add_argument("--project", required=True)
    workflow_next.add_argument("--input", help="JSON input for a single capability step")
    _add_common_json(workflow_next)
    workflow_next.set_defaults(handler=_cmd_workflow_next)
    workflow_complete = workflow_commands.add_parser(
        "complete", help="complete the current agent or human workflow step"
    )
    workflow_complete.add_argument("run")
    workflow_complete.add_argument("step")
    workflow_complete.add_argument("--project", required=True)
    workflow_complete.add_argument("--evidence", action="append", default=[])
    workflow_complete.add_argument("--allow-missing-outputs", action="store_true")
    _add_common_json(workflow_complete)
    workflow_complete.set_defaults(handler=_cmd_workflow_complete)
    workflow_approve = workflow_commands.add_parser(
        "approve", help="record a required human gate decision"
    )
    workflow_approve.add_argument("run")
    workflow_approve.add_argument("gate")
    workflow_approve.add_argument("--project", required=True)
    workflow_approve.add_argument("--approver", required=True)
    workflow_approve.add_argument("--decision", required=True)
    _add_common_json(workflow_approve)
    workflow_approve.set_defaults(handler=_cmd_workflow_approve)

    context = commands.add_parser(
        "context", help="plan and activate a minimal task-specific research context"
    )
    context_commands = context.add_subparsers(dest="context_command", required=True)
    context_build = context_commands.add_parser("build", help="rebuild the local routing index")
    _add_common_json(context_build)
    context_build.set_defaults(handler=_cmd_context_build)
    context_search = context_commands.add_parser("search", help="search indexed skills and tools")
    context_search.add_argument("query", nargs="?", default="")
    context_search.add_argument("--all", action="store_true", help="include inactive candidates")
    _add_common_json(context_search)
    context_search.set_defaults(handler=_cmd_context_search)
    context_plan = context_commands.add_parser("plan", help="select a minimal context for a task")
    context_plan.add_argument("task")
    context_plan.add_argument("--include", action="append", default=[])
    context_plan.add_argument("--exclude", action="append", default=[])
    context_plan.add_argument("--rebuild", action="store_true")
    _add_common_json(context_plan)
    context_plan.set_defaults(handler=_cmd_context_plan)
    context_activate = context_commands.add_parser("activate", help="activate a saved context plan")
    context_activate.add_argument("plan")
    _add_common_json(context_activate)
    context_activate.set_defaults(handler=_cmd_context_activate)
    context_status = context_commands.add_parser("status", help="show the active context plan")
    context_status.add_argument("--plan")
    _add_common_json(context_status)
    context_status.set_defaults(handler=_cmd_context_status)
    context_explain = context_commands.add_parser("explain", help="explain a context plan")
    context_explain.add_argument("plan", nargs="?")
    _add_common_json(context_explain)
    context_explain.set_defaults(handler=_cmd_context_explain)
    context_deactivate = context_commands.add_parser("deactivate", help="clear task activation")
    _add_common_json(context_deactivate)
    context_deactivate.set_defaults(handler=_cmd_context_deactivate)

    artifact = commands.add_parser(
        "artifact", help="register and verify typed, provenance-preserving project artifacts"
    )
    artifact_commands = artifact.add_subparsers(dest="artifact_command", required=True)
    artifact_register = artifact_commands.add_parser("register", help="register a project file")
    artifact_register.add_argument("project")
    artifact_register.add_argument("path")
    artifact_register.add_argument("--type", required=True)
    artifact_register.add_argument("--creator", required=True)
    artifact_register.add_argument("--source", required=True)
    artifact_register.add_argument(
        "--evidence-status",
        default="unverified",
        choices=[
            "verified_evidence",
            "reported_finding",
            "interpretation",
            "hypothesis",
            "unverified",
        ],
    )
    artifact_register.add_argument("--input", action="append", default=[])
    artifact_register.add_argument("--metadata", help="JSON object")
    _add_common_json(artifact_register)
    artifact_register.set_defaults(handler=_cmd_artifact_register)
    artifact_list = artifact_commands.add_parser("list", help="list project artifacts")
    artifact_list.add_argument("project")
    _add_common_json(artifact_list)
    artifact_list.set_defaults(handler=_cmd_artifact_list)
    artifact_show = artifact_commands.add_parser("show", help="show an artifact record")
    artifact_show.add_argument("project")
    artifact_show.add_argument("artifact")
    artifact_show.set_defaults(handler=_cmd_artifact_show)
    artifact_verify = artifact_commands.add_parser("verify", help="verify an artifact digest")
    artifact_verify.add_argument("project")
    artifact_verify.add_argument("artifact")
    _add_common_json(artifact_verify)
    artifact_verify.set_defaults(handler=_cmd_artifact_verify)

    # The extension subsystem adds its command group without leaking its internals into this module.
    try:
        from alem.extensions.cli import register_commands
    except ImportError:
        register_commands = None
    if register_commands is not None:
        register_commands(commands)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        workspace = _workspace(arguments)
        if arguments.command is None:
            stdout_tty = getattr(sys.stdout, "isatty", lambda: False)()
            stdin_tty = getattr(sys.stdin, "isatty", lambda: False)()
            if stdout_tty and stdin_tty:
                from alem.terminal.tui import AlemApp

                previous_no_color = os.environ.get("NO_COLOR")
                if arguments.no_color:
                    os.environ["NO_COLOR"] = "1"
                try:
                    AlemApp(workspace, no_color=arguments.no_color).run()
                finally:
                    if arguments.no_color:
                        if previous_no_color is None:
                            os.environ.pop("NO_COLOR", None)
                        else:
                            os.environ["NO_COLOR"] = previous_no_color
                return 0
            parser.print_help()
            return 0
        handler: Command = arguments.handler
        return handler(arguments, workspace)
    except (AlemError, ExtensionError, OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
