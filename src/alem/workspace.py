"""Workspace discovery and guarded local file operations."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alem.errors import UnsafePathError, WorkspaceNotFoundError

WORKSPACE_MARKER = "alem.toml"


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


@dataclass(frozen=True, slots=True)
class Workspace:
    """An Alem workspace rooted at a directory containing ``alem.toml``."""

    root: Path

    @classmethod
    def discover(cls, start: str | Path | None = None) -> Workspace:
        candidate = _resolved(Path(start) if start is not None else Path.cwd())
        if candidate.is_file():
            candidate = candidate.parent
        for directory in (candidate, *candidate.parents):
            if (directory / WORKSPACE_MARKER).is_file():
                return cls(directory)
        raise WorkspaceNotFoundError(
            f"No {WORKSPACE_MARKER} found from {candidate}. Run Alem from the repository root."
        )

    def path(self, *parts: str) -> Path:
        target = _resolved(self.root.joinpath(*parts))
        self.assert_local(target)
        return target

    def assert_local(self, path: str | Path) -> Path:
        target = _resolved(Path(path))
        try:
            target.relative_to(_resolved(self.root))
        except ValueError as exc:
            raise UnsafePathError(f"Refusing to access path outside workspace: {target}") from exc
        return target

    @property
    def runtime(self) -> Path:
        return self.path(".alem")

    def ensure_runtime(self) -> list[Path]:
        created: list[Path] = []
        for relative in (
            ".alem/state",
            ".alem/cache",
            ".alem/logs",
            ".alem/plugins",
            ".alem/venvs",
            ".alem/tmp",
            "projects",
            "exports",
        ):
            directory = self.path(relative)
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                created.append(directory)
        return created

    def atomic_write_text(self, relative: str, content: str) -> Path:
        target = self.path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        return target

    def write_json(self, relative: str, value: Any) -> Path:
        return self.atomic_write_text(relative, json.dumps(value, indent=2, sort_keys=True) + "\n")

    def read_json(self, relative: str, default: Any = None) -> Any:
        target = self.path(relative)
        if not target.exists():
            return default
        with target.open("r", encoding="utf-8") as stream:
            return json.load(stream)
