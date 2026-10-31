"""OpenAlex provider implemented only against Alem extension API v1."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime

from alem.extensions.api import BaseExtension, ExecutionRequest, ExecutionResponse


def _abstract(inverted_index):
    if not isinstance(inverted_index, dict):
        return None
    positioned = []
    for word, positions in inverted_index.items():
        if isinstance(word, str) and isinstance(positions, list):
            positioned.extend(
                (position, word) for position in positions if isinstance(position, int)
            )
    return " ".join(word for _, word in sorted(positioned)) or None


class OpenAlexSearch(BaseExtension):
    extension_type = "tool"

    def invoke(self, request: ExecutionRequest) -> ExecutionResponse:
        if request.capability != "academic_search":
            raise ValueError(f"unsupported capability: {request.capability}")
        query = str(request.input.get("query", "")).strip()
        if not query:
            raise ValueError("academic_search requires a non-empty query")
        limit = max(1, min(int(request.input.get("limit", 10)), 100))
        credentials = request.context.get("credentials", {})
        params = {"search": query, "per-page": str(limit)}
        if isinstance(credentials, dict) and credentials.get("OPENALEX_MAILTO"):
            params["mailto"] = credentials["OPENALEX_MAILTO"]
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
        http_request = urllib.request.Request(url, headers={"User-Agent": "AlemResearch/0.1"})
        with urllib.request.urlopen(http_request, timeout=20) as response:
            document = json.load(response)
        items = []
        for work in document.get("results", []):
            doi = work.get("doi")
            authors = [
                entry.get("author", {}).get("display_name")
                for entry in work.get("authorships", [])
                if entry.get("author", {}).get("display_name")
            ]
            primary = work.get("primary_location") or {}
            items.append(
                {
                    "title": work.get("display_name") or work.get("title"),
                    "authors": authors,
                    "year": work.get("publication_year"),
                    "doi": doi.removeprefix("https://doi.org/") if isinstance(doi, str) else None,
                    "url": primary.get("landing_page_url") or work.get("id"),
                    "external_id": work.get("id"),
                    "abstract": _abstract(work.get("abstract_inverted_index")),
                    "citation_count": work.get("cited_by_count"),
                    "source": "OpenAlex",
                    "verification_status": "retrieved_metadata",
                }
            )
        return ExecutionResponse(
            {
                "query": query,
                "items": items,
                "total": document.get("meta", {}).get("count"),
                "retrieved_at": datetime.now(UTC).isoformat(),
                "database": "OpenAlex",
            },
            {"provider": "org.alem.openalex", "request_url": url.split("mailto=")[0].rstrip("&?")},
        )


plugin = OpenAlexSearch()
