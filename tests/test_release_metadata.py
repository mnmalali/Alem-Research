from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_is_synchronized_across_project_metadata() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_version = pyproject["project"]["version"]
    init_text = (ROOT / "src/alem/__init__.py").read_text(encoding="utf-8")
    citation_text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog_text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert re.search(rf'__version__\s*=\s*["\']{re.escape(package_version)}["\']', init_text)
    assert re.search(rf"^version:\s*{re.escape(package_version)}$", citation_text, re.MULTILINE)
    assert f"version = {{{package_version}}}" in readme_text
    assert re.search(rf"^## {re.escape(package_version)}\s+—", changelog_text, re.MULTILINE)
