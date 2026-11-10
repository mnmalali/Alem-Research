"""Provision maintainer-accepted integrations from the versioned release registry."""

from __future__ import annotations

import copy
import platform
from datetime import UTC, datetime
from typing import Any

from alem.config import load_config
from alem.errors import AlemError
from alem.extensions import PluginCatalogue, PluginManager
from alem.extensions.manager import plugin_tree_digest
from alem.extensions.manifest import Manifest, load_manifest
from alem.extensions.versions import satisfies
from alem.integrations import IntegrationRecord, load_integrations
from alem.setup_workspace import sync_all_skill_adapters
from alem.workspace import Workspace


def _catalogue(workspace: Workspace) -> PluginCatalogue:
    config = load_config(workspace)
    values = config.raw.get("plugins", {}).get("catalogues", [])
    if not isinstance(values, list) or not values or not isinstance(values[0], str):
        raise AlemError("alem.toml must configure a repository-local plugin catalogue")
    path = workspace.path(values[0])
    if not path.is_file():
        raise AlemError(f"configured plugin catalogue does not exist: {path}")
    return PluginCatalogue(path)


def _manifest_supported(manifest: Manifest) -> tuple[bool, str | None]:
    os_name = {"darwin": "macos", "windows": "windows", "linux": "linux"}.get(
        platform.system().lower(), platform.system().lower()
    )
    if os_name not in manifest.operating_systems:
        return False, f"unsupported-platform: release does not support {os_name}"
    current = platform.python_version()
    if not satisfies(current, manifest.python):
        return False, f"missing-runtime: requires Python {manifest.python}; found {current}"
    return True, None


def _accepted_order(
    accepted: list[IntegrationRecord], manifests: dict[str, Manifest]
) -> tuple[list[IntegrationRecord], list[dict[str, str]]]:
    by_plugin = {item.plugin_id: item for item in accepted if item.plugin_id}
    ordered: list[IntegrationRecord] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    failures: dict[str, str] = {}

    def visit(record: IntegrationRecord) -> None:
        plugin_id = record.plugin_id or ""
        if plugin_id in visited:
            return
        if plugin_id in visiting:
            raise AlemError(f"accepted plugin dependency cycle includes {plugin_id}")
        visiting.add(plugin_id)
        try:
            for dependency in manifests[plugin_id].plugin_dependencies:
                target = by_plugin.get(dependency.id)
                if target is None:
                    raise AlemError(
                        f"accepted plugin {plugin_id} depends on {dependency.id}, "
                        "which is not provisionable on this platform"
                    )
                visit(target)
            visited.add(plugin_id)
            ordered.append(record)
        except AlemError as exc:
            failures.setdefault(record.id, str(exc))
            raise
        finally:
            visiting.remove(plugin_id)

    for item in accepted:
        try:
            visit(item)
        except AlemError:
            continue
    return ordered, [{"id": key, "reason": value} for key, value in failures.items()]


def reconcile_accepted_integrations(workspace: Workspace) -> dict[str, Any]:
    """Install or update every supported accepted release, without touching candidates."""
    catalogue = _catalogue(workspace)
    records = load_integrations(workspace)
    accepted = [item for item in records if item.acceptance == "accepted"]
    manifests: dict[str, Manifest] = {}
    ready_records: list[IntegrationRecord] = []
    results: dict[str, Any] = {
        "accepted": len(accepted),
        "installed": [],
        "updated": [],
        "already_current": [],
        "pinned": [],
        "unsupported": [],
        "failed": [],
        "candidates_untouched": sum(item.acceptance != "accepted" for item in records),
    }
    for item in accepted:
        try:
            entry = catalogue.get(item.plugin_id or "")
            source = catalogue.resolve_source(entry)
            manifest = load_manifest(source, check_compatibility=False)
            if entry.version != item.release_version or manifest.version != item.release_version:
                raise AlemError("release version does not match the pinned registry entry")
            actual_digest = plugin_tree_digest(source)
            if actual_digest != item.release_digest:
                raise AlemError("release digest does not match the checked-in source tree")
            manifests[manifest.id] = manifest
            supported, reason = _manifest_supported(manifest)
            if not supported:
                results["unsupported"].append(
                    {"id": item.id, "plugin_id": manifest.id, "reason": reason}
                )
                continue
            ready_records.append(item)
        except Exception as exc:
            results["failed"].append({"id": item.id, "reason": str(exc)})

    ordered, dependency_failures = _accepted_order(ready_records, manifests)
    results["failed"].extend(dependency_failures)

    manager = PluginManager(workspace.root, catalogue=catalogue.index)
    for item in ordered:
        plugin_id = item.plugin_id or ""
        manifest = manifests[plugin_id]
        entry = catalogue.get(plugin_id)
        state = manager._load_state()
        previous = copy.deepcopy(state["plugins"].get(plugin_id))
        try:
            installed_manifest = manager._installed_manifest(plugin_id, previous)
            approved_digest = manager._verify_digest(installed_manifest, previous)
            integrity_current = approved_digest == previous.get("execution_approved_digest")
            installed_digest = previous.get("digest") == item.release_digest
        except Exception:
            integrity_current = False
            installed_digest = False
        pin = previous.get("pinned_release") if isinstance(previous, dict) else None
        if (
            isinstance(pin, dict)
            and previous.get("version") == pin.get("version")
            and previous.get("digest") == pin.get("digest")
            and previous.get("enabled") is True
            and integrity_current
        ):
            results["pinned"].append(plugin_id)
            continue
        code_current = (
            isinstance(previous, dict)
            and previous.get("version") == item.release_version
            and installed_digest
            and previous.get("enabled") is True
            and integrity_current
        )
        if code_current:
            state["plugins"][plugin_id].update(
                {
                    "acceptance": item.acceptance,
                    "authorship": item.authorship,
                    "contributor": item.contributor or "",
                    "release_version": item.release_version or "",
                    "release_digest": item.release_digest or "",
                    "release_registry": "integrations/registry.toml",
                }
            )
            manager._save_state(state)
            results["already_current"].append(plugin_id)
            continue
        try:
            manager.install(
                plugin_id,
                approved=True,
                install_python_dependencies=True,
                release_metadata={
                    "acceptance": item.acceptance,
                    "authorship": item.authorship,
                    "contributor": item.contributor or "",
                    "release_version": item.release_version or "",
                    "release_digest": item.release_digest or "",
                    "release_registry": "integrations/registry.toml",
                },
                enable_after_install=True,
                immutable_release=True,
            )
            (results["updated"] if previous else results["installed"]).append(plugin_id)
        except Exception as exc:
            results["failed"].append({"id": item.id, "reason": str(exc)})

    sync_all_skill_adapters(workspace)
    results["updated_at"] = datetime.now(UTC).isoformat()
    workspace.write_json(".alem/state/integrations.json", results)
    return results
