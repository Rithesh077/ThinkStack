"""
hybrid search module.

combines semantic and keyword search results using reciprocal rank
fusion (rrf) to produce a single ranked result list that benefits
from both search strategies.
"""

import logging
from collections import defaultdict

from domain.search.models import SearchQuery, SearchResult, SearchResponse
from domain.search.semantic_search import semantic_search
from domain.search.keyword_search import keyword_search

logger = logging.getLogger(__name__)


def _reciprocal_rank_fusion(
    result_lists: list[list[SearchResult]],
    k: int = 60,
) -> list[SearchResult]:
    """merge multiple ranked result lists using reciprocal rank fusion.

    rrf assigns scores based on rank position rather than raw scores,
    making it robust to score scale differences between search methods.
    the formula is: score = sum(1 / (k + rank)) across all lists.

    args:
        result_lists: list of ranked search result lists to merge.
        k: rrf constant, higher values reduce the impact of high ranks.

    returns:
        merged and re-ranked list of search results.
    """
    scores = defaultdict(float)
    result_map = {}

    for results in result_lists:
        for rank, result in enumerate(results):
            key = result.chunk_id
            scores[key] += 1.0 / (k + rank + 1)
            if key not in result_map:
                result_map[key] = result

    sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    merged = []
    for key in sorted_keys:
        result = result_map[key]
        result.score = round(scores[key], 4)
        result.source = "hybrid"
        merged.append(result)

    return merged


def hybrid_search(query: SearchQuery) -> SearchResponse:
    """perform combined semantic and keyword search with rrf ranking.

    runs both search strategies in sequence and merges their results
    using reciprocal rank fusion for robust ranking.

    args:
        query: search query with text, top_k, and optional filters.

    returns:
        search response with merged and ranked results.
    """
    semantic_results = semantic_search(query)
    kw_results = keyword_search(query)

    merged = _reciprocal_rank_fusion([semantic_results, kw_results])
    top_results = merged[:query.top_k]

    logger.info(
        "hybrid search for '%s': %d semantic + %d keyword = %d merged results",
        query.query[:50],
        len(semantic_results),
        len(kw_results),
        len(top_results),
    )

    return SearchResponse(
        query=query.query,
        results=top_results,
        total_found=len(top_results),
        search_type="hybrid",
    )
