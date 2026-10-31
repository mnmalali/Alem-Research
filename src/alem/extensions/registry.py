"""Capability discovery and provider routing."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from .errors import PluginNotFoundError, RoutingError
from .manifest import Manifest


@dataclass(frozen=True, slots=True)
class Provider:
    plugin_id: str
    plugin_version: str
    capability: str
    capability_version: str
    extension_type: str
    priority: int


class PluginRegistry:
    """Immutable discovery view over installed, enabled manifests."""

    def __init__(
        self,
        manifests: Iterable[Manifest],
        routes: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        providers: dict[str, list[Provider]] = {}
        for manifest in manifests:
            for capability in manifest.capabilities:
                providers.setdefault(capability.name, []).append(
                    Provider(
                        manifest.id,
                        manifest.version,
                        capability.name,
                        capability.version,
                        capability.extension_type,
                        capability.priority,
                    )
                )
        for values in providers.values():
            values.sort(key=lambda item: (-item.priority, item.plugin_id))
        self._providers = providers
        self._routes = dict(routes or {})

    def capabilities(self) -> list[str]:
        return sorted(self._providers)

    def providers(self, capability: str, capability_version: str | None = None) -> list[Provider]:
        providers = list(self._providers.get(capability, ()))
        if capability_version is not None:
            providers = [
                item for item in providers if item.capability_version == capability_version
            ]
        return providers

    def resolve(
        self,
        capability: str,
        provider: str | None = None,
        *,
        capability_version: str = "1.0",
    ) -> list[Provider]:
        available = self.providers(capability, capability_version)
        if not available:
            raise RoutingError(
                f"no enabled plugin provides capability {capability!r} version "
                f"{capability_version!r}"
            )
        by_id = {item.plugin_id: item for item in available}
        if provider is not None:
            try:
                return [by_id[provider]]
            except KeyError as exc:
                raise PluginNotFoundError(
                    f"enabled plugin {provider!r} does not provide capability "
                    f"{capability!r} version {capability_version!r}"
                ) from exc
        route = self._routes.get(capability, {})
        order: list[str] = []
        default = route.get("default") if isinstance(route, Mapping) else None
        fallbacks = route.get("fallbacks", []) if isinstance(route, Mapping) else []
        if isinstance(default, str):
            order.append(default)
        if isinstance(fallbacks, Sequence) and not isinstance(fallbacks, str | bytes):
            order.extend(item for item in fallbacks if isinstance(item, str))
        order.extend(item.plugin_id for item in available)
        seen: set[str] = set()
        resolved: list[Provider] = []
        for plugin_id in order:
            if plugin_id in by_id and plugin_id not in seen:
                seen.add(plugin_id)
                resolved.append(by_id[plugin_id])
        return resolved
