"""Stable public contracts for Alem extension API v1.

Plugins may import this module.  Everything else under ``alem.extensions`` is
framework implementation detail unless explicitly re-exported from
``alem.extensions``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable

API_VERSION = "1.0"
ExtensionType = Literal["tool", "skill", "agent", "workflow"]


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """Serializable request passed to a capability provider."""

    capability: str
    capability_version: str = "1.0"
    operation: str = "invoke"
    input: Mapping[str, Any] = field(default_factory=dict)
    context: Mapping[str, Any] = field(default_factory=dict)
    api_version: str = API_VERSION

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExecutionRequest:
        return cls(
            capability=str(value["capability"]),
            capability_version=str(value.get("capability_version", "1.0")),
            operation=str(value.get("operation", "invoke")),
            input=dict(value.get("input", {})),
            context=dict(value.get("context", {})),
            api_version=str(value.get("api_version", API_VERSION)),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "api_version": self.api_version,
            "capability": self.capability,
            "capability_version": self.capability_version,
            "operation": self.operation,
            "input": dict(self.input),
            "context": dict(self.context),
        }


@dataclass(frozen=True, slots=True)
class ExecutionResponse:
    """Serializable result returned by an extension."""

    output: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_value(cls, value: Any) -> ExecutionResponse:
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping) and "output" in value:
            return cls(value["output"], dict(value.get("metadata", {})))
        return cls(value)

    def to_mapping(self) -> dict[str, Any]:
        return {"output": self.output, "metadata": dict(self.metadata)}


@runtime_checkable
class Extension(Protocol):
    """Common executable extension contract.

    A plugin entry point is an instance (or zero-argument class) implementing
    ``invoke``. Data-only skills may omit an entry point and expose assets via
    their manifest instead.
    """

    api_version: ClassVar[str]
    extension_type: ClassVar[ExtensionType]

    def invoke(self, request: ExecutionRequest) -> ExecutionResponse | Any:
        """Handle one request without relying on conversational memory."""


@runtime_checkable
class ToolExtension(Extension, Protocol):
    """A callable integration or deterministic research tool."""

    extension_type: ClassVar[Literal["tool"]]


@runtime_checkable
class SkillExtension(Extension, Protocol):
    """An executable skill; declarative skills may instead use manifest assets."""

    extension_type: ClassVar[Literal["skill"]]


@runtime_checkable
class AgentExtension(Extension, Protocol):
    """A specialist agent invoked through a declared capability."""

    extension_type: ClassVar[Literal["agent"]]


@runtime_checkable
class WorkflowExtension(Extension, Protocol):
    """A resumable orchestration workflow."""

    extension_type: ClassVar[Literal["workflow"]]


class BaseExtension:
    """Optional convenience base class; implementing the protocol is sufficient."""

    api_version: ClassVar[str] = API_VERSION
    extension_type: ClassVar[ExtensionType]

    def invoke(self, request: ExecutionRequest) -> ExecutionResponse | Any:
        raise NotImplementedError
