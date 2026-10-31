"""Offline search over the pinned Wenyu catalog without a YAML dependency."""

from __future__ import annotations

import re
from pathlib import Path

from alem.extensions.api import BaseExtension, ExecutionRequest, ExecutionResponse

ENTRY = re.compile(r"^\s+- name:\s*(?P<name>[^\s#]+)\s*$")
FIELD = re.compile(
    r"^\s+(?P<field>directory|repo_url|purpose|runtime_mode|mutation_class):\s*(?P<value>.*)$"
)


def _entries() -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in (Path(__file__).with_name("skills.yml")).read_text(encoding="utf-8").splitlines():
        match = ENTRY.match(line)
        if match:
            if current:
                values.append(current)
            current = {"name": match.group("name")}
            continue
        if current:
            field = FIELD.match(line)
            if field:
                value = field.group("value").strip().strip('"')
                current[field.group("field")] = value
    if current:
        values.append(current)
    return values


class WenyuCatalog(BaseExtension):
    extension_type = "tool"

    def invoke(self, request: ExecutionRequest) -> ExecutionResponse:
        if request.capability != "research_skill_catalog":
            raise ValueError(f"unsupported capability: {request.capability}")
        query = str(request.input.get("query", "")).strip().lower()
        limit = max(1, min(int(request.input.get("limit", 20)), 100))
        entries = _entries()
        if query:
            entries = [
                item
                for item in entries
                if query in " ".join(item.values()).lower()
            ]
        return ExecutionResponse(
            {"query": query, "items": entries[:limit], "total": len(entries)},
            {
                "provider": "community.wenyu-research-catalog",
                "catalog_revision": "8547d889612ca624d523f39d20d35a97dbd87802",
                "offline": True,
            },
        )


plugin = WenyuCatalog()
