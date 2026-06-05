"""
search api routes.

exposes hybrid search functionality combining semantic and keyword
search over the knowledge base.
"""

import logging
from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from domain.search.models import SearchQuery
from domain.search.hybrid_search import hybrid_search

logger = logging.getLogger(__name__)
router = APIRouter()


class SearchRequest(BaseModel):
    """request body for search endpoints."""
    query: str
    top_k: int = Field(default=10, ge=1, le=50)
    doc_ids: list[str] = Field(default_factory=list)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


@router.post("")
async def search(request: SearchRequest):
    """search the knowledge base using hybrid semantic and keyword search.

    combines vector similarity and bm25 keyword matching using
    reciprocal rank fusion for robust result ranking.

    args:
        request: search parameters including query text and filters.

    returns:
        ranked search results with relevance scores and source metadata.
    """
    search_query = SearchQuery(
        query=request.query,
        top_k=request.top_k,
        doc_ids=request.doc_ids,
        min_score=request.min_score,
    )

    response = hybrid_search(search_query)

    return {
        "query": response.query,
        "results": [asdict(r) for r in response.results],
        "total_found": response.total_found,
        "search_type": response.search_type,
    }
