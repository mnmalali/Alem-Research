"""Machine-readable capability contracts and JSON Schema validation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from alem.extensions.errors import PluginExecutionError
from alem.workspace import Workspace


@dataclass(frozen=True, slots=True)
class CapabilityContract:
    capability: str
    version: str
    path: Path
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]

    def validate_input(self, value: Mapping[str, Any]) -> None:
        self._validate(self.input_schema, value, "input")

    def validate_output(self, value: Any) -> None:
        self._validate(self.output_schema, value, "output")

    def _validate(self, schema: Mapping[str, Any], value: Any, label: str) -> None:
        try:
            Draft202012Validator(schema).validate(value)
        except ValidationError as exc:
            location = ".".join(str(part) for part in exc.absolute_path) or "<root>"
            raise PluginExecutionError(
                f"{self.capability} {self.version} {label} violates its contract "
                f"at {location}: {exc.message}"
            ) from exc


class ContractRegistry:
    """Read contracts from the workspace without importing provider code."""

    def __init__(self, workspace: Workspace | str | Path) -> None:
        self.workspace = (
            workspace
            if isinstance(workspace, Workspace)
            else Workspace(Path(workspace).resolve())
        )
        self.root = self.workspace.path("contracts/capabilities")

    def path_for(self, capability: str, version: str) -> Path:
        return self.root / capability / f"{version}.json"

    def get(self, capability: str, version: str = "1.0") -> CapabilityContract | None:
        path = self.path_for(capability, version)
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PluginExecutionError(f"cannot read capability contract {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise PluginExecutionError(f"capability contract must be an object: {path}")
        if raw.get("schema_version") != 1:
            raise PluginExecutionError(f"unsupported capability contract schema: {path}")
        if raw.get("capability") != capability or raw.get("version") != version:
            raise PluginExecutionError(f"capability contract identity mismatch: {path}")
        input_schema = raw.get("input")
        output_schema = raw.get("output")
        if not isinstance(input_schema, dict) or not isinstance(output_schema, dict):
            raise PluginExecutionError(f"contract input and output must be objects: {path}")
        try:
            Draft202012Validator.check_schema(input_schema)
            Draft202012Validator.check_schema(output_schema)
        except SchemaError as exc:
            raise PluginExecutionError(f"invalid JSON Schema in {path}: {exc.message}") from exc
        return CapabilityContract(capability, version, path, input_schema, output_schema)

    def describe(self, capability: str, version: str = "1.0") -> dict[str, Any]:
        contract = self.get(capability, version)
        if contract is None:
            raise PluginExecutionError(
                f"no contract is registered for {capability!r} version {version!r}"
            )
        return json.loads(contract.path.read_text(encoding="utf-8"))
