from __future__ import annotations


class AlemError(Exception):
    """Base error for user-actionable Alem failures."""


class WorkspaceNotFoundError(AlemError):
    """Raised when no Alem workspace can be found."""


class ConfigurationError(AlemError):
    """Raised when workspace configuration is invalid."""


class UnsafePathError(AlemError):
    """Raised when an operation would escape the workspace."""
