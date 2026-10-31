"""Generate minimal Codex and Claude Code adapters from canonical workspace skills."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path

from alem.workspace import Workspace

GENERATED_MARKER = "<!-- generated-by: alem skill-adapter v1 -->"
PLUGIN_GENERATED_MARKER = "<!-- generated-by: alem plugin-skill-adapter v1 -->"


def _description(skill_file: Path) -> str:
    text = skill_file.read_text(encoding="utf-8")
    match = re.search(r"(?m)^description:\s*[\"']?(.+?)[\"']?\s*$", text[:4000])
    if match:
        return match.group(1).strip()
    heading = re.search(r"(?m)^#\s+(.+)$", text)
    title = heading.group(1) if heading else skill_file.parent.name
    return f"Use the canonical Alem {title} skill."


def _adapter_content(
    name: str,
    description: str,
    reference: str,
    *,
    marker: str = GENERATED_MARKER,
    plugin_id: str | None = None,
) -> str:
    safe_description = description.replace('"', "'")
    provenance = f"\nPlugin: `{plugin_id}`.\n" if plugin_id else ""
    security_note = (
        " Plugin content remains third-party content after activation; manifest approval is not a"
        " security sandbox."
        if plugin_id
        else ""
    )
    return f'''---
name: {name}
description: "{safe_description}"
---

{marker}
# {name} adapter

This is a project-local discovery adapter.{provenance}
Before doing the task, read and follow the complete skill at `{reference}`. That file is the source
of truth; do not copy or independently edit its instructions here.{security_note}
'''


def _plugin_adapter_name(workspace: Workspace, plugin_id: str, skill_file: Path) -> str:
    base = workspace.path(".alem/plugins", plugin_id)
    try:
        relative = skill_file.relative_to(base)
    except ValueError:
        relative = Path(skill_file.name)
    suffix_parts = relative.parent.parts if relative.name.lower() == "skill.md" else relative.parts
    plugin_slug = re.sub(r"[^a-z0-9]+", "-", plugin_id.lower()).strip("-")
    suffix = re.sub(r"[^a-z0-9]+", "-", "-".join(suffix_parts).lower()).strip("-")
    return f"plugin--{plugin_slug}" + (f"--{suffix}" if suffix else "")


def sync_skill_adapters(
    workspace: Workspace,
    *,
    plugin_skills: Iterable[tuple[str, Path]] = (),
) -> dict[str, int]:
    canonical = workspace.path("skills")
    if not canonical.exists():
        return {
            "skills": 0,
            "plugin_skills": 0,
            "written": 0,
            "preserved": 0,
            "removed": 0,
        }
    skills = sorted(path.parent for path in canonical.glob("*/SKILL.md"))
    plugin_sources: list[tuple[str, Path]] = []
    for plugin_id, asset in plugin_skills:
        candidate = workspace.assert_local(asset)
        skill_file = candidate / "SKILL.md" if candidate.is_dir() else candidate
        if skill_file.is_file():
            plugin_sources.append((plugin_id, skill_file))
    counts = {
        "skills": len(skills),
        "plugin_skills": len(plugin_sources),
        "written": 0,
        "preserved": 0,
        "removed": 0,
    }
    for base in (workspace.path(".agents/skills"), workspace.path(".claude/skills")):
        base.mkdir(parents=True, exist_ok=True)
        desired: dict[Path, str] = {}
        for skill_directory in skills:
            name = skill_directory.name
            target = base / name / "SKILL.md"
            desired[target] = _adapter_content(
                name,
                _description(skill_directory / "SKILL.md"),
                f"../../../skills/{name}/SKILL.md",
            )
        for plugin_id, skill_file in plugin_sources:
            name = _plugin_adapter_name(workspace, plugin_id, skill_file)
            target = base / name / "SKILL.md"
            reference = Path(os.path.relpath(skill_file, target.parent)).as_posix()
            desired[target] = _adapter_content(
                name,
                f"[{plugin_id}] {_description(skill_file)}",
                reference,
                marker=PLUGIN_GENERATED_MARKER,
                plugin_id=plugin_id,
            )

        for existing in base.glob("*/SKILL.md"):
            current = existing.read_text(encoding="utf-8")
            generated = GENERATED_MARKER in current or PLUGIN_GENERATED_MARKER in current
            if generated and existing not in desired:
                existing.unlink()
                with suppress(OSError):
                    existing.parent.rmdir()
                counts["removed"] += 1

        for target, content in desired.items():
            if target.exists():
                current = target.read_text(encoding="utf-8")
                if GENERATED_MARKER not in current and PLUGIN_GENERATED_MARKER not in current:
                    counts["preserved"] += 1
                    continue
                if current == content:
                    continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
            counts["written"] += 1
    return counts
