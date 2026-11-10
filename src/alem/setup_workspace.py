"""Local-only workspace initialization."""

from __future__ import annotations

import platform
import stat
import subprocess
import sys
import venv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alem.adapters import sync_skill_adapters
from alem.config import load_config
from alem.extensions import ExtensionError, PluginCatalogue, PluginManager
from alem.integrations import load_integrations
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
    """Reconcile accepted releases, then classify catalog entries without provisioning them."""
    from alem.reconciliation import reconcile_accepted_integrations

    result: dict[str, Any] = {
        "official": {"installed": [], "updated": [], "already_current": []},
        "community_accepted": {"installed": [], "updated": [], "already_current": []},
        "community_available": {"verified": [], "unverified": []},
        "reconciliation": {
            "accepted": 0,
            "installed": [],
            "updated": [],
            "already_current": [],
            "pinned": [],
            "unsupported": [],
            "failed": [],
            "candidates_untouched": 0,
        },
    }
    catalogue_path = _configured_catalogue(workspace, config)
    if catalogue_path is None:
        return result

    catalogue = PluginCatalogue(catalogue_path)
    registry_path = workspace.path("integrations/registry.toml")
    records = load_integrations(workspace) if registry_path.is_file() else []
    by_plugin = {item.plugin_id: item for item in records if item.plugin_id}
    accepted_ids = {
        item.plugin_id for item in records if item.acceptance == "accepted" and item.plugin_id
    }
    for entry in catalogue.search():
        if entry.channel == "community" and entry.id not in accepted_ids:
            result["community_available"][entry.verification].append(entry.id)
    reconciliation = reconcile_accepted_integrations(workspace) if registry_path.is_file() else None
    if reconciliation is not None:
        result["reconciliation"] = reconciliation
        for category, ids in (
            ("installed", reconciliation["installed"]),
            ("updated", reconciliation["updated"]),
            ("already_current", reconciliation["already_current"]),
            ("pinned", reconciliation["pinned"]),
        ):
            for plugin_id in ids:
                record = by_plugin.get(plugin_id)
                if record is None:
                    continue
                group = "official" if record.authorship == "alem-official" else "community_accepted"
                result[group][category].append(plugin_id)
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
        bootstrap = workspace.path("scripts/bootstrap_runtime.py")
        completed = subprocess.run(
            [sys.executable, str(bootstrap), str(workspace.root)],
            cwd=workspace.root,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError(
                "Alem dependencies could not be installed into .alem/venv; "
                "see the pip output above"
            )
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
        "local_venv_ready": bool(local_python(workspace)),
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
