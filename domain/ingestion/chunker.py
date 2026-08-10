"""Split document text into overlapping chunks for embedding.

A chunk is the unit of retrieval -- search returns chunks, never whole papers.
Bigger chunks are not safer, they are blurrier: one vector has to represent
everything in it, so a long chunk covering five topics scores weakly on all
five. `chunk_size` is that trade-off.

Overlap exists so a sentence spanning a boundary is still findable.
"""

import logging

from config import settings
from domain.ingestion.models import TextChunk

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    """Roughly 1.3 tokens per word. Approximate on purpose: the real tokeniser
    is the embedding model's, and loading it here to count would cost more than
    the imprecision does."""
    words = len(text.split())
    return int(words * 1.3)


def _split_by_separators(text: str, separators: list[str]) -> list[str]:
    """Split on the first separator that actually divides the text.

    Ordered widest-first (paragraph, then sentence, then word) so a chunk
    breaks at the coarsest boundary available rather than mid-sentence.
    """
    if not separators:
        return [text]

    separator = separators[0]
    remaining = separators[1:]

    parts = text.split(separator)
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) <= 1:
        return _split_by_separators(text, remaining) if remaining else [text]

    return parts


def chunk_text(
    text: str,
    doc_id: str,
    chunk_size: int = settings.chunk_size,
    chunk_overlap: int = settings.chunk_overlap,
) -> list[TextChunk]:
    """Chunks of about `chunk_size` tokens, overlapping by `chunk_overlap`."""
    # empty / whitespace-only input yields no chunks. without this guard the
    # splitter bottoms out at [""] and emits a single empty chunk, which would
    # then be embedded and stored as a junk zero-vector.
    if not text or not text.strip():
        return []

    separators = ["\n\n", "\n", ". ", " "]
    segments = _split_by_separators(text, separators)

    chunks = []
    current_chunk = []
    current_tokens = 0

    for segment in segments:
        segment_tokens = _estimate_tokens(segment)

        if current_tokens + segment_tokens > chunk_size and current_chunk:
            chunk_text_content = " ".join(current_chunk)
            chunks.append(chunk_text_content)

            overlap_tokens = 0
            overlap_parts = []
            for part in reversed(current_chunk):
                part_tokens = _estimate_tokens(part)
                if overlap_tokens + part_tokens > chunk_overlap:
                    break
                overlap_parts.insert(0, part)
                overlap_tokens += part_tokens

            current_chunk = overlap_parts
            current_tokens = overlap_tokens

        current_chunk.append(segment)
        current_tokens += segment_tokens

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    result = []
    for i, chunk_content in enumerate(chunks):
        result.append(TextChunk(
            chunk_id=f"{doc_id}_chunk_{i:04d}",
            doc_id=doc_id,
            text=chunk_content,
            chunk_index=i,
            token_count=_estimate_tokens(chunk_content),
        ))

    logger.info("created %d chunks from document %s", len(result), doc_id)
    return result


def chunk_pages(
    pages: list[dict],
    doc_id: str,
    chunk_size: int = settings.chunk_size,
    chunk_overlap: int = settings.chunk_overlap,
) -> list[TextChunk]:
    """As chunk_text, but each chunk remembers which page it came from.

    The page number is what lets a search result point at a place in the PDF
    rather than at a paper, so it has to survive the merging of small pages.
    """
    full_text = "\n\n".join(p["text"] for p in pages)
    chunks = chunk_text(full_text, doc_id, chunk_size, chunk_overlap)

    for chunk in chunks:
        best_page = 0
        best_overlap = 0
        for page in pages:
            # count character overlap between chunk text and page text
            overlap = sum(
                1 for word in chunk.text.split()[:20]
                if word in page["text"]
            )
            if overlap > best_overlap:
                best_overlap = overlap
                best_page = page["page_number"]
        chunk.page_number = best_page

    return chunks
