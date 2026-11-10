"""Readiness checks for accepted integrations; discovery never imports plugin code."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from alem.config import load_config
from alem.errors import AlemError
from alem.extensions import PluginCatalogue, PluginManager
from alem.extensions.manager import plugin_tree_digest
from alem.extensions.manifest import Manifest, load_manifest
from alem.integrations import IntegrationRecord, load_integrations
from alem.workspace import Workspace


def _catalogue(workspace: Workspace) -> PluginCatalogue:
    configured = load_config(workspace).raw.get("plugins", {}).get("catalogues", [])
    if not isinstance(configured, list) or not configured or not isinstance(configured[0], str):
        raise AlemError("alem.toml must configure a plugin catalogue")
    return PluginCatalogue(workspace.path(configured[0]))


def _hardware_check(name: str) -> tuple[bool, str]:
    candidates = {
        "gpu": (("nvidia-smi", "--query-gpu=name", "--format=csv,noheader"), ("rocm-smi",)),
        "gpu:nvidia": (("nvidia-smi", "--query-gpu=name", "--format=csv,noheader"),),
        "gpu:rocm": (("rocm-smi",),),
    }.get(name)
    if candidates is None:
        return False, f"unsupported hardware readiness check: {name}"
    for command in candidates:
        executable = shutil.which(command[0])
        if not executable:
            continue
        try:
            result = subprocess.run(
                [executable, *command[1:]],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and result.stdout.strip():
            return True, f"hardware present: {name}"
    return False, f"required hardware is not available: {name}"


def _service_check(url: str, timeout: float = 2.0) -> tuple[bool, str]:
    host = urlparse(url).hostname or url
    request = urllib.request.Request(url, headers={"User-Agent": "Alem-readiness-check/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if 200 <= response.status < 400:
                return True, f"service reachable: {host} (HTTP {response.status})"
            return False, f"service unavailable: {host} (HTTP {response.status})"
    except urllib.error.HTTPError as exc:
        return False, f"service unavailable: {host} (HTTP {exc.code})"
    except (OSError, TimeoutError, urllib.error.URLError):
        return False, f"service unavailable: {host} (network check failed)"


def _accepted_record(workspace: Workspace, identifier: str) -> IntegrationRecord:
    for record in load_integrations(workspace):
        if record.acceptance == "accepted" and identifier in {record.id, record.plugin_id}:
            return record
    raise AlemError(f"no accepted integration matches {identifier!r}")


def _installed_root(manager: PluginManager, plugin_id: str) -> Any | None:
    state = manager._load_state()
    record = state["plugins"].get(plugin_id)
    if not isinstance(record, dict):
        return None
    return manager._installed_manifest(plugin_id, record), record


def tool_status(
    workspace: Workspace,
    record: IntegrationRecord,
    *,
    check_services: bool = True,
) -> dict[str, Any]:
    catalogue = _catalogue(workspace)
    entry = catalogue.get(record.plugin_id or "")
    source = catalogue.resolve_source(entry)
    manager = PluginManager(workspace.root, catalogue=catalogue.index)
    blockers: list[str] = []
    checks: list[dict[str, str]] = []
    readiness = "ready"
    manifest: Manifest | None = None
    integrity_ok = False

    os_name = {"darwin": "macos", "windows": "windows", "linux": "linux"}.get(
        platform.system().lower(), platform.system().lower()
    )
    try:
        manifest = load_manifest(source, check_compatibility=False)
        if os_name not in manifest.operating_systems:
            readiness = "unsupported-platform"
            blockers.append(f"release does not support {os_name}")
        checks.append(
            {
                "name": "platform",
                "status": "pass" if readiness != "unsupported-platform" else "blocked",
                "message": (
                    f"supported on {', '.join(manifest.operating_systems)}"
                    if readiness != "unsupported-platform"
                    else blockers[-1]
                ),
            }
        )
        if plugin_tree_digest(source) != record.release_digest:
            readiness = "error"
            blockers.append("checked-in release source does not match its pinned digest")
    except Exception as exc:
        readiness = "error"
        blockers.append(f"accepted release metadata could not be loaded: {exc}")
        checks.append({"name": "release", "status": "fail", "message": str(exc)})

    try:
        installed = _installed_root(manager, record.plugin_id or "")
    except Exception as exc:
        installed = None
        readiness = "error"
        blockers.append(f"managed plugin state could not be loaded: {exc}")
        checks.append({"name": "provisioning", "status": "fail", "message": str(exc)})
    missing_configuration: list[str] = []
    optional_configuration: list[str] = []
    if installed is None:
        if readiness != "error":
            if readiness == "ready":
                readiness = "missing-runtime"
            blockers.append("accepted tool is not provisioned; run `alem setup` or `alem update`")
            checks.append(
                {"name": "provisioning", "status": "blocked", "message": blockers[-1]}
            )
    else:
        installed_manifest, state = installed
        if not state.get("enabled") or not state.get("execution_approved_digest"):
            if readiness == "ready":
                readiness = "missing-runtime"
            blockers.append("managed plugin is disabled or no longer execution-approved")
            checks.append({"name": "provisioning", "status": "blocked", "message": blockers[-1]})
        else:
            checks.append(
                {"name": "provisioning", "status": "pass", "message": "managed plugin is enabled"}
            )
        manifest = installed_manifest
        try:
            actual_digest = manager._verify_digest(installed_manifest, state)
            if actual_digest != state.get("execution_approved_digest"):
                raise ValueError("execution approval does not match installed files")
            integrity_ok = True
        except Exception:
            readiness = "error"
            blockers.append("installed files or dependencies failed integrity verification")
            checks.append({"name": "integrity", "status": "fail", "message": blockers[-1]})

    if readiness not in {"unsupported-platform", "error"} and manifest is not None:
        for runtime in record.required_runtimes:
            candidates = [runtime]
            if os.name == "nt" and not runtime.lower().endswith((".cmd", ".exe", ".bat")):
                candidates.extend((f"{runtime}.cmd", f"{runtime}.exe"))
            exists = any(workspace.path(candidate).is_file() for candidate in candidates)
            if not exists:
                if readiness == "ready":
                    readiness = "missing-runtime"
                blockers.append(f"missing managed runtime: {runtime}")
            checks.append(
                {
                    "name": f"runtime:{runtime}",
                    "status": "pass" if exists else "blocked",
                    "message": f"managed runtime present: {runtime}"
                    if exists
                    else f"missing managed runtime: {runtime}",
                }
            )

        for hardware in record.required_hardware:
            present, message = _hardware_check(hardware)
            if not present:
                if readiness in {"ready", "missing-runtime"}:
                    readiness = "missing-hardware"
                blockers.append(message)
            checks.append(
                {
                    "name": f"hardware:{hardware}",
                    "status": "pass" if present else "blocked",
                    "message": message,
                }
            )

        missing_configuration = [
            name for name in manifest.required_credentials if not os.environ.get(name)
        ]
        optional_configuration = [
            name for name in manifest.optional_credentials if not os.environ.get(name)
        ]
        if missing_configuration:
            if readiness in {"ready", "missing-runtime"}:
                readiness = "needs-configuration"
            blockers.append(
                "required configuration is missing: " + ", ".join(missing_configuration)
            )
        checks.append(
            {
                "name": "configuration",
                "status": "blocked" if missing_configuration else "pass",
                "message": "missing: " + ", ".join(missing_configuration)
                if missing_configuration
                else "all required environment variables are present",
            }
        )

        if check_services and readiness in {"ready", "missing-runtime"}:
            for service in record.service_checks:
                reachable, message = _service_check(service)
                if not reachable:
                    readiness = "service-unavailable"
                    blockers.append(message)
                checks.append(
                    {
                        "name": f"service:{urlparse(service).hostname or service}",
                        "status": "pass" if reachable else "blocked",
                        "message": message,
                    }
                )

    release_current = bool(
        installed
        and installed[1].get("version") == record.release_version
        and installed[1].get("release_digest") == record.release_digest
    )
    pinned_release = installed[1].get("pinned_release") if installed else None
    last_reconciliation = workspace.read_json(".alem/state/integrations.json", default={})
    last_failure = None
    if isinstance(last_reconciliation, dict):
        failed = last_reconciliation.get("failed", [])
        if isinstance(failed, list):
            last_failure = next(
                (item for item in failed if isinstance(item, dict) and item.get("id") == record.id),
                None,
            )
    available = bool(
        installed and installed[1].get("enabled") and integrity_ok
    )
    return {
        "id": record.id,
        "plugin_id": record.plugin_id,
        "name": record.name,
        "acceptance": record.acceptance,
        "authorship": record.authorship,
        "contributor": record.contributor,
        "release_version": record.release_version,
        "release_digest": record.release_digest,
        "capabilities": list(record.capabilities),
        "available": available,
        "availability": "available" if available else "accepted-not-provisioned",
        "release_current": release_current,
        "pinned": isinstance(pinned_release, dict),
        "last_reconciliation_failure": last_failure,
        "readiness": readiness,
        "blockers": blockers,
        "checks": checks,
        "missing_configuration": missing_configuration,
        "optional_configuration": optional_configuration,
        "configuration_instructions": record.configuration_instructions,
    }


def list_tool_statuses(
    workspace: Workspace,
    *,
    identifier: str | None = None,
    check_services: bool = True,
) -> list[dict[str, Any]]:
    records = [item for item in load_integrations(workspace) if item.acceptance == "accepted"]
    if identifier is not None:
        records = [_accepted_record(workspace, identifier)]
    return [tool_status(workspace, item, check_services=check_services) for item in records]
