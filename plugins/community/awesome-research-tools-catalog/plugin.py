"""Offline search over a Markdown research-tool list."""

from __future__ import annotations

import re
from pathlib import Path

from alem.extensions.api import BaseExtension, ExecutionRequest, ExecutionResponse

ITEM = re.compile(r"^\s*[-*]\s+\[([^]]+)\]\(([^)]+)\)\s*(?:[-–—:]\s*(.*))?$")


def _items() -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    category = ""
    for line in Path(__file__).with_name("AWESOME.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            category = line[3:].strip()
            continue
        match = ITEM.match(line)
        if match:
            url = match.group(2).strip()
            if category == "Contents" or url.startswith("#"):
                continue
            values.append(
                {
                    "name": match.group(1).strip(),
                    "url": url,
                    "description": (match.group(3) or "").strip(),
                    "category": category,
                }
            )
    return values


class AwesomeCatalog(BaseExtension):
    extension_type = "tool"

    def invoke(self, request: ExecutionRequest) -> ExecutionResponse:
        if request.capability != "research_tool_catalog":
            raise ValueError(f"unsupported capability: {request.capability}")
        query = str(request.input.get("query", "")).strip().lower()
        limit = max(1, min(int(request.input.get("limit", 20)), 100))
        entries = _items()
        if query:
            entries = [
                item for item in entries if query in " ".join(item.values()).lower()
            ]
        return ExecutionResponse(
            {"query": query, "items": entries[:limit], "total": len(entries)},
            {
                "provider": "community.awesome-research-tools-catalog",
                "catalog_revision": "1369c3c55e17f37a9abbe7f4ddc5ba2b0636a7f1",
                "offline": True,
                "trust": "discovery_only",
            },
        )


plugin = AwesomeCatalog()
