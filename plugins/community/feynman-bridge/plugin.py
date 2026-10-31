"""A narrow, approval-gated bridge to an already-installed Feynman CLI."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from alem.extensions.api import BaseExtension, ExecutionRequest, ExecutionResponse

MODES = {
    "research": (),
    "lit": ("lit",),
    "deepresearch": ("deepresearch",),
    "draft": ("draft",),
    "recipe": ("recipe",),
    "autoresearch": ("autoresearch",),
}


def _find_feynman(request: ExecutionRequest) -> str | None:
    workspace = Path(str(request.context.get("workspace", "."))).resolve()
    local = workspace / ".alem" / "tools" / "feynman" / "node_modules" / ".bin"
    names = ("feynman.cmd", "feynman.exe", "feynman") if os.name == "nt" else ("feynman",)
    for name in names:
        candidate = local / name
        if candidate.is_file():
            return str(candidate)
    return shutil.which("feynman")


class FeynmanBridge(BaseExtension):
    extension_type = "tool"

    def invoke(self, request: ExecutionRequest) -> ExecutionResponse:
        if request.capability != "research_agent":
            raise ValueError(f"unsupported capability: {request.capability}")
        topic = str(request.input.get("topic", "")).strip()
        if not topic:
            raise ValueError("research_agent requires a non-empty topic")
        mode = str(request.input.get("mode", "research")).strip().lower()
        if mode not in MODES:
            raise ValueError(f"mode must be one of: {', '.join(MODES)}")
        executable = _find_feynman(request)
        if executable is None:
            raise RuntimeError(
                "Feynman CLI was not found on PATH; install the audited pinned version "
                "separately before enabling this bridge"
            )

        data_dir = Path(str(request.context.get("plugin_data_dir", "."))).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        command = [executable, *MODES[mode], topic]
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "WINDIR": os.environ.get("WINDIR", ""),
            "TEMP": os.environ.get("TEMP", ""),
            "TMP": os.environ.get("TMP", ""),
            "HOME": str(data_dir),
            "USERPROFILE": str(data_dir),
            "FEYNMAN_TELEMETRY": "off",
        }
        credentials = request.context.get("credentials", {})
        if isinstance(credentials, dict):
            for name in ("FEYNMAN_TELEMETRY", "OPENALEX_API_KEY", "SEMANTIC_SCHOLAR_API_KEY"):
                value = credentials.get(name)
                if value:
                    environment[name] = str(value)
        completed = subprocess.run(
            command,
            cwd=data_dir,
            env=environment,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=900,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError(
                f"Feynman exited with status {completed.returncode}: {completed.stderr[-2000:]}"
            )
        return ExecutionResponse(
            {
                "topic": topic,
                "mode": mode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "workspace": str(data_dir),
            },
            {
                "provider": "community.feynman-bridge",
                "upstream": "https://github.com/Companion-Inc/feynman",
                "telemetry_default": "off",
            },
        )


plugin = FeynmanBridge()
