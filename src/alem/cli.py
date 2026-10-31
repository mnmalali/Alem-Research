"""Command-line interface for the workspace-local Alem foundation."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from alem import __version__
from alem.config import load_config
from alem.errors import AlemError
from alem.extensions import ExtensionError
from alem.health import run_health_checks
from alem.knowledge import update_index
from alem.projects import create_project, export_project
from alem.setup_workspace import initialize_workspace, sync_all_skill_adapters
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
        ready = [*official["installed"], *official["already_ready"]]
        print(
            "Official plugins: "
            + (", ".join(ready) if ready else "none configured")
            + " (installed and enabled automatically)"
        )
        community = result["plugins"]["community_available"]
        verified = ", ".join(community["verified"]) or "none"
        unverified = ", ".join(community["unverified"]) or "none"
        print("Community plugins are available but opt-in.")
        print(f"  Verified community plugins: {verified}")
        print(f"  Unverified community plugins: {unverified}")
        print(
            "  Inspect with `alem plugin search`; install with "
            "`alem plugin install <id> --approve`."
        )
    return 0


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
            "WARNING: sensitive-file exclusions were disabled; "
            "inspect the archive before sharing"
        )
    return 0


def _cmd_knowledge_index(arguments: argparse.Namespace, workspace: Workspace) -> int:
    index, count = update_index(workspace)
    print(f"Indexed {count} knowledge pages in {index.relative_to(workspace.root)}")
    return 0


def _cmd_skill_sync(arguments: argparse.Namespace, workspace: Workspace) -> int:
    counts = sync_all_skill_adapters(workspace)
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
    registry = workspace.path("integrations/registry.toml")
    with registry.open("rb") as stream:
        data = tomllib.load(stream)
    integrations = data.get("integrations", [])
    if arguments.status:
        integrations = [item for item in integrations if item.get("status") == arguments.status]
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
    print(f"{'ID':<{widths['id']}}  {'STATUS':<{widths['status']}}  CAPABILITY")
    for item in integrations:
        print(
            f"{item.get('id', ''):<{widths['id']}}  "
            f"{item.get('status', ''):<{widths['status']}}  {item.get('capability', '')}"
        )
    return 0


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


def _add_common_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alem",
        description="Your research. Your knowledge. Your AI research workspace.",
    )
    parser.add_argument("--version", action="version", version=f"alem {__version__}")
    parser.add_argument(
        "--workspace",
        type=Path,
        help="workspace root or a path inside it (default: current directory)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    setup = commands.add_parser(
        "setup",
        help="initialize runtime, install official plugins, and report opt-in community plugins",
    )
    setup.add_argument("--create-venv", action="store_true", help="create .alem/venv")
    _add_common_json(setup)
    setup.set_defaults(handler=_cmd_setup)

    health = commands.add_parser("health", aliases=["doctor"], help="run diagnostics")
    health.add_argument("--strict", action="store_true", help="treat warnings as failures")
    _add_common_json(health)
    health.set_defaults(handler=_cmd_health)

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

    workflow = commands.add_parser("workflow", aliases=["workflows"], help="inspect workflows")
    workflow_commands = workflow.add_subparsers(dest="workflow_command", required=True)
    workflow_list = workflow_commands.add_parser("list", help="list workflow specifications")
    _add_common_json(workflow_list)
    workflow_list.set_defaults(handler=_cmd_workflow_list)

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
