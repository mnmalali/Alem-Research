"""Create and dependency-seed the workspace Python runtime without importing Alem."""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
import venv
from pathlib import Path

IMPORT_CHECK = "import jsonschema, yaml"


def bootstrap(root: Path) -> int:
    root = root.resolve()
    runtime = root / ".alem" / "venv"
    runtime_python = (
        runtime / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else runtime / "bin" / "python"
    )
    if not runtime_python.is_file():
        runtime.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True, clear=False, symlinks=False).create(runtime)
    if not runtime_python.is_file():
        raise RuntimeError(f"virtual environment did not create its Python interpreter: {runtime}")

    with (root / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream).get("project", {})
    requirements = project.get("dependencies")
    if not isinstance(requirements, list) or not all(
        isinstance(item, str) and item.strip() for item in requirements
    ):
        raise RuntimeError("pyproject.toml project.dependencies must be a string array")

    state_dir = root / ".alem" / "state"
    marker_path = state_dir / "runtime-dependencies.json"
    expected = {"requirements": requirements, "python": str(runtime_python.resolve())}
    try:
        existing = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        existing = None
    check = subprocess.run(
        [str(runtime_python), "-c", IMPORT_CHECK],
        cwd=root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if existing != expected or check.returncode != 0:
        command = [
            str(runtime_python),
            "-m",
            "pip",
            "--isolated",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            "--no-input",
            "--no-warn-script-location",
            *requirements,
        ]
        installed = subprocess.run(command, cwd=root, check=False, stdout=sys.stderr)
        if installed.returncode:
            return installed.returncode
        verified = subprocess.run(
            [str(runtime_python), "-c", IMPORT_CHECK], cwd=root, check=False
        )
        if verified.returncode:
            raise RuntimeError("workspace Python runtime is missing a core Alem dependency")
        state_dir.mkdir(parents=True, exist_ok=True)
        temporary = marker_path.with_suffix(".tmp")
        content = json.dumps(expected, indent=2, sort_keys=True) + "\n"
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(marker_path)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: bootstrap_runtime.py WORKSPACE_ROOT")
    try:
        raise SystemExit(bootstrap(Path(sys.argv[1])))
    except (OSError, RuntimeError, tomllib.TOMLDecodeError) as exc:
        print(f"Alem runtime bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
