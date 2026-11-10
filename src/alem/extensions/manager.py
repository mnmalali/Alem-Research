"""Workspace-local plugin lifecycle, approvals, dependency resolution, and routing."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import uuid
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


def plugin_tree_digest(root: str | os.PathLike[str]) -> str:
    """Return the deterministic SHA-256 digest used by release pinning and install state."""
    return _tree_digest(Path(root).resolve())


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
    pip_token = uuid.uuid4().hex
    pip_home = sandbox / f"plugin-pip-home-{plugin_id}-{pip_token}"
    pip_cache = sandbox / f"plugin-pip-cache-{plugin_id}-{pip_token}"
    pip_os_temp = sandbox / f"plugin-pip-temp-{plugin_id}-{pip_token}"
    for directory in (pip_home, pip_cache, pip_os_temp):
        directory.mkdir(parents=True)
    pip_config = sandbox / f"plugin-pip-{plugin_id}-{pip_token}.ini"
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
        release_metadata: Mapping[str, str] | None = None,
        enable_after_install: bool = False,
        immutable_release: bool = False,
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
        if immutable_release:
            return self._install_immutable_release(
                source,
                plan,
                install_python_dependencies=install_python_dependencies,
                release_metadata=release_metadata,
                enable_after_install=enable_after_install,
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
            transaction_id = uuid.uuid4().hex
            staged_plugin = self.plugins_dir / f".stage-{manifest.id}-{transaction_id}"
            staged_dependencies = self.dependencies_dir / f".stage-{manifest.id}-{transaction_id}"
            backup_plugin = self.plugins_dir / f".backup-{manifest.id}-{transaction_id}"
            backup_dependencies = self.dependencies_dir / f".backup-{manifest.id}-{transaction_id}"
            failed_plugin = self.plugins_dir / f".failed-{manifest.id}-{transaction_id}"
            failed_dependencies = self.dependencies_dir / f".failed-{manifest.id}-{transaction_id}"
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
                    sandbox=self.alem_dir,
                    plugin_id=manifest.id,
                )
                dependency_digest = _tree_digest(staged_dependencies)
                dependency_lock = _dependency_lock(staged_dependencies)
                dependency_path = dependency_target.relative_to(self.workspace).as_posix()

            previous_record = copy.deepcopy(state["plugins"].get(manifest.id))
            moved_plugin = False
            moved_dependencies = False
            installed_plugin = False
            installed_dependencies = False
            try:
                if target.exists():
                    os.replace(target, backup_plugin)
                    moved_plugin = True
                if dependency_target.exists():
                    os.replace(dependency_target, backup_dependencies)
                    moved_dependencies = True
                os.replace(staged_plugin, target)
                installed_plugin = True
                if manifest.python_dependencies:
                    os.replace(staged_dependencies, dependency_target)
                    installed_dependencies = True
                plugin_record = {
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
                if moved_plugin and previous_record is not None:
                    previous_record["path"] = backup_plugin.relative_to(self.workspace).as_posix()
                    if moved_dependencies:
                        previous_record["dependency_path"] = (
                            backup_dependencies.relative_to(self.workspace).as_posix()
                        )
                    plugin_record["previous_release"] = previous_record
                if manifest.id == root_plugin.id and release_metadata:
                    plugin_record.update(release_metadata)
                state["plugins"][manifest.id] = plugin_record
                self._save_state(state)
                if enable_after_install:
                    self.enable(manifest.id, approve_execution=True)
            except Exception:
                if installed_plugin and target.exists():
                    os.replace(target, failed_plugin)
                if installed_dependencies and dependency_target.exists():
                    os.replace(dependency_target, failed_dependencies)
                if moved_plugin:
                    os.replace(backup_plugin, target)
                if moved_dependencies:
                    os.replace(backup_dependencies, dependency_target)
                if previous_record is None:
                    state["plugins"].pop(manifest.id, None)
                else:
                    state["plugins"][manifest.id] = previous_record
                self._save_state(state)
                raise
        return plan

    def _install_immutable_release(
        self,
        source: str | os.PathLike[str],
        plan: InstallPlan,
        *,
        install_python_dependencies: bool,
        release_metadata: Mapping[str, str] | None,
        enable_after_install: bool,
    ) -> InstallPlan:
        """Install release trees at content-addressed paths; never replace the working tree."""
        root_plugin = plan.plugins[-1]
        root_source, root_label = self._resolve_source(source)
        sources: dict[str, tuple[Path, str]] = {root_plugin.id: (root_source, root_label)}
        if self.catalogue:
            for manifest in plan.plugins[:-1]:
                entry = self.catalogue.get(manifest.id)
                sources[manifest.id] = (self.catalogue.resolve_source(entry), entry.id)

        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.dependencies_dir.mkdir(parents=True, exist_ok=True)
        state = self._load_state()
        dependency_constraints: dict[str, list[str]] = {}
        for parent in plan.plugins:
            for dependency in parent.plugin_dependencies:
                dependency_constraints.setdefault(dependency.id, []).append(dependency.version)
        for manifest in plan.plugins:
            if manifest.id != root_plugin.id and manifest.id not in state["plugins"]:
                raise DependencyError(
                    f"accepted release dependency {manifest.id} must be reconciled separately"
                )
            if manifest.id != root_plugin.id:
                previous_dependency = state["plugins"][manifest.id]
                try:
                    installed_dependency = self._installed_manifest(
                        manifest.id, previous_dependency
                    )
                    installed_token = self._verify_digest(
                        installed_dependency, previous_dependency
                    )
                except ExtensionError as exc:
                    raise DependencyError(
                        f"accepted dependency {manifest.id} is not intact; reconcile it first"
                    ) from exc
                if (
                    previous_dependency.get("acceptance") != "accepted"
                    or not previous_dependency.get("enabled")
                    or previous_dependency.get("execution_approved_digest") != installed_token
                    or not all(
                        satisfies(installed_dependency.version, constraint)
                        for constraint in dependency_constraints.get(manifest.id, [])
                    )
                ):
                    raise DependencyError(
                        f"accepted dependency {manifest.id} must be reconciled separately"
                    )
                continue
            plugin_source, label = sources[manifest.id]
            source_digest = _tree_digest(plugin_source)
            target_name = f"{manifest.id}--v{manifest.version}--{source_digest[:16]}"
            target = self.plugins_dir / target_name
            if target.exists() and _tree_digest(target) != source_digest:
                target = self.plugins_dir / f"{target_name}--{uuid.uuid4().hex[:8]}"
            if not target.exists():
                _copy_plugin(plugin_source, target)
            installed_manifest = load_manifest(target)
            plugin_digest = _tree_digest(target)
            if (
                installed_manifest.id != manifest.id
                or installed_manifest.version != manifest.version
                or plugin_digest != source_digest
            ):
                raise PluginIntegrityError(
                    f"content-addressed release verification failed for {manifest.id}"
                )

            dependency_path: str | None = None
            dependency_digest: str | None = None
            dependency_lock: list[str] = []
            if manifest.python_dependencies:
                dependency_name = f"{manifest.id}--v{manifest.version}--{source_digest[:16]}"
                dependency_target = self.dependencies_dir / dependency_name
                recorded_dependency = (
                    state["plugins"].get(manifest.id, {}).get("dependency_digest")
                    if isinstance(state["plugins"].get(manifest.id), dict)
                    else None
                )
                if dependency_target.exists():
                    try:
                        existing_dependency_digest = _tree_digest(dependency_target)
                    except ExtensionError:
                        existing_dependency_digest = None
                    if (
                        not recorded_dependency
                        or existing_dependency_digest != recorded_dependency
                    ):
                        dependency_target = self.dependencies_dir / (
                            dependency_name + "--" + uuid.uuid4().hex[:8]
                        )
                if not dependency_target.exists():
                    _install_pinned_dependencies(
                        manifest.python_dependencies,
                        dependency_target,
                        workspace=self.workspace,
                        sandbox=self.alem_dir,
                        plugin_id=manifest.id,
                    )
                dependency_digest = _tree_digest(dependency_target)
                dependency_lock = _dependency_lock(dependency_target)
                dependency_path = dependency_target.relative_to(self.workspace).as_posix()

            previous = copy.deepcopy(state["plugins"].get(manifest.id))
            plugin_record: dict[str, Any] = {
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
                    {"id": item.id, "version": item.version, "optional": item.optional}
                    for item in manifest.plugin_dependencies
                ],
            }
            if previous:
                current_path = target.relative_to(self.workspace).as_posix()
                if previous.get("path") != current_path:
                    plugin_record["previous_release"] = previous
                elif isinstance(previous.get("previous_release"), dict):
                    plugin_record["previous_release"] = previous["previous_release"]
            if manifest.id == root_plugin.id and release_metadata:
                plugin_record.update(release_metadata)
            state["plugins"][manifest.id] = plugin_record
            self._save_state(state)
            if enable_after_install:
                try:
                    self.enable(manifest.id, approve_execution=True)
                except Exception:
                    if previous is None:
                        state["plugins"].pop(manifest.id, None)
                    else:
                        state["plugins"][manifest.id] = previous
                    self._save_state(state)
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

    def rollback(self, plugin_id: str) -> dict[str, Any]:
        """Restore the immediately previous managed release and pin it against reconciliation."""
        state, record = self._record(plugin_id)
        previous = record.get("previous_release")
        if not isinstance(previous, dict):
            raise PluginNotFoundError(f"no managed rollback release is recorded for {plugin_id}")
        current_manifest = self._installed_manifest(plugin_id, record)
        previous_manifest = self._installed_manifest(plugin_id, previous)
        self._verify_digest(current_manifest, record)
        previous_token = self._verify_digest(previous_manifest, previous)
        previous_approval = previous.get("execution_approved_digest")
        if previous_approval and previous_approval != previous_token:
            raise PluginIntegrityError(f"previous release approval is invalid for {plugin_id}")

        active_plugin = (self.workspace / str(record["path"])).resolve()
        previous_plugin = (self.workspace / str(previous["path"])).resolve()
        active_plugin.relative_to(self.plugins_dir.resolve())
        previous_plugin.relative_to(self.plugins_dir.resolve())
        token = uuid.uuid4().hex
        forward_plugin = self.plugins_dir / f".backup-{plugin_id}-rollback-{token}"

        current_dependency_text = record.get("dependency_path")
        previous_dependency_text = previous.get("dependency_path")
        active_dependency = (
            (self.workspace / current_dependency_text).resolve()
            if isinstance(current_dependency_text, str)
            else None
        )
        previous_dependency = (
            (self.workspace / previous_dependency_text).resolve()
            if isinstance(previous_dependency_text, str)
            else None
        )
        if active_dependency is not None:
            active_dependency.relative_to(self.dependencies_dir.resolve())
        if previous_dependency is not None:
            previous_dependency.relative_to(self.dependencies_dir.resolve())
        forward_dependency = self.dependencies_dir / f".backup-{plugin_id}-rollback-{token}"

        moved_current_plugin = False
        moved_previous_plugin = False
        moved_current_dependency = False
        moved_previous_dependency = False
        try:
            os.replace(active_plugin, forward_plugin)
            moved_current_plugin = True
            os.replace(previous_plugin, active_plugin)
            moved_previous_plugin = True
            if active_dependency is not None and active_dependency.exists():
                os.replace(active_dependency, forward_dependency)
                moved_current_dependency = True
            if previous_dependency is not None and previous_dependency.exists():
                os.replace(previous_dependency, self.dependencies_dir / plugin_id)
                moved_previous_dependency = True

            restored = copy.deepcopy(previous)
            restored["path"] = active_plugin.relative_to(self.workspace).as_posix()
            restored["dependency_path"] = (
                (self.dependencies_dir / plugin_id).relative_to(self.workspace).as_posix()
                if moved_previous_dependency
                else None
            )
            prior_forward = copy.deepcopy(record)
            prior_forward.pop("previous_release", None)
            prior_forward.pop("pinned_release", None)
            prior_forward["path"] = forward_plugin.relative_to(self.workspace).as_posix()
            if moved_current_dependency:
                prior_forward["dependency_path"] = forward_dependency.relative_to(
                    self.workspace
                ).as_posix()
            restored["previous_release"] = prior_forward
            restored["pinned_release"] = {
                "version": restored.get("version"),
                "digest": restored.get("digest"),
                "release_digest": restored.get("release_digest"),
            }
            state["plugins"][plugin_id] = restored
            self._save_state(state)
            return {
                "plugin_id": plugin_id,
                "version": restored.get("version"),
                "digest": restored.get("release_digest", restored.get("digest")),
                "pinned": True,
            }
        except Exception:
            if moved_previous_dependency:
                os.replace(self.dependencies_dir / plugin_id, previous_dependency)
            if moved_current_dependency:
                os.replace(forward_dependency, active_dependency)
            if moved_previous_plugin:
                os.replace(active_plugin, previous_plugin)
            if moved_current_plugin:
                os.replace(forward_plugin, active_plugin)
            raise

    def unpin(self, plugin_id: str) -> None:
        state, record = self._record(plugin_id)
        if not record.pop("pinned_release", None):
            raise PluginNotFoundError(f"no release pin is recorded for {plugin_id}")
        self._save_state(state)

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
        readiness_by_plugin: dict[str, dict[str, Any]] = {}
        try:
            from alem.tool_status import list_tool_statuses
            from alem.workspace import Workspace

            readiness_by_plugin = {
                item["plugin_id"]: item
                for item in list_tool_statuses(
                    Workspace(self.workspace), check_services=False
                )
                if item.get("plugin_id")
            }
        except Exception:
            # Manually managed development workspaces may not have a release registry.
            readiness_by_plugin = {}
        try:
            candidates = self.registry(enabled_only=True).resolve(
                capability, provider, capability_version=capability_version
            )
        except RoutingError as exc:
            blocked = [
                item
                for item in readiness_by_plugin.values()
                if capability in item.get("capabilities", [])
            ]
            detail = "; ".join(
                f"{item['plugin_id']}: {item['readiness']}"
                + (f" ({'; '.join(item['blockers'])})" if item["blockers"] else "")
                for item in blocked
            )
            if detail:
                raise RoutingError(
                    f"no ready provider for {capability!r}; accepted providers: {detail}. "
                    "Run `alem tools status` for diagnostics."
                ) from exc
            raise
        supplied = dict(credentials or {})
        ready_candidates = []
        failures: list[dict[str, Any]] = []
        for candidate in candidates:
            record = state["plugins"][candidate.plugin_id]
            tool = readiness_by_plugin.get(candidate.plugin_id)
            if tool and tool.get("readiness") in {
                "unsupported-platform",
                "missing-hardware",
                "missing-runtime",
                "error",
            }:
                failures.append(
                    {
                        "provider": candidate.plugin_id,
                        "reason": tool["readiness"],
                    }
                )
                continue
            try:
                manifest = self._installed_manifest(candidate.plugin_id, record)
                digest = self._verify_digest(manifest, record)
                if record.get("execution_approved_digest") != digest:
                    failures.append(
                        {
                            "provider": candidate.plugin_id,
                            "reason": "execution_approval_missing",
                        }
                    )
                    continue
                missing = [
                    name for name in manifest.required_credentials if not supplied.get(name)
                ]
                if missing:
                    failures.append(
                        {
                            "provider": candidate.plugin_id,
                            "reason": "needs_configuration",
                            "configuration": missing,
                        }
                    )
                    continue
                ready_candidates.append(candidate)
            except (ExtensionError, OSError, ValueError) as exc:
                failures.append(
                    {
                        "provider": candidate.plugin_id,
                        "reason": type(exc).__name__,
                    }
                )
        if provider is not None and not ready_candidates:
            summary = "; ".join(
                f"{item['provider']}: {item['reason']}"
                + (
                    " (" + ", ".join(item["configuration"]) + ")"
                    if item.get("configuration")
                    else ""
                )
                for item in failures
            )
            raise RoutingError(
                f"provider {provider!r} is blocked for {capability!r}: {summary}; "
                "run `alem tools status` or `alem tools configure <id>`"
            )
        if not ready_candidates:
            summary = "; ".join(
                f"{item['provider']}: {item['reason']}"
                + (
                    " (" + ", ".join(item["configuration"]) + ")"
                    if item.get("configuration")
                    else ""
                )
                for item in failures
            )
            raise RoutingError(
                f"no ready provider for {capability!r}; blocked: {summary}. "
                "Run `alem tools status` or `alem tools configure <id>`."
            )
        candidates = ready_candidates
        for candidate in candidates:
            record = state["plugins"][candidate.plugin_id]
            try:
                manifest = self._installed_manifest(candidate.plugin_id, record)
                digest = self._verify_digest(manifest, record)
                if record.get("execution_approved_digest") != digest:
                    raise ApprovalRequired("execution", candidate.plugin_id)
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
                failures.append(
                    {
                        "provider": candidate.plugin_id,
                        "reason": "provider_execution_failed",
                        "error_type": type(exc).__name__,
                    }
                )
                if provider is not None:
                    raise
        summary = "; ".join(
            f"{failure['provider']}: {failure.get('reason', failure.get('error_type', 'blocked'))}"
            for failure in failures
        )
        raise RoutingError(f"all providers failed for {capability!r}: {summary}")
