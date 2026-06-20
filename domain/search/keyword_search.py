"""
keyword search module.

provides bm25-based keyword search over document chunks stored in
the vector store. serves as a complement to semantic search for
queries where exact term matching is more appropriate.
"""

import logging
import re

from rank_bm25 import BM25Okapi

from infrastructure.local_vector_store import get_vector_store
from domain.search.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """simple whitespace and punctuation tokenizer.

    args:
        text: input text string.

    returns:
        list of lowercase tokens.
    """
    text = text.lower()
    tokens = re.findall(r"\b\w+\b", text)
    return tokens


def keyword_search(query: SearchQuery) -> list[SearchResult]:
    """search the knowledge base using bm25 keyword matching.

    retrieves all documents from the vector store, builds a bm25 index
    in memory, and returns the top-k results ranked by bm25 score.

    args:
        query: search query with text, top_k, and optional filters.

    returns:
        list of search results sorted by descending bm25 score.
    """
    store = get_vector_store()

    if store.count() == 0:
        return []

    where_filter = None
    if query.doc_ids:
        where_filter = {"doc_id": {"$in": query.doc_ids}}

    all_docs = store.get(where=where_filter)

    if not all_docs["ids"]:
        return []

    corpus = [_tokenize(doc) for doc in all_docs["documents"]]
    bm25 = BM25Okapi(corpus)

    query_tokens = _tokenize(query.query)
    scores = bm25.get_scores(query_tokens)

    scored_indices = sorted(
        enumerate(scores),
        key=lambda x: x[1],
        reverse=True,
    )[:query.top_k]

    results = []
    for idx, score in scored_indices:
        if score <= 0:
            continue

        results.append(SearchResult(
            chunk_id=all_docs["ids"][idx],
            doc_id=all_docs["metadatas"][idx].get("doc_id", ""),
            text=all_docs["documents"][idx],
            score=round(float(score), 4),
            metadata=all_docs["metadatas"][idx],
            source="keyword",
        ))

    logger.info(
        "keyword search for '%s' returned %d results",
        query.query[:50],
        len(results),
    )
    return results
