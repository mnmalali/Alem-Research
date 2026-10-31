"""Public entry points for Alem's versioned extension system."""

from .api import (
    API_VERSION,
    AgentExtension,
    BaseExtension,
    ExecutionRequest,
    ExecutionResponse,
    Extension,
    SkillExtension,
    ToolExtension,
    WorkflowExtension,
)
from .catalogue import CatalogueEntry, PluginCatalogue
from .errors import (
    ApprovalRequired,
    CompatibilityError,
    DependencyError,
    ExtensionError,
    ManifestError,
    PluginExecutionError,
    PluginIntegrityError,
    PluginNotFoundError,
    RoutingError,
)
from .manager import ExtensionAsset, InstalledPlugin, InstallPlan, PluginManager
from .manifest import (
    Capability,
    Manifest,
    Permissions,
    PluginDependency,
    load_manifest,
    validate_manifest,
)
from .registry import PluginRegistry, Provider

__all__ = [
    "API_VERSION",
    "AgentExtension",
    "ApprovalRequired",
    "BaseExtension",
    "Capability",
    "CatalogueEntry",
    "CompatibilityError",
    "DependencyError",
    "ExecutionRequest",
    "ExecutionResponse",
    "Extension",
    "ExtensionAsset",
    "ExtensionError",
    "InstallPlan",
    "InstalledPlugin",
    "Manifest",
    "ManifestError",
    "Permissions",
    "PluginCatalogue",
    "PluginDependency",
    "PluginExecutionError",
    "PluginIntegrityError",
    "PluginManager",
    "PluginNotFoundError",
    "PluginRegistry",
    "Provider",
    "RoutingError",
    "SkillExtension",
    "ToolExtension",
    "WorkflowExtension",
    "load_manifest",
    "validate_manifest",
]
