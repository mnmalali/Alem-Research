"""Subprocess execution adapter for installed plugins."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from .api import ExecutionRequest, ExecutionResponse
from .errors import PluginExecutionError
from .manifest import Manifest


class SubprocessRuntime:
    """Execute one request in a fresh isolated-interpreter process."""

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

    def invoke(
        self,
        manifest: Manifest,
        request: ExecutionRequest,
        *,
        dependency_root: Path | None = None,
    ) -> ExecutionResponse:
        if manifest.entrypoint is None:
            raise PluginExecutionError(f"plugin {manifest.id} has no executable entry point")
        runner = Path(__file__).with_name("runner.py").resolve()
        # src/alem/extensions/runtime.py -> src
        core_root = Path(__file__).resolve().parents[2]
        command = [
            sys.executable,
            "-I",
            "-S",
            str(runner),
            "--plugin-root",
            str(manifest.root),
            "--entrypoint",
            manifest.entrypoint,
            "--core-root",
            str(core_root),
        ]
        if dependency_root and dependency_root.is_dir():
            command.extend(("--dependency-root", str(dependency_root)))
        # Do not forward arbitrary secrets or Python path customizations.
        allowed_environment = {
            key: os.environ[key]
            for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "HOME", "LANG", "LC_ALL")
            if key in os.environ
        }
        allowed_environment["PYTHONIOENCODING"] = "utf-8"
        try:
            completed = subprocess.run(
                command,
                input=json.dumps(request.to_mapping()),
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=self.timeout_seconds,
                env=allowed_environment,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PluginExecutionError(
                f"plugin {manifest.id} exceeded {self.timeout_seconds:g}s execution timeout"
            ) from exc
        try:
            message = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            stderr = completed.stderr[-2000:]
            raise PluginExecutionError(
                f"plugin {manifest.id} returned an invalid protocol response; stderr: {stderr}"
            ) from exc
        if not isinstance(message, Mapping) or not message.get("ok"):
            error = message.get("error", {}) if isinstance(message, Mapping) else {}
            detail = (
                error.get("message", "unknown plugin error")
                if isinstance(error, Mapping)
                else str(error)
            )
            raise PluginExecutionError(f"plugin {manifest.id} failed: {detail}")
        response = message.get("response")
        if not isinstance(response, Mapping) or "output" not in response:
            raise PluginExecutionError(f"plugin {manifest.id} returned a malformed response")
        return ExecutionResponse.from_value(response)
