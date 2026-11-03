"""Local-only workspace initialization."""

from __future__ import annotations

import platform
import stat
import sys
import venv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alem.adapters import sync_skill_adapters
from alem.config import load_config
from alem.extensions import ExtensionError, PluginCatalogue, PluginManager
from alem.workspace import Workspace


def sync_all_skill_adapters(workspace: Workspace, *, mode: str | None = None) -> dict[str, int]:
    """Synchronize canonical and enabled plugin skills through one adapter layer."""
    config = load_config(workspace)
    catalogue: Path | None = None
    configured = config.raw.get("plugins", {}).get("catalogues", [])
    if isinstance(configured, list) and configured and isinstance(configured[0], str):
        candidate = workspace.path(configured[0])
        if candidate.is_file():
            catalogue = candidate
    plugin_skills: list[tuple[str, Path]] = []
    try:
        manager = PluginManager(workspace.root, catalogue=catalogue)
        plugin_skills = [
            (asset.plugin_id, asset.path) for asset in manager.discover_assets("skill")
        ]
    except (ExtensionError, OSError, ValueError):
        # A damaged plugin never blocks core setup; generated plugin adapters
        # are removed until its integrity is restored and it is enabled again.
        plugin_skills = []
    return sync_skill_adapters(
        workspace,
        plugin_skills=plugin_skills,
        mode=mode or config.context.mode,
    )


def _configured_catalogue(workspace: Workspace, config) -> Path | None:
    configured = config.raw.get("plugins", {}).get("catalogues", [])
    if isinstance(configured, list) and configured and isinstance(configured[0], str):
        candidate = workspace.path(configured[0])
        if candidate.is_file():
            return candidate
    return None


def _setup_plugins(workspace: Workspace, config) -> dict[str, Any]:
    """Install trusted official plugins and report opt-in community choices."""
    result: dict[str, Any] = {
        "official": {"installed": [], "enabled": [], "already_ready": []},
        "community_available": {"verified": [], "unverified": []},
    }
    catalogue_path = _configured_catalogue(workspace, config)
    if catalogue_path is None:
        return result

    catalogue = PluginCatalogue(catalogue_path)
    for entry in catalogue.search():
        if entry.channel == "community":
            result["community_available"][entry.verification].append(entry.id)

    manager = PluginManager(workspace.root, catalogue=catalogue_path)
    installed = {item.id: item for item in manager.list_installed()}
    for entry in catalogue.search():
        if entry.channel != "official":
            continue
        if entry.id not in installed:
            manager.install(entry.id, approved=True)
            result["official"]["installed"].append(entry.id)
            installed = {item.id: item for item in manager.list_installed()}
        if not installed[entry.id].enabled:
            manager.enable(entry.id, approve_execution=True)
            result["official"]["enabled"].append(entry.id)
        else:
            result["official"]["already_ready"].append(entry.id)
    return result


def initialize_workspace(
    workspace: Workspace,
    *,
    create_venv: bool = False,
) -> dict[str, Any]:
    config = load_config(workspace)
    created = workspace.ensure_runtime()
    plugins = _setup_plugins(workspace, config)
    adapters = sync_all_skill_adapters(workspace)
    from alem.context import build_context_index

    context_index = build_context_index(workspace)
    launcher = workspace.path("alem")
    if platform.system().lower() != "windows" and launcher.is_file():
        launcher.chmod(
            launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        )
    local_venv = workspace.path(".alem/venv")
    venv_created = False
    if create_venv and not local_venv.exists():
        venv.EnvBuilder(with_pip=True, clear=False, symlinks=False).create(local_venv)
        venv_created = True
    record = {
        "workspace_version": config.workspace_version,
        "initialized_at": datetime.now(UTC).isoformat(),
        "root": str(workspace.root),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "created_paths": [str(path.relative_to(workspace.root)) for path in created],
        "skill_adapters": adapters,
        "plugins": plugins,
        "context": {
            "mode": config.context.mode,
            "indexed_entries": len(context_index["entries"]),
            "index_digest": context_index["digest"],
        },
        "local_venv_created": venv_created,
        "scope_guarantee": "All recorded paths resolve inside the workspace root.",
    }
    workspace.write_json(".alem/state/workspace.json", record)
    return record


def local_python(workspace: Workspace) -> Path | None:
    candidates = (
        workspace.path(".alem/venv/Scripts/python.exe"),
        workspace.path(".alem/venv/bin/python"),
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)
