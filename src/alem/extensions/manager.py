"""Workspace-local plugin lifecycle, approvals, dependency resolution, and routing."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import distributions
from pathlib import Path
from typing import Any

from .api import API_VERSION, ExecutionRequest, ExecutionResponse
from .catalogue import PluginCatalogue
from .errors import (
    ApprovalRequired,
    DependencyError,
    ExtensionError,
    PluginExecutionError,
    PluginIntegrityError,
    PluginNotFoundError,
    RoutingError,
)
from .manifest import Manifest, load_manifest
from .registry import PluginRegistry
from .runtime import SubprocessRuntime
from .versions import satisfies

STATE_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class InstalledPlugin:
    id: str
    name: str
    version: str
    enabled: bool
    installation_approved: bool
    execution_approved: bool
    capabilities: tuple[str, ...]
    source: str


@dataclass(frozen=True, slots=True)
class ExtensionAsset:
    """One enabled declarative skill, agent, or workflow asset."""

    plugin_id: str
    extension_type: str
    path: Path


@dataclass(frozen=True, slots=True)
class InstallPlan:
    """Dependency-first, immutable install plan."""

    plugins: tuple[Manifest, ...]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        raise PluginIntegrityError(f"plugin directory is missing: {root}")

    def is_link_or_reparse(path: Path) -> bool:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if is_junction is not None and is_junction():
            return True
        try:
            attributes = os.lstat(path).st_file_attributes
        except (AttributeError, OSError):
            return False
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return bool(attributes & reparse_flag)

    if is_link_or_reparse(root):
        raise PluginIntegrityError(f"plugin tree root may not be a link or junction: {root}")
    files: list[Path] = []
    for current_text, directories, filenames in os.walk(root, followlinks=False):
        current = Path(current_text)
        for name in directories:
            path = current / name
            if is_link_or_reparse(path):
                raise PluginIntegrityError(
                    f"plugin trees may not contain links, junctions, or reparse points: {path}"
                )
        for name in filenames:
            path = current / name
            if is_link_or_reparse(path):
                raise PluginIntegrityError(
                    f"plugin trees may not contain links, junctions, or reparse points: {path}"
                )
            if "__pycache__" not in path.parts and not path.name.endswith((".pyc", ".pyo")):
                files.append(path)
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _copy_plugin(source: Path, destination: Path) -> None:
    ignored = shutil.ignore_patterns(".git", ".venv", "venv", "__pycache__", "*.pyc", "*.pyo")
    # Digest first so symlinks are rejected instead of followed by copytree.
    _tree_digest(source)
    shutil.copytree(source, destination, ignore=ignored, symlinks=False)


def _dependency_lock(root: Path) -> list[str]:
    """Return normalized installed distribution versions without importing them."""
    locked = []
    for distribution in distributions(path=[str(root)]):
        name = distribution.metadata.get("Name")
        if name and distribution.version:
            locked.append(f"{name}=={distribution.version}")
    return sorted(set(locked), key=str.casefold)


def _integrity_token(plugin_digest: str, dependency_digest: str | None) -> str:
    if dependency_digest is None:
        return plugin_digest
    value = f"plugin:{plugin_digest}\ndependencies:{dependency_digest}\n"
    return hashlib.sha256(value.encode()).hexdigest()


def _install_pinned_dependencies(
    requirements: tuple[str, ...],
    target: Path,
    *,
    workspace: Path,
    sandbox: Path,
    plugin_id: str,
) -> None:
    """Install reviewed exact pins into a staged workspace-local directory."""
    target.mkdir(parents=True)
    pip_home = sandbox / "home"
    pip_cache = sandbox / "cache"
    pip_os_temp = sandbox / "temp"
    for directory in (pip_home, pip_cache, pip_os_temp):
        directory.mkdir(parents=True)
    pip_config = sandbox / "pip-config.ini"
    pip_config.write_text("[global]\ndisable-pip-version-check = true\n", encoding="utf-8")
    pip_environment = {
        key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "PATH") if key in os.environ
    }
    pip_environment.update(
        {
            "HOME": str(pip_home),
            "USERPROFILE": str(pip_home),
            "APPDATA": str(pip_home / "appdata"),
            "LOCALAPPDATA": str(pip_home / "localappdata"),
            "XDG_CONFIG_HOME": str(pip_home / "config"),
            "XDG_CACHE_HOME": str(pip_cache),
            "PIP_CONFIG_FILE": str(pip_config),
            "PIP_CACHE_DIR": str(pip_cache),
            "TEMP": str(pip_os_temp),
            "TMP": str(pip_os_temp),
            "TMPDIR": str(pip_os_temp),
            "PYTHONIOENCODING": "utf-8",
        }
    )
    command = [
        sys.executable,
        "-m",
        "pip",
        "--isolated",
        "install",
        "--disable-pip-version-check",
        "--no-cache-dir",
        "--no-input",
        "--no-deps",
        "--only-binary=:all:",
        "--target",
        str(target),
        *requirements,
    ]
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        cwd=workspace,
        env=pip_environment,
    )
    if completed.returncode:
        raise DependencyError(
            f"workspace-local dependency installation failed for {plugin_id}: "
            f"{completed.stderr[-2000:]}"
        )


class PluginManager:
    """Own all mutable plugin state inside one Alem workspace."""

    def __init__(
        self,
        workspace: str | os.PathLike[str],
        *,
        catalogue: str | os.PathLike[str] | None = None,
        runtime: SubprocessRuntime | None = None,
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.alem_dir = self.workspace / ".alem"
        self.plugins_dir = self.alem_dir / "plugins"
        self.dependencies_dir = self.alem_dir / "plugin-dependencies"
        self.data_dir = self.alem_dir / "plugin-data"
        self.state_path = self.alem_dir / "state" / "plugins.json"
        self.catalogue = PluginCatalogue(catalogue) if catalogue else None
        self.runtime = runtime or SubprocessRuntime()

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {"schema_version": STATE_SCHEMA_VERSION, "plugins": {}, "routes": {}}

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._empty_state()
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PluginIntegrityError(f"cannot read plugin state: {exc}") from exc
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != STATE_SCHEMA_VERSION
            or not isinstance(value.get("plugins"), dict)
            or not isinstance(value.get("routes"), dict)
        ):
            raise PluginIntegrityError("plugin state has an unsupported or malformed schema")
        return value

    def _save_state(self, state: Mapping[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, self.state_path)

    def _resolve_source(self, source: str | os.PathLike[str]) -> tuple[Path, str]:
        path = Path(source)
        if path.exists():
            return path.resolve(), str(path.resolve())
        if self.catalogue is None:
            raise PluginNotFoundError(
                f"plugin source does not exist and no catalogue is configured: {source}"
            )
        entry = self.catalogue.get(str(source))
        return self.catalogue.resolve_source(entry), entry.id

    def _record(self, plugin_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        state = self._load_state()
        try:
            record = state["plugins"][plugin_id]
        except KeyError as exc:
            raise PluginNotFoundError(f"plugin is not installed: {plugin_id}") from exc
        if not isinstance(record, dict):
            raise PluginIntegrityError(f"malformed state for plugin {plugin_id}")
        return state, record

    def _installed_manifest(
        self, plugin_id: str, record: Mapping[str, Any] | None = None
    ) -> Manifest:
        if record is None:
            _, record = self._record(plugin_id)
        relative = record.get("path")
        if not isinstance(relative, str):
            raise PluginIntegrityError(f"malformed path state for plugin {plugin_id}")
        root = (self.workspace / relative).resolve()
        try:
            root.relative_to(self.alem_dir.resolve())
        except ValueError as exc:
            raise PluginIntegrityError(f"plugin path escaped .alem: {relative}") from exc
        manifest = load_manifest(root)
        if manifest.id != plugin_id or manifest.version != record.get("version"):
            raise PluginIntegrityError(f"installed manifest identity changed for {plugin_id}")
        return manifest

    def _verify_digest(self, manifest: Manifest, record: Mapping[str, Any]) -> str:
        actual = _tree_digest(manifest.root)
        if actual != record.get("digest"):
            raise PluginIntegrityError(
                f"installed files for {manifest.id} changed; update/reinstall "
                "and approve execution again"
            )
        dependency_digest: str | None = None
        dependency_path = record.get("dependency_path")
        if dependency_path is not None:
            if not isinstance(dependency_path, str):
                raise PluginIntegrityError(f"malformed dependency path state for {manifest.id}")
            dependency_root = (self.workspace / dependency_path).resolve()
            try:
                dependency_root.relative_to(self.dependencies_dir.resolve())
            except ValueError as exc:
                raise PluginIntegrityError(
                    f"dependency path escaped .alem for {manifest.id}"
                ) from exc
            dependency_digest = _tree_digest(dependency_root)
            if dependency_digest != record.get("dependency_digest"):
                raise PluginIntegrityError(
                    f"installed dependencies for {manifest.id} changed; update/reinstall "
                    "and approve execution again"
                )
            if _dependency_lock(dependency_root) != record.get("dependency_lock"):
                raise PluginIntegrityError(
                    f"installed dependency metadata for {manifest.id} changed"
                )
        return _integrity_token(actual, dependency_digest)

    def _dependency_edges(self, plugin_id: str, record: Mapping[str, Any]) -> list[dict[str, Any]]:
        stored = record.get("plugin_dependencies")
        if isinstance(stored, list) and all(isinstance(item, dict) for item in stored):
            return stored
        manifest = self._installed_manifest(plugin_id, record)
        return [
            {"id": item.id, "version": item.version, "optional": item.optional}
            for item in manifest.plugin_dependencies
        ]

    def _enabled_required_dependents(self, plugin_id: str, state: Mapping[str, Any]) -> list[str]:
        dependents = []
        for candidate_id, record in state["plugins"].items():
            if candidate_id == plugin_id or not record.get("enabled"):
                continue
            try:
                edges = self._dependency_edges(candidate_id, record)
            except ExtensionError:
                continue
            if any(
                edge.get("id") == plugin_id and not edge.get("optional", False) for edge in edges
            ):
                dependents.append(candidate_id)
        return sorted(dependents)

    def plan_install(self, source: str | os.PathLike[str]) -> InstallPlan:
        root, _ = self._resolve_source(source)
        requested = load_manifest(root)
        state = self._load_state()
        ordered: list[Manifest] = []
        visiting: list[str] = []
        selected: dict[str, Manifest] = {}

        def visit(manifest: Manifest) -> None:
            if manifest.id in visiting:
                cycle = " -> ".join((*visiting, manifest.id))
                raise DependencyError(f"plugin dependency cycle: {cycle}")
            existing_selected = selected.get(manifest.id)
            if existing_selected:
                if existing_selected.version != manifest.version:
                    raise DependencyError(
                        f"dependency conflict for {manifest.id}: "
                        f"{existing_selected.version} vs {manifest.version}"
                    )
                return
            selected[manifest.id] = manifest
            visiting.append(manifest.id)
            for dependency in manifest.plugin_dependencies:
                installed = state["plugins"].get(dependency.id)
                if isinstance(installed, Mapping) and satisfies(
                    str(installed.get("version", "")), dependency.version
                ):
                    continue
                if self.catalogue is None:
                    if dependency.optional:
                        continue
                    raise DependencyError(
                        f"dependency {dependency.id} requires a configured catalogue"
                    )
                try:
                    dep_source = self.catalogue.resolve_source(self.catalogue.get(dependency.id))
                except PluginNotFoundError:
                    if dependency.optional:
                        continue
                    raise DependencyError(
                        f"required dependency is unavailable: {dependency.id}"
                    ) from None
                dep_manifest = load_manifest(dep_source)
                if not satisfies(dep_manifest.version, dependency.version):
                    raise DependencyError(
                        f"catalogue version {dep_manifest.version} of {dependency.id} "
                        f"does not satisfy {dependency.version}"
                    )
                visit(dep_manifest)
            visiting.pop()
            ordered.append(manifest)

        visit(requested)
        return InstallPlan(tuple(ordered))

    def install(
        self,
        source: str | os.PathLike[str],
        *,
        approved: bool = False,
        install_python_dependencies: bool = False,
    ) -> InstallPlan:
        plan = self.plan_install(source)
        root_plugin = plan.plugins[-1]
        if not approved:
            raise ApprovalRequired("installation", root_plugin.id)
        for manifest in plan.plugins:
            if manifest.python_dependencies and not install_python_dependencies:
                raise DependencyError(
                    f"{manifest.id} declares Python dependencies; explicitly enable "
                    "workspace-local dependency installation"
                )
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        state = self._load_state()
        source_root, source_label = self._resolve_source(source)
        source_by_id = {root_plugin.id: (source_root, source_label)}
        if self.catalogue:
            for manifest in plan.plugins[:-1]:
                entry = self.catalogue.get(manifest.id)
                source_by_id[manifest.id] = (self.catalogue.resolve_source(entry), entry.id)
        for manifest in plan.plugins:
            plugin_source, label = source_by_id[manifest.id]
            target = self.plugins_dir / manifest.id
            dependency_target = self.dependencies_dir / manifest.id
            self.dependencies_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="install-", dir=self.alem_dir) as temp_text:
                transaction = Path(temp_text)
                staged_plugin = transaction / "new-plugin"
                staged_dependencies = transaction / "new-dependencies"
                old_plugin = transaction / "old-plugin"
                old_dependencies = transaction / "old-dependencies"
                _copy_plugin(plugin_source, staged_plugin)
                staged_manifest = load_manifest(staged_plugin)
                if staged_manifest.id != manifest.id or staged_manifest.version != manifest.version:
                    raise PluginIntegrityError("plugin changed while it was being installed")
                plugin_digest = _tree_digest(staged_plugin)
                dependency_path: str | None = None
                dependency_digest: str | None = None
                dependency_lock: list[str] = []
                if manifest.python_dependencies:
                    _install_pinned_dependencies(
                        manifest.python_dependencies,
                        staged_dependencies,
                        workspace=self.workspace,
                        sandbox=transaction / "pip-sandbox",
                        plugin_id=manifest.id,
                    )
                    dependency_digest = _tree_digest(staged_dependencies)
                    dependency_lock = _dependency_lock(staged_dependencies)
                    dependency_path = dependency_target.relative_to(self.workspace).as_posix()

                previous_record = state["plugins"].get(manifest.id)
                moved_plugin = False
                moved_dependencies = False
                installed_plugin = False
                installed_dependencies = False
                try:
                    if target.exists():
                        os.replace(target, old_plugin)
                        moved_plugin = True
                    if dependency_target.exists():
                        os.replace(dependency_target, old_dependencies)
                        moved_dependencies = True
                    os.replace(staged_plugin, target)
                    installed_plugin = True
                    if manifest.python_dependencies:
                        os.replace(staged_dependencies, dependency_target)
                        installed_dependencies = True
                    state["plugins"][manifest.id] = {
                        "name": manifest.name,
                        "version": manifest.version,
                        "path": target.relative_to(self.workspace).as_posix(),
                        "source": label,
                        "digest": plugin_digest,
                        "enabled": False,
                        "installation_approved_at": _utc_now(),
                        "execution_approved_digest": None,
                        "execution_approved_at": None,
                        "dependency_path": dependency_path,
                        "dependency_digest": dependency_digest,
                        "dependency_lock": dependency_lock,
                        "plugin_dependencies": [
                            {
                                "id": item.id,
                                "version": item.version,
                                "optional": item.optional,
                            }
                            for item in manifest.plugin_dependencies
                        ],
                    }
                    # Save each dependency-first step. If a later plugin fails,
                    # installed dependencies remain recorded and disabled.
                    self._save_state(state)
                except Exception:
                    if installed_plugin and target.exists():
                        shutil.rmtree(target)
                    if installed_dependencies and dependency_target.exists():
                        shutil.rmtree(dependency_target)
                    if moved_plugin:
                        os.replace(old_plugin, target)
                    if moved_dependencies:
                        os.replace(old_dependencies, dependency_target)
                    if previous_record is None:
                        state["plugins"].pop(manifest.id, None)
                    else:
                        state["plugins"][manifest.id] = previous_record
                    raise
        return plan

    def list_installed(self) -> list[InstalledPlugin]:
        state = self._load_state()
        values: list[InstalledPlugin] = []
        for plugin_id, record in sorted(state["plugins"].items()):
            digest_matches = False
            try:
                manifest = self._installed_manifest(plugin_id, record)
                digest_matches = self._verify_digest(manifest, record) == record.get(
                    "execution_approved_digest"
                )
                name = manifest.name
                version = manifest.version
                capabilities = tuple(item.name for item in manifest.capabilities)
            except ExtensionError:
                # Keep lifecycle commands usable so a damaged plugin can still
                # be disabled, updated, or removed without affecting others.
                name = str(record.get("name", plugin_id))
                version = str(record.get("version", "unknown"))
                capabilities = ()
            values.append(
                InstalledPlugin(
                    id=plugin_id,
                    name=name,
                    version=version,
                    enabled=bool(record.get("enabled")),
                    installation_approved=bool(record.get("installation_approved_at")),
                    execution_approved=digest_matches,
                    capabilities=capabilities,
                    source=str(record.get("source", "")),
                )
            )
        return values

    def enable(self, plugin_id: str, *, approve_execution: bool = False) -> None:
        state, record = self._record(plugin_id)
        manifest = self._installed_manifest(plugin_id, record)
        digest = self._verify_digest(manifest, record)
        missing_or_disabled = [
            edge["id"]
            for edge in self._dependency_edges(plugin_id, record)
            if not edge.get("optional", False)
            and (
                edge["id"] not in state["plugins"]
                or not state["plugins"][edge["id"]].get("enabled")
            )
        ]
        if missing_or_disabled:
            raise DependencyError(
                f"cannot enable {plugin_id}; enable required dependencies first: "
                + ", ".join(sorted(missing_or_disabled))
            )
        record["enabled"] = True
        if approve_execution:
            record["execution_approved_digest"] = digest
            record["execution_approved_at"] = _utc_now()
        self._save_state(state)

    def approve_execution(self, plugin_id: str, *, approved: bool = False) -> None:
        if not approved:
            raise ApprovalRequired("execution", plugin_id)
        state, record = self._record(plugin_id)
        manifest = self._installed_manifest(plugin_id, record)
        record["execution_approved_digest"] = self._verify_digest(manifest, record)
        record["execution_approved_at"] = _utc_now()
        self._save_state(state)

    def disable(self, plugin_id: str) -> None:
        state, record = self._record(plugin_id)
        dependents = self._enabled_required_dependents(plugin_id, state)
        if dependents:
            raise DependencyError(
                f"cannot disable {plugin_id}; required by enabled plugins: " + ", ".join(dependents)
            )
        record["enabled"] = False
        self._save_state(state)

    def remove(self, plugin_id: str, *, purge_data: bool = False) -> None:
        state, record = self._record(plugin_id)
        dependents = self._enabled_required_dependents(plugin_id, state)
        if dependents:
            raise DependencyError(
                f"cannot remove {plugin_id}; required by enabled plugins: " + ", ".join(dependents)
            )
        path = (self.workspace / str(record["path"])).resolve()
        path.relative_to(self.plugins_dir.resolve())
        if path.exists():
            shutil.rmtree(path)
        dependency_path = record.get("dependency_path")
        if isinstance(dependency_path, str):
            dep = (self.workspace / dependency_path).resolve()
            dep.relative_to(self.dependencies_dir.resolve())
            if dep.exists():
                shutil.rmtree(dep)
        if purge_data:
            data = (self.data_dir / plugin_id).resolve()
            data.relative_to(self.data_dir.resolve())
            if data.exists():
                shutil.rmtree(data)
        del state["plugins"][plugin_id]
        for _capability, route in list(state["routes"].items()):
            if not isinstance(route, dict):
                continue
            if route.get("default") == plugin_id:
                route["default"] = None
            route["fallbacks"] = [item for item in route.get("fallbacks", []) if item != plugin_id]
        self._save_state(state)

    def update(
        self,
        plugin_id: str,
        *,
        source: str | os.PathLike[str] | None = None,
        approved: bool = False,
        install_python_dependencies: bool = False,
    ) -> InstallPlan:
        _, record = self._record(plugin_id)
        update_source = source if source is not None else str(record.get("source", ""))
        if not approved:
            raise ApprovalRequired("update installation", plugin_id)
        preview = self.plan_install(update_source)
        if preview.plugins[-1].id != plugin_id:
            raise DependencyError(
                f"update source identifies {preview.plugins[-1].id}, expected {plugin_id}"
            )
        plan = self.install(
            update_source, approved=True, install_python_dependencies=install_python_dependencies
        )
        return plan

    def set_route(self, capability: str, *, default: str, fallbacks: Sequence[str] = ()) -> None:
        if default in fallbacks or len(set(fallbacks)) != len(fallbacks):
            raise RoutingError("default and fallback provider IDs must be unique")
        state = self._load_state()
        for plugin_id in (default, *fallbacks):
            record = state["plugins"].get(plugin_id)
            if not isinstance(record, Mapping):
                raise PluginNotFoundError(f"provider plugin is not installed: {plugin_id}")
            manifest = self._installed_manifest(plugin_id, record)
            if capability not in {item.name for item in manifest.capabilities}:
                raise RoutingError(f"plugin {plugin_id} does not provide {capability}")
        state["routes"][capability] = {"default": default, "fallbacks": list(fallbacks)}
        self._save_state(state)

    def registry(self, *, enabled_only: bool = True) -> PluginRegistry:
        state = self._load_state()
        manifests: list[Manifest] = []
        for plugin_id, record in state["plugins"].items():
            if enabled_only and not record.get("enabled"):
                continue
            try:
                # Integrity is enforced per candidate immediately before execution.
                # Discovery therefore remains available when one unrelated plugin is
                # broken, and the router can still reach a healthy fallback.
                manifests.append(self._installed_manifest(plugin_id, record))
            except ExtensionError:
                continue
        return PluginRegistry(manifests, state["routes"])

    def discover_assets(
        self, extension_type: str | None = None, *, enabled_only: bool = True
    ) -> list[ExtensionAsset]:
        """Discover declarative assets without importing plugin code.

        Codex and Claude compatibility adapters can consume this shared view;
        the plugin system itself remains agent-neutral.
        """
        if extension_type not in {None, "skill", "agent", "workflow"}:
            raise ValueError("asset extension_type must be skill, agent, workflow, or None")
        state = self._load_state()
        discovered: list[ExtensionAsset] = []
        for plugin_id, record in state["plugins"].items():
            if enabled_only and not record.get("enabled"):
                continue
            try:
                manifest = self._installed_manifest(plugin_id, record)
                self._verify_digest(manifest, record)
            except ExtensionError:
                continue
            groups = {
                "skill": manifest.skills,
                "agent": manifest.agents,
                "workflow": manifest.workflows,
            }
            for asset_type, paths in groups.items():
                if extension_type is None or extension_type == asset_type:
                    discovered.extend(
                        ExtensionAsset(plugin_id, asset_type, manifest.root / path)
                        for path in paths
                    )
        return sorted(
            discovered,
            key=lambda item: (item.extension_type, item.plugin_id, item.path.as_posix()),
        )

    def invoke(
        self,
        capability: str,
        payload: Mapping[str, Any],
        *,
        provider: str | None = None,
        capability_version: str = "1.0",
        operation: str = "invoke",
        credentials: Mapping[str, str] | None = None,
    ) -> ExecutionResponse:
        from alem.contracts import ContractRegistry

        contract = ContractRegistry(self.workspace).get(capability, capability_version)
        if contract is not None:
            contract.validate_input(payload)
        state = self._load_state()
        candidates = self.registry(enabled_only=True).resolve(
            capability, provider, capability_version=capability_version
        )
        failures: list[dict[str, str]] = []
        for candidate in candidates:
            record = state["plugins"][candidate.plugin_id]
            try:
                manifest = self._installed_manifest(candidate.plugin_id, record)
                digest = self._verify_digest(manifest, record)
                if record.get("execution_approved_digest") != digest:
                    raise ApprovalRequired("execution", candidate.plugin_id)
                supplied = dict(credentials or {})
                missing = [name for name in manifest.required_credentials if not supplied.get(name)]
                if missing:
                    raise PluginExecutionError(
                        f"plugin {manifest.id} requires credentials: {', '.join(missing)}"
                    )
                allowed_names = set(manifest.required_credentials) | set(
                    manifest.optional_credentials
                )
                credential_payload = {
                    name: supplied[name] for name in allowed_names if supplied.get(name)
                }
                data_path = self.data_dir / manifest.id
                data_path.mkdir(parents=True, exist_ok=True)
                request = ExecutionRequest(
                    capability=capability,
                    capability_version=capability_version,
                    operation=operation,
                    input=dict(payload),
                    context={
                        "plugin_id": manifest.id,
                        "plugin_version": manifest.version,
                        "workspace": str(self.workspace),
                        "plugin_data_dir": str(data_path),
                        "credentials": credential_payload,
                        "declared_permissions": {
                            "network": list(manifest.permissions.network),
                            "filesystem_read": list(manifest.permissions.filesystem_read),
                            "filesystem_write": list(manifest.permissions.filesystem_write),
                            "subprocess": manifest.permissions.subprocess,
                            "native_code": manifest.permissions.native_code,
                        },
                    },
                    api_version=API_VERSION,
                )
                dependency_path = record.get("dependency_path")
                dependency_root = (
                    (self.workspace / dependency_path).resolve()
                    if isinstance(dependency_path, str)
                    else None
                )
                response = self.runtime.invoke(manifest, request, dependency_root=dependency_root)
                if contract is not None:
                    contract.validate_output(response.output)
                metadata = dict(response.metadata)
                metadata["provider"] = manifest.id
                metadata["plugin_version"] = manifest.version
                metadata.pop("provider_failures", None)
                if failures:
                    metadata["provider_failures"] = list(failures)
                return ExecutionResponse(response.output, metadata)
            except (ApprovalRequired, PluginExecutionError, PluginIntegrityError) as exc:
                # Preserve routing evidence without exposing plugin tracebacks,
                # exception text, request data, or credential values.
                failures.append({"provider": candidate.plugin_id, "error_type": type(exc).__name__})
                if provider is not None:
                    raise
        summary = "; ".join(
            f"{failure['provider']}: {failure['error_type']}" for failure in failures
        )
        raise RoutingError(f"all providers failed for {capability!r}: {summary}")
