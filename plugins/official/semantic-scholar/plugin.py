"""Semantic Scholar provider implemented against Alem extension API v1."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime

from alem.extensions.api import BaseExtension, ExecutionRequest, ExecutionResponse


class SemanticScholarSearch(BaseExtension):
    extension_type = "tool"

    def invoke(self, request: ExecutionRequest) -> ExecutionResponse:
        if request.capability != "academic_search":
            raise ValueError(f"unsupported capability: {request.capability}")
        query = str(request.input.get("query", "")).strip()
        if not query:
            raise ValueError("academic_search requires a non-empty query")
        limit = max(1, min(int(request.input.get("limit", 10)), 100))
        fields = "paperId,title,authors,year,externalIds,url,abstract,citationCount,publicationDate"
        url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(
            {"query": query, "limit": str(limit), "fields": fields}
        )
        headers = {"User-Agent": "AlemResearch/0.1"}
        credentials = request.context.get("credentials", {})
        if isinstance(credentials, dict) and credentials.get("SEMANTIC_SCHOLAR_API_KEY"):
            headers["x-api-key"] = credentials["SEMANTIC_SCHOLAR_API_KEY"]
        http_request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(http_request, timeout=20) as response:
            document = json.load(response)
        items = []
        for paper in document.get("data", []):
            external = paper.get("externalIds") or {}
            items.append(
                {
                    "title": paper.get("title"),
                    "authors": [
                        author.get("name")
                        for author in paper.get("authors", [])
                        if author.get("name")
                    ],
                    "year": paper.get("year"),
                    "doi": external.get("DOI"),
                    "url": paper.get("url"),
                    "external_id": paper.get("paperId"),
                    "abstract": paper.get("abstract"),
                    "citation_count": paper.get("citationCount"),
                    "source": "Semantic Scholar",
                    "verification_status": "retrieved_metadata",
                }
            )
        return ExecutionResponse(
            {
                "query": query,
                "items": items,
                "total": document.get("total"),
                "retrieved_at": datetime.now(UTC).isoformat(),
                "database": "Semantic Scholar",
            },
            {"provider": "org.alem.semantic-scholar"},
        )


plugin = SemanticScholarSearch()
