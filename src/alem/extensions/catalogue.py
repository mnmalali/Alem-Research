"""Repository-backed plugin catalogue reader."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .errors import ManifestError, PluginNotFoundError
from .manifest import load_manifest


@dataclass(frozen=True, slots=True)
class CatalogueEntry:
    id: str
    version: str
    channel: str
    verification: str
    source: str
    summary: str
    author: str
    repository: str
    license: str
    extension_types: tuple[str, ...]
    capabilities: tuple[str, ...]


class PluginCatalogue:
    """A checked-in TOML index; no network service is required."""

    def __init__(self, index: str | Path) -> None:
        self.index = Path(index).resolve()
        self._entries = self._load()

    def _load(self) -> dict[str, CatalogueEntry]:
        if not self.index.is_file():
            raise PluginNotFoundError(f"catalogue index not found: {self.index}")
        try:
            with self.index.open("rb") as stream:
                raw = tomllib.load(stream)
        except tomllib.TOMLDecodeError as exc:
            raise ManifestError(f"invalid catalogue TOML: {exc}") from exc
        if set(raw) != {"schema_version", "plugins"} or raw.get("schema_version") != 1:
            raise ManifestError("catalogue must contain schema_version = 1 and [[plugins]]")
        plugins = raw.get("plugins")
        if not isinstance(plugins, list):
            raise ManifestError("catalogue.plugins must be an array of tables")
        result: dict[str, CatalogueEntry] = {}
        expected = {
            "id",
            "version",
            "channel",
            "verification",
            "source",
            "summary",
            "author",
            "repository",
            "license",
            "extension_types",
            "capabilities",
        }
        for index, value in enumerate(plugins):
            if not isinstance(value, Mapping) or set(value) != expected:
                raise ManifestError(
                    f"catalogue plugin {index} must contain exactly {sorted(expected)}"
                )
            for key in expected - {"extension_types", "capabilities"}:
                if not isinstance(value[key], str) or not value[key].strip():
                    raise ManifestError(
                        f"catalogue plugin {index}.{key} must be a non-empty string"
                    )
            if value["channel"] not in {"official", "community"}:
                raise ManifestError("catalogue channel must be official or community")
            verification = value["verification"]
            allowed_verification = (
                {"official"} if value["channel"] == "official" else {"verified", "unverified"}
            )
            if verification not in allowed_verification:
                raise ManifestError(
                    f"catalogue plugin {index}.verification must be one of "
                    f"{sorted(allowed_verification)}"
                )
            for key in ("extension_types", "capabilities"):
                if not isinstance(value[key], list) or not all(
                    isinstance(item, str) for item in value[key]
                ):
                    raise ManifestError(f"catalogue plugin {index}.{key} must be a string array")
            entry = CatalogueEntry(
                id=value["id"],
                version=value["version"],
                channel=value["channel"],
                verification=verification,
                source=value["source"],
                summary=value["summary"],
                author=value["author"],
                repository=value["repository"],
                license=value["license"],
                extension_types=tuple(value["extension_types"]),
                capabilities=tuple(value["capabilities"]),
            )
            if entry.id in result:
                raise ManifestError(f"duplicate catalogue plugin id: {entry.id}")
            source_path = self.resolve_source(entry)
            manifest = load_manifest(source_path, check_compatibility=False)
            if manifest.id != entry.id or manifest.version != entry.version:
                raise ManifestError(f"catalogue entry {entry.id} does not match its manifest")
            if tuple(manifest.types) != entry.extension_types:
                raise ManifestError(
                    f"catalogue entry {entry.id} extension_types do not match its manifest"
                )
            if tuple(item.name for item in manifest.capabilities) != entry.capabilities:
                raise ManifestError(
                    f"catalogue entry {entry.id} capabilities do not match its manifest"
                )
            result[entry.id] = entry
        return result

    def resolve_source(self, entry: CatalogueEntry | str) -> Path:
        item = self._entries[entry] if isinstance(entry, str) else entry
        # v1 catalogues intentionally support checked-in relative sources only.
        source = Path(item.source)
        if source.is_absolute():
            raise ManifestError(
                f"catalogue source must be a repository-relative path: {item.source}"
            )
        resolved = (self.index.parent / source).resolve()
        repository_root = self.index.parent.parent.resolve()
        try:
            resolved.relative_to(repository_root)
        except ValueError as exc:
            raise ManifestError(f"catalogue source escapes its repository: {item.source}") from exc
        return resolved

    def get(self, plugin_id: str) -> CatalogueEntry:
        try:
            return self._entries[plugin_id]
        except KeyError as exc:
            raise PluginNotFoundError(f"plugin not found in catalogue: {plugin_id}") from exc

    def search(self, query: str = "") -> list[CatalogueEntry]:
        terms = [term for term in re.split(r"\s+", query.lower().strip()) if term]
        values = []
        for entry in self._entries.values():
            haystack = " ".join(
                (entry.id, entry.summary, entry.author, *entry.extension_types, *entry.capabilities)
            ).lower()
            if all(term in haystack for term in terms):
                values.append(entry)
        return sorted(values, key=lambda item: (item.channel != "official", item.id))
