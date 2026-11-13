"""The interactive Alem welcome/dashboard view."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import TextIO

from alem.models import model_status

from .mascot import PALETTE, render_ansi, should_use_color, supports_unicode

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _rgb(value: tuple[int, int, int], text: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"\x1b[38;2;{value[0]};{value[1]};{value[2]}m{text}\x1b[0m"


def _width(stream: TextIO) -> int:
    try:
        return max(20, int(os.get_terminal_size(stream.fileno()).columns))
    except (AttributeError, OSError, ValueError):
        return 80


def _projects(root: Path) -> list[str]:
    projects = root / "projects"
    if not projects.is_dir():
        return []
    return sorted(
        path.name
        for path in projects.iterdir()
        if path.is_dir() and (path / "PROJECT.md").is_file()
    )


def _workflows(root: Path) -> list[str]:
    workflows = root / "workflows"
    if not workflows.is_dir():
        return []
    return sorted(
        path.stem
        for pattern in ("*.yaml", "*.yml", "*.md")
        for path in workflows.glob(pattern)
        if path.name.lower() != "readme.md"
    )


def _row(label: str, value: str, enabled: bool) -> str:
    return f"  {_rgb(PALETTE['L'], label, enabled):<22} {value}"


def render_dashboard(
    workspace: object,
    *,
    file: TextIO | None = None,
    color: bool | None = None,
    no_color: bool = False,
) -> None:
    """Render a compact dashboard without taking over non-interactive output."""

    output = file or sys.stdout
    root = Path(str(getattr(workspace, "root", workspace)))
    use_color = should_use_color(output, no_color=no_color) if color is None else color
    unicode = supports_unicode(output)
    width = _width(output)
    print(file=output)

    owl = render_ansi(use_color, unicode=unicode).splitlines()
    title = _rgb(PALETTE["P"], "ALEM RESEARCH", use_color)
    tagline = _rgb(PALETTE["A"], "Research deeper.", use_color)
    if width >= 42:
        for index, line in enumerate(owl):
            if index == 1:
                print(f"  {line:<20}  {title}", file=output)
            elif index == 2:
                print(f"  {line:<20}  {tagline}", file=output)
            else:
                print(f"  {line}", file=output)
    else:
        print(f"  {title}", file=output)
        print(f"  {tagline}", file=output)

    current = model_status(root)
    selected = current.get("current") or "not selected"
    statuses = current.get("providers", [])
    configured = sum(
        item.get("readiness") in {"configured", "local"}
        for item in statuses
        if isinstance(item, dict)
    )
    projects = _projects(root)
    workflows = _workflows(root)

    print(file=output)
    print(_rgb(PALETTE["D"], "─" * min(width, 76), use_color), file=output)
    print(_rgb(PALETTE["P"], "Workspace", use_color), file=output)
    print(_row("root", str(root), use_color), file=output)
    print(_row("projects", str(len(projects)), use_color), file=output)
    print(_row("current model", selected, use_color), file=output)
    print(
        _row(
            "provider readiness",
            f"{configured} configured / {len(statuses)} catalogued",
            use_color,
        ),
        file=output,
    )

    print(file=output)
    print(_rgb(PALETTE["P"], "Research Workflows", use_color), file=output)
    workflow_text = ", ".join(workflows[:4]) if workflows else "none discovered"
    print(f"  {workflow_text}", file=output)
    print("  /deepresearch  /lit  /review  /audit  /replicate", file=output)
    print("  /recipe        /compare  /draft  /autoresearch  /summarize", file=output)

    print(file=output)
    print(_rgb(PALETTE["P"], "Quick actions", use_color), file=output)
    print("  alem model list       inspect providers and model IDs", file=output)
    print("  alem model login      configure an API key or inspect OAuth support", file=output)
    print("  alem model set        choose the workspace default", file=output)
    print("  alem health           run workspace diagnostics", file=output)
    print("  alem project list     inspect local research projects", file=output)
    print(file=output)
    print(
        _rgb(
            PALETTE["A"],
            "Tip: run `alem --help` for the grouped command dashboard.",
            use_color,
        ),
        file=output,
    )


def visible_width(text: str) -> int:
    """Return display width for tests and output-layout callers."""

    return len(ANSI_RE.sub("", text))
