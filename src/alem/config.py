"""Typed access to the small, stable part of ``alem.toml``."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alem.errors import ConfigurationError
from alem.workspace import Workspace


@dataclass(frozen=True, slots=True)
class CapabilityRoute:
    default: str | None
    fallbacks: tuple[str, ...]

    @property
    def providers(self) -> tuple[str, ...]:
        return ((self.default,) if self.default else ()) + self.fallbacks


@dataclass(frozen=True, slots=True)
class AlemConfig:
    workspace: Workspace
    raw: dict[str, Any]
    workspace_version: int
    plugin_api_version: str
    capability_routes: dict[str, CapabilityRoute]

    def route_for(self, capability: str) -> CapabilityRoute:
        return self.capability_routes.get(capability, CapabilityRoute(None, ()))


def load_config(workspace: Workspace | str | Path | None = None) -> AlemConfig:
    ws = workspace if isinstance(workspace, Workspace) else Workspace.discover(workspace)
    path = ws.path("alem.toml")
    try:
        with path.open("rb") as stream:
            raw = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"Cannot read {path}: {exc}") from exc

    alem = raw.get("alem")
    plugins = raw.get("plugins")
    if not isinstance(alem, dict) or not isinstance(plugins, dict):
        raise ConfigurationError("alem.toml must contain [alem] and [plugins] tables")
    version = alem.get("workspace_version")
    api_version = plugins.get("api_version")
    if version != 1:
        raise ConfigurationError(f"Unsupported workspace_version: {version!r}; expected 1")
    if not isinstance(api_version, str) or not api_version:
        raise ConfigurationError("plugins.api_version must be a non-empty string")

    routes: dict[str, CapabilityRoute] = {}
    capabilities = raw.get("capabilities", {})
    if not isinstance(capabilities, dict):
        raise ConfigurationError("[capabilities] must be a table")
    for name, value in capabilities.items():
        if not isinstance(value, dict):
            raise ConfigurationError(f"capabilities.{name} must be a table")
        default = value.get("default")
        fallbacks = value.get("fallbacks", [])
        if default is not None and not isinstance(default, str):
            raise ConfigurationError(f"capabilities.{name}.default must be a string")
        if not isinstance(fallbacks, list) or not all(isinstance(item, str) for item in fallbacks):
            raise ConfigurationError(f"capabilities.{name}.fallbacks must be an array of strings")
        ordered_fallbacks = tuple(item for item in fallbacks if item != default)
        routes[name] = CapabilityRoute(default, ordered_fallbacks)

    return AlemConfig(ws, raw, version, api_version, routes)
