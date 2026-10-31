"""Minimal third-party extension: no imports from Alem internals."""

from alem.extensions.api import BaseExtension, ExecutionRequest, ExecutionResponse


class StaticAcademicSearch(BaseExtension):
    extension_type = "tool"

    def invoke(self, request: ExecutionRequest) -> ExecutionResponse:
        query = str(request.input.get("query", "")).strip()
        if not query:
            raise ValueError("query is required")
        return ExecutionResponse(
            {
                "query": query,
                "total": 1,
                "database": "Community example fixture",
                "retrieved_at": "2000-01-01T00:00:00+00:00",
                "items": [
                    {
                        "title": f"Example result for {query}",
                        "authors": ["Alem Community"],
                        "year": 2000,
                        "doi": None,
                        "url": None,
                        "external_id": "community-example-1",
                        "abstract": "Deterministic demonstration data; not a real paper.",
                        "citation_count": 0,
                        "source": "Community example fixture",
                        "verification_status": "synthetic_example_do_not_cite",
                    }
                ],
            },
            {"provider": "dev.community.static-search", "synthetic": True},
        )


plugin = StaticAcademicSearch()
