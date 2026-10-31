"""Strict parser and validator for ``plugin.toml`` schema version 1."""

from __future__ import annotations

import os
import platform
import re
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .api import API_VERSION, ExtensionType
from .errors import CompatibilityError, ManifestError
from .versions import Version, satisfies

MANIFEST_FILENAME = "plugin.toml"
MANIFEST_SCHEMA_VERSION = 1
_PLUGIN_ID = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)+$")
_CAPABILITY = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
_ENTRYPOINT = re.compile(r"^[A-Za-z0-9_./-]+\.py:[A-Za-z_][A-Za-z0-9_]*$")
_CREDENTIAL = re.compile(r"^[A-Z][A-Z0-9_]*$")
_PYTHON_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*"
    r"(?:\[[A-Za-z0-9._-]+(?:,[A-Za-z0-9._-]+)*\])?"
    r"==[0-9][A-Za-z0-9]*(?:[._+-][A-Za-z0-9]+)+$"
)
_TOP_KEYS = {
    "schema_version",
    "plugin",
    "capabilities",
    "compatibility",
    "dependencies",
    "permissions",
    "credentials",
    "documentation",
    "assets",
}
_PLUGIN_KEYS = {
    "id",
    "name",
    "version",
    "api",
    "description",
    "author",
    "repository",
    "license",
    "types",
    "entrypoint",
}
_CAPABILITY_KEYS = {"name", "version", "extension_type", "priority", "description"}
_COMPAT_KEYS = {"python", "operating_systems", "coding_agents"}
_DEPENDENCY_KEYS = {"plugins", "python"}
_PLUGIN_DEP_KEYS = {"id", "version", "optional"}
_PERMISSION_KEYS = {"network", "filesystem_read", "filesystem_write", "subprocess", "native_code"}
_CREDENTIAL_KEYS = {"required", "optional"}
_DOCUMENTATION_KEYS = {"installation", "usage"}
_ASSET_KEYS = {"skills", "agents", "workflows"}
_EXTENSION_TYPES: set[str] = {"tool", "skill", "agent", "workflow"}


@dataclass(frozen=True, slots=True)
class Capability:
    name: str
    version: str
    extension_type: ExtensionType
    priority: int
    description: str


@dataclass(frozen=True, slots=True)
class PluginDependency:
    id: str
    version: str
    optional: bool = False


@dataclass(frozen=True, slots=True)
class Permissions:
    network: tuple[str, ...]
    filesystem_read: tuple[str, ...]
    filesystem_write: tuple[str, ...]
    subprocess: bool
    native_code: bool


@dataclass(frozen=True, slots=True)
class Manifest:
    path: Path
    id: str
    name: str
    version: str
    api: str
    description: str
    author: str
    repository: str
    license: str
    types: tuple[ExtensionType, ...]
    entrypoint: str | None
    capabilities: tuple[Capability, ...]
    python: str
    operating_systems: tuple[str, ...]
    coding_agents: tuple[str, ...]
    plugin_dependencies: tuple[PluginDependency, ...]
    python_dependencies: tuple[str, ...]
    permissions: Permissions
    required_credentials: tuple[str, ...]
    optional_credentials: tuple[str, ...]
    installation_instructions: str
    usage_instructions: str
    skills: tuple[str, ...]
    agents: tuple[str, ...]
    workflows: tuple[str, ...]

    @property
    def root(self) -> Path:
        return self.path.parent

    def check_runtime_compatibility(self) -> None:
        if not satisfies(API_VERSION, self.api, api=True):
            raise CompatibilityError(
                f"{self.id} requires Alem extension API {self.api}; runtime is {API_VERSION}"
            )
        current = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if not satisfies(current, self.python):
            raise CompatibilityError(
                f"{self.id} requires Python {self.python}; runtime is {current}"
            )
        os_name = {"darwin": "macos", "windows": "windows", "linux": "linux"}.get(
            platform.system().lower(), platform.system().lower()
        )
        if os_name not in self.operating_systems:
            raise CompatibilityError(f"{self.id} does not support operating system {os_name!r}")


def _table(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise ManifestError(f"[{key}] table is required")
    return value


def _unknown(mapping: Mapping[str, Any], allowed: set[str], label: str) -> None:
    extra = sorted(set(mapping) - allowed)
    if extra:
        raise ManifestError(f"unknown keys in {label}: {', '.join(extra)}")


def _string(mapping: Mapping[str, Any], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{label}.{key} must be a non-empty string")
    return value.strip()


def _strings(
    mapping: Mapping[str, Any], key: str, label: str, *, required: bool = True
) -> tuple[str, ...]:
    value = mapping.get(key)
    if value is None and not required:
        return ()
    if (
        not isinstance(value, list)
        or (required and not value)
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise ManifestError(
            f"{label}.{key} must be a {'non-empty ' if required else ''}string array"
        )
    values = tuple(item.strip() for item in value)
    if len(set(values)) != len(values):
        raise ManifestError(f"{label}.{key} contains duplicate values")
    return values


def _safe_relative(root: Path, text: str, label: str, *, must_exist: bool = True) -> str:
    candidate = Path(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ManifestError(f"{label} must be a path inside the plugin directory")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ManifestError(f"{label} escapes the plugin directory") from exc
    if must_exist and not resolved.exists():
        raise ManifestError(f"{label} does not exist: {text}")
    return candidate.as_posix()


def load_manifest(path: str | os.PathLike[str], *, check_compatibility: bool = True) -> Manifest:
    candidate = Path(path)
    manifest_path = candidate / MANIFEST_FILENAME if candidate.is_dir() else candidate
    if not manifest_path.is_file():
        raise ManifestError(f"plugin manifest not found: {manifest_path}")
    try:
        with manifest_path.open("rb") as stream:
            data = tomllib.load(stream)
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"invalid TOML in {manifest_path}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise ManifestError("manifest root must be a TOML table")
    _unknown(data, _TOP_KEYS, "manifest root")
    if data.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ManifestError(f"schema_version must be {MANIFEST_SCHEMA_VERSION}")

    plugin = _table(data, "plugin")
    _unknown(plugin, _PLUGIN_KEYS, "[plugin]")
    plugin_id = _string(plugin, "id", "plugin")
    if not _PLUGIN_ID.fullmatch(plugin_id):
        raise ManifestError("plugin.id must be a lowercase, namespaced identifier")
    version = _string(plugin, "version", "plugin")
    Version.parse(version)
    api = _string(plugin, "api", "plugin")
    satisfies(API_VERSION, api, api=True)  # validate syntax; compatibility checked below
    raw_types = _strings(plugin, "types", "plugin")
    if not set(raw_types) <= _EXTENSION_TYPES:
        raise ManifestError(f"plugin.types may only contain {sorted(_EXTENSION_TYPES)}")
    types = tuple(raw_types)  # type: ignore[assignment]
    entrypoint_raw = plugin.get("entrypoint")
    entrypoint: str | None = None
    if entrypoint_raw is not None:
        if not isinstance(entrypoint_raw, str) or not _ENTRYPOINT.fullmatch(entrypoint_raw):
            raise ManifestError("plugin.entrypoint must use relative-file.py:attribute syntax")
        file_part, attribute = entrypoint_raw.split(":", 1)
        safe_file = _safe_relative(manifest_path.parent, file_part, "plugin.entrypoint")
        entrypoint = f"{safe_file}:{attribute}"

    raw_capabilities = data.get("capabilities")
    if not isinstance(raw_capabilities, list):
        raise ManifestError(
            "[[capabilities]] entries are required (an empty array is allowed for data-only skills)"
        )
    capabilities: list[Capability] = []
    for index, raw in enumerate(raw_capabilities):
        if not isinstance(raw, Mapping):
            raise ManifestError(f"capabilities[{index}] must be a table")
        _unknown(raw, _CAPABILITY_KEYS, f"capabilities[{index}]")
        name = _string(raw, "name", f"capabilities[{index}]")
        if not _CAPABILITY.fullmatch(name):
            raise ManifestError(f"invalid capability name: {name!r}")
        capability_version = _string(raw, "version", f"capabilities[{index}]")
        Version.parse(capability_version, api=True)
        extension_type = _string(raw, "extension_type", f"capabilities[{index}]")
        if extension_type not in types:
            raise ManifestError(
                f"capability {name!r} uses undeclared extension type {extension_type!r}"
            )
        priority = raw.get("priority", 100)
        if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= 1000:
            raise ManifestError(f"capability {name!r} priority must be an integer from 0 to 1000")
        capabilities.append(
            Capability(
                name, capability_version, extension_type, priority, str(raw.get("description", ""))
            )
        )  # type: ignore[arg-type]
    if capabilities and entrypoint is None:
        raise ManifestError(
            "plugins that provide executable capabilities require plugin.entrypoint"
        )
    if len({item.name for item in capabilities}) != len(capabilities):
        raise ManifestError("capability names must be unique within a plugin")

    compatibility = _table(data, "compatibility")
    _unknown(compatibility, _COMPAT_KEYS, "[compatibility]")
    python_constraint = _string(compatibility, "python", "compatibility")
    satisfies(
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        python_constraint,
    )
    operating_systems = _strings(compatibility, "operating_systems", "compatibility")
    allowed_os = {"windows", "linux", "macos"}
    if not set(operating_systems) <= allowed_os:
        raise ManifestError(
            f"compatibility.operating_systems may only contain {sorted(allowed_os)}"
        )
    coding_agents = _strings(compatibility, "coding_agents", "compatibility")
    if not set(coding_agents) <= {"codex", "claude-code", "none"}:
        raise ManifestError("compatibility.coding_agents contains an unsupported agent identifier")

    dependencies = _table(data, "dependencies")
    _unknown(dependencies, _DEPENDENCY_KEYS, "[dependencies]")
    raw_plugin_dependencies = dependencies.get("plugins", [])
    if not isinstance(raw_plugin_dependencies, list):
        raise ManifestError("dependencies.plugins must be an array of inline tables")
    plugin_dependencies: list[PluginDependency] = []
    for index, raw in enumerate(raw_plugin_dependencies):
        if not isinstance(raw, Mapping):
            raise ManifestError(f"dependencies.plugins[{index}] must be a table")
        _unknown(raw, _PLUGIN_DEP_KEYS, f"dependencies.plugins[{index}]")
        dep_id = _string(raw, "id", f"dependencies.plugins[{index}]")
        if not _PLUGIN_ID.fullmatch(dep_id) or dep_id == plugin_id:
            raise ManifestError(f"invalid plugin dependency id: {dep_id!r}")
        constraint = _string(raw, "version", f"dependencies.plugins[{index}]")
        satisfies("0.0.0", constraint)  # syntax only
        optional = raw.get("optional", False)
        if not isinstance(optional, bool):
            raise ManifestError(f"dependencies.plugins[{index}].optional must be boolean")
        plugin_dependencies.append(PluginDependency(dep_id, constraint, optional))
    if len({item.id for item in plugin_dependencies}) != len(plugin_dependencies):
        raise ManifestError("plugin dependencies must be unique")
    python_dependencies = _strings(dependencies, "python", "dependencies", required=False)
    for requirement in python_dependencies:
        if not _PYTHON_REQUIREMENT.fullmatch(requirement):
            raise ManifestError(
                "dependencies.python entries must be exact index requirements such as "
                "'package[extra]==1.2.3'; options, URLs, paths, and ranges are forbidden"
            )

    permissions = _table(data, "permissions")
    _unknown(permissions, _PERMISSION_KEYS, "[permissions]")
    network = _strings(permissions, "network", "permissions", required=False)
    for host in network:
        if "://" in host or "/" in host or not re.fullmatch(r"[A-Za-z0-9.*-]+", host):
            raise ManifestError(
                f"permissions.network must contain host patterns, not URLs: {host!r}"
            )
    filesystem_read = _strings(permissions, "filesystem_read", "permissions", required=False)
    filesystem_write = _strings(permissions, "filesystem_write", "permissions", required=False)
    subprocess_permission = permissions.get("subprocess", False)
    native_code = permissions.get("native_code", False)
    if not isinstance(subprocess_permission, bool) or not isinstance(native_code, bool):
        raise ManifestError("permissions.subprocess and native_code must be boolean")

    credentials = _table(data, "credentials")
    _unknown(credentials, _CREDENTIAL_KEYS, "[credentials]")
    required_credentials = _strings(credentials, "required", "credentials", required=False)
    optional_credentials = _strings(credentials, "optional", "credentials", required=False)
    for credential in (*required_credentials, *optional_credentials):
        if not _CREDENTIAL.fullmatch(credential):
            raise ManifestError(
                f"credential names must be uppercase environment-style identifiers: {credential!r}"
            )
    if set(required_credentials) & set(optional_credentials):
        raise ManifestError("a credential cannot be both required and optional")

    documentation = _table(data, "documentation")
    _unknown(documentation, _DOCUMENTATION_KEYS, "[documentation]")
    installation = _string(documentation, "installation", "documentation")
    usage = _string(documentation, "usage", "documentation")

    assets = _table(data, "assets")
    _unknown(assets, _ASSET_KEYS, "[assets]")
    skills = tuple(
        _safe_relative(manifest_path.parent, item, "assets.skills")
        for item in _strings(assets, "skills", "assets", required=False)
    )
    agents = tuple(
        _safe_relative(manifest_path.parent, item, "assets.agents")
        for item in _strings(assets, "agents", "assets", required=False)
    )
    workflows = tuple(
        _safe_relative(manifest_path.parent, item, "assets.workflows")
        for item in _strings(assets, "workflows", "assets", required=False)
    )
    for extension_type, declared_assets in (
        ("skill", skills),
        ("agent", agents),
        ("workflow", workflows),
    ):
        if declared_assets and extension_type not in types:
            raise ManifestError(
                f"assets.{extension_type}s requires {extension_type!r} in plugin.types"
            )

    manifest = Manifest(
        path=manifest_path.resolve(),
        id=plugin_id,
        name=_string(plugin, "name", "plugin"),
        version=version,
        api=api,
        description=_string(plugin, "description", "plugin"),
        author=_string(plugin, "author", "plugin"),
        repository=_string(plugin, "repository", "plugin"),
        license=_string(plugin, "license", "plugin"),
        types=types,
        entrypoint=entrypoint,
        capabilities=tuple(capabilities),
        python=python_constraint,
        operating_systems=operating_systems,
        coding_agents=coding_agents,
        plugin_dependencies=tuple(plugin_dependencies),
        python_dependencies=python_dependencies,
        permissions=Permissions(
            network, filesystem_read, filesystem_write, subprocess_permission, native_code
        ),
        required_credentials=required_credentials,
        optional_credentials=optional_credentials,
        installation_instructions=installation,
        usage_instructions=usage,
        skills=skills,
        agents=agents,
        workflows=workflows,
    )
    if check_compatibility:
        manifest.check_runtime_compatibility()
    return manifest


def validate_manifest(
    path: str | os.PathLike[str], *, check_compatibility: bool = True
) -> list[str]:
    """Validate a plugin and return non-fatal warnings.

    Validation errors are raised as :class:`ManifestError` or
    :class:`CompatibilityError`; a successful return is safe for discovery but
    is not a security verdict.
    """
    manifest = load_manifest(path, check_compatibility=check_compatibility)
    warnings: list[str] = []
    if manifest.permissions.native_code:
        warnings.append("plugin requests native-code execution")
    if manifest.permissions.subprocess:
        warnings.append("plugin requests subprocess execution")
    if "*" in manifest.permissions.network:
        warnings.append("plugin requests unrestricted network access")
    if manifest.python_dependencies:
        warnings.append("plugin declares third-party Python dependencies")
    return warnings
