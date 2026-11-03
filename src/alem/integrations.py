"""Canonical integration maturity, trust, and implementation registry."""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass
from typing import Any

from alem.config import load_config
from alem.errors import AlemError
from alem.extensions import PluginCatalogue
from alem.workspace import Workspace

INTEGRATION_SCHEMA_VERSION = 2
KINDS = {"provider", "bridge", "assets", "catalog", "pattern"}
STATUSES = {
    "discovered",
    "assessed",
    "adapted",
    "contract-tested",
    "workflow-proven",
    "blocked",
    "deprecated",
}
TRUST = {"official", "verified", "unverified", "not-executable"}


@dataclass(frozen=True, slots=True)
class IntegrationRecord:
    id: str
    name: str
    kind: str
    status: str
    trust: str
    capabilities: tuple[str, ...]
    cost: str
    authentication: str
    privacy: str
    notes: str
    plugin_id: str | None = None
    upstream_id: str | None = None

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


def _optional_string(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AlemError(f"integration {key} must be a non-empty string when present")
    return value.strip()


def load_integrations(workspace: Workspace) -> list[IntegrationRecord]:
    path = workspace.path("integrations/registry.toml")
    try:
        with path.open("rb") as stream:
            raw = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise AlemError(f"cannot read integration registry: {exc}") from exc
    if raw.get("schema_version") == 1:
        legacy = raw.get("integrations", [])
        if not isinstance(legacy, list):
            raise AlemError("legacy integration registry must define [[integrations]]")
        migrated: list[IntegrationRecord] = []
        for item in legacy:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise AlemError("invalid legacy integration record")
            capability = item.get("capability")
            status = item.get("status")
            bundled = status == "bundled-plugin"
            migrated.append(
                IntegrationRecord(
                    id=item["id"],
                    name=item["id"].replace("-", " ").title(),
                    kind="provider",
                    status="contract-tested" if bundled else "discovered",
                    trust="official" if bundled else "unverified",
                    capabilities=(capability,) if isinstance(capability, str) else (),
                    cost=str(item.get("cost", "unknown")),
                    authentication=str(item.get("authentication", "unknown")),
                    privacy=str(item.get("privacy", "not recorded")),
                    notes=str(item.get("notes", "Migrated from integration registry schema 1.")),
                )
            )
        return migrated
    if raw.get("schema_version") != INTEGRATION_SCHEMA_VERSION:
        raise AlemError(
            f"integration registry must use schema_version = {INTEGRATION_SCHEMA_VERSION}"
        )
    values = raw.get("integrations")
    if not isinstance(values, list):
        raise AlemError("integration registry must define [[integrations]]")
    records: list[IntegrationRecord] = []
    seen: set[str] = set()
    required_strings = {
        "id",
        "name",
        "kind",
        "status",
        "trust",
        "cost",
        "authentication",
        "privacy",
        "notes",
    }
    allowed = required_strings | {"capabilities", "plugin_id", "upstream_id"}
    for index, item in enumerate(values):
        if not isinstance(item, dict):
            raise AlemError(f"integration {index} must be a table")
        unknown = sorted(set(item) - allowed)
        if unknown:
            raise AlemError(f"integration {index} has unknown fields: {', '.join(unknown)}")
        for key in required_strings:
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise AlemError(f"integration {index}.{key} must be a non-empty string")
        integration_id = item["id"].strip()
        if integration_id in seen:
            raise AlemError(f"duplicate integration id: {integration_id}")
        seen.add(integration_id)
        if item["kind"] not in KINDS:
            raise AlemError(f"invalid integration kind for {integration_id}: {item['kind']}")
        if item["status"] not in STATUSES:
            raise AlemError(f"invalid integration status for {integration_id}: {item['status']}")
        if item["trust"] not in TRUST:
            raise AlemError(f"invalid integration trust for {integration_id}: {item['trust']}")
        capabilities = item.get("capabilities", [])
        if not isinstance(capabilities, list) or not all(
            isinstance(value, str) and value.strip() for value in capabilities
        ):
            raise AlemError(f"integration {integration_id}.capabilities must be a string array")
        records.append(
            IntegrationRecord(
                id=integration_id,
                name=item["name"].strip(),
                kind=item["kind"],
                status=item["status"],
                trust=item["trust"],
                capabilities=tuple(value.strip() for value in capabilities),
                cost=item["cost"].strip(),
                authentication=item["authentication"].strip(),
                privacy=item["privacy"].strip(),
                notes=item["notes"].strip(),
                plugin_id=_optional_string(item, "plugin_id"),
                upstream_id=_optional_string(item, "upstream_id"),
            )
        )
    return records


def validate_integrations(workspace: Workspace) -> dict[str, Any]:
    from alem.contracts import ContractRegistry
    from alem.extensions.manifest import load_manifest

    records = load_integrations(workspace)
    config = load_config(workspace)
    catalogues = config.raw.get("plugins", {}).get("catalogues", [])
    catalogue = None
    if isinstance(catalogues, list) and catalogues and isinstance(catalogues[0], str):
        path = workspace.path(catalogues[0])
        if path.is_file():
            catalogue = PluginCatalogue(path)
    errors: list[str] = []
    contracts = ContractRegistry(workspace)
    for record in records:
        if record.status in {"adapted", "contract-tested", "workflow-proven"}:
            if record.plugin_id is None and record.kind != "pattern":
                errors.append(f"{record.id}: implemented status requires plugin_id")
                continue
            if record.plugin_id and catalogue:
                try:
                    entry = catalogue.get(record.plugin_id)
                except Exception as exc:  # surfaced as a registry validation result
                    errors.append(f"{record.id}: {exc}")
                    continue
                if tuple(entry.capabilities) != record.capabilities:
                    errors.append(
                        f"{record.id}: capabilities differ from catalogue plugin {record.plugin_id}"
                    )
                if record.status in {"contract-tested", "workflow-proven"}:
                    manifest = load_manifest(
                        catalogue.resolve_source(entry), check_compatibility=False
                    )
                    for capability in manifest.capabilities:
                        if contracts.get(capability.name, capability.version) is None:
                            errors.append(
                                f"{record.id}: missing contract for "
                                f"{capability.name} {capability.version}"
                            )
        if (
            record.trust == "official"
            and record.plugin_id
            and not record.plugin_id.startswith("org.alem.")
        ):
            errors.append(f"{record.id}: official trust requires an org.alem plugin")
    return {
        "valid": not errors,
        "schema_version": INTEGRATION_SCHEMA_VERSION,
        "integrations": len(records),
        "errors": errors,
    }


def find_integration(workspace: Workspace, integration_id: str) -> IntegrationRecord:
    for record in load_integrations(workspace):
        if record.id == integration_id:
            return record
    raise AlemError(f"unknown integration: {integration_id}")
