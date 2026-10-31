"""Errors exposed by Alem's public extension API."""


class ExtensionError(Exception):
    """Base class for extension subsystem failures."""


class ManifestError(ExtensionError):
    """A plugin manifest is missing data or violates the v1 schema."""


class CompatibilityError(ExtensionError):
    """A plugin is incompatible with this Alem/API/Python version."""


class ApprovalRequired(ExtensionError):
    """A security-sensitive operation was attempted without explicit approval."""

    def __init__(self, action: str, plugin_id: str) -> None:
        self.action = action
        self.plugin_id = plugin_id
        super().__init__(f"explicit approval is required for {action} of plugin {plugin_id!r}")


class DependencyError(ExtensionError):
    """Plugin dependencies cannot be resolved safely."""


class PluginNotFoundError(ExtensionError):
    """A requested plugin is not installed or present in the catalogue."""


class PluginIntegrityError(ExtensionError):
    """Installed plugin files changed after approval."""


class PluginExecutionError(ExtensionError):
    """A plugin process failed, timed out, or returned an invalid response."""


class RoutingError(ExtensionError):
    """No approved, enabled provider could satisfy a capability request."""
