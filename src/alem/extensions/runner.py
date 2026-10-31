"""Isolated-process protocol runner.

This file is launched with Python's ``-I`` flag.  A process boundary protects
the Alem process from accidental global-state corruption, but it is **not** an
OS security sandbox: plugin code still has the user's filesystem and network
privileges.  See ``docs/plugin-security.md``.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import sys
import traceback
from pathlib import Path


def _load(plugin_root: Path, entrypoint: str):
    file_text, attribute = entrypoint.split(":", 1)
    source = (plugin_root / file_text).resolve()
    source.relative_to(plugin_root.resolve())
    spec = importlib.util.spec_from_file_location("_alem_external_plugin", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load plugin entry point {entrypoint}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    value = getattr(module, attribute)
    if isinstance(value, type):
        value = value()
    return value


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--plugin-root", required=True)
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--core-root", required=True)
    parser.add_argument("--dependency-root")
    args = parser.parse_args()
    plugin_root = Path(args.plugin_root).resolve()
    search_paths = [str(Path(args.core_root).resolve()), str(plugin_root)]
    if args.dependency_root:
        search_paths.append(str(Path(args.dependency_root).resolve()))
    # Trusted core contracts always win over plugin and dependency packages.
    # Plugin-local helper modules win over third-party dependencies.
    sys.path[:0] = search_paths
    try:
        from alem.extensions.api import ExecutionRequest, ExecutionResponse

        raw = json.load(sys.stdin)
        request = ExecutionRequest.from_mapping(raw)
        # Keep plugin logging away from the JSON stdout protocol.
        with contextlib.redirect_stdout(sys.stderr):
            plugin = _load(plugin_root, args.entrypoint)
            if not hasattr(plugin, "invoke"):
                raise TypeError("plugin entry point must implement invoke(request)")
            response = ExecutionResponse.from_value(plugin.invoke(request))
        json.dump({"ok": True, "response": response.to_mapping()}, sys.stdout)
        return 0
    except Exception as exc:  # exception crosses a JSON process boundary
        json.dump(
            {
                "ok": False,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": "".join(traceback.format_exception(exc))[-8000:],
                },
            },
            sys.stdout,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
