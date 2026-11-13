"""CLI adapter for the public extension subsystem."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from alem.config import load_config
from alem.context import build_context_index
from alem.errors import AlemError
from alem.integrations import load_integrations
from alem.setup_workspace import sync_all_skill_adapters
from alem.tool_status import list_tool_statuses
from alem.workspace import Workspace

from .catalogue import PluginCatalogue
from .errors import ApprovalRequired
from .manager import PluginManager, plugin_tree_digest
from .manifest import Manifest, load_manifest, validate_manifest


def _json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def _catalogue_path(workspace: Workspace) -> Path:
    config = load_config(workspace)
    catalogues = config.raw.get("plugins", {}).get("catalogues", [])
    if not isinstance(catalogues, list) or not catalogues or not isinstance(catalogues[0], str):
        raise AlemError("alem.toml must configure at least one repository-local plugin catalogue")
    return workspace.path(catalogues[0])


def _manager(workspace: Workspace, *, synchronize_routes: bool = True) -> PluginManager:
    manager = PluginManager(workspace.root, catalogue=_catalogue_path(workspace))
    if not synchronize_routes:
        return manager
    state = workspace.read_json(".alem/state/plugins.json", default={})
    configured_routes = state.get("routes", {}) if isinstance(state, dict) else {}
    installed = {item.id: item for item in manager.list_installed()}
    config = load_config(workspace)
    all_providers = manager.registry(enabled_only=False)
    for capability, route in config.capability_routes.items():
        # A route explicitly written with `alem capability route` wins over the
        # repository default. The default is only seeded once providers exist.
        existing_route = (
            configured_routes.get(capability) if isinstance(configured_routes, dict) else None
        )
        if isinstance(existing_route, dict) and existing_route.get("default"):
            continue
        provider_ids = {item.plugin_id for item in all_providers.providers(capability)}
        if route.default not in installed or route.default not in provider_ids:
            continue
        fallbacks = [item for item in route.fallbacks if item in installed and item in provider_ids]
        manager.set_route(capability, default=route.default, fallbacks=fallbacks)
    return manager


def _permissions(manifest: Manifest) -> dict[str, Any]:
    return {
        "network": list(manifest.permissions.network),
        "filesystem_read": list(manifest.permissions.filesystem_read),
        "filesystem_write": list(manifest.permissions.filesystem_write),
        "subprocess": manifest.permissions.subprocess,
        "native_code": manifest.permissions.native_code,
        "credentials": {
            "required": list(manifest.required_credentials),
            "optional": list(manifest.optional_credentials),
        },
    }


def _plugin_list(arguments: argparse.Namespace, workspace: Workspace) -> int:
    values = _manager(workspace).list_installed()
    if arguments.json:
        _json({"plugins": [asdict(value) for value in values]})
        return 0
    if not values:
        print("No plugins installed. Run `alem plugin search` to inspect the local catalogue.")
        return 0
    print("ID  VERSION  ENABLED  EXECUTION APPROVED  CAPABILITIES")
    for value in values:
        print(
            f"{value.id}  {value.version}  {'yes' if value.enabled else 'no'}  "
            f"{'yes' if value.execution_approved else 'no'}  {', '.join(value.capabilities) or '-'}"
        )
    return 0


def _plugin_search(arguments: argparse.Namespace, workspace: Workspace) -> int:
    entries = PluginCatalogue(_catalogue_path(workspace)).search(arguments.query or "")
    accepted = {
        item.plugin_id: item
        for item in load_integrations(workspace)
        if item.acceptance == "accepted" and item.plugin_id
    }
    values = [
        {
            **asdict(entry),
            "acceptance": (
                accepted[entry.id].acceptance if entry.id in accepted else "candidate"
            ),
            "authorship": accepted[entry.id].authorship if entry.id in accepted else "unknown",
        }
        for entry in entries
    ]
    if arguments.json:
        _json({"plugins": values})
        return 0
    if not entries:
        print("No catalogue plugins matched")
        return 0
    print("ID  VERSION  ACCEPTANCE  AUTHORSHIP  VERIFICATION  TYPES  CAPABILITIES")
    for entry, value in zip(entries, values, strict=True):
        print(
            f"{entry.id}  {entry.version}  {value['acceptance']}  {value['authorship']}  "
            f"{entry.verification}  {','.join(entry.extension_types)}  "
            f"{','.join(entry.capabilities) or '-'}"
        )
        print(f"  {entry.summary}")
    return 0


def _plugin_validate(arguments: argparse.Namespace, workspace: Workspace) -> int:
    path = Path(arguments.path)
    if not path.is_absolute():
        path = workspace.path(arguments.path)
    manifest = load_manifest(path, check_compatibility=not arguments.ignore_runtime)
    warnings = validate_manifest(path, check_compatibility=not arguments.ignore_runtime)
    result = {
        "valid": True,
        "security_verdict": False,
        "id": manifest.id,
        "name": manifest.name,
        "version": manifest.version,
        "api": manifest.api,
        "types": list(manifest.types),
        "capabilities": [asdict(item) for item in manifest.capabilities],
        "permissions": _permissions(manifest),
        "source_digest": plugin_tree_digest(manifest.root),
        "warnings": warnings,
    }
    if arguments.json:
        _json(result)
    else:
        print(f"Valid plugin manifest: {manifest.id} {manifest.version}")
        print(f"Types: {', '.join(manifest.types)}")
        print(f"Capabilities: {', '.join(item.name for item in manifest.capabilities) or '-'}")
        print(f"Permissions: {json.dumps(result['permissions'], sort_keys=True)}")
        print(f"Source digest (SHA-256): {result['source_digest']}")
        for warning in warnings:
            print(f"WARNING: {warning}")
        print("Manifest validation is not a security verdict or sandbox.")
    return 0


def _describe_plan(manager: PluginManager, source: str) -> list[dict[str, Any]]:
    plan = manager.plan_install(source)
    return [
        {
            "id": manifest.id,
            "version": manifest.version,
            "source": str(manifest.root),
            "permissions": _permissions(manifest),
            "python_dependencies": list(manifest.python_dependencies),
        }
        for manifest in plan.plugins
    ]


def _plugin_install(arguments: argparse.Namespace, workspace: Workspace) -> int:
    manager = _manager(workspace, synchronize_routes=False)
    plan = _describe_plan(manager, arguments.plugin)
    if not arguments.approve:
        print(json.dumps({"installation_plan": plan}, indent=2), file=os.sys.stderr)
        raise ApprovalRequired("installation", plan[-1]["id"])
    installed = manager.install(
        arguments.plugin,
        approved=True,
        install_python_dependencies=arguments.with_python_dependencies,
    )
    build_context_index(workspace)
    print("Installed locally (disabled): " + ", ".join(item.id for item in installed.plugins))
    print("Review, then run `alem plugin enable <id> --approve` to approve execution.")
    return 0


def _plugin_enable(arguments: argparse.Namespace, workspace: Workspace) -> int:
    if not arguments.approve:
        raise ApprovalRequired("execution", arguments.plugin)
    manager = _manager(workspace, synchronize_routes=False)
    manager.enable(arguments.plugin, approve_execution=True)
    # Re-open to synchronize any configured capability default/fallback now available.
    _manager(workspace)
    sync_all_skill_adapters(workspace)
    build_context_index(workspace)
    print(f"Enabled and execution-approved: {arguments.plugin}")
    return 0


def _plugin_disable(arguments: argparse.Namespace, workspace: Workspace) -> int:
    _manager(workspace).disable(arguments.plugin)
    sync_all_skill_adapters(workspace)
    build_context_index(workspace)
    print(f"Disabled: {arguments.plugin}")
    return 0


def _plugin_remove(arguments: argparse.Namespace, workspace: Workspace) -> int:
    if not arguments.yes:
        raise AlemError(
            "removal requires --yes; plugin data is preserved unless --purge-data is set"
        )
    _manager(workspace).remove(arguments.plugin, purge_data=arguments.purge_data)
    sync_all_skill_adapters(workspace)
    build_context_index(workspace)
    print(
        f"Removed plugin code and dependencies: {arguments.plugin}; "
        f"data {'removed' if arguments.purge_data else 'preserved'}"
    )
    return 0


def _plugin_update(arguments: argparse.Namespace, workspace: Workspace) -> int:
    if not arguments.approve:
        raise ApprovalRequired("update installation", arguments.plugin)
    plan = _manager(workspace).update(
        arguments.plugin,
        source=arguments.source,
        approved=True,
        install_python_dependencies=arguments.with_python_dependencies,
    )
    sync_all_skill_adapters(workspace)
    build_context_index(workspace)
    print("Updated locally and disabled pending renewed execution approval: " + plan.plugins[-1].id)
    return 0


def _plugin_rollback(arguments: argparse.Namespace, workspace: Workspace) -> int:
    result = _manager(workspace, synchronize_routes=False).rollback(arguments.plugin)
    sync_all_skill_adapters(workspace)
    build_context_index(workspace)
    print(
        f"Restored {result['plugin_id']} {result['version']} and pinned it; "
        "run `alem plugin unpin <id>` before reconciling a newer accepted release."
    )
    return 0


def _plugin_unpin(arguments: argparse.Namespace, workspace: Workspace) -> int:
    _manager(workspace, synchronize_routes=False).unpin(arguments.plugin)
    print(f"Removed the release pin for {arguments.plugin}; run `alem update` to reconcile.")
    return 0


def _plugin_assets(arguments: argparse.Namespace, workspace: Workspace) -> int:
    assets = _manager(workspace).discover_assets(arguments.type, enabled_only=not arguments.all)
    values = [
        {
            "plugin_id": asset.plugin_id,
            "extension_type": asset.extension_type,
            "path": str(asset.path.relative_to(workspace.root)),
        }
        for asset in assets
    ]
    if arguments.json:
        _json({"assets": values})
    elif not values:
        print("No declarative plugin assets discovered")
    else:
        for value in values:
            print(f"{value['extension_type']}  {value['plugin_id']}  {value['path']}")
    return 0


def _safe_slug(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not value:
        raise AlemError("plugin name must contain a letter or number")
    return value


def _starter_manifest(plugin_id: str, name: str) -> str:
    return f"""schema_version = 1

[plugin]
id = "{plugin_id}"
name = {json.dumps(name)}
version = "0.1.0"
api = ">=1.0,<2.0"
description = "A functional echo example generated by the Alem plugin development kit."
author = "Local developer"
repository = "local://{plugin_id}"
license = "MIT"
types = ["tool"]
entrypoint = "plugin.py:plugin"

[[capabilities]]
name = "example_echo"
version = "1.0"
extension_type = "tool"
priority = 100
description = "Return structured input unchanged for development and integration tests."

[compatibility]
python = ">=3.11"
operating_systems = ["windows", "linux", "macos"]
coding_agents = ["codex", "claude-code"]

[dependencies]
plugins = []
python = []

[permissions]
network = []
filesystem_read = []
filesystem_write = []
subprocess = false
native_code = false

[credentials]
required = []
optional = []

[documentation]
installation = "Validate and install with approval; enable with separate execution approval."
usage = "Invoke example_echo with a JSON object; the object is returned under output.echo."

[assets]
skills = []
agents = []
workflows = []
"""


STARTER_CODE = '''"""Example Alem API v1 plugin; it imports only documented public contracts."""

from alem.extensions.api import BaseExtension, ExecutionRequest, ExecutionResponse


class EchoTool(BaseExtension):
    extension_type = "tool"

    def invoke(self, request: ExecutionRequest) -> ExecutionResponse:
        return ExecutionResponse(
            output={"echo": dict(request.input)},
            metadata={"operation": request.operation},
        )


plugin = EchoTool()
'''


STARTER_TEST = """from alem.extensions import ExecutionRequest
from plugin import plugin


def test_echo_contract():
    response = plugin.invoke(ExecutionRequest("example_echo", input={"value": 3}))
    assert response.output == {"echo": {"value": 3}}
"""


def _plugin_create(arguments: argparse.Namespace, workspace: Workspace) -> int:
    display_name = " ".join(arguments.name.split())
    slug = _safe_slug(display_name)
    plugin_id = arguments.id or f"community.{slug}"
    if not re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)+", plugin_id):
        raise AlemError("--id must be a lowercase, namespaced identifier such as community.my-tool")
    destination = (
        workspace.assert_local(Path(arguments.path))
        if arguments.path and Path(arguments.path).is_absolute()
        else workspace.path(arguments.path or f"plugins/community/{slug}")
    )
    if destination.exists():
        raise AlemError(f"destination already exists: {destination}")
    (destination / "tests").mkdir(parents=True)
    (destination / "plugin.toml").write_text(
        _starter_manifest(plugin_id, display_name), encoding="utf-8", newline="\n"
    )
    (destination / "plugin.py").write_text(STARTER_CODE, encoding="utf-8", newline="\n")
    (destination / "tests/test_plugin.py").write_text(STARTER_TEST, encoding="utf-8", newline="\n")
    (destination / "README.md").write_text(
        f"# {display_name}\n\nA functional Alem API v1 starter plugin.\n\n"
        "Document source revision, license and attribution, dependency pins, permissions, "
        "credential names, telemetry, supported platforms, and readiness prerequisites.\n\n"
        "```bash\nalem plugin validate .\npython -m pytest\n```\n\n"
        "A candidate stays non-accepted until a maintainer merges an explicit release-registry "
        "entry. Acceptance makes it part of normal setup/update; it does not create an OS "
        "sandbox.\n",
        encoding="utf-8",
        newline="\n",
    )
    load_manifest(destination)
    print(f"Created validated plugin starter: {destination.relative_to(workspace.root)}")
    return 0


def _capability_list(arguments: argparse.Namespace, workspace: Workspace) -> int:
    registry = _manager(workspace).registry(enabled_only=not arguments.all)
    capabilities = registry.capabilities()
    if arguments.json:
        _json({"capabilities": capabilities})
    else:
        print("\n".join(capabilities) if capabilities else "No capabilities discovered")
    return 0


def _capability_providers(arguments: argparse.Namespace, workspace: Workspace) -> int:
    providers = (
        _manager(workspace)
        .registry(enabled_only=not arguments.all)
        .providers(arguments.capability, arguments.capability_version)
    )
    if arguments.json:
        _json({"providers": [asdict(item) for item in providers]})
    elif not providers:
        print("No providers discovered")
    else:
        for item in providers:
            print(
                f"{item.plugin_id} {item.plugin_version} "
                f"{item.extension_type} priority={item.priority}"
            )
    return 0


def _capability_route(arguments: argparse.Namespace, workspace: Workspace) -> int:
    _manager(workspace).set_route(
        arguments.capability,
        default=arguments.default,
        fallbacks=arguments.fallback,
    )
    print(
        f"Route {arguments.capability}: {arguments.default}"
        + (f" -> {' -> '.join(arguments.fallback)}" if arguments.fallback else "")
    )
    return 0


def _capability_describe(arguments: argparse.Namespace, workspace: Workspace) -> int:
    from alem.contracts import ContractRegistry

    _json(ContractRegistry(workspace).describe(arguments.capability, arguments.capability_version))
    return 0


def _input_payload(arguments: argparse.Namespace, workspace: Workspace) -> dict[str, Any]:
    if arguments.input_file:
        candidate = Path(arguments.input_file)
        path = workspace.assert_local(
            candidate if candidate.is_absolute() else workspace.root / candidate
        )
        raw = path.read_text(encoding="utf-8")
    else:
        raw = arguments.input
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AlemError(f"capability input must be a JSON object: {exc}") from exc
    if not isinstance(payload, dict):
        raise AlemError("capability input must be a JSON object")
    return payload


def _credentials(
    manager: PluginManager,
    capability: str,
    capability_version: str,
    provider: str | None,
) -> dict[str, str]:
    if capability == "model_completion":
        # The core model gateway resolves its own environment/workspace-local
        # credential with provider-specific precedence.  No secret crosses a
        # plugin process boundary for this built-in capability.
        return {}
    candidates = manager.registry(enabled_only=True).resolve(
        capability, provider, capability_version=capability_version
    )
    names: set[str] = set()
    for candidate in candidates:
        manifest = load_manifest(manager.plugins_dir / candidate.plugin_id)
        names.update(manifest.required_credentials)
        names.update(manifest.optional_credentials)
    # Only explicitly declared names cross the plugin process boundary.
    return {name: os.environ[name] for name in names if os.environ.get(name)}


def _capability_invoke(arguments: argparse.Namespace, workspace: Workspace) -> int:
    manager = _manager(workspace)
    payload = _input_payload(arguments, workspace)
    response = manager.invoke(
        arguments.capability,
        payload,
        provider=arguments.provider,
        capability_version=arguments.capability_version,
        operation=arguments.operation,
        credentials=_credentials(
            manager,
            arguments.capability,
            arguments.capability_version,
            arguments.provider,
        ),
    )
    _json(response.to_mapping())
    return 0


def _tool_list(arguments: argparse.Namespace, workspace: Workspace) -> int:
    values = list_tool_statuses(workspace)
    if arguments.json:
        _json({"tools": values})
        return 0
    if not values:
        print("No accepted integrations are registered")
        return 0
    print("ID  AUTHORSHIP  READINESS  AVAILABLE")
    for value in values:
        print(
            f"{value['id']}  {value['authorship']}  {value['readiness']}  "
            f"{'yes' if value['available'] else 'no'}"
        )
        for blocker in value["blockers"]:
            print(f"  - {blocker}")
    return 0


def _tool_status(arguments: argparse.Namespace, workspace: Workspace) -> int:
    values = list_tool_statuses(workspace, identifier=arguments.integration)
    if arguments.json:
        _json({"tools": values} if arguments.integration is None else {"tool": values[0]})
    elif arguments.integration is None:
        _tool_list(SimpleNamespace(json=False), workspace)
    else:
        value = values[0]
        print(
            f"{value['id']} ({value['plugin_id']})\n"
            f"Acceptance: {value['acceptance']}\n"
            f"Authorship: {value['authorship']}"
            + (f" — {value['contributor']}" if value["contributor"] else "")
            + f"\nRelease: {value['release_version']}\n"
            f"Available: {'yes' if value['available'] else 'no'}\n"
            f"Readiness: {value['readiness']}"
        )
        for blocker in value["blockers"]:
            print(f"  - {blocker}")
    return 0


def _tool_doctor(arguments: argparse.Namespace, workspace: Workspace) -> int:
    values = list_tool_statuses(workspace, identifier=arguments.integration)
    if arguments.json:
        _json({"tools": values})
    else:
        for value in values:
            print(f"{value['id']}: {value['readiness']}")
            for check in value["checks"]:
                print(f"  [{check['status']}] {check['name']}: {check['message']}")
    return 1 if any(value["readiness"] != "ready" for value in values) else 0


def _tool_configure(arguments: argparse.Namespace, workspace: Workspace) -> int:
    value = list_tool_statuses(
        workspace,
        identifier=arguments.integration,
        check_services=False,
    )[0]
    missing = value["missing_configuration"]
    if not missing:
        print(f"{value['id']}: all required configuration is present")
        if value["configuration_instructions"]:
            print(value["configuration_instructions"])
        return 0
    print(f"{value['id']} requires these environment variable names: {', '.join(missing)}")
    if value["configuration_instructions"]:
        print(value["configuration_instructions"])
    print(
        "Set the values through your operating system's secret manager or a hidden-input "
        "shell session. Alem does not persist or print secret values; capability invocation "
        "forwards only variables declared by the plugin manifest. Then rerun `alem tools doctor "
        f"{value['id']}`."
    )
    return 0


def register_commands(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    tools = commands.add_parser("tools", help="list accepted tools and check readiness")
    tool_commands = tools.add_subparsers(dest="tools_command", required=True)
    listing = tool_commands.add_parser("list", help="list accepted integrations and readiness")
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(handler=_tool_list)

    status = tool_commands.add_parser("status", help="show accepted integration blockers")
    status.add_argument("integration", nargs="?")
    status.add_argument("--json", action="store_true")
    status.set_defaults(handler=_tool_status)

    doctor = tool_commands.add_parser(
        "doctor", help="check local and declared service prerequisites"
    )
    doctor.add_argument("integration", nargs="?")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(handler=_tool_doctor)

    configure = tool_commands.add_parser(
        "configure", help="show secure setup guidance for accepted tool prerequisites"
    )
    configure.add_argument("integration")
    configure.set_defaults(handler=_tool_configure)

    plugin = commands.add_parser("plugin", help="develop and manage workspace-local plugins")
    plugin_commands = plugin.add_subparsers(dest="plugin_command", required=True)

    listing = plugin_commands.add_parser("list", help="list installed plugins")
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(handler=_plugin_list)

    search = plugin_commands.add_parser("search", help="search the checked-in catalogue")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--json", action="store_true")
    search.set_defaults(handler=_plugin_search)

    validate = plugin_commands.add_parser("validate", help="strictly validate a plugin manifest")
    validate.add_argument("path")
    validate.add_argument("--ignore-runtime", action="store_true")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(handler=_plugin_validate)

    install = plugin_commands.add_parser("install", help="install into .alem/plugins (disabled)")
    install.add_argument("plugin")
    install.add_argument(
        "--approve", action="store_true", help="explicitly approve this install plan"
    )
    install.add_argument(
        "--with-python-dependencies",
        action="store_true",
        help="install declared dependencies under .alem/plugin-dependencies",
    )
    install.set_defaults(handler=_plugin_install)

    enable = plugin_commands.add_parser("enable", help="approve execution and enable a plugin")
    enable.add_argument("plugin")
    enable.add_argument(
        "--approve", action="store_true", help="explicitly approve current code digest"
    )
    enable.set_defaults(handler=_plugin_enable)

    disable = plugin_commands.add_parser("disable", help="remove a plugin from routing")
    disable.add_argument("plugin")
    disable.set_defaults(handler=_plugin_disable)

    remove = plugin_commands.add_parser(
        "remove", help="remove installed code and local dependencies"
    )
    remove.add_argument("plugin")
    remove.add_argument("--yes", action="store_true", help="confirm removal")
    remove.add_argument(
        "--purge-data", action="store_true", help="also delete .alem/plugin-data/<id>"
    )
    remove.set_defaults(handler=_plugin_remove)

    update = plugin_commands.add_parser(
        "update", help="replace an installed plugin from its source"
    )
    update.add_argument("plugin")
    update.add_argument("--source")
    update.add_argument("--approve", action="store_true")
    update.add_argument("--with-python-dependencies", action="store_true")
    update.set_defaults(handler=_plugin_update)

    rollback = plugin_commands.add_parser(
        "rollback", help="restore the previous managed release and pin it"
    )
    rollback.add_argument("plugin")
    rollback.set_defaults(handler=_plugin_rollback)

    unpin = plugin_commands.add_parser(
        "unpin", help="allow Alem update to reconcile a newer release"
    )
    unpin.add_argument("plugin")
    unpin.set_defaults(handler=_plugin_unpin)

    create = plugin_commands.add_parser("create", help="generate a functional API v1 starter")
    create.add_argument("name")
    create.add_argument("--id")
    create.add_argument("--path")
    create.set_defaults(handler=_plugin_create)

    assets = plugin_commands.add_parser(
        "assets", help="discover enabled declarative skill, agent, and workflow assets"
    )
    assets.add_argument("--type", choices=["skill", "agent", "workflow"])
    assets.add_argument("--all", action="store_true", help="include disabled plugins")
    assets.add_argument("--json", action="store_true")
    assets.set_defaults(handler=_plugin_assets)

    capability = commands.add_parser(
        "capability", help="discover, route, and invoke abstract capabilities"
    )
    capability_commands = capability.add_subparsers(dest="capability_command", required=True)
    capability_list = capability_commands.add_parser("list", help="list discovered capabilities")
    capability_list.add_argument("--all", action="store_true", help="include disabled plugins")
    capability_list.add_argument("--json", action="store_true")
    capability_list.set_defaults(handler=_capability_list)

    providers = capability_commands.add_parser("providers", help="list capability providers")
    providers.add_argument("capability")
    providers.add_argument("--capability-version", default="1.0")
    providers.add_argument("--all", action="store_true")
    providers.add_argument("--json", action="store_true")
    providers.set_defaults(handler=_capability_providers)

    describe = capability_commands.add_parser(
        "describe", help="show the machine-readable contract for a capability"
    )
    describe.add_argument("capability")
    describe.add_argument("--capability-version", default="1.0")
    describe.set_defaults(handler=_capability_describe)

    route = capability_commands.add_parser("route", help="set a workspace-local provider order")
    route.add_argument("capability")
    route.add_argument("--default", required=True)
    route.add_argument("--fallback", action="append", default=[])
    route.set_defaults(handler=_capability_route)

    invoke = capability_commands.add_parser("invoke", help="invoke through capability routing")
    invoke.add_argument("capability")
    input_group = invoke.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", help="JSON object")
    input_group.add_argument("--input-file", help="workspace-local JSON file")
    invoke.add_argument("--provider")
    invoke.add_argument("--capability-version", default="1.0")
    invoke.add_argument("--operation", default="invoke")
    invoke.set_defaults(handler=_capability_invoke)
