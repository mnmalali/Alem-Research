"""Canonical integration maturity, trust, and implementation registry."""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import parse_qsl, urlparse

from alem.config import load_config
from alem.errors import AlemError
from alem.extensions import PluginCatalogue
from alem.workspace import Workspace

INTEGRATION_SCHEMA_VERSION = 3
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
ACCEPTANCE = {"accepted", "candidate", "rejected"}
AUTHORSHIP = {"alem-official", "community-contributor", "unknown"}
SECRET_QUERY_KEYS = {
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "key",
    "token",
    "access_token",
}


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
    acceptance: str = "candidate"
    authorship: str = "unknown"
    contributor: str | None = None
    release_version: str | None = None
    release_digest: str | None = None
    required_hardware: tuple[str, ...] = ()
    required_runtimes: tuple[str, ...] = ()
    service_checks: tuple[str, ...] = ()
    configuration_instructions: str = ""

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
    schema_version = raw.get("schema_version")
    if schema_version not in {2, INTEGRATION_SCHEMA_VERSION}:
        raise AlemError(
            "integration registry must use schema_version = 1, 2, or "
            f"{INTEGRATION_SCHEMA_VERSION}"
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
    old_allowed = required_strings | {"capabilities", "plugin_id", "upstream_id"}
    release_fields = {
        "acceptance",
        "authorship",
        "contributor",
        "release_version",
        "release_digest",
        "required_hardware",
        "required_runtimes",
        "service_checks",
        "configuration_instructions",
    }
    allowed = old_allowed | (
        release_fields if schema_version == INTEGRATION_SCHEMA_VERSION else set()
    )
    for index, item in enumerate(values):
        if not isinstance(item, dict):
            raise AlemError(f"integration {index} must be a table")
        unknown = sorted(set(item) - allowed)
        if unknown:
            raise AlemError(f"integration {index} has unknown fields: {', '.join(unknown)}")
        if schema_version == INTEGRATION_SCHEMA_VERSION and not {
            "acceptance",
            "authorship",
        } <= set(item):
            raise AlemError(f"integration {index} must declare acceptance and authorship")
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
        acceptance = item.get("acceptance", "candidate")
        authorship = item.get("authorship", "unknown")
        if acceptance not in ACCEPTANCE:
            raise AlemError(f"invalid acceptance state for {integration_id}: {acceptance}")
        if authorship not in AUTHORSHIP:
            raise AlemError(f"invalid authorship for {integration_id}: {authorship}")
        contributor = _optional_string(item, "contributor")
        release_version = _optional_string(item, "release_version")
        release_digest = _optional_string(item, "release_digest")
        if release_digest is not None and (
            len(release_digest) != 64
            or not all(char in "0123456789abcdef" for char in release_digest)
        ):
            raise AlemError(f"integration {integration_id}.release_digest must be SHA-256 hex")
        if release_version is not None:
            from alem.extensions.versions import Version

            try:
                Version.parse(release_version)
            except ValueError as exc:
                raise AlemError(
                    f"integration {integration_id}.release_version must be semantic version"
                ) from exc
        if acceptance == "accepted":
            if item["status"] not in {"contract-tested", "workflow-proven"}:
                raise AlemError(
                    f"accepted integration {integration_id} must be contract-tested or "
                    "workflow-proven"
                )
            if not item.get("plugin_id"):
                raise AlemError(f"accepted integration {integration_id} requires plugin_id")
            if not release_version or not release_digest:
                raise AlemError(
                    f"accepted integration {integration_id} requires a pinned release_version "
                    "and release_digest"
                )
            if authorship == "unknown":
                raise AlemError(f"accepted integration {integration_id} requires known authorship")
            if authorship == "community-contributor" and not contributor:
                raise AlemError(
                    f"community-authored integration {integration_id} requires "
                    "contributor attribution"
                )
        capabilities = item.get("capabilities", [])
        if not isinstance(capabilities, list) or not all(
            isinstance(value, str) and value.strip() for value in capabilities
        ):
            raise AlemError(f"integration {integration_id}.capabilities must be a string array")
        readiness_lists: dict[str, tuple[str, ...]] = {}
        for key in ("required_hardware", "required_runtimes", "service_checks"):
            values = item.get(key, [])
            if not isinstance(values, list) or not all(
                isinstance(value, str) and value.strip() for value in values
            ):
                raise AlemError(f"integration {integration_id}.{key} must be a string array")
            readiness_lists[key] = tuple(value.strip() for value in values)
        for service in readiness_lists["service_checks"]:
            parsed = urlparse(service)
            has_secret_query = any(
                key.casefold() in SECRET_QUERY_KEYS
                for key, _value in parse_qsl(parsed.query)
            )
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or has_secret_query
            ):
                raise AlemError(
                    f"integration {integration_id}.service_checks must contain "
                    "credential-free HTTP URLs"
                )
        for runtime in readiness_lists["required_runtimes"]:
            path = PurePosixPath(runtime)
            if (
                "\\" in runtime
                or path.is_absolute()
                or ".." in path.parts
                or not runtime.startswith(".alem/")
            ):
                raise AlemError(
                    f"integration {integration_id}.required_runtimes must stay under .alem/"
                )
        instructions = item.get("configuration_instructions", "")
        if not isinstance(instructions, str):
            raise AlemError(
                f"integration {integration_id}.configuration_instructions must be a string"
            )
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
                acceptance=acceptance,
                authorship=authorship,
                contributor=contributor,
                release_version=release_version,
                release_digest=release_digest,
                required_hardware=readiness_lists["required_hardware"],
                required_runtimes=readiness_lists["required_runtimes"],
                service_checks=readiness_lists["service_checks"],
                configuration_instructions=instructions.strip(),
            )
        )
    return records


def validate_integrations(workspace: Workspace) -> dict[str, Any]:
    from alem.contracts import ContractRegistry
    from alem.extensions.manager import plugin_tree_digest
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
    accepted_by_plugin = {
        record.plugin_id: record for record in records if record.acceptance == "accepted"
    }
    for record in records:
        if record.acceptance == "accepted":
            if catalogue is None:
                errors.append(
                    f"{record.id}: accepted release requires a configured plugin catalogue"
                )
                continue
            try:
                entry = catalogue.get(record.plugin_id or "")
                source = catalogue.resolve_source(entry)
                manifest = load_manifest(source, check_compatibility=False)
                if (
                    entry.version != record.release_version
                    or manifest.version != record.release_version
                ):
                    errors.append(
                        f"{record.id}: accepted release version does not match catalogue/manifest"
                    )
                if plugin_tree_digest(source) != record.release_digest:
                    errors.append(
                        f"{record.id}: accepted release digest does not match source tree"
                    )
                if entry.capabilities != record.capabilities:
                    errors.append(
                        f"{record.id}: capabilities differ from catalogue plugin {record.plugin_id}"
                    )
                if record.status in {"contract-tested", "workflow-proven"}:
                    for capability in manifest.capabilities:
                        if contracts.get(capability.name, capability.version) is None:
                            errors.append(
                                f"{record.id}: missing contract for "
                                f"{capability.name} {capability.version}"
                            )
                for dependency in manifest.plugin_dependencies:
                    accepted_dependency = accepted_by_plugin.get(dependency.id)
                    if accepted_dependency is None:
                        errors.append(
                            f"{record.id}: plugin dependency {dependency.id} must also be accepted"
                        )
                    else:
                        from alem.extensions.versions import satisfies

                        if not satisfies(
                            accepted_dependency.release_version or "0.0.0", dependency.version
                        ):
                            errors.append(
                                f"{record.id}: accepted release "
                                f"{accepted_dependency.release_version} of dependency "
                                f"{dependency.id} does not satisfy {dependency.version}"
                            )
            except Exception as exc:
                errors.append(f"{record.id}: accepted release validation failed: {exc}")
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
