"""Workspace diagnostics with machine-readable results."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from alem.adapters import GENERATED_MARKER
from alem.config import load_config
from alem.errors import AlemError
from alem.workspace import Workspace

Status = Literal["pass", "warn", "fail", "info"]


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    status: Status
    message: str


@dataclass(frozen=True, slots=True)
class HealthReport:
    checks: tuple[Check, ...]

    @property
    def ok(self) -> bool:
        return all(check.status != "fail" for check in self.checks)

    def as_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "checks": [asdict(check) for check in self.checks]}

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2)


def _tracked_sensitive_files(root: Path) -> list[str]:
    if not (root / ".git").exists() or not shutil.which("git"):
        return []
    result = subprocess.run(
        ["git", "ls-files"], cwd=root, text=True, capture_output=True, check=False
    )
    risky: list[str] = []
    sensitive_names = {".env", "credentials.json", "secrets.toml", "id_rsa", "id_ed25519"}
    for item in result.stdout.splitlines():
        path = Path(item)
        if path.name.lower() in sensitive_names or path.suffix.lower() in {".pem", ".key"}:
            risky.append(item)
    return risky


def run_health_checks(workspace: Workspace) -> HealthReport:
    checks: list[Check] = []
    checks.append(Check("python", "pass", f"Python {sys.version.split()[0]} is supported"))
    try:
        config = load_config(workspace)
        checks.append(
            Check("configuration", "pass", f"Workspace schema {config.workspace_version} is valid")
        )
    except AlemError as exc:
        checks.append(Check("configuration", "fail", str(exc)))

    if workspace.runtime.is_dir():
        checks.append(Check("runtime", "pass", ".alem runtime is workspace-local"))
    else:
        checks.append(
            Check("runtime", "warn", "Run `alem setup` to initialize local runtime state")
        )

    canonical = sorted(workspace.path("skills").glob("*/SKILL.md"))
    if canonical:
        checks.append(Check("skills", "pass", f"Found {len(canonical)} canonical project skills"))
    else:
        checks.append(Check("skills", "fail", "No canonical skills found under skills/"))

    for agent_name, relative in (
        ("Codex", ".agents/skills"),
        ("Claude Code", ".claude/skills"),
    ):
        adapters = sorted(workspace.path(relative).glob("*/SKILL.md"))
        valid = sum(GENERATED_MARKER in path.read_text(encoding="utf-8") for path in adapters)
        if canonical and valid == len(canonical):
            checks.append(
                Check(f"{agent_name} adapters", "pass", f"{valid} local adapters present")
            )
        else:
            checks.append(
                Check(
                    f"{agent_name} adapters",
                    "warn",
                    f"{valid}/{len(canonical)} generated adapters; run `alem setup` to synchronize",
                )
            )

    for instructions, label in (("AGENTS.md", "Codex"), ("CLAUDE.md", "Claude Code")):
        if workspace.path(instructions).is_file():
            checks.append(Check(f"{label} instructions", "pass", f"{instructions} is present"))
        else:
            checks.append(Check(f"{label} instructions", "fail", f"Missing {instructions}"))

    risky = _tracked_sensitive_files(workspace.root)
    checks.append(
        Check(
            "tracked secrets",
            "fail" if risky else "pass",
            (
                f"Sensitive-looking tracked files: {', '.join(risky)}"
                if risky
                else "No obvious secret files are tracked"
            ),
        )
    )

    for executable in ("git", "pandoc", "quarto", "latex", "jupyter"):
        found = shutil.which(executable)
        checks.append(
            Check(
                f"optional:{executable}",
                "info",
                found or "not found (optional; core Alem functionality remains available)",
            )
        )
    return HealthReport(tuple(checks))
