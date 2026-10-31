"""Research project creation and privacy-conscious export."""

from __future__ import annotations

import re
import shutil
import zipfile
from datetime import date
from pathlib import Path

from alem.errors import AlemError
from alem.workspace import Workspace


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise AlemError("Project name must contain at least one letter or number")
    return slug


def create_project(workspace: Workspace, name: str, slug: str | None = None) -> Path:
    project_slug = slugify(slug or name)
    source = workspace.path("templates/project")
    if not source.is_dir():
        raise AlemError("Project template is missing: templates/project")
    destination = workspace.path("projects", project_slug)
    if destination.exists():
        raise AlemError(f"Project already exists: {destination.relative_to(workspace.root)}")
    shutil.copytree(source, destination)
    replacements = {
        "{{project_name}}": name,
        "{{project_slug}}": project_slug,
        "{{created_date}}": date.today().isoformat(),
        # The committed human-readable template intentionally remains useful
        # when copied by hand, so support its plain placeholder vocabulary too.
        "Project title": name,
        "project-slug": project_slug,
        "YYYY-MM-DD": date.today().isoformat(),
    }
    for path in destination.rglob("*"):
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for needle, replacement in replacements.items():
            content = content.replace(needle, replacement)
        path.write_text(content, encoding="utf-8", newline="\n")
    return destination


DEFAULT_EXPORT_EXCLUDES = (
    ".env",
    ".env*",
    ".alem",
    "credentials",
    "credentials*.json",
    "secrets",
    "secrets*.toml",
    "00_admin/private",
    "03_data/raw",
    "03_data/sensitive",
    "*.pdf",
    "*.key",
    "*.pem",
)


def _matches_exclude(relative: Path) -> bool:
    normalized = relative.as_posix().lower()
    for pattern in DEFAULT_EXPORT_EXCLUDES:
        pattern_lower = pattern.lower()
        if "*" in pattern_lower and relative.match(pattern_lower):
            return True
        if normalized == pattern_lower or normalized.startswith(pattern_lower.rstrip("/") + "/"):
            return True
        if relative.name.lower() == pattern_lower:
            return True
    return False


def export_project(
    workspace: Workspace,
    project_slug: str,
    output: str | Path | None = None,
    *,
    include_sensitive: bool = False,
) -> Path:
    source = workspace.path("projects", slugify(project_slug))
    if not source.is_dir():
        raise AlemError(f"Unknown project: {project_slug}")
    if output is None:
        destination = workspace.path("exports", f"{source.name}-{date.today().isoformat()}.zip")
    else:
        requested = Path(output)
        destination = (
            workspace.assert_local(requested)
            if requested.is_absolute()
            else workspace.path(requested.as_posix())
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            is_junction = getattr(path, "is_junction", lambda: False)
            if path.is_symlink() or is_junction():
                raise AlemError(f"Refusing to export linked path: {path.relative_to(source)}")
            try:
                path.resolve().relative_to(source.resolve())
            except ValueError as exc:
                raise AlemError(
                    f"Refusing to export path outside project: {path.relative_to(source)}"
                ) from exc
            if not path.is_file():
                continue
            relative = path.relative_to(source)
            if not include_sensitive and _matches_exclude(relative):
                continue
            archive.write(path, Path(source.name) / relative)
    return destination
